"""Jadro RAG: vyhľadanie kontextu a príprava správ pre model.
Používa ho príkazový riadok (ask.py) aj webové rozhranie (app.py)."""
import chromadb
import ollama

from config import (COLLECTION, DB_DIR, EMBED_MODEL, RELEVANCE_MARGIN, TOP_K_ONTOLOGY,
                    TOP_K_PDF)

SYSTEM_PROMPT = """Si asistent pre e-shop s hračkami. Odpovedáš po slovensky.
Odpovedaj IBA na základe poskytnutého kontextu (ontológia e-shopu a PDF dokumenty).
Kontext môže obsahovať aj úryvky, ktoré s otázkou nesúvisia – tie ignoruj.
Ak odpoveď v kontexte nie je, povedz to otvorene a nevymýšľaj si.
Pri tvrdeniach uvádzaj čísla zdrojov v hranatých zátvorkách, napr. [1], [3]."""


def get_collection():
    client = chromadb.PersistentClient(path=str(DB_DIR))
    return client.get_collection(COLLECTION)


def retrieve(col, question, k_ontology=TOP_K_ONTOLOGY, k_pdf=TOP_K_PDF):
    """Hľadá zvlášť v ontológii a zvlášť v PDF, aby ontológiu (pár desiatok
    záznamov) neprevalcovali tisíce kúskov z PDF."""
    qvec = ollama.embed(model=EMBED_MODEL, input=[question])["embeddings"][0]
    hits = []
    for doc_type, k in (("ontology", k_ontology), ("pdf", k_pdf)):
        if k <= 0:
            continue
        res = col.query(query_embeddings=[qvec], n_results=k, where={"type": doc_type})
        hits += zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
    hits.sort(key=lambda h: h[2])
    # zahodíme kúsky výrazne horšie ako najlepší výsledok (nesúvisiaci šum)
    if hits:
        hits = [h for h in hits if h[2] <= hits[0][2] + RELEVANCE_MARGIN]
    return hits


def source_label(meta):
    if meta.get("type") == "pdf":
        return f"{meta['source']}, str. {meta['page']}"
    return f"{meta['source']} – {meta.get('title', '')}"


def build_messages(question, hits):
    context = "\n\n".join(f"[{i}] ({source_label(m)})\n{doc}" for i, (doc, m, _) in enumerate(hits, 1))
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Kontext:\n{context}\n\nOtázka: {question}"},
    ]
