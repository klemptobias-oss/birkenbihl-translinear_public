######## START: build_prosa_adapter.py ########
from pathlib import Path
import subprocess, sys
from shared.catalog_updater import update_catalog

ROOT = Path(__file__).parent.resolve()
RUNNER = ROOT / "prosa_pdf.py"

def run_one(input_path: Path, language: str) -> None:
    if not input_path.is_file():
        print(f"⚠ Datei fehlt: {input_path} — übersprungen"); return

    # Extrahiere Autor und Werk aus dem Pfad
    # Pfad: texte/griechisch/prosa/Autor/Werk/datei.txt
    try:
        relative_base = ROOT / "texte" / language / "prosa"
        relative_path = input_path.relative_to(relative_base)
        path_parts = relative_path.parts
        author = path_parts[0]
        work = path_parts[1]
    except (ValueError, IndexError):
        print(f"✗ Pfad konnte nicht zerlegt werden: {input_path}"); return
    
    # Korrigierte Zielordner-Struktur: <Hauptordner>/<Sprache>/<Gattung>/...
    target_dir = ROOT / "pdf" / language / "prosa" / author / work
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Erstelle spiegelidentische Ordner
    texte_drafts_dir = ROOT / "texte_drafts" / language / "prosa" / author / work
    pdf_drafts_dir = ROOT / "pdf_drafts" / language / "prosa" / author / work
    texte_drafts_dir.mkdir(parents=True, exist_ok=True)
    pdf_drafts_dir.mkdir(parents=True, exist_ok=True)
    
    # Erstelle .gitkeep Dateien
    (target_dir / ".gitkeep").touch(exist_ok=True)
    (texte_drafts_dir / ".gitkeep").touch(exist_ok=True)
    (pdf_drafts_dir / ".gitkeep").touch(exist_ok=True)

    # Extrahiere den Basisnamen der Eingabedatei (ohne .txt)
    input_stem = input_path.stem
    
    before = {p.name for p in ROOT.glob("*.pdf")}
    print(f"→ Erzeuge PDFs für: {input_path}")
    subprocess.check_call([sys.executable, str(RUNNER), str(input_path)], cwd=str(ROOT))
    after = {p.name for p in ROOT.glob("*.pdf")}
    new_pdfs = sorted(after - before)

    if not new_pdfs:
        print("⚠ Keine PDFs erzeugt."); return

    relevant_pdfs = [name for name in new_pdfs if name.startswith(input_stem)]
    
    if not relevant_pdfs:
        print(f"⚠ Keine passenden PDFs für {input_stem} gefunden."); return

    for name in relevant_pdfs:
        src = ROOT / name
        dst = target_dir / name
        src.replace(dst)
        print(f"✓ PDF → {dst}")

    # Katalog aktualisieren
    update_catalog(language, "Prosa", author, work, input_path)

def main():
    if not RUNNER.exists():
        print(f"✗ {RUNNER.name} nicht gefunden – Abbruch."); sys.exit(1)
    
    src_root = ROOT / "texte"
    if not src_root.is_dir():
        print(f"✗ Haupt-Textordner '{src_root}' nicht gefunden – Abbruch."); sys.exit(1)

    language_dirs = [p for p in src_root.iterdir() if p.is_dir()]
    if not language_dirs:
        print(f"✗ Keine Sprachordner in '{src_root}' gefunden – Abbruch."); sys.exit(1)

    print(f"✓ {len(language_dirs)} Sprachordner gefunden: {[r.name for r in language_dirs]}")
    all_inputs = []

    for lang_dir in language_dirs:
        search_root = lang_dir / "prosa"
        if not search_root.is_dir():
            continue

        birkenbihl_patterns = ["**/*_birkenbihl.txt", "**/*BIRKENBIHL*.txt"]
        
        inputs_for_lang = []
        for pattern in birkenbihl_patterns:
            inputs_for_lang.extend(search_root.glob(pattern))
        
        if inputs_for_lang:
            print(f"✓ Gefunden: {len(inputs_for_lang)} Birkenbihl-Dateien in '{lang_dir.name}/prosa'")
            for inp in sorted(inputs_for_lang):
                print(f"  - {inp.relative_to(search_root)}")
                all_inputs.append((inp, lang_dir.name))

    if not all_inputs:
        print(f"✗ Keine Birkenbihl-Dateien in Unterordnern gefunden – Abbruch."); sys.exit(1)

    for inp, lang_name in all_inputs:
        try:
            run_one(inp, lang_name)
        except subprocess.CalledProcessError as e:
            print(f"✗ Fehler bei {inp.name}: {e}")

if __name__ == "__main__":
    main()
######## ENDE: build_prosa_adapter.py ########

