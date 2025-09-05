from pathlib import Path
import shutil, subprocess, sys, re
from datetime import datetime

ROOT = Path(__file__).parent.resolve()
DRAFTS = ROOT / "texte_drafts"
PDF_OUT = ROOT / "pdf_drafts"
PDF_OUT.mkdir(exist_ok=True)

# Welche Draft-Datei gehört zu welchem Werk?
WORKS = {
    "Aias":       r"^Aias_birkenbihl(?:_DRAFT.*)?\.txt$",
    "Trachiniae": r"^Trachiniae_birkenbihl(?:_DRAFT.*)?\.txt$",
    "Agamemnon":  r"^Agamemnon_birkenbihl(?:_DRAFT.*)?\.txt$",
}

def latest_for(work: str):
    pat = re.compile(WORKS[work], re.IGNORECASE)
    candidates = [p for p in (DRAFTS.glob("*.txt")) if pat.match(p.name)]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)

def build_one(work: str, draft_path: Path):
    # Map auf InputTragödie*.txt (im Repo-Root, wie dein Code erwartet)
    input_name = f"InputTragödie{work}.txt"
    tmp_input = ROOT / input_name
    shutil.copyfile(draft_path, tmp_input)
    print(f"→ {work}: Draft übernommen: {draft_path.name} → {input_name}")

    # Tragödien-Satz ausführen
    subprocess.check_call([sys.executable, "tragoedie_pdf.py"])

    # Erwartete Ausgabedateien
    base_norm = f"Tragödie{work}_Normal.pdf"
    base_bold = f"Tragödie{work}_Fett.pdf"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    draft_norm = PDF_OUT / f"{work}_DRAFT_{ts}_Normal.pdf"
    draft_bold = PDF_OUT / f"{work}_DRAFT_{ts}_Fett.pdf"

    # verschieben und zusätzlich "LATEST" Symlinks/Kopien pflegen
    shutil.move(str(ROOT / base_norm), draft_norm)
    shutil.move(str(ROOT / base_bold), draft_bold)

    latest_norm = PDF_OUT / f"{work}_DRAFT_LATEST_Normal.pdf"
    latest_bold = PDF_OUT / f"{work}_DRAFT_LATEST_Fett.pdf"
    for dst, src in [(latest_norm, draft_norm), (latest_bold, draft_bold)]:
        if dst.exists():
            dst.unlink()
        shutil.copyfile(src, dst)

    print(f"✓ {work}: PDFs → {draft_norm.name}, {draft_bold.name}")
    print(f"✓ {work}: LATEST → {latest_norm.name}, {latest_bold.name}")

def main():
    any_found = False
    for work in WORKS:
        path = latest_for(work)
        if path:
            any_found = True
            build_one(work, path)
        else:
            print(f"ℹ {work}: kein Draft gefunden (übersprungen).")
    if not any_found:
        print("✗ Keine Draft-TXTs in texte_drafts/ gefunden."); sys.exit(1)

if __name__ == "__main__":
    main()
