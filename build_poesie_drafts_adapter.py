######## START: build_poesie_drafts_adapter.py ########
from pathlib import Path
import subprocess, sys, json

ROOT = Path(__file__).parent.resolve()
SRC_ROOT = ROOT / "texte_drafts" / "poesie_drafts"       # Eingaben
DST_BASE = ROOT / "pdf_drafts" / "poesie_drafts"         # Ausgaben (spiegelbildlich)

RUNNER = ROOT / "poesie_pdf.py"                          # 24 Varianten (Poesie)

def run_one(input_path: Path, tag_config: dict = None) -> None:
    if not input_path.is_file():
        print(f"⚠ Datei fehlt: {input_path} — übersprungen"); return

    # Extrahiere Autor und Werk aus dem Pfad
    # input_path: texte_drafts/poesie_drafts/Autor/Werk/datei.txt
    # relative_to(SRC_ROOT): Autor/Werk/datei.txt
    relative_path = input_path.relative_to(SRC_ROOT)
    path_parts = relative_path.parts
    author = path_parts[0]
    work = path_parts[1] if len(path_parts) > 1 else ""
    
    # Erstelle Zielordner: pdf_drafts/poesie_drafts/Autor/Werk/
    target_dir = DST_BASE / author / work
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Erstelle .gitkeep Datei um sicherzustellen, dass der Ordner bei Git gepusht wird
    gitkeep_file = target_dir / ".gitkeep"
    if not gitkeep_file.exists():
        gitkeep_file.write_text("")

    # Extrahiere den Basisnamen der Eingabedatei (ohne .txt)
    input_stem = input_path.stem
    
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
        cmd = [sys.executable, str(RUNNER), str(input_path)]
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
        # Lösche temporäre Konfigurationsdatei
        if config_file and config_file.exists():
            config_file.unlink()
    
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
    if len(sys.argv) < 2:
        print("Verwendung: python build_poesie_drafts_adapter.py <input_file> [tag_config.json]")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    tag_config = None
    
    # Lade Tag-Konfiguration falls vorhanden
    if len(sys.argv) > 2:
        config_file = Path(sys.argv[2])
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                tag_config = json.load(f)
    
    run_one(input_file, tag_config)

if __name__ == "__main__":
    main()
######## END: build_poesie_drafts_adapter.py ########