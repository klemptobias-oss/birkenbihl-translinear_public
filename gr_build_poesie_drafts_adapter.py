######## START: build_poesie_drafts_adapter.py ########
from pathlib import Path
import subprocess, sys, json, re, shlex, time, traceback, os

ROOT = Path(__file__).parent.resolve()
SRC_ROOT = ROOT / "texte_drafts" / "poesie_drafts"       # Eingaben
DST_BASE = ROOT / "pdf_drafts" / "poesie_drafts"         # Ausgaben (spiegelbildlich)

RUNNER = ROOT / "poesie_pdf.py"                          # 24 Varianten (Poesie)

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

def run_one(input_path: Path) -> None:
    if not input_path.is_file():
        print(f"⚠ Datei fehlt: {input_path} — übersprungen"); return

    tag_config = None

    # Ableitung des relativen Pfads unterhalb von texte_drafts
    try:
        parts = input_path.resolve().parts
        texte_drafts_index = parts.index("texte_drafts")
        relative_parts = list(parts[texte_drafts_index + 1 : -1])
        if not relative_parts:
            raise ValueError("leerer relativer Pfad")
    except (ValueError, IndexError):
        relative_parts = ["unknown", "poesie", "Unsortiert", "Unbenannt"]
    
    relative_path = Path(*relative_parts)
    target_dir = ROOT / "pdf_drafts" / relative_path
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Erstelle .gitkeep Datei um sicherzustellen, dass der Ordner bei Git gepusht wird
    gitkeep_file = target_dir / ".gitkeep"
    if not gitkeep_file.exists():
        gitkeep_file.write_text("")

    # Extrahiere den Basisnamen der Eingabedatei (ohne .txt)
    input_stem = input_path.stem
    
    # Lese den Text und entferne die Konfigurationszeilen
    text_content = input_path.read_text(encoding="utf-8")
    metadata = extract_metadata_sections(text_content)
    print(f"→ Extrahierte Metadaten: {list(metadata.keys())}")
    
    release_base = normalize_release_base(metadata.get("RELEASE_BASE", ""))
    print(f"→ Release Base: {release_base}")
    
    force_meter = False
    if metadata.get("VERSMASS", "").lower() == "true":
        force_meter = True
        print(f"→ Versmaß aktiviert (VERSMASS=true)")
    if metadata.get("METER_MODE", "").lower() == "with":
        force_meter = True
        print(f"→ Versmaß aktiviert (METER_MODE=with)")
    
    # Extrahiere HIDE_PIPES aus Metadaten
    hide_pipes = metadata.get("HIDE_PIPES", "false").lower() == "true"

    config_blob = metadata.get("TAG_CONFIG")
    if config_blob:
        try:
            tag_config = json.loads(config_blob)
            print(f"✓ Tag-Konfiguration gefunden: {len(tag_config.get('tag_colors', {}))} Farben, {len(tag_config.get('hidden_tags', []))} versteckte Tags")
        except Exception as e:
            print(f"⚠ Fehler beim Parsen der Tag-Konfiguration: {e}")
            tag_config = None

    clean_text = strip_metadata_comments(text_content)
    
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
    
    # --- START robust subprocess invocation of poesie_pdf.py ---
    # This will stream poesie_pdf output live, enforce a per-call timeout,
    # and report a clear error/exit code to the outer CI.
    try:
        POESIE_PDF_CALL_TIMEOUT = int(os.environ.get("POESIE_PDF_CALL_TIMEOUT", "600"))
    except Exception:
        POESIE_PDF_CALL_TIMEOUT = 600

    poesie_script = str(RUNNER)

    cmd = [sys.executable, "-u", poesie_script, str(temp_input)]

    if force_meter:
        cmd.append("--force-meter")
        print(f"→ Kommando enthält --force-meter Flag")
        if config_file:
            cmd.extend(["--tag-config", str(config_file)])
        print(f"→ Kommando enthält --tag-config: {config_file}")
    if hide_pipes:
        cmd.extend(["--hide-pipes"])
        print(f"→ Kommando enthält --hide-pipes Flag")

    print("build_poesie_drafts_adapter.py: INVOCATION CMD: %s" % shlex.join(cmd))
    sys.stdout.flush()

    proc = None
    start = time.time()
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(ROOT)
        )

        # stream stdout lines live, enforce timeout
        while True:
            line = proc.stdout.readline()
            if line:
                # Print streamed line exactly as produced
                print(line.rstrip("\n"))
                sys.stdout.flush()
            else:
                # no immediate line; check if process finished
                if proc.poll() is not None:
                    break
                # check timeout
                if time.time() - start > POESIE_PDF_CALL_TIMEOUT:
                    print("ERROR: poesie_pdf subprocess exceeded timeout (%ds) — killing." % POESIE_PDF_CALL_TIMEOUT)
                    sys.stdout.flush()
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    raise TimeoutError("poesie_pdf call timeout")
                # small sleep to avoid busy loop
                time.sleep(0.1)

        rc = proc.poll()
        if rc is None:
            rc = proc.wait()
        print("build_poesie_drafts_adapter.py: poesie_pdf exited with rc=%s" % rc)
        sys.stdout.flush()
        if rc != 0:
            print("ERROR: poesie_pdf returned non-zero exit status %s" % rc)
            # Intentionally re-raise to make CI step fail so you get visible failure
            raise SystemExit(rc)

    except TimeoutError as te:
        print("build_poesie_drafts_adapter.py: TimeoutError while running poesie_pdf: %s" % str(te))
        traceback.print_exc()
        sys.stdout.flush()
        raise
    except Exception as e:
        print("build_poesie_drafts_adapter.py: Exception while running poesie_pdf:", str(e))
        traceback.print_exc()
        sys.stdout.flush()
        raise
    finally:
        # Cleanup: delete temp files
        try:
        if config_file and config_file.exists():
            config_file.unlink()
        except Exception:
            pass
        try:
        if temp_input.exists():
            temp_input.unlink()
        except Exception:
            pass

    # --- END robust subprocess invocation ---
    
    after = {p.name for p in ROOT.glob("*.pdf")}
    new_pdfs = sorted(after - before)

    if not new_pdfs:
        print("⚠ Keine PDFs erzeugt."); return

    # Der Runner benennt die PDFs nach dem temporären Dateinamen.
    # Wir müssen sie zurück auf den originalen Stammnamen umbenennen.
    temp_stem = temp_input.stem
    
    sanitized_release_base = release_base.strip()
    
    for name in new_pdfs:
        bare = name[:-4] if name.lower().endswith(".pdf") else name
        suffix = ""
        if bare.startswith(temp_stem):
            suffix = bare[len(temp_stem):]
        else:
            original_stem = input_stem
            if bare.startswith(original_stem):
                suffix = bare[len(original_stem):]
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