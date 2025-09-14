######## START: build_poesie_adapter.py ########
from pathlib import Path
import subprocess, sys

ROOT = Path(__file__).parent.resolve()
SRC_ROOT = ROOT / "texte" / "poesie"                # Eingaben
DST_BASE = ROOT / "pdf" / "poesie"                  # Ausgaben

RUNNER = ROOT / "poesie_pdf.py"                      # 24 Varianten (Poesie)

def run_one(input_path: Path) -> None:
    if not input_path.is_file():
        print(f"⚠ Datei fehlt: {input_path} — übersprungen"); return

    # Extrahiere Autor und Werk aus dem Pfad
    # input_path: texte/poesie/Autor/Werk/datei.txt
    # relative_to(SRC_ROOT): Autor/Werk/datei.txt
    relative_path = input_path.relative_to(SRC_ROOT)
    path_parts = relative_path.parts
    author = path_parts[0]
    work = path_parts[1] if len(path_parts) > 1 else ""
    
    # Erstelle Zielordner: pdf/poesie/Autor/Werk/
    target_dir = DST_BASE / author / work
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Erstelle spiegelidentische Ordner in texte_drafts und pdf_drafts
    texte_drafts_dir = ROOT / "texte_drafts" / "poesie_drafts" / author / work
    pdf_drafts_dir = ROOT / "pdf_drafts" / "poesie_drafts" / author / work
    texte_drafts_dir.mkdir(parents=True, exist_ok=True)
    pdf_drafts_dir.mkdir(parents=True, exist_ok=True)
    
    # Erstelle .gitkeep Dateien um sicherzustellen, dass die Ordner bei Git gepusht werden
    gitkeep_target = target_dir / ".gitkeep"
    gitkeep_texte_drafts = texte_drafts_dir / ".gitkeep"
    gitkeep_pdf_drafts = pdf_drafts_dir / ".gitkeep"
    
    if not gitkeep_target.exists():
        gitkeep_target.write_text("")
    if not gitkeep_texte_drafts.exists():
        gitkeep_texte_drafts.write_text("")
    if not gitkeep_pdf_drafts.exists():
        gitkeep_pdf_drafts.write_text("")

    # Extrahiere den Basisnamen der Eingabedatei (ohne .txt)
    input_stem = input_path.stem
    
    before = {p.name for p in ROOT.glob("*.pdf")}
    print(f"→ Erzeuge PDFs für: {input_path}")
    subprocess.check_call([sys.executable, str(RUNNER), str(input_path)], cwd=str(ROOT))
    after = {p.name for p in ROOT.glob("*.pdf")}
    new_pdfs = sorted(after - before)

    if not new_pdfs:
        print("⚠ Keine PDFs erzeugt."); return

    # Filtere nur die PDFs, die zu dieser Eingabedatei gehören
    relevant_pdfs = [name for name in new_pdfs if name.startswith(input_stem)]
    
    if not relevant_pdfs:
        print(f"⚠ Keine passenden PDFs für {input_stem} gefunden."); return

    for name in relevant_pdfs:
        src = ROOT / name
        dst = target_dir / name
        src.replace(dst)
        print(f"✓ PDF → {dst}")

def main():
    if not RUNNER.exists():
        print(f"✗ {RUNNER.name} nicht gefunden – Abbruch."); sys.exit(1)
    if not SRC_ROOT.exists():
        print(f"✗ Eingabeordner fehlt: {SRC_ROOT} – Abbruch."); sys.exit(1)

    # Suche rekursiv nach _birkenbihl.txt und BIRKENBIHL.txt Dateien
    # in der Struktur: texte/poesie/Autor/Werk/*.txt
    birkenbihl_patterns = [
        "**/*_birkenbihl.txt",
        "**/*BIRKENBIHL*.txt"
    ]
    
    inputs = []
    for pattern in birkenbihl_patterns:
        inputs.extend(SRC_ROOT.glob(pattern))
    
    inputs = sorted(inputs)
    
    if not inputs:
        print(f"✗ Keine _birkenbihl.txt oder BIRKENBIHL.txt Dateien in {SRC_ROOT}/<Autor>/<Werk>/ gefunden – Abbruch."); sys.exit(1)

    print(f"✓ Gefunden: {len(inputs)} Birkenbihl-Dateien")
    for inp in inputs:
        print(f"  - {inp.relative_to(SRC_ROOT)}")

    for inp in inputs:
        try:
            run_one(inp)
        except subprocess.CalledProcessError as e:
            print(f"✗ Fehler bei {inp.name}: {e}")

if __name__ == "__main__":
    main()
######## ENDE: build_poesie_adapter.py ########

