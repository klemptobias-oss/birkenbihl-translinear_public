######## START: build_prosa_adapter.py ########
from pathlib import Path
import subprocess, sys

ROOT = Path(__file__).parent.resolve()
SRC_ROOT = ROOT / "texte" / "prosa"                 # Eingaben
DST_BASE = ROOT / "pdf" / "prosa"                   # Ausgaben

RUNNER = ROOT / "prosa_pdf.py"                       # 12 Varianten (Prosa)

def run_one(input_path: Path) -> None:
    if not input_path.is_file():
        print(f"⚠ Datei fehlt: {input_path} — übersprungen"); return

    # Extrahiere Autor und Werk aus dem Pfad
    # input_path: texte/prosa/Autor/Werk/datei.txt
    # relative_to(SRC_ROOT): Autor/Werk/datei.txt
    relative_path = input_path.relative_to(SRC_ROOT)
    path_parts = relative_path.parts
    author = path_parts[0]
    work = path_parts[1] if len(path_parts) > 1 else ""
    
    # Erstelle Zielordner: pdf/prosa/Autor/Werk/
    target_dir = DST_BASE / author / work
    target_dir.mkdir(parents=True, exist_ok=True)

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

    # Suche rekursiv nach _birkenbihl.txt Dateien
    # in der Struktur: texte/prosa/Autor/Werk/*.txt
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
######## ENDE: build_prosa_adapter.py ########

