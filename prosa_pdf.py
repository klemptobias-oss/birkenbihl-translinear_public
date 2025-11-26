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
    Install a SIGALRM that will abort the process after PROSA_PDF_TIMEOUT seconds.
    Default: 600 seconds. This prevents CI from hanging forever.
    """
    try:
        timeout = int(os.environ.get("PROSA_PDF_TIMEOUT", "600"))
        def _timeout_handler(signum, frame):
            msg = "prosa_pdf: GLOBAL TIMEOUT reached (%s seconds) - aborting" % timeout
            logger.error(msg)
            try:
                sys.stdout.flush(); sys.stderr.flush()
            except Exception:
                pass
            # exit with non-zero so CI marks failure
            raise SystemExit(2)
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout)
        logger.info("prosa_pdf: global timeout installed: %s seconds", timeout)
    except Exception:
        logger.exception("prosa_pdf: failed to install global timeout (continuing without alarm)")

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

    base = base_from_input_path(Path(infile))
    base_name = str(base)  # for logging and debug dumps
    
    # --- START: install a global timeout and log start ---
    def _install_global_timeout():
        """
        Install a SIGALRM handler which aborts the process after PROSA_PDF_TIMEOUT seconds.
        Default timeout: 600 seconds (10 minutes). This prevents CI jobs from hanging forever.
        """
        try:
            timeout = int(os.environ.get("PROSA_PDF_TIMEOUT", "600"))
            def _timeout_handler(signum, frame):
                logging.getLogger(__name__).error("prosa_pdf: GLOBAL TIMEOUT reached (%s seconds) - aborting", timeout)
                # attempt to flush stdout/stderr so CI shows this immediately
                try:
                    sys.stdout.flush()
                    sys.stderr.flush()
                except Exception:
                    pass
                # exit non-zero so CI marks job failed
                raise SystemExit(2)
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(timeout)
            logging.getLogger(__name__).info("prosa_pdf: global timeout installed: %s seconds", timeout)
        except Exception:
            logging.getLogger(__name__).exception("prosa_pdf: failed to install global timeout (continuing without alarm)")

    _install_global_timeout()
    logging.getLogger(__name__).info("prosa_pdf: START processing file=%s", base_name)
    # make sure logs are visible quickly in CI
    try:
        sys.stdout.flush()
    except Exception:
        pass
    t_start = time.time()
    # --- END start/timeout block ---
    
    generated_files = []  # track created PDFs
    
    t_process = time.time()
    blocks_raw = Prosa.process_input_file(infile)
    logging.getLogger(__name__).info("prosa_pdf: process_input_file done (%.2f s), blocks_raw=%d", time.time() - t_process, len(blocks_raw) if blocks_raw else 0)
    
    # WICHTIG: Kommentare MÜSSEN VOR group_pairs_into_flows() erkannt werden,
    # da discover_and_attach_comments() nach block['gr'] (String) sucht,
    # aber nach group_pairs_into_flows() haben flow-Blöcke nur noch block['gr_tokens'] (Liste)!
    # --- robust comment discovery: never abort the whole run because of comment attach errors ---
    logger.info("prosa_pdf: START processing file=%s", base_name)
    try:
        sys.stdout.flush()
    except Exception:
        pass
    start_time = time.time()
    
    # robust call to discover_and_attach_comments: try new signature, fallback to old
    # WICHTIG: Aufruf VOR group_pairs_into_flows(), damit block['gr'] noch vorhanden ist!
    blocks_with_comments = None
    comment_regexes = None
    strip_comment_lines = True
    try:
        blocks_with_comments = preprocess.discover_and_attach_comments(
            blocks_raw,
            comment_regexes=comment_regexes,
            strip_comment_lines=strip_comment_lines,
        )
    except TypeError:
        try:
            blocks_with_comments = preprocess.discover_and_attach_comments(blocks_raw)
        except Exception as e:
            logger.exception("prosa_pdf: discover/attach comments failed (continuing without comments): %s", e)
            blocks_with_comments = blocks_raw
    except Exception as e:
        logger.exception("prosa_pdf: discover/attach comments failed (continuing without comments): %s", e)
        blocks_with_comments = blocks_raw

    if blocks_with_comments is None:
        logger.debug("prosa_pdf: discover_and_attach_comments returned None -> using original blocks")
        blocks_with_comments = blocks_raw
    
    # JETZT: Tokenisierung durchführen (nach Kommentar-Erkennung)
    t_group = time.time()
    blocks = Prosa.group_pairs_into_flows(blocks_with_comments)
    logging.getLogger(__name__).info("prosa_pdf: group_pairs_into_flows done (%.2f s), blocks=%d", time.time() - t_group, len(blocks) if blocks else 0)
    
    # Verwende blocks als final_blocks (Kommentare sind bereits erkannt und angehängt)
    final_blocks = blocks

    # Compact debug summary for CI logs: print only first block's comments and a short mask sample.
    try:
        c0 = final_blocks[0].get('comments') if isinstance(final_blocks, list) and final_blocks else None
        mask0 = final_blocks[0].get('comment_token_mask') if isinstance(final_blocks, list) and final_blocks else None
        logger.info("DEBUG prosa_pdf: final_blocks[0].comments=%s mask_sample=%s",
                    (c0 if c0 else []),
                    (mask0[:40] if mask0 is not None else None))
    except Exception:
        logger.debug("prosa_pdf: failed to print final_blocks[0] debug info", exc_info=True)

    # Erkenne Sprache aus Dateinamen
    ancient_lang_strength = _detect_language_from_filename(infile)
    print(f"  → Erkannte Sprache: {ancient_lang_strength}")

    # NEUE KONFIGURATION: 8 Varianten pro Input-Datei
    # - NORMAL: Nichts fett (weder antike Sprache noch Überschriften)
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
    
    # ---- Stelle sicher, dass Kommentare erkannt und zugeordnet sind ----
    # WICHTIG: discover_and_attach_comments wurde bereits oben aufgerufen (vor der Loop)
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
        
        # Pipeline: apply_colors -> apply_tag_visibility (NUR wenn tag_config vorhanden) -> optional remove_all_tags (NO_TAGS)
        # WICHTIG: discover_and_attach_comments wurde bereits oben aufgerufen - nicht nochmal!
        try:
            t1 = time.time()
            logging.getLogger(__name__).info("prosa_pdf: apply_colors START (strength=%s, color=%s, tag=%s)", strength, color_mode, tag_mode)
            disable_comment_bg_flag = (final_tag_config.get('disable_comment_bg', False) if isinstance(final_tag_config, dict) else False)
            # WICHTIG: apply_colors wird IMMER aufgerufen (auch bei BLACK_WHITE), 
            # da es Farben basierend auf tag_config hinzufügt. Bei BLACK_WHITE werden Farben später entfernt.
            blocks_with_colors = preprocess.apply_colors(final_blocks, final_tag_config, disable_comment_bg=disable_comment_bg_flag)
            
            # WICHTIG: Tag-Sichtbarkeit basierend auf tag_mode und tag_config
            # Bei TAGS-Varianten: Tags bleiben erhalten, aber apply_tag_visibility wird aufgerufen,
            # um die Tag-Sichtbarkeit basierend auf tag_config zu steuern (z.B. hide für bestimmte Wortarten)
            # Bei NO_TAGS-Varianten: Alle Tags werden später komplett entfernt
            blocks_after_visibility = blocks_with_colors
            if tag_mode == "TAGS" and final_tag_config:
                # Bei TAGS-Varianten: Tag-Sichtbarkeit basierend auf tag_config anwenden
                # (z.B. wenn Nomen-Tags versteckt werden sollen, werden sie entfernt)
                # WICHTIG: apply_tag_visibility entfernt nur die Tags, die in tag_config als "hide" markiert sind
                # Prüfe, ob ALLE Tags versteckt sind - wenn ja, dann keine Filterung (Tags bleiben bei TAGS-Varianten)
                all_hidden = all(conf.get("hide") in (True, "true", "True", "hide", "Hide") 
                                for conf in final_tag_config.values() 
                                if isinstance(conf, dict))
                if not all_hidden:
                    # Nicht alle Tags sind versteckt - wende Tag-Sichtbarkeit an
                    hidden_by_wortart = (final_tag_config.get("hidden_tags_by_wortart") if isinstance(final_tag_config, dict) else None)
                    blocks_after_visibility = preprocess.apply_tag_visibility(blocks_with_colors, final_tag_config, hidden_tags_by_wortart=hidden_by_wortart)
                    logging.getLogger(__name__).info("prosa_pdf: TAGS mode - applied tag visibility based on tag_config (not all tags hidden)")
                else:
                    # Alle Tags sind versteckt - aber bei TAGS-Varianten wollen wir Tags behalten!
                    logging.getLogger(__name__).info("prosa_pdf: TAGS mode - all tags marked as hide in tag_config, but keeping all tags (TAGS variant)")
            elif tag_mode == "TAGS":
                # Bei TAGS-Varianten ohne tag_config: Alle Tags bleiben erhalten
                logging.getLogger(__name__).info("prosa_pdf: TAGS mode - keeping all tags (no tag_config)")
            else:
                logging.getLogger(__name__).info("prosa_pdf: NO_TAGS mode - will remove all tags in next step")
        except Exception as e:
            tb = traceback.format_exc()
            logging.getLogger(__name__).error("prosa_pdf: apply_colors/apply_tag_visibility failed (continuing): %s", str(e))
            logging.getLogger(__name__).debug("prosa_pdf: apply_colors/apply_tag_visibility traceback (first 800 chars):\n%s", tb[:800])
            blocks_after_visibility = final_blocks
        
        # 3) Entferne ALLE Tags für NO_TAGS-Varianten (NUR bei NO_TAGS!)
        # WICHTIG: Diese Prüfung muss NACH dem try-except-Block stehen, damit sie auch bei Fehlern ausgeführt wird
        if tag_mode == "NO_TAGS":
            # Bei NO_TAGS-Varianten: Entferne ALLE Tags komplett
            # WICHTIG: Verwende blocks_with_colors, nicht blocks_after_visibility (die könnte bei Fehlern final_blocks sein)
            blocks_after_visibility = preprocess.remove_all_tags(blocks_with_colors, final_tag_config)
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
            final_blocks = preprocess.remove_all_color_symbols(blocks_no_empty_trans)
        else: # COLOR
            final_blocks = blocks_no_empty_trans

        # Schritt 5: PDF rendern mit dem final prozessierten Block-Set.
        out_name = output_pdf_name(base, NameOpts(strength=strength, color_mode=color_mode, tag_mode=tag_mode))
        
        # Füge _NoTrans hinzu, wenn alle Übersetzungen ausgeblendet sind
        if has_no_translations:
            p = Path(out_name)
            out_name = p.with_name(p.stem + "_NoTrans" + p.suffix).name
        opts = PdfRenderOptions(strength=strength, color_mode=color_mode, tag_mode=tag_mode, versmass_mode="REMOVE_MARKERS")
        
        # --- DEBUG-HILFSFUNKTIONEN ---
        import re
        RE_TAG_INLINE = re.compile(r'\([A-Za-z0-9/≈äöüßÄÖÜ]+\)')
        
        def _sample_tokens_with_tags(blocks, limit=20):
            found = []
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                for seqk in ('gr_tokens','de_tokens','en_tokens'):
                    seq = b.get(seqk, [])
                    for tok in (seq or []):
                        if tok and RE_TAG_INLINE.search(tok):
                            found.append(tok)
                            if len(found) >= limit:
                                return found
            return found
        
        def _count_flow_comments(blocks):
            total = 0
            examples = []
            for b in blocks:
                if isinstance(b, dict):
                    # Prüfe direkt auf type='comment'
                    if b.get('type') == 'comment':
                        total += 1
                        if len(examples) < 3:
                            examples.append(b.get('content') or b.get('text') or b.get('original_line') or '')
                    # Prüfe auf flow-Blöcke mit Kommentaren
                    if b.get('type') == 'flow':
                        if 'flow_blocks' in b and isinstance(b['flow_blocks'], list):
                            for fb in b['flow_blocks']:
                                if isinstance(fb, dict) and fb.get('type') == 'comment':
                                    total += 1
                                    if len(examples) < 3:
                                        examples.append(fb.get('content') or fb.get('text') or fb.get('original_line') or '')
            return total, examples[:3]
        
        # Drucke kurze Zusammenfassung
        sample = _sample_tokens_with_tags(final_blocks, limit=20)
        print(f"DEBUG: verbleibende Tokens mit '(...)' (sollte LEER sein bei Tag-Entfernung): {len(sample)} gefunden")
        if sample:
            logger.debug(f"DEBUG: Beispiele: {sample[:5]}")
        num_comments, comment_examples = _count_flow_comments(final_blocks)
        logger.debug(f"DEBUG: Anzahl gefundener Kommentare in final_blocks = {num_comments}. Beispiele: {comment_examples}")
        # --- Ende DEBUG ---
        
        # WICHTIG: Die unified_api wird jetzt nur noch für das Rendering aufgerufen.
        # Die Vorverarbeitung ist hier abgeschlossen. `tag_config` wird trotzdem durchgereicht,
        # falls der Renderer selbst noch Konfigurationsdetails benötigt (z.B. für Platzierung).
        # build the PDF document (via create_pdf_unified which calls Prosa.create_pdf which calls doc.build())
        logger.info("prosa_pdf: about to call reportlab build() for %s (blocks=%d)", out_name, total_blocks)
        try:
            sys.stdout.flush()
        except Exception:
            pass
        try:
            # call the real build (this may be the long blocking step)
            create_pdf_unified("prosa", Prosa, final_blocks, out_name, opts, payload=None, tag_config=final_tag_config, hide_pipes=hide_pipes)
            logger.info("prosa_pdf: reportlab build() finished for %s", out_name)
            generated_files.append(out_name)
            logger.info("✓ PDF created -> %s", out_name)
        except Exception:
            logger.exception("prosa_pdf: reportlab build() FAILED for %s", out_name)
            raise
        finally:
            # cancel the global alarm because the heavy work finished
            try:
                signal.alarm(0)
            except Exception:
                pass
    
    # turn off the alarm now that the heavy section finished (if it was set)
    try:
        signal.alarm(0)
    except Exception:
        pass
    
    # final summary for CI logs: list files created
    try:
        end_time = time.time()
        logger.info("prosa_pdf: finished processing %s in %.1f seconds", base_name, end_time - t_start)
        logger.info("prosa_pdf: END processing file=%s created_files=%d", base_name, len(generated_files))
        for f in generated_files:
            logger.info("✓ PDF created -> %s", f)
        try:
            sys.stdout.flush()
        except Exception:
            pass
    except Exception:
        logger.debug("prosa_pdf: failed to log generated files", exc_info=True)
    
    # optional: print suppressed counts for table warnings
    for f in [h for h in getattr(logger, "filters", []) if isinstance(h, _RepeatedMessageFilter)]:
        total_suppressed = sum(1 for c in f._counts.values() if c > 100)
        if total_suppressed > 0:
            logger.info("Suppressed repeated Table/Comment warnings (patterns suppressed: %d)", total_suppressed)

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
            print("DEBUG prosa_pdf: hidden_tags:", tag_config.get("hidden_tags"))
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

