"""Naplnenie vektorovej databázy: ontológia + všetky PDF v priečinku pdfs/.

Spustenie:  python ingest.py
Pri každom spustení sa databáza vytvorí nanovo (dát je málo, je to rýchle
a nehrozia duplicity). Stačí pridať nové PDF do pdfs/ a spustiť znova.
"""
import re
import sys

import chromadb
import ollama
from pypdf import PdfReader

from config import (CHUNK_OVERLAP, CHUNK_SIZE, COLLECTION, DB_DIR, EMBED_MODEL,
                    ONTOLOGY_FILE, PDF_DIR)
from ontology_loader import load_ontology_documents

sys.stdout.reconfigure(encoding="utf-8")


_DOUBLED = re.compile(r"^(.{2,}?)\s*\1\s*$")
_INDD_LINE = re.compile(r"\.indd\b")            # tlačové značky z InDesignu
_PAGE_NUMBER = re.compile(r"^\s*\d{1,3}\s*$")    # samotné číslo strany (čísla setov majú 5+ číslic)


def clean_page_text(text):
    """Vyčistí text vytiahnutý z PDF (hlavne katalógy):
    - riadky zdvojené kvôli 'falošnému tučnému' písmu ('Od 6 rokovOd 6 rokov') -> raz,
    - technické riadky z tlače (*.indd, samotné čísla strán) -> preč."""
    out = []
    for line in text.splitlines():
        if _INDD_LINE.search(line):
            continue
        m = _DOUBLED.match(line)
        line = m.group(1) if m else line
        if _PAGE_NUMBER.match(line):
            continue
        out.append(line)
    return "\n".join(out)


def split_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Rozdelí text na prekrývajúce sa kúsky, snaží sa deliť na hranici vety/odseku."""
    text = " ".join(text.split())
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            cut = max(text.rfind(". ", start + size // 2, end), text.rfind("\n", start + size // 2, end))
            if cut != -1:
                end = cut + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def load_pdf_chunks():
    items = []
    pdfs = sorted(PDF_DIR.glob("**/*.pdf"))
    if not pdfs:
        print(f"  (v {PDF_DIR} nie sú žiadne PDF)")
    for pdf in pdfs:
        try:
            reader = PdfReader(str(pdf))
        except Exception as e:
            print(f"  ! {pdf.name}: nedá sa otvoriť ({e})")
            continue
        n_before = len(items)
        skipped = 0
        for page_no, page in enumerate(reader.pages, start=1):
            try:
                text = clean_page_text(page.extract_text() or "")
            except Exception:
                skipped += 1  # poškodená/príliš zložitá strana – preskočíme ju
                continue
            for i, chunk in enumerate(split_text(text)):
                items.append({
                    "id": f"pdf::{pdf.relative_to(PDF_DIR)}::{page_no}::{i}",
                    "text": chunk,
                    "meta": {"source": pdf.name, "page": page_no, "type": "pdf",
                             "folder": pdf.parent.relative_to(PDF_DIR).as_posix()},
                })
        added = len(items) - n_before
        note = "" if added else "  ← žiadny text (asi skenované PDF, treba OCR)"
        if skipped:
            note += f"  (preskočené nečitateľné strany: {skipped})"
        print(f"  {pdf.name}: {len(reader.pages)} strán, {added} kúskov{note}")
    return items


def load_ontology_chunks():
    items = []
    for i, (title, text) in enumerate(load_ontology_documents(ONTOLOGY_FILE)):
        items.append({
            "id": f"owl::{i}",
            "text": text,
            "meta": {"source": ONTOLOGY_FILE.name, "title": title, "type": "ontology"},
        })
    print(f"  {ONTOLOGY_FILE.name}: {len(items)} dokumentov")
    return items


def embed(texts, batch=32):
    vectors = []
    for i in range(0, len(texts), batch):
        vectors.extend(ollama.embed(model=EMBED_MODEL, input=texts[i:i + batch])["embeddings"])
        print(f"\r  embedovanie {min(i + batch, len(texts))}/{len(texts)}", end="", flush=True)
    print()
    return vectors


def main():
    PDF_DIR.mkdir(exist_ok=True)
    print("Načítavam ontológiu...")
    items = load_ontology_chunks()
    print("Načítavam PDF...")
    items += load_pdf_chunks()

    print(f"Vytváram embeddingy ({EMBED_MODEL})...")
    vectors = embed([it["text"] for it in items])

    client = chromadb.PersistentClient(path=str(DB_DIR))
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    col = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
    for i in range(0, len(items), 500):
        part = items[i:i + 500]
        col.add(
            ids=[it["id"] for it in part],
            documents=[it["text"] for it in part],
            metadatas=[it["meta"] for it in part],
            embeddings=vectors[i:i + 500],
        )
    print(f"Hotovo: {col.count()} kúskov uložených v {DB_DIR}")


if __name__ == "__main__":
    main()
