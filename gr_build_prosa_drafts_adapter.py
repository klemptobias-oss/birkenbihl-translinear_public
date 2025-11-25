######## START: build_prosa_drafts_adapter.py ########
from pathlib import Path
import subprocess, sys, json, re

ROOT = Path(__file__).parent.resolve()
SRC_ROOT = ROOT / "texte_drafts" / "prosa_drafts"        # Eingaben
DST_BASE = ROOT / "pdf_drafts" / "prosa_drafts"          # Ausgaben (spiegelbildlich)

RUNNER = ROOT / "prosa_pdf.py"                           # 12 Varianten (Prosa)

META_HEADER_RE = re.compile(
    r'<!--\s*(TAG_CONFIG|RELEASE_BASE|VERSMASS|METER_MODE|HIDE_PIPES):(.*?)\s*-->',
    re.DOTALL | re.IGNORECASE
)

def extract_metadata_sections(text: str) -> dict:
    meta = {}
    for key, value in META_HEADER_RE.findall(text):
        meta[key.strip().upper()] = value.strip()
    return meta

def strip_metadata_comments(text: str) -> str:
    return META_HEADER_RE.sub('', text)

def normalize_release_base(base: str) -> str:
    if not base:
        return ""
    cleaned = base.strip()
    if "_birkenbihl" not in cleaned:
        cleaned += "_birkenbihl"
    return cleaned

def run_one(input_path: Path, tag_config: dict = None) -> None:
    if not input_path.is_file():
        print(f"⚠ Datei fehlt: {input_path} — übersprungen"); return

    # Ermittele den relativen Pfad unterhalb von texte_drafts (inkl. Sprache/Kategorie)
    try:
        parts = input_path.resolve().parts
        texte_drafts_index = parts.index("texte_drafts")
        relative_parts = list(parts[texte_drafts_index + 1 : -1])
        if not relative_parts:
            raise ValueError("leerer relativer Pfad")
    except (ValueError, IndexError):
        relative_parts = ["unknown", "prosa", "Unsortiert", "Unbenannt"]
    
    relative_path = Path(*relative_parts)
    target_dir = ROOT / "pdf_drafts" / relative_path
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Erstelle .gitkeep Datei um sicherzustellen, dass der Ordner bei Git gepusht wird
    gitkeep_file = target_dir / ".gitkeep"
    if not gitkeep_file.exists():
        gitkeep_file.write_text("")

    # Extrahiere den Basisnamen der Eingabedatei (ohne .txt)
    input_stem = input_path.stem
    
    # Lese den Text und extrahiere Metadaten
    text_content = input_path.read_text(encoding="utf-8")
    metadata = extract_metadata_sections(text_content)
    print(f"→ Extrahierte Metadaten: {list(metadata.keys())}")
    
    release_base = normalize_release_base(metadata.get("RELEASE_BASE", ""))
    print(f"→ Release Base: {release_base}")
    
    # Extrahiere HIDE_PIPES aus Metadaten
    hide_pipes = metadata.get("HIDE_PIPES", "false").lower() == "true"

    if tag_config is None:
        config_blob = metadata.get("TAG_CONFIG")
        if config_blob:
            try:
                tag_config = json.loads(config_blob)
                print(f"✓ Tag-Konfiguration gefunden: {len(tag_config.get('tag_colors', {}))} Farben, {len(tag_config.get('hidden_tags', []))} versteckte Tags")
            except Exception as e:
                print(f"⚠ Fehler beim Parsen der Tag-Konfiguration: {e}")
                tag_config = None

    # Entferne Metadaten-Kommentare aus dem Text für die Verarbeitung
    clean_text = strip_metadata_comments(text_content)
    
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
        if hide_pipes:
            cmd.extend(["--hide-pipes"])
        
        # Führe den Runner aus und übertrage Tag-Konfiguration
        import traceback
        try:
            result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Fehler beim Ausführen des Runners: {result.stderr}")
                return
            print(result.stdout)
        except Exception as e:
            print(f"ERROR: processing draft {input_path} failed with exception:")
            traceback.print_exc()
            # continue so CI can try other drafts
            return
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
    temp_prefix = f"temp_{input_stem}"
    relevant_pdfs = [
        name for name in new_pdfs
        if name.startswith(input_stem) or name.startswith(temp_prefix)
    ]
    
    if not relevant_pdfs:
        print(f"⚠ Keine passenden PDFs für {input_stem} gefunden."); return

    sanitized_release_base = release_base.strip()
    
    for name in relevant_pdfs:
        bare = name[:-4] if name.lower().endswith(".pdf") else name
        suffix = ""
        temp_prefix = f"temp_{input_stem}"
        if bare.startswith(temp_prefix):
            suffix = bare[len(temp_prefix):]
        elif bare.startswith(input_stem):
            suffix = bare[len(input_stem):]
        else:
            suffix = bare
        
        if sanitized_release_base:
            final_bare = f"{sanitized_release_base}{suffix}"
        else:
            final_bare = bare[5:] if bare.startswith("temp_") else bare
        final_name = f"{final_bare}.pdf"
        
        src = ROOT / name
        dst = target_dir / final_name
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