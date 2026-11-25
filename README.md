# Hračkárska poradňa – lokálny RAG pre e-shop s hračkami

RAG (Retrieval-Augmented Generation) nad **OWL ontológiou e-shopu s hračkami** a **PDF o produktoch**
(katalóg LEGO, pravidlá hier, návody, výročné správy výrobcov). Všetko beží lokálne:

- **Ollama** – chatovací model `gemma3:4b` a viacjazyčný embedding model `bge-m3`
- **ChromaDB** – vektorová databáza uložená v priečinku `db/`
- **FastAPI + vlastné webové rozhranie** – otázky v prehliadači, odpoveď sa vypisuje priebežne, zdroje sa dajú rozkliknúť

📄 Podrobná dokumentácia (architektúra, ontológia, spracovanie dát, vyhľadávanie, API, testovanie):
**[docs/DOKUMENTACIA.md](docs/DOKUMENTACIA.md)**

## Inštalácia od nuly (Windows)
1. Nainštaluj [Ollama](https://ollama.com/download) a Python 3.11+.
2. V priečinku projektu (PowerShell):
   ```powershell
   ollama pull bge-m3
   ollama pull gemma3:4b
   python -m venv .venv
   .\.venv\Scripts\python -m pip install -r requirements.txt
   .\.venv\Scripts\python stiahni_pdf.py     # stiahne PDF z pôvodných zdrojov do pdfs/
   .\.venv\Scripts\python ingest.py          # naplní vektorovú databázu (pár minút)
   ```
3. Spusti **`spusti-web.bat`** (dvojklik) → otvorí sa http://127.0.0.1:8000.

PDF ani databáza nie sú v gite (veľkosť a autorské práva výrobcov) – vytvoria sa krokmi vyššie.
Ak niektorý server sťahovanie zablokuje, `stiahni_pdf.py` vypíše odkaz a cestu, kam súbor uložiť ručne.

## Spustenie
| Súbor | Čo robí |
|---|---|
| `spusti-web.bat` | webové rozhranie na http://127.0.0.1:8000 (čierne okno nechaj otvorené) |
| `spusti.bat` | otázky v textovom okne (príkazový riadok) |
| `aktualizuj-databazu.bat` | prebuduje databázu po pridaní/zmazaní PDF v `pdfs/` |

Z príkazového riadku:
```powershell
.\.venv\Scripts\python ask.py "Aké LEGO Disney sety sú v katalógu a koľko stoja?"
.\.venv\Scripts\python ask.py --show "Ako sa hrá Dixit?"     # --show vypíše aj nájdené zdroje
```

## Štruktúra projektu
| Súbor | Účel |
|---|---|
| `hrackarstvo-eshop.owl` | ontológia (triedy, vlastnosti, produkty, výrobcovia, zákazníci, objednávky, recenzie…) |
| `ontology_loader.py` | prevod OWL → slovenské texty (`python ontology_loader.py` ukáže ukážku) |
| `stiahni_pdf.py` | zoznam PDF a ich zdrojov + stiahnutie do `pdfs/` |
| `ingest.py` | načíta ontológiu + PDF, vyčistí text, rozdelí na kúsky, vytvorí embeddingy, uloží do `db/` |
| `rag.py` | jadro: vyhľadanie kontextu a príprava promptu |
| `ask.py` | otázky z príkazového riadku |
| `app.py` | FastAPI server pre webové rozhranie |
| `web/index.html` | webové rozhranie |
| `config.py` | modely, cesty, veľkosť kúskov, počty výsledkov |

## Zdroje (pdfs/)
Podpriečinok určuje farbu zdroja vo webe: ontológia = žltá, `produkty/` = červená,
`vyrobcovia/` = zelená, ostatné = modrá.
- `produkty/` – LEGO katalóg jún–dec 2025 (SK), pravidlá Monopoly a Dixit, návody Play-Doh, Nerf,
  Barbie DreamHouse, Hot Wheels Track Builder a Super Track (EN)
- `vyrobcovia/` – LEGO výročná správa 2024, Mattel výsledky 2024, Hasbro výročná správa 2024
  (kópia z dfcfw.com), Ravensburger konsolidovaná závierka 2023 (DE)

Vlastné PDF stačí skopírovať do `pdfs/` (aj do podpriečinkov) a spustiť `aktualizuj-databazu.bat`.
Skenované PDF (obrázky bez textu) treba najprv prehnať OCR – ingest na ne upozorní.

## Ako funguje vyhľadávanie
- Hľadá sa **zvlášť v ontológii** (`TOP_K_ONTOLOGY`) **a zvlášť v PDF** (`TOP_K_PDF`), aby pár desiatok
  záznamov ontológie nezaniklo medzi stovkami kúskov z PDF.
- Výsledky horšie ako najlepší výsledok + `RELEVANCE_MARGIN` sa zahodia (menej šumu → menej vymýšľania).
- Text z PDF sa pri ingeste čistí (zdvojené riadky z katalógov, tlačové značky, čísla strán).
- Obmedzenia: číselné filtre („všetky hračky do 20 €“) vyhľadávanie podľa podobnosti nezvládne presne;
  každá otázka sa rieši samostatne (bez pamäte konverzácie).

## Zmena modelu
V `config.py` zmeň `CHAT_MODEL` (napr. `qwen2.5:7b` alebo `llama3.1:8b` – lepšie, ale pomalšie).
Ak zmeníš `EMBED_MODEL`, treba znova spustiť `ingest.py`.
