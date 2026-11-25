"""Otázky nad RAG databázou z príkazového riadku.

  python ask.py                      -> interaktívny režim
  python ask.py "Aké hračky má LEGO?" -> jedna otázka
  python ask.py --show "..."          -> zobrazí aj nájdené zdroje
"""
import sys

import ollama

from config import CHAT_MODEL
from rag import build_messages, get_collection, retrieve, source_label

sys.stdout.reconfigure(encoding="utf-8")


def answer(col, question, show=False):
    hits = retrieve(col, question)
    if show:
        print("\n--- Nájdené zdroje ---")
        for i, (_, m, d) in enumerate(hits, 1):
            print(f"[{i}] {source_label(m)}  (vzdialenosť {d:.3f})")
        print("----------------------\n")

    stream = ollama.chat(model=CHAT_MODEL, messages=build_messages(question, hits), stream=True)
    for part in stream:
        print(part["message"]["content"], end="", flush=True)
    print("\n\nZdroje:")
    for i, (_, m, _) in enumerate(hits, 1):
        print(f"  [{i}] {source_label(m)}")


def main():
    args = sys.argv[1:]
    show = "--show" in args
    args = [a for a in args if a != "--show"]

    try:
        col = get_collection()
    except Exception:
        sys.exit("Databáza neexistuje – najprv spusti: python ingest.py")

    if args:
        answer(col, " ".join(args), show)
        return

    print(f"RAG hračkárstvo ({col.count()} kúskov, model {CHAT_MODEL}). Prázdny riadok = koniec.")
    while True:
        try:
            q = input("\nOtázka: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            break
        print()
        answer(col, q, show)


if __name__ == "__main__":
    main()
