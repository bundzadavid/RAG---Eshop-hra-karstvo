"""Webové rozhranie pre RAG.

Spustenie:  python app.py   (alebo dvojklik na spusti-web.bat)
Otvorí sa http://127.0.0.1:8000
"""
import json
import sys
import threading
import webbrowser
from collections import Counter
from pathlib import Path

import ollama
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import CHAT_MODEL, EMBED_MODEL
from rag import build_messages, get_collection, retrieve

sys.stdout.reconfigure(encoding="utf-8")

WEB_DIR = Path(__file__).resolve().parent / "web"
HOST, PORT = "127.0.0.1", 8000

# Pekné názvy pre známe súbory (ostatné sa odvodia z názvu súboru)
NICE_NAMES = {
    "hrackarstvo-eshop.owl": "Ontológia e-shopu",
    "zakon-108-2024-ochrana-spotrebitela.pdf": "Zákon 108/2024 o ochrane spotrebiteľa",
    "rada-eu-nariadenie-o-bezpecnosti-hraciek-2025.pdf": "Nariadenie EÚ o bezpečnosti hračiek (2025)",
    "ek-usmernenie-k-smernici-o-hrackach-EN.pdf": "Usmernenie k smernici o hračkách (EN)",
    "ek-bezpecnost-hraciek-brozura.pdf": "Bezpečnosť hračiek – brožúra EK",
    "ek-tipy-bezpecne-zaobchadzanie-s-hrackami.pdf": "Tipy na bezpečné hračky – EK",
    "soi-kontrola-hraciek-2020.pdf": "SOI: kontrola hračiek 2020",
    "soi-chemikalie-v-hrackach-2022.pdf": "SOI: chemikálie v hračkách 2022",
    "soi-plastove-hracky.pdf": "SOI: plastové hračky",
    "beuc-spotrebitelske-pravo-sk-2022.pdf": "BEUC: spotrebiteľské právo",
    "beuc-digitalne-prava-sk.pdf": "BEUC: digitálne práva",
    "lego-katalog-SK-2025-jun-dec.pdf": "LEGO katalóg jún–december 2025",
    "hasbro-monopoly-pravidla.pdf": "Monopoly: pravidlá hry (EN)",
    "dixit-pravidla-EN.pdf": "Dixit: pravidlá hry (EN)",
    "hasbro-play-doh-navod.pdf": "Play-Doh: návod (EN)",
    "hasbro-nerf-bezpecnost.pdf": "Nerf: návod a bezpečnosť (EN)",
    "mattel-barbie-dreamhouse-navod.pdf": "Barbie DreamHouse: návod (EN)",
    "mattel-hot-wheels-track-builder-navod.pdf": "Hot Wheels Track Builder: návod (EN)",
    "mattel-hot-wheels-super-track-navod.pdf": "Hot Wheels Super Track: návod (EN)",
    "lego-vyrocna-sprava-2024.pdf": "LEGO: výročná správa 2024",
    "mattel-vysledky-2024.pdf": "Mattel: výsledky 2024",
    "hasbro-vyrocna-sprava-2024.pdf": "Hasbro: výročná správa 2024",
    "ravensburger-konzern-2023-DE.pdf": "Ravensburger: závierka 2023 (DE)",
}


def nice_name(source):
    if source in NICE_NAMES:
        return NICE_NAMES[source]
    return Path(source).stem.replace("-", " ").replace("_", " ").capitalize()


FOLDER_GROUPS = {"produkty": "produkt", "vyrobcovia": "vyrobca"}


def source_group(meta):
    """ontology / produkt / vyrobca / pdf – podľa toho sa v UI farbí kocka.
    Skupina PDF sa určí podľa podpriečinka v pdfs/."""
    if meta.get("type") == "ontology":
        return "ontology"
    top = meta.get("folder", ".").split("/")[0]
    return FOLDER_GROUPS.get(top, "pdf")


app = FastAPI(title="Hračkárska poradňa")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

def col():
    # zakaždým nanovo – ingest.py databázu prebuduje a starý odkaz by prestal platiť
    return get_collection()


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/info")
def info():
    try:
        c = col()
    except Exception:
        return JSONResponse({"error": "Databáza zatiaľ neexistuje. Spusti aktualizuj-databazu.bat."}, 503)
    metas = c.get(include=["metadatas"])["metadatas"]
    counts = Counter(m["source"] for m in metas)
    groups = {m["source"]: source_group(m) for m in metas}
    order = {"ontology": 0, "produkt": 1, "vyrobca": 2, "pdf": 3}
    sources = sorted(
        ({"source": s, "name": nice_name(s), "group": groups[s], "chunks": n} for s, n in counts.items()),
        key=lambda x: (order[x["group"]], x["name"]),
    )
    return {"chunks": len(metas), "sources": sources, "chat_model": CHAT_MODEL, "embed_model": EMBED_MODEL}


class Question(BaseModel):
    question: str


@app.post("/api/ask")
def ask(q: Question):
    def stream():
        def line(obj):
            return json.dumps(obj, ensure_ascii=False) + "\n"

        question = q.question.strip()
        if not question:
            yield line({"type": "error", "message": "Napíš otázku."})
            return
        try:
            hits = retrieve(col(), question)
        except Exception as e:
            yield line({"type": "error", "message": _explain(e)})
            return

        sources = []
        for i, (doc, m, d) in enumerate(hits, 1):
            sources.append({
                "n": i,
                "name": nice_name(m["source"]),
                "group": source_group(m),
                "where": f"str. {m['page']}" if m.get("type") == "pdf" else m.get("title", "").replace("Ontológia – ", ""),
                "text": doc,
                "score": round(1 - d, 3),
            })
        yield line({"type": "sources", "sources": sources})

        try:
            for part in ollama.chat(model=CHAT_MODEL, messages=build_messages(question, hits), stream=True):
                token = part["message"]["content"]
                if token:
                    yield line({"type": "token", "text": token})
        except Exception as e:
            yield line({"type": "error", "message": _explain(e)})
            return
        yield line({"type": "done"})

    return StreamingResponse(stream(), media_type="application/x-ndjson")


def _explain(e):
    msg = str(e)
    if "connect" in msg.lower() or "refused" in msg.lower():
        return "Ollama nebeží. Spusti ju z ponuky Štart (napíš „Ollama“) a skús to znova."
    if "not found" in msg.lower():
        return f"Model nie je stiahnutý. Spusti v termináli: ollama pull {CHAT_MODEL}"
    return f"Chyba: {msg}"


if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}"
    print(f"Hračkárska poradňa beží na {url}  (zastavíš ju zatvorením tohto okna)")
    if "--no-browser" not in sys.argv:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
