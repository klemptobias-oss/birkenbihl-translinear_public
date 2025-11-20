######## START: build_prosa_drafts_adapter.py ########
from pathlib import Path
import subprocess, sys, json, re

ROOT = Path(__file__).parent.resolve()
SRC_ROOT = ROOT / "texte_drafts" / "prosa_drafts"        # Eingaben
DST_BASE = ROOT / "pdf_drafts" / "prosa_drafts"          # Ausgaben (spiegelbildlich)

RUNNER = ROOT / "prosa_pdf.py"                           # 12 Varianten (Prosa)

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

def run_one(input_path: Path, tag_config: dict = None) -> None:
    if not input_path.is_file():
        print(f"⚠ Datei fehlt: {input_path} — übersprungen"); return

    # Extrahiere Tag-Konfiguration aus der Datei, falls keine externe übergeben wurde
    if tag_config is None:
        tag_config = extract_tag_config_from_file(input_path)
        if tag_config:
            print(f"✓ Tag-Konfiguration aus Datei extrahiert: {len(tag_config)} Regeln")
        else:
            print("⚠ Keine Tag-Konfiguration gefunden, verwende Standard-Konfiguration")

    # Extrahiere Sprache, Autor und Werk aus dem Pfad
    # Pfad: texte_drafts/<Sprache>/prosa/<Autor>/<Werk>/datei.txt
    try:
        parts = input_path.parts
        texte_drafts_index = parts.index("texte_drafts")
        
        language = parts[texte_drafts_index + 1]
        # gattung "prosa" ist an index + 2
        author = parts[texte_drafts_index + 3]
        work = parts[texte_drafts_index + 4]

    except (ValueError, IndexError):
        # Fallback, wenn die Struktur nicht wie erwartet ist
        author = "unknown"
        work = "unknown"
        language = "unknown"
    
    # Korrigierte Zielordner-Struktur: pdf_drafts/<Sprache>/prosa/<Autor>/<Werk>/
    target_dir = ROOT / "pdf_drafts" / language / "prosa" / author / work
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Erstelle .gitkeep Datei um sicherzustellen, dass der Ordner bei Git gepusht wird
    gitkeep_file = target_dir / ".gitkeep"
    if not gitkeep_file.exists():
        gitkeep_file.write_text("")

    # Extrahiere den Basisnamen der Eingabedatei (ohne .txt)
    input_stem = input_path.stem
    
    # Lese den Text und extrahiere Tag-Konfiguration
    text_content = input_path.read_text(encoding="utf-8")
    tag_config = None
    
    # Suche nach Tag-Konfiguration im Text
    import re
    config_match = re.search(r'<!-- TAG_CONFIG:(.+?) -->', text_content)
    if config_match:
        try:
            import json
            tag_config = json.loads(config_match.group(1))
            print(f"✓ Tag-Konfiguration gefunden: {len(tag_config.get('tag_colors', {}))} Farben, {len(tag_config.get('hidden_tags', []))} versteckte Tags")
        except Exception as e:
            print(f"⚠ Fehler beim Parsen der Tag-Konfiguration: {e}")
    
    # Entferne Tag-Konfiguration aus dem Text für die Verarbeitung
    clean_text = re.sub(r'<!-- TAG_CONFIG:.+? -->\n?', '', text_content)
    
    # Schreibe bereinigten Text in temporäre Datei
    temp_input = ROOT / f"temp_{input_path.name}"
    temp_input.write_text(clean_text, encoding="utf-8")
    
    before = {p.name for p in ROOT.glob("*.pdf")}
    print(f"→ Erzeuge PDFs für: {input_path}")
    
    # Erstelle temporäre Konfigurationsdatei für Tag-Einstellungen
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
        
        # Führe den Runner aus und übertrage Tag-Konfiguration
        result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Fehler beim Ausführen des Runners: {result.stderr}")
            return
        print(result.stdout)
    except Exception as e:
        print(f"Fehler beim Ausführen des Runners: {e}")
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

    # Filtere nur die PDFs, die zu dieser Eingabedatei gehören
    # Berücksichtige sowohl den ursprünglichen Namen als auch den temp_ Namen
    temp_stem = f"temp_{input_path.name.replace('.txt', '')}"
    relevant_pdfs = [name for name in new_pdfs if name.startswith(input_stem) or name.startswith(temp_stem)]
    
    if not relevant_pdfs:
        print(f"⚠ Keine passenden PDFs für {input_stem} gefunden."); return

    for name in relevant_pdfs:
        src = ROOT / name
        dst = target_dir / name
        src.replace(dst)
        print(f"✓ PDF → {dst}")

def main():
    if len(sys.argv) < 2:
        print("Verwendung: python build_prosa_drafts_adapter.py <input_file> [tag_config.json]")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    tag_config = None
    
    # Lade Tag-Konfiguration falls vorhanden (optionaler zweiter Parameter)
    if len(sys.argv) > 2:
        config_file = Path(sys.argv[2])
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    tag_config = json.load(f)
            except json.JSONDecodeError as e:
                print(f"⚠ Fehler beim Laden der JSON-Konfiguration: {e}")
                tag_config = None
    
    run_one(input_file, tag_config)

if __name__ == "__main__":
    main()
######## END: build_prosa_drafts_adapter.py ########