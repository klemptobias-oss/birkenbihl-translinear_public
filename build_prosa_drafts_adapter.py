######## START: build_prosa_drafts_adapter.py ########
from pathlib import Path
import subprocess, sys, json, re, shlex, time, traceback, os

ROOT = Path(__file__).parent.resolve()
SRC_ROOT = ROOT / "texte_drafts" / "prosa_drafts"        # Eingaben
DST_BASE = ROOT / "pdf_drafts" / "prosa_drafts"          # Ausgaben (spiegelbildlich)

RUNNER = ROOT / "prosa_pdf.py"                           # 12 Varianten (Prosa)

META_HEADER_RE = re.compile(
    r'<!--\s*(TAG_CONFIG|RELEASE_BASE|PATH_PREFIX|RELEASE_NAME|VERSMASS|METER_MODE|HIDE_PIPES):(.*?)\s*-->',
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
    sys.stdout.flush()
    
    # Erstelle temporäre Konfigurationsdatei für Tag-Einstellungen
    config_file = None
    if tag_config:
        config_file = ROOT / "temp_tag_config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(tag_config, f, ensure_ascii=False, indent=2)
    
    # --- START robust subprocess invocation of prosa_pdf.py ---
    # This will stream prosa_pdf output live, enforce a per-call timeout,
    # and report a clear error/exit code to the outer CI.
    try:
        PROSA_PDF_CALL_TIMEOUT = int(os.environ.get("PROSA_PDF_CALL_TIMEOUT", "600"))
    except Exception:
        PROSA_PDF_CALL_TIMEOUT = 600

    prosa_script = str(RUNNER)

    cmd = [sys.executable, "-u", prosa_script, str(temp_input)]

    # If there were extra flags in the previous implementation (e.g. --tag-config,
    # --force-meter, --hide-pipes) we should append them here. Try to preserve
    # optional variables if available in local variables (best-effort).
    if config_file:
        cmd.extend(["--tag-config", str(config_file)])
    if hide_pipes:
        cmd.extend(["--hide-pipes"])

    print("build_prosa_drafts_adapter.py: INVOCATION CMD: %s" % shlex.join(cmd))
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
                if time.time() - start > PROSA_PDF_CALL_TIMEOUT:
                    print("ERROR: prosa_pdf subprocess exceeded timeout (%ds) — killing." % PROSA_PDF_CALL_TIMEOUT)
                    sys.stdout.flush()
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    raise TimeoutError("prosa_pdf call timeout")
                # small sleep to avoid busy loop
                time.sleep(0.1)

        rc = proc.poll()
        if rc is None:
            rc = proc.wait()
        print("build_prosa_drafts_adapter.py: prosa_pdf exited with rc=%s" % rc)
        sys.stdout.flush()
        if rc != 0:
            print("ERROR: prosa_pdf returned non-zero exit status %s" % rc)
            # Intentionally don't crash the whole adapter — report and continue/abort
            # Here we re-raise to make CI step fail so you get visible failure
            raise SystemExit(rc)

    except TimeoutError as te:
        print("build_prosa_drafts_adapter.py: TimeoutError while running prosa_pdf: %s" % str(te))
        traceback.print_exc()
        sys.stdout.flush()
        raise
    except Exception as e:
        print("build_prosa_drafts_adapter.py: Exception while running prosa_pdf:", str(e))
        traceback.print_exc()
        sys.stdout.flush()
        raise
    finally:
        try:
            if proc and proc.stdout:
                proc.stdout.close()
        except Exception:
            pass
        # Lösche temporäre Dateien
        if config_file and config_file.exists():
            config_file.unlink()
        if temp_input.exists():
            temp_input.unlink()

    # --- END robust subprocess invocation ---
    
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

    # KRITISCH: Verwende IMMER den Upload-Filename (input_stem), NICHT RELEASE_BASE!
    # Grund: Browser muss PDFs anhand des Upload-Filenames finden können
    # RELEASE_BASE kann normalisiert sein (z.B. gr_de statt gr_de_en), was zu 404s führt
    # Lösung: PDF-Name = Upload-Filename + Variant-Suffix
    # Beispiel: agamemnon_gr_de_en_stil1_birkenbihl_draft_translinear_DRAFT_20251130_011301_GR_Fett_Colour_Tag.pdf
    
    # Extrahiere den Pfad-Teil aus PATH_PREFIX Metadaten (falls vorhanden)
    # Fallback: Extrahiere aus RELEASE_BASE (alte Methode, für Kompatibilität)
    # Format PATH_PREFIX: "GR_prosa_Philosophie_Platon_Menon"
    # Format RELEASE_BASE (alt): "GR_prosa_Philosophie_Platon_Menon__menon_gr_de_stil1_birkenbihl"
    path_prefix = ""
    
    if "PATH_PREFIX" in metadata and metadata["PATH_PREFIX"]:
        # NEUE Methode: PATH_PREFIX aus Metadaten
        path_prefix = metadata["PATH_PREFIX"] + "__"
        print(f"→ Verwende PATH_PREFIX aus Metadaten: {path_prefix}")
    elif release_base and "__" in release_base:
        # ALTE Methode (Fallback): Extrahiere aus RELEASE_BASE
        path_prefix = release_base.split("__")[0] + "__"
        print(f"→ Verwende PATH_PREFIX aus RELEASE_BASE (Fallback): {path_prefix}")
    
    for name in relevant_pdfs:
        bare = name[:-4] if name.lower().endswith(".pdf") else name
        
        # KRITISCH: Extrahiere nur den Variant-Suffix (ab _Normal oder _GR_Fett oder _LAT_Fett)
        # Das PDF heißt z.B.: "temp_epistulaemorales1_lat_de_en_stil1_birkenbihl_draft_translinear_DRAFT_20251130_023827_LAT_Fett_BlackWhite_NoTags"
        # Wir wollen nur: "_LAT_Fett_BlackWhite_NoTags"
        
        import re
        variant_match = re.search(r'_(Normal|GR_Fett|LAT_Fett)_', bare)
        if variant_match:
            suffix = '_' + bare[variant_match.start()+1:]  # Ab dem Variant-Teil
        else:
            # Fallback: Alte Logik
            temp_prefix = f"temp_{input_stem}"
            if bare.startswith(temp_prefix):
                suffix = bare[len(temp_prefix):]
            elif bare.startswith(input_stem):
                suffix = bare[len(input_stem):]
            else:
                suffix = bare
        
        # FINALE LÖSUNG: Verwende Pfad-Prefix (wenn vorhanden) + Upload-Filename + Variant-Suffix
        if path_prefix:
            final_bare = f"{path_prefix}{input_stem}{suffix}"
        else:
            # Fallback: Nur Upload-Filename + Suffix (für alte Dateien ohne RELEASE_BASE)
            final_bare = f"{input_stem}{suffix}"
        
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