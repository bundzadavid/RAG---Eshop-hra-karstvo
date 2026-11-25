"""Stiahne verejne dostupné PDF, ktoré RAG používa, z ich pôvodných zdrojov.

PDF nie sú v gite (veľkosť + autorské práva výrobcov). Spustenie:
    python stiahni_pdf.py
Potom:
    python ingest.py
"""
import sys
import urllib.request

from config import PDF_DIR

sys.stdout.reconfigure(encoding="utf-8")

# niektoré servery (napr. cdn.hasbro.com) vrátia PDF len "bežnému prehliadaču"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

PDFS = {
    # --- produkty: katalógy, návody, pravidlá hier ---
    "produkty/lego-katalog-SK-2025-jun-dec.pdf":
        "https://www.lego.com/cdn/cs/set/assets/bltc40256d7ebc51acb/2HY25_SK.pdf",
    "produkty/hasbro-monopoly-pravidla.pdf":
        "https://assets-us-01.kc-usercontent.com/500e0a65-283d-00ef-33b2-7f1f20488fe2/ff7a7a19-3fd1-45c7-b9b8-ee321681ef60/C1009C048_INST_MN_CLASSIC_F22_FAR.pdf",
    "produkty/dixit-pravidla-EN.pdf":
        "https://cdn.svc.asmodee.net/production-libellud/uploads/2022/03/DIXIT_REFRESH_RULES_US-UK-AU_BD.pdf",
    "produkty/hasbro-nerf-bezpecnost.pdf":
        "https://cdn.hasbro.com/faaa3d5019832273570327fcdc971786a399f134/9531a7eea3324d2f1a856837dd5a35ed.pdf",
    "produkty/hasbro-play-doh-navod.pdf":
        "https://assets-us-01.kc-usercontent.com/500e0a65-283d-00ef-33b2-7f1f20488fe2/4b749219-bca4-43a0-8084-7d16e8371bb3/B34080000_335842%20_PD_PLAYDOH_TEXTURES_AND_TOOLS_INST_RC.pdf",
    "produkty/mattel-barbie-dreamhouse-navod.pdf":
        "https://service.mattel.com/instruction_sheets/JHH47-4C.pdf",
    "produkty/mattel-hot-wheels-track-builder-navod.pdf":
        "https://service.mattel.com/instruction_sheets/BHT76-Eng.pdf",
    "produkty/mattel-hot-wheels-super-track-navod.pdf":
        "https://service.mattel.com/instruction_sheets/BHT61-Eng.pdf",
    # --- výrobcovia: výročné správy ---
    "vyrobcovia/lego-vyrocna-sprava-2024.pdf":
        "https://lego.com/cdn/cs/aboutus/assets/blt1cdf90a38318ef56/the_LEGO_Group_Annual_Report_2024.pdf",
    "vyrobcovia/mattel-vysledky-2024.pdf":
        "https://s21.q4cdn.com/605014885/files/doc_financials/2024/q4/Mattel-Reports-Fourth-Quarter-and-Full-Year-2024-Financial-Results.pdf",
    "vyrobcovia/hasbro-vyrocna-sprava-2024.pdf":  # kópia z dfcfw.com (hasbro.com blokuje sťahovanie)
        "https://pdf.dfcfw.com/pdf/H2_AN202504041651402643_1.pdf",
    "vyrobcovia/ravensburger-konzern-2023-DE.pdf":
        "https://www.lobbyregister.bundestag.de/media/69/e1/564729/RAG_2023.pdf",
}


def main():
    ok = 0
    for rel, url in PDFS.items():
        target = PDF_DIR / rel
        if target.exists():
            print(f"  ✓ {rel} (už existuje)")
            ok += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
            if not data.startswith(b"%PDF"):
                raise ValueError("server nevrátil PDF")
            target.write_bytes(data)
            print(f"  ✓ {rel} ({len(data) // 1024} kB)")
            ok += 1
        except Exception as e:
            print(f"  ✗ {rel}: {e}")
            print(f"      stiahni ručne v prehliadači: {url}")
            print(f"      a ulož ako: {target}")
    print(f"\nStiahnuté {ok}/{len(PDFS)}. Ďalší krok: python ingest.py")


if __name__ == "__main__":
    main()
