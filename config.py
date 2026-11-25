"""Spoločné nastavenia RAG systému."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Zdroje dát
ONTOLOGY_FILE = BASE_DIR / "hrackarstvo-eshop.owl"
PDF_DIR = BASE_DIR / "pdfs"

# Vektorová databáza (Chroma, ukladá sa lokálne na disk)
DB_DIR = BASE_DIR / "db"
COLLECTION = "hrackarstvo"

# Modely v Ollame
#  - bge-m3: viacjazyčný embedding model (dobre zvláda slovenčinu)
#  - gemma3:4b: menší chatovací model, beží aj bez dedikovanej grafiky
EMBED_MODEL = "bge-m3"
CHAT_MODEL = "gemma3:4b"

# Delenie PDF textu na kúsky (v znakoch)
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Koľko najrelevantnejších kúskov sa pošle modelu
# (z ontológie a z PDF zvlášť, aby ontológia nezanikla medzi tisíckami PDF kúskov)
TOP_K_ONTOLOGY = 4
TOP_K_PDF = 4
# Kúsky s kosínusovou vzdialenosťou horšou ako (najlepší výsledok + táto hodnota)
# sa zahodia – malý model si inak z nesúvisiaceho kontextu vymýšľa
RELEVANCE_MARGIN = 0.18
