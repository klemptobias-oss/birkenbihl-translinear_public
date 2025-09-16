######## START: build_poesie_drafts_adapter.py ########
from pathlib import Path
import subprocess, sys, json, re

ROOT = Path(__file__).parent.resolve()
SRC_ROOT = ROOT / "texte_drafts" / "poesie_drafts"       # Eingaben
DST_BASE = ROOT / "pdf_drafts" / "poesie_drafts"         # Ausgaben (spiegelbildlich)

RUNNER = ROOT / "poesie_pdf.py"                          # 24 Varianten (Poesie)

def extract_tag_config_from_file(file_path: Path) -> dict:
    """
    Extrahiert die TAG_CONFIG aus der ersten Zeile der Datei.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            
        # Suche nach dem HTML-Kommentar mit der TAG_CONFIG
        match = re.search(r'<!-- TAG_CONFIG:(.*?) -->', first_line)
        if match:
            json_str = match.group(1)
            return json.loads(json_str)
        else:
            return {}
    except Exception as e:
        print(f"⚠ Fehler beim Extrahieren der Tag-Konfiguration aus {file_path}: {e}")
        return {}

def run_one(input_path: Path) -> None:
    if not input_path.is_file():
        print(f"⚠ Datei fehlt: {input_path} — übersprungen"); return

    # Extrahiere Tag-Konfiguration aus der Datei
    tag_config = extract_tag_config_from_file(input_path)
    if tag_config:
        print(f"✓ Tag-Konfiguration aus Datei extrahiert: {len(tag_config)} Regeln")
    else:
        print("⚠ Keine Tag-Konfiguration gefunden, verwende Standard-Konfiguration des Runners")

    # Extrahiere Autor und Werk aus dem Pfad
    # input_path: texte_drafts/poesie_drafts/Autor/Werk/datei.txt
    # relative_to(SRC_ROOT): Autor/Werk/datei.txt
    try:
        relative_path = input_path.relative_to(SRC_ROOT)
        path_parts = relative_path.parts
        author = path_parts[0]
        work = path_parts[1] if len(path_parts) > 1 else ""
    except ValueError:
        # Fallback, wenn die Datei außerhalb des erwarteten Pfades liegt
        author = "unknown"
        work = "unknown"
    
    # Erstelle Zielordner: pdf_drafts/poesie_drafts/Autor/Werk/
    target_dir = DST_BASE / author / work
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Erstelle .gitkeep Datei um sicherzustellen, dass der Ordner bei Git gepusht wird
    gitkeep_file = target_dir / ".gitkeep"
    if not gitkeep_file.exists():
        gitkeep_file.write_text("")

    # Extrahiere den Basisnamen der Eingabedatei (ohne .txt)
    input_stem = input_path.stem
    
    # Lese den Text und entferne die Konfigurationszeile
    text_content = input_path.read_text(encoding="utf-8")
    clean_text = re.sub(r'<!-- TAG_CONFIG:.+? -->\n?', '', text_content, count=1)
    
    # Schreibe bereinigten Text in temporäre Datei
    temp_input = ROOT / f"temp_{input_path.name}"
    temp_input.write_text(clean_text, encoding="utf-8")
    
    before = {p.name for p in ROOT.glob("*.pdf")}
    print(f"→ Erzeuge PDFs für: {temp_input.name}")
    
    # Erstelle temporäre Konfigurationsdatei für Tag-Einstellungen, falls eine Konfig vorhanden ist
    config_file = None
    if tag_config:
        config_file = ROOT / "temp_tag_config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(tag_config, f, ensure_ascii=False, indent=2)
    
    try:
        # Führe den Runner mit optionaler Konfiguration aus
        cmd = [sys.executable, str(RUNNER), str(temp_input)]
        if config_file:
            cmd.extend(["--tag-config", str(config_file)])
        
        # Führe den Runner aus
        result = subprocess.run(cmd, cwd=str(ROOT), check=True, capture_output=True, text=True)
        print(result.stdout)

    except subprocess.CalledProcessError as e:
        print(f"Fehler beim Ausführen des Runners für {input_path.name}:")
        print(e.stderr)
        return
    finally:
        # Lösche temporäre Dateien
        if config_file and config_file.exists():
            config_file.unlink()
        if temp_input.exists():
            temp_input.unlink()
    
    after = {p.name for p in ROOT.glob("*.pdf")}
    new_pdfs = sorted(after - before)

    if not new_pdfs:
        print("⚠ Keine PDFs erzeugt."); return

    # Der Runner benennt die PDFs nach dem temporären Dateinamen.
    # Wir müssen sie zurück auf den originalen Stammnamen umbenennen.
    temp_stem = temp_input.stem
    
    for name in new_pdfs:
        if name.startswith(temp_stem):
            # Ersetze den temporären Stamm durch den originalen
            final_name = name.replace(temp_stem, input_stem, 1)
            src = ROOT / name
            dst = target_dir / final_name
            src.replace(dst)
            print(f"✓ PDF → {dst}")

def main():
    # Dieser Adapter wird typischerweise mit genau einem Dateipfad aufgerufen.
    if len(sys.argv) < 2:
        print(f"Verwendung: python {sys.argv[0]} <input_file_path>")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    
    if not input_file.exists():
        print(f"✗ Eingabedatei nicht gefunden: {input_file}")
        sys.exit(1)

    run_one(input_file)

if __name__ == "__main__":
    main()
######## END: build_poesie_drafts_adapter.py ########