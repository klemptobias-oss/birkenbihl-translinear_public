######## START: prosa_pdf.py ########
# === UPPER TRANSITION (Prosa-Orchestrator mit optionalen Datei-Argumenten) ================
"""
prosa_pdf.py
Orchestrator für Prosa (Platon/Aristoteles/Thukydides/…).

- Standard: verarbeitet ALLE .txt im Projekt-Root.
- Wenn Dateipfade als Argumente übergeben werden (sys.argv[1:]),
  verarbeitet er GENAU diese Dateien (egal wo sie liegen).

Erzeugt 4 Varianten pro Input:
- Antike Sprache (GR oder LAT) immer FETT
- Deutsche Übersetzung(en) immer NORMAL
- Color (COLOR|BLACK_WHITE) × Tags (TAGS|NO_TAGS)

Die Sprache wird automatisch aus dem Dateinamen erkannt:
- *_gr_* → GR_FETT
- *_lat_* → LAT_FETT
"""

from __future__ import annotations
from pathlib import Path
import os, itertools, sys
from pathlib import Path
import logging
import os
import json
import tempfile
import time
import signal
import sys
import traceback
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors

# Reduce noisy DEBUG output - set root logger to INFO
logging.getLogger().setLevel(logging.INFO)

# Throttle / suppress huge repeated debug lines from low-level loops
class _RepeatThrottleFilter(logging.Filter):
    def __init__(self, name='', max_messages=3000):
        super().__init__(name)
        self.max_messages = int(os.environ.get("LOG_THROTTLE_MAX", max_messages))
        self.counter = {}
    def filter(self, record):
        msg = getattr(record, "getMessage", lambda: str(record))()
        # target the debug spam we know: _process_pair_block_for_tags
        if "_process_pair_block_for_tags" in msg:
            cnt = self.counter.get("_process_pair_block_for_tags", 0) + 1
            self.counter["_process_pair_block_for_tags"] = cnt
            if cnt > self.max_messages:
                # drop extra messages
                if cnt == self.max_messages + 1:
                    # log once that we've suppressed further lines
                    logging.getLogger(__name__).warning(
                        "prosa_pdf: suppressed further _process_pair_block_for_tags debug lines (>%d)", self.max_messages)
                return False
        return True

# --- START: Repeated-message throttling filter (prevents log-spam) ---
from typing import Iterable

class _RepeatedMessageFilter(logging.Filter):
    def __init__(self, patterns: Iterable[str] = None, max_occurrences: int = 60):
        super().__init__()
        self.patterns = list(patterns) if patterns else [
            "Table-Breite zu groß",
            "Kommentar verarbeiten:",
            "Kommentar-Paragraph HINZUGEFÜGT",
            "Added",
        ]
        self.max_occurrences = int(max_occurrences)
        self._counts = {p: 0 for p in self.patterns}

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        for p in self.patterns:
            if p in msg:
                c = self._counts[p]
                if c < self.max_occurrences:
                    self._counts[p] = c + 1
                    return True
                elif c == self.max_occurrences:
                    record.msg = f"{p}: further identical messages suppressed after {self.max_occurrences} occurrences"
                    self._counts[p] = c + 1
                    return True
                else:
                    return False
        return True

try:
    logger.addFilter(_RepeatedMessageFilter(max_occurrences=100))
except Exception:
    pass
# --- END: Repeated-message throttling filter ---

# Ensure stream handler with throttle filter
logger = logging.getLogger(__name__)
if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    sh = logging.StreamHandler(stream=sys.stdout)
    sh.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    sh.addFilter(_RepeatThrottleFilter())
    logger.addHandler(sh)
    logger.setLevel(logging.DEBUG)


# Attach log throttle to suppress mass warnings (table width, tag removal spam)
try:
    from shared.log_throttle import setup_logging_throttle
    setup_logging_throttle()
except Exception:
    logging.getLogger().debug("prosa_pdf: log throttle not available/failed to init")

# Print an immediate startup banner so CI shows process start
try:
    banner = "prosa_pdf: startup pid=%s argv=%s" % (os.getpid(), " ".join(sys.argv))
    print(banner)
    sys.stdout.flush()
    logger.info(banner)
except Exception:
    # never fail here
    pass

def _install_global_timeout():
    """
    Installiert einen globalen Timeout-Handler (nur auf Unix-Systemen).
    WICHTIG: Reduziert auf 6 Minuten (360 Sekunden) statt 10 Minuten.
    """
    try:
        import signal
        # TIMEOUT: Reduziert auf 6 Minuten (360 Sekunden)
        TIMEOUT_SECONDS = 360  # GEÄNDERT von 600 auf 360
        
        def timeout_handler(signum, frame):
            logger = logging.getLogger(__name__)
            logger.error("prosa_pdf: GLOBAL TIMEOUT after %d seconds - aborting", TIMEOUT_SECONDS)
            sys.exit(124)  # Timeout exit code
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(TIMEOUT_SECONDS)
        logger = logging.getLogger(__name__)
        logger.info("prosa_pdf: global timeout installed: %d seconds", TIMEOUT_SECONDS)
    except Exception:
        # Windows oder andere Plattformen ohne SIGALRM
        pass

# Try to install the timeout immediately (defensive)
_install_global_timeout()

import Prosa_Code as Prosa

# Ensure final_blocks always exists to avoid NameError in except blocks
final_blocks = None
from shared.unified_api import create_pdf_unified, PdfRenderOptions
from shared.naming import base_from_input_path, output_pdf_name, PdfRenderOptions as NameOpts
from shared import preprocess

def _discover_inputs_default() -> list[str]:
    root = Path(".")
    return sorted(str(p) for p in root.glob("*.txt"))

def _args_or_default() -> list[str]:
    if len(sys.argv) > 1:
        return [str(Path(a)) for a in sys.argv[1:]]
    return _discover_inputs_default()

def _detect_language_from_filename(filename: str) -> str:
    """
    Erkennt die Sprache aus dem Dateinamen.
    - *_gr_* → GR_FETT
    - *_lat_* → LAT_FETT
    """
    filename_lower = filename.lower()
    if "_lat_" in filename_lower:
        return "LAT_FETT"
    elif "_gr_" in filename_lower:
        return "GR_FETT"
    else:
        # Fallback: Wenn nicht erkennbar, verwende GR_FETT
        print(f"  ⚠ Sprache nicht erkennbar aus Dateinamen, verwende GR_FETT als Fallback")
        return "GR_FETT"

def _get_default_tag_config(language: str) -> dict:
    """
    Erstellt die Standard-Farbkonfiguration für die angegebene Sprache.
    
    Griechisch:
    - Nomen → rot (#)
    - Verben → grün (-)
    - Partizipien → purpur/magenta (§)
    - Infinitive → purpur/magenta (§)
    - Adjektive → blau (+)
    
    Latein:
    - Nomen (inkl. nur Abl) → rot (#)
    - Verben → grün (-)
    - Partizipien → purpur/magenta (§)
    - Infinitive (Inf) → purpur/magenta (§)
    - Gerundium (Ger) → purpur/magenta (§)
    - Gerundivum (Gdv) → purpur/magenta (§)
    - Supinum (Spn) → purpur/magenta (§)
    - Adjektive → blau (+)
    """
    config = {}
    
    # Nomen → rot
    config['nomen'] = {'color': 'red'}
    for kasus in ['N', 'G', 'D', 'A', 'V', 'Abl']:  # Abl für Latein
        config[f'nomen_{kasus}'] = {'color': 'red'}
    
    # Verben → grün
    config['verb'] = {'color': 'green'}
    for tag in ['Prä', 'Imp', 'Aor', 'AorS', 'Per', 'Plq', 'Fu', 'Fu1', 'Fu2', 'Akt', 'Med', 'Pas', 'M/P', 'Op', 'Knj', 'Imv']:  # NEU: Fu1, Fu2
        config[f'verb_{tag}'] = {'color': 'green'}
    
    # Partizipien → purpur/magenta (§)
    config['partizip'] = {'color': 'magenta'}
    for tag in ['Prä', 'Imp', 'Aor', 'AorS', 'Per', 'Plq', 'Fu', 'Fu1', 'Fu2', 'N', 'G', 'D', 'A', 'V', 'Akt', 'Med', 'Pas', 'M/P']:  # NEU: Fu1, Fu2
        config[f'partizip_{tag}'] = {'color': 'magenta'}
    
    # Infinitive → grün (-) wie andere Verben
    config['verb_Inf'] = {'color': 'green'}
    
    # Latein-spezifische Formen → purpur/magenta (§)
    if language == "LAT_FETT":
        config['verb_Ger'] = {'color': 'magenta'}  # Gerundium
        config['verb_Gdv'] = {'color': 'magenta'}  # Gerundivum
        config['verb_Spn'] = {'color': 'magenta'}  # Supinum
        config['verb_Fu1'] = {'color': 'green'}    # NEU: Futur 1 als Verb → grün
        config['verb_Fu2'] = {'color': 'green'}    # NEU: Futur 2 als Verb → grün
        config['partizip_Fu1'] = {'color': 'magenta'}  # NEU: Futur 1 Partizip → magenta
        config['partizip_Fu2'] = {'color': 'magenta'}  # NEU: Futur 2 Partizip → magenta
    
    # Adjektive → blau
    config['adjektiv'] = {'color': 'blue'}
    for tag in ['N', 'G', 'D', 'A', 'V', 'Kmp', 'Sup']:
        config[f'adjektiv_{tag}'] = {'color': 'blue'}
    
    return config

def _process_one_input(infile: str, tag_config: dict = None, hide_pipes: bool = False) -> None:
    if not os.path.isfile(infile):
        print(f"⚠ Datei fehlt: {infile} — übersprungen"); return

    print(f"→ Verarbeite: {infile}")
    base = base_from_input_path(Path(infile))
    print(f"→ Base-Name aus Datei: {base}")
    
    logger = logging.getLogger(__name__)
    logger.info("prosa_pdf: START processing file=%s", str(base))
    start_time = time.time()
    
    blocks = Prosa.process_input_file(infile)
    
    # WICHTIG: Für Prosa werden Kommentare NICHT automatisch als separate Blöcke erkannt
    # Wir müssen discover_and_attach_comments aufrufen
    from shared.preprocess import discover_and_attach_comments
    # KRITISCH: discover_and_attach_comments akzeptiert NUR blocks, KEIN source_file!
    blocks = discover_and_attach_comments(blocks)
    logger.info(f"discover_and_attach_comments() returned {len(blocks)} blocks")
    
    # DIAGNOSE: Zeige Block-Typen
    from collections import Counter
    block_types = Counter(b.get('type', 'unknown') for b in blocks if isinstance(b, dict))
    logger.info(f"Block-Typen: {dict(block_types)}")
    
    # KRITISCH: Prüfe, ob flow/pair-Blöcke vorhanden sind!
    flow_count = sum(1 for b in blocks if isinstance(b, dict) and b.get('type') == 'flow')
    pair_count = sum(1 for b in blocks if isinstance(b, dict) and b.get('type') == 'pair')
    logger.info(f"flow_blocks={flow_count}, pair_blocks={pair_count}")
    
    # KRITISCH: Wenn pair_count > 0 und flow_count == 0, rufe group_pairs_into_flows() auf!
    if pair_count > 0 and flow_count == 0:
        logger.info(f"Converting {pair_count} pair blocks to flow blocks...")
        blocks = Prosa.group_pairs_into_flows(blocks)
        
        # Re-check nach Konvertierung
        flow_count_after = sum(1 for b in blocks if isinstance(b, dict) and b.get('type') == 'flow')
        pair_count_after = sum(1 for b in blocks if isinstance(b, dict) and b.get('type') == 'pair')
        logger.info(f"After conversion: flow_blocks={flow_count_after}, pair_blocks={pair_count_after}")
    
    if flow_count == 0 and pair_count == 0:
        logger.error("ERROR: KEIN TRANSLINEAR-TEXT!")
        return  # WICHTIG: Abbrechen, da keine verarbeitbaren Blöcke vorhanden sind
    
    final_blocks = blocks
    
    print(f"→ Anzahl Blöcke: {len(blocks)}")

    # Erkenne Sprache aus Dateinamen
    ancient_lang_strength = _detect_language_from_filename(infile)
    print(f"  → Erkannte Sprache: {ancient_lang_strength}")

    # WICHTIG: Prosa hat KEINE Versmaß-Varianten
    # NEUE KONFIGURATION: 8 Varianten pro Input (wie bei Poesie)
    # - NORMAL (antike Sprache nicht fett) + FETT (antike Sprache fett)
    # - COLOR + BLACK_WHITE
    # - TAGS + NO_TAGS
    # WICHTIG: Bei PROSA ist die Fettung anders:
    # - NORMAL: deutsche Übersetzung normal, antike Sprache normal
    # - GR_FETT/LAT_FETT: Antike Sprache fett, Überschriften normal (um Tinte zu sparen)
    strengths = ("NORMAL", ancient_lang_strength)
    colors    = ("COLOR", "BLACK_WHITE")
    tags      = ("TAGS", "NO_TAGS")

    # Verwende die neue Standard-Farbkonfiguration basierend auf der Sprache
    default_prosa_tag_config = _get_default_tag_config(ancient_lang_strength)
    
    # Wenn keine spezifische tag_config übergeben wird (Standardfall für build_prosa_adapter),
    # verwende die Standard-Farbkonfiguration.
    final_tag_config = tag_config if tag_config is not None else default_prosa_tag_config

    # --- KORREKTE VERARBEITUNGS-PIPELINE ---
    # WICHTIG: Reihenfolge - Farben ZUERST (basierend auf ORIGINALEN Tags), dann Tags entfernen
    
    # DEBUG: Zeige tag_config-Struktur
    if final_tag_config:
        print(f"DEBUG prosa_pdf: tag_config keys: {list(final_tag_config.keys())[:10]}")
        hide_count = sum(1 for conf in final_tag_config.values() if isinstance(conf, dict) and (conf.get('hide') == True or conf.get('hide') == 'hide' or conf.get('hide') == 'true'))
        print(f"DEBUG prosa_pdf: {hide_count} Regeln mit hide=true gefunden")
    
    # Kommentare sind bereits in final_blocks['comments'] vorhanden
    
    num_variants = len(list(itertools.product(strengths, colors, tags)))
    total_blocks = len(final_blocks) if isinstance(final_blocks, list) else 0
    logging.getLogger(__name__).info("prosa_pdf: Starting PDF generation loop for %d variants, total_blocks=%d", num_variants, total_blocks)
    
    variant_index = 0
    for strength, color_mode, tag_mode in itertools.product(strengths, colors, tags):
        variant_index += 1
        logging.getLogger(__name__).info("prosa_pdf: processing variant %d/%d (strength=%s, color=%s, tag=%s)", variant_index, num_variants, strength, color_mode, tag_mode)
        try:
            sys.stdout.flush()
        except Exception:
            pass
        
        # KRITISCH: Wir müssen für JEDE Variante eine FRISCHE KOPIE der Blöcke verwenden
        # und die Preprocessing-Schritte NEU durchführen!
        import copy
        variant_blocks = copy.deepcopy(final_blocks)
        
        # Pipeline: apply_colors -> apply_tag_visibility (NUR wenn tag_config vorhanden) -> optional remove_all_tags (NO_TAGS)
        try:
            t1 = time.time()
            logging.getLogger(__name__).info("prosa_pdf: apply_colors START (strength=%s, color=%s, tag=%s)", strength, color_mode, tag_mode)
            disable_comment_bg_flag = (final_tag_config.get('disable_comment_bg', False) if isinstance(final_tag_config, dict) else False)
            # WICHTIG: apply_colors wird IMMER aufgerufen (auch bei BLACK_WHITE), 
            # da es Farben basierend auf tag_config hinzufügt. Bei BLACK_WHITE werden Farben später entfernt.
            blocks_with_colors = preprocess.apply_colors(variant_blocks, final_tag_config, disable_comment_bg=disable_comment_bg_flag)
            t2 = time.time()
            logging.getLogger(__name__).info("prosa_pdf: apply_colors END (%.2fs)", t2 - t1)
        except Exception as e:
            tb = traceback.format_exc()
            logging.getLogger(__name__).error("prosa_pdf: apply_colors failed: %s", str(e))
            logging.getLogger(__name__).debug("prosa_pdf: apply_colors traceback:\n%s", tb[:800])
            blocks_with_colors = variant_blocks
        
        # 2) Tag-Sichtbarkeit anwenden (wenn tag_config vorhanden)
        try:
            # WICHTIG: Tag-Sichtbarkeit basierend auf tag_config anwenden (wie in Poesie)
            # apply_tag_visibility wird IMMER aufgerufen (auch bei TAGS), um die Tag-Sichtbarkeit zu steuern
            # Bei TAGS-Varianten: Entfernt nur die Tags, die in tag_config als "hide" markiert sind
            # Bei NO_TAGS-Varianten: Werden später alle Tags entfernt
            hidden_by_wortart = (final_tag_config.get("hidden_tags_by_wortart") if isinstance(final_tag_config, dict) else None)
            blocks_after_visibility = preprocess.apply_tag_visibility(blocks_with_colors, final_tag_config, hidden_tags_by_wortart=hidden_by_wortart)
            logging.getLogger(__name__).info("prosa_pdf: applied tag visibility (tag_mode=%s)", tag_mode)
        except Exception as e:
            tb = traceback.format_exc()
            logging.getLogger(__name__).error("prosa_pdf: apply_colors/apply_tag_visibility failed (continuing): %s", str(e))
            logging.getLogger(__name__).debug("prosa_pdf: apply_colors/apply_tag_visibility traceback (first 800 chars):\n%s", tb[:800])
            # WICHTIG: Verwende blocks_with_colors falls verfügbar, sonst variant_blocks
            blocks_after_visibility = blocks_with_colors if 'blocks_with_colors' in locals() else variant_blocks
        
        # 3) Entferne ALLE Tags für NO_TAGS-Varianten (NUR bei NO_TAGS!)
        if tag_mode != "TAGS":  # NO_TAGS - wie in Poesie
            # Bei NO_TAGS-Varianten: Entferne ALLE Tags komplett
            # WICHTIG: Verwende blocks_after_visibility (die bereits durch apply_tag_visibility verarbeitet wurde)
            blocks_after_visibility = preprocess.remove_all_tags(blocks_after_visibility, final_tag_config)
            # NO_TAG variant: strip any remaining tags from tokens
            for b in blocks_after_visibility:
                if b.get("type") not in ("pair", "flow"):
                    continue
                for i, t in enumerate(b.get("gr_tokens", [])):
                    if t:
                        b["gr_tokens"][i] = preprocess.remove_all_tags_from_token(t)
            logging.getLogger(__name__).info("prosa_pdf: NO_TAGS mode - removed all tags")
        # Bei TAGS-Varianten: blocks_after_visibility wurde bereits oben gesetzt (oder ist blocks_with_colors)
        # Es ist bereits korrekt, keine weitere Aktion nötig

        # Schritt 3: Entferne leere Übersetzungszeilen (wenn alle Übersetzungen ausgeblendet)
        # WICHTIG: Verwende blocks_after_visibility, nicht blocks_with_colors!
        blocks_no_empty_trans = preprocess.remove_empty_translation_lines(blocks_after_visibility)
        
        # Prüfe, ob alle Übersetzungen ausgeblendet sind (für _NoTrans Tag)
        has_no_translations = preprocess.all_blocks_have_no_translations(blocks_no_empty_trans)

        # Schritt 4: Farbsymbole entfernen (für _BlackWhite-Versionen).
        if color_mode == "BLACK_WHITE":
            variant_final_blocks = preprocess.remove_all_color_symbols(blocks_no_empty_trans)
        else: # COLOR
            variant_final_blocks = blocks_no_empty_trans

        # Schritt 5: PDF rendern mit dem final prozessierten Block-Set.
        out_name = output_pdf_name(base, NameOpts(strength=strength, color_mode=color_mode, tag_mode=tag_mode))
        
        # Füge _NoTrans hinzu, wenn alle Übersetzungen ausgeblendet sind
        if has_no_translations:
            p = Path(out_name)
            out_name = p.with_name(p.stem + "_NoTrans" + p.suffix).name
        opts = PdfRenderOptions(strength=strength, color_mode=color_mode, tag_mode=tag_mode, versmass_mode="REMOVE_MARKERS")
        
        # build the PDF via unified API
        logger.info("prosa_pdf: about to call reportlab build() for %s (blocks=%d)", out_name, len(variant_final_blocks))
        try:
            sys.stdout.flush()
        except Exception:
            pass
        try:
            create_pdf_unified("prosa", Prosa, variant_final_blocks, out_name, opts, payload=None, tag_config=final_tag_config, hide_pipes=hide_pipes)
            logger.info("prosa_pdf: reportlab build() finished for %s", out_name)
            print(f"✓ PDF erstellt → {out_name}")
        except Exception:
            logger.exception("prosa_pdf: reportlab build() FAILED for %s", out_name)
            raise
    
    try:
        end_time = time.time()
        logger.info("prosa_pdf: finished processing %s in %.1f seconds", str(base), end_time - start_time)
        try:
            sys.stdout.flush()
        except Exception:
            pass
    except Exception:
        pass

def main():
    # Parse command line arguments for tag config
    import argparse
    parser = argparse.ArgumentParser(description='Prosa PDF Generator')
    parser.add_argument('input_files', nargs='*', help='Input files to process')
    parser.add_argument('--tag-config', help='JSON file with tag configuration')
    parser.add_argument('--hide-pipes', action='store_true', help='Hide pipes (|) in translations')
    args = parser.parse_args()
    
    # Use input files from arguments, or fallback to default discovery
    inputs = args.input_files if args.input_files else _args_or_default()
    if not inputs:
        print("⚠ Keine .txt gefunden."); return
    
    # Load tag configuration if provided
    tag_config = None
    if args.tag_config:
        import json
        try:
            with open(args.tag_config, 'r', encoding='utf-8') as f:
                tag_config = json.load(f)
            # DEBUG: Zeige tag_config-Struktur
            print("DEBUG prosa_pdf: geladene tag_config keys:", list(tag_config.keys())[:10])
            print("DEBUG prosa_pdf: tag_colors count:", len(tag_config.get("tag_colors", {})))
            print("DEBUG prosa_pdf: hidden_tags:", tag_config.get("hiddenTags"))
            # Prüfe hide-Regeln
            hide_count = sum(1 for conf in tag_config.values() if isinstance(conf, dict) and (conf.get('hide') == True or conf.get('hide') == 'hide' or conf.get('hide') == 'true'))
            print(f"DEBUG prosa_pdf: {hide_count} Regeln mit hide=true gefunden")
            # Zeige erste Regel mit hide=true
            for rule_id, conf in list(tag_config.items())[:5]:
                if isinstance(conf, dict):
                    hide_val = conf.get('hide')
                    if hide_val == True or hide_val == 'hide' or hide_val == 'true':
                        print(f"DEBUG prosa_pdf: Regel '{rule_id}' hat hide={hide_val}")
            # Debug-Ausgabe nur für externe JSON-Dateien (nicht für Draft-Konfigurationen)
            if 'sup_tags' in tag_config and 'sub_tags' in tag_config:
                print(f"Tag-Konfiguration geladen: {len(tag_config.get('sup_tags', []))} SUP, {len(tag_config.get('sub_tags', []))} SUB")
            else:
                print(f"Tag-Konfiguration geladen: {len(tag_config)} Regeln")
        except Exception as e:
            print(f"Fehler beim Laden der Tag-Konfiguration: {e}")
    
    for infile in inputs:
        print(f"→ Verarbeite: {infile}")
        try:
            _process_one_input(infile, tag_config, hide_pipes=args.hide_pipes)
        except Exception as e:
            print(f"✗ Fehler bei {infile}: {e}")

if __name__ == "__main__":
    main()
# === LOWER TRANSITION =====================================================================
######## ENDE: prosa_pdf.py ########

