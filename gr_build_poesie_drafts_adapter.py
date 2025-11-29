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

    # Extrahiere den Basisnamen der Eingabedatei (ohne .txt)
    input_stem = input_path.stem
    
    # Lese den Text und entferne die Konfigurationszeilen
    text_content = input_path.read_text(encoding="utf-8")
    metadata = extract_metadata_sections(text_content)
    print(f"→ Extrahierte Metadaten: {list(metadata.keys())}")
    
    # KRITISCH: Baue Verzeichnisstruktur aus Metadaten (wie im Frontend erwartet)
    # Frontend erwartet: pdf_drafts/griechisch/poesie/Epos/Homer/Ilias/
    # Alte Struktur war: pdf_drafts/poesie_drafts/Homer/Ilias/
    sprache = metadata.get("SPRACHE", "").strip().lower() or "griechisch"
    gattung = metadata.get("GATTUNG", "").strip().lower() or "poesie"
    kategorie = metadata.get("KATEGORIE", "").strip() or "Unsortiert"
    autor = metadata.get("AUTOR", "").strip() or "Unbekannt"
    werk = metadata.get("WERK", "").strip() or input_path.stem.split("_")[0]
    
    # Baue relativen Pfad (wie Frontend erwartet)
    relative_path = Path(sprache) / gattung / kategorie / autor / werk
    target_dir = ROOT / "pdf_drafts" / relative_path
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"→ Zielverzeichnis: {target_dir}")
    
    # Erstelle .gitkeep Datei um sicherzustellen, dass der Ordner bei Git gepusht wird
    gitkeep_file = target_dir / ".gitkeep"
    if not gitkeep_file.exists():
        gitkeep_file.write_text("")
    
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
    
    # NEUE Position (RICHTIG) - Zeile ~145 (NACH temp_input.write_text, VOR subprocess.Popen):
    before = {p.name for p in ROOT.glob("*.pdf")}  # ← GENAU HIER!
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
    
    # WICHTIG: Tag-Config IMMER hinzufügen, wenn vorhanden (nicht nur bei force_meter!)
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
            raise SystemExit(rc)
        
        # KRITISCH: PDF-Matching HIER (innerhalb try, VOR finally)!
        print(f"→ Prüfe ROOT-Verzeichnis: {ROOT}")
        all_pdfs_in_root = list(ROOT.glob("*.pdf"))
        print(f"→ Alle PDFs in ROOT: {[p.name for p in all_pdfs_in_root]}")
        
        after = {p.name for p in ROOT.glob("*.pdf")}
        new_pdfs = sorted(after - before)
        
        print(f"→ Snapshot AFTER subprocess: {len(after)} PDFs, {len(new_pdfs)} neue PDFs")
        
        if new_pdfs:
            # KRITISCH: Die PDFs heißen "temp_agamemnon_..." (mit temp_ Präfix!)
            temp_stem = temp_input.stem  # z.B. "temp_agamemnon_gr_de_en_stil1_birkenbihl_draft_translinear_DRAFT_20251128_232610"
            
            # Entferne "temp_" Präfix und DRAFT_TIMESTAMP
            base_without_temp = temp_stem[5:] if temp_stem.startswith('temp_') else temp_stem
            
            # Entferne DRAFT_TIMESTAMP Suffix
            match = re.match(r'^(.+?)_draft_translinear_DRAFT_\d{8}_\d{6}$', base_without_temp)
            if match:
                clean_base = match.group(1)  # z.B. "agamemnon_gr_de_en_stil1_birkenbihl"
            else:
                clean_base = base_without_temp
            
            print(f"→ Suche PDFs mit Basis: temp_{clean_base}")
            
            # Finde ALLE PDFs, die mit "temp_" + clean_base beginnen
            relevant_pdfs = []
            for name in new_pdfs:
                if name.startswith(f'temp_{clean_base}'):
                    relevant_pdfs.append(name)
            
            if not relevant_pdfs:
                print(f"⚠ Keine passenden PDFs gefunden für Basis: temp_{clean_base}")
                print(f"   Gefundene PDFs: {new_pdfs[:3] if len(new_pdfs) > 0 else 'keine'}")
                return

            sanitized_release_base = release_base.strip()

            for name in relevant_pdfs:
                bare = name[:-4] if name.lower().endswith(".pdf") else name
                
                # Entferne "temp_" Präfix
                if bare.startswith('temp_'):
                    bare = bare[5:]
                
                # Entferne den clean_base Präfix, behalte nur Suffix (z.B. "_Normal_Colour_Tag")
                if bare.startswith(clean_base):
                    suffix = bare[len(clean_base):]
                else:
                    suffix = '_' + bare
                
                # Erstelle finalen Namen
                if sanitized_release_base:
                    final_bare = f"{sanitized_release_base}{suffix}"
                else:
                    final_bare = clean_base + suffix
                
                final_name = f"{final_bare}.pdf"
                
                src = ROOT / name
                dst = target_dir / final_name
                src.replace(dst)
                print(f"✓ PDF → {dst}")

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
        # Cleanup NACH dem PDF-Verschieben
        # --- Cleanup: delete temp files ---
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
    
def apply_bold_if_needed(text, bold_text):
    """Apply bold formatting if needed, preserving existing styles"""
    if bold_text:
        # Check if text already has a style attribute (e.g., color)
        if '<span style="' in text:
            # Insert font-weight: bold into existing style
            text = text.replace('<span style="', '<span style="font-weight: bold; ')
        else:
            # No existing style, just add bold
            return f"<b>{text}</b>"
    return text

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