######## START: build_poesie_adapter.py ########
from pathlib import Path
import subprocess, sys

ROOT = Path(__file__).parent.resolve()
SRC_ROOT = ROOT / "texte" / "poesie"                # Eingaben
DST_BASE = ROOT / "pdf" / "original_poesie_pdf"     # Ausgaben

RUNNER = ROOT / "poesie_pdf.py"                      # 24 Varianten (Poesie)

def run_one(input_path: Path) -> None:
    if not input_path.is_file():
        print(f"⚠ Datei fehlt: {input_path} — übersprungen"); return

    author = input_path.parent.name
    target_dir = DST_BASE / author
    target_dir.mkdir(parents=True, exist_ok=True)

    before = {p.name for p in ROOT.glob("*.pdf")}
    print(f"→ Erzeuge PDFs für: {input_path}")
    subprocess.check_call([sys.executable, str(RUNNER), str(input_path)], cwd=str(ROOT))
    after = {p.name for p in ROOT.glob("*.pdf")}
    new_pdfs = sorted(after - before)

    if not new_pdfs:
        print("⚠ Keine PDFs erzeugt."); return

    for name in new_pdfs:
        src = ROOT / name
        dst = target_dir / name
        src.replace(dst)
        print(f"✓ PDF → {dst}")

def main():
    if not RUNNER.exists():
        print(f"✗ {RUNNER.name} nicht gefunden – Abbruch."); sys.exit(1)
    if not SRC_ROOT.exists():
        print(f"✗ Eingabeordner fehlt: {SRC_ROOT} – Abbruch."); sys.exit(1)

    inputs = sorted(p for p in SRC_ROOT.glob("*/*.txt"))
    if not inputs:
        print(f"✗ Keine Eingaben in {SRC_ROOT}/<Autor>/*.txt – Abbruch."); sys.exit(1)

    for inp in inputs:
        try:
            run_one(inp)
        except subprocess.CalledProcessError as e:
            print(f"✗ Fehler bei {inp.name}: {e}")

if __name__ == "__main__":
    main()
######## ENDE: build_poesie_adapter.py ########

