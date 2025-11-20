######## START: build_poesie_adapter.py ########
from pathlib import Path
import subprocess, sys
# from shared.catalog_updater import update_catalog <-- Entfernt

ROOT = Path(__file__).parent.resolve()
RUNNER = ROOT / "poesie_pdf.py"

def run_one(input_path: Path, language: str) -> None:
    if not input_path.is_file():
        print(f"⚠ Datei fehlt: {input_path} — übersprungen"); return

    # Extrahiere Kategorie, Autor und Werk aus dem Pfad
    # Pfad: /home/tobias/Desktop/Webseite_GODLIKE/texte/latein/poesie/Kategorie/Autor/Werk/datei.txt
    try:
        # Finde die Position von "texte/latein/poesie" im Pfad und extrahiere die Teile danach
        path_str = str(input_path)
        search_str = f"/texte/{language}/poesie/"
        idx = path_str.find(search_str)
        if idx == -1:
            print(f"✗ Pfad-Struktur nicht erkannt: {input_path}"); return

        relative_part = path_str[idx + len(search_str):]
        path_parts = relative_part.split('/')
        if len(path_parts) < 3:
            print(f"✗ Pfad hat nicht genug Teile (erwartet: Kategorie/Autor/Werk): {input_path}"); return

        category = path_parts[0]  # z.B. "Epos", "Drama", "Lyrik"
        author = path_parts[1]
        work = path_parts[2]
    except (ValueError, IndexError):
        print(f"✗ Pfad konnte nicht zerlegt werden: {input_path}"); return
    
    # Korrigierte Zielordner-Struktur: <Hauptordner>/<Sprache>/<Gattung>/<Kategorie>/...
    target_dir = ROOT / "pdf" / language / "poesie" / category / author / work
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Erstelle spiegelidentische Ordner
    texte_drafts_dir = ROOT / "texte_drafts" / language / "poesie" / category / author / work
    pdf_drafts_dir = ROOT / "pdf_drafts" / language / "poesie" / category / author / work
    texte_drafts_dir.mkdir(parents=True, exist_ok=True)
    pdf_drafts_dir.mkdir(parents=True, exist_ok=True)
    
    # Erstelle .gitkeep Dateien
    (target_dir / ".gitkeep").touch(exist_ok=True)
    (texte_drafts_dir / ".gitkeep").touch(exist_ok=True)
    (pdf_drafts_dir / ".gitkeep").touch(exist_ok=True)

    # Extrahiere den Basisnamen der Eingabedatei (ohne .txt)
    input_stem = input_path.stem
    
    print(f"→ Erzeuge PDFs für: {input_path}")
    subprocess.check_call([sys.executable, str(RUNNER), str(input_path)], cwd=str(ROOT))
    
    # Finde ALLE PDFs im Root, die zum Input-Stem passen (unabhängig davon, ob sie neu sind)
    all_pdfs_in_root = list(ROOT.glob("*.pdf"))
    relevant_pdfs = [p for p in all_pdfs_in_root if p.stem.startswith(input_stem)]

    if not relevant_pdfs:
        print(f"⚠ Keine passenden PDFs für {input_stem} gefunden."); return

    for pdf_path in relevant_pdfs:
        dst = target_dir / pdf_path.name
        pdf_path.replace(dst)
        print(f"✓ PDF → {dst}")
        
    # Katalog aktualisieren <-- Entfernt
    # update_catalog(language, "Poesie", author, work, input_path)

def main():
    if not RUNNER.exists():
        print(f"✗ {RUNNER.name} nicht gefunden – Abbruch."); sys.exit(1)

    # Fester Pfad für lateinische Poesie-Texte
    search_root = Path("/home/tobias/Desktop/Webseite_GODLIKE/texte/latein/poesie")
    if not search_root.is_dir():
        print(f"✗ Lateinischer Poesie-Ordner '{search_root}' nicht gefunden – Abbruch."); sys.exit(1)

    print(f"✓ Suche nach Birkenbihl-Dateien in: {search_root}")

    # Finde ALLE Birkenbihl-Dateien und filtere dann manuell
    all_birkenbihl = list(search_root.glob("**/*_birkenbihl.txt"))
    
    # Filtere: Akzeptiere ALLE Birkenbihl-Texte (2-sprachig, 3-sprachig, mit/ohne Versmaß)
    # NICHT: _goldenhands.txt (für andere Zwecke)
    all_inputs = []
    for file_path in all_birkenbihl:
        filename = file_path.name.lower()
        
        # Ignoriere goldenhands
        if "goldenhands" in filename:
            continue
        
        # Akzeptiere ALLE Birkenbihl-Dateien mit _stil1 (egal ob _de, _en, _de_en, _en_de, mit/ohne _Versmaß)
        if "_stil1" in filename and "_birkenbihl.txt" in filename:
            all_inputs.append(file_path)

    if not all_inputs:
        print(f"✗ Keine Birkenbihl-Dateien in '{search_root}' gefunden – Abbruch."); sys.exit(1)

    print(f"✓ Gefunden: {len(all_inputs)} Birkenbihl-Dateien")
    for inp in sorted(all_inputs):
        print(f"  - {inp.relative_to(search_root)}")

    for inp in all_inputs:
        try:
            run_one(inp, "latein")
        except subprocess.CalledProcessError as e:
            print(f"✗ Fehler bei {inp.name}: {e}")

if __name__ == "__main__":
    main()
######## ENDE: lat_build_poesie_adapter.py ########

