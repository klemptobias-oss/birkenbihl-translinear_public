######## START: poesie_pdf.py ########
# === UPPER TRANSITION (Poesie-Orchestrator mit optionalen Datei-Argumenten) ===============
"""
poesie_pdf.py
Orchestrator für Poesie (Tragödie/Komödie/Epos).

- Standard: verarbeitet ALLE .txt im Projekt-Root.
- Wenn Dateipfade als Argumente übergeben werden (sys.argv[1:]),
  verarbeitet er GENAU diese Dateien (egal wo sie liegen).

Erzeugt 4 Varianten pro Input:
- Antike Sprache (GR oder LAT) immer FETT
- Deutsche Übersetzung(en) immer NORMAL
- Color (COLOR|BLACK_WHITE) × Tags (TAGS|NO_TAGS)
- Optional: Versmaß-Varianten wenn Versmaß-Marker vorhanden

Die Sprache wird automatisch aus dem Dateinamen erkannt:
- *_gr_* → GR_FETT
- *_lat_* → LAT_FETT
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import os, re, itertools, sys
import logging

# Reduce noisy DEBUG output - set root logger to INFO
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)

# Ensure final_blocks always exists to avoid NameError in except blocks
final_blocks = None

import Poesie_Code as Poesie
from shared.unified_api import create_pdf_unified, PdfRenderOptions
from shared.naming import base_from_input_path, output_pdf_name, PdfRenderOptions as NameOpts
from shared import preprocess
from shared.versmass import has_meter_markers


def _discover_inputs_default() -> list[str]:
    root = Path(".")
    return sorted(str(p) for p in root.glob("*.txt"))

def _args_or_default() -> list[str]:
    # Wenn Argumente übergeben wurden, nimm GENAU diese Dateien
    if len(sys.argv) > 1:
        return [str(Path(a)) for a in sys.argv[1:]]
    return _discover_inputs_default()

def _add_suffix_before_ext(filename: str, suffix: str) -> str:
    p = Path(filename)
    return p.with_name(p.stem + suffix + p.suffix).name

def _input_has_meter_info(blocks: list[dict]) -> bool:
    """
    Prüft, ob irgendein gr_tokens-Block in der Datei Versmaß-Marker enthält.
    
    ### WICHTIG: VERSMASSPUNKT VORERST EINGEFROREN ###
    # has_meter_markers gibt immer False zurück (siehe shared/versmass.py)
    # Daher gibt diese Funktion auch immer False zurück.
    """
    return False  # DEAKTIVIERT - keine Versmaß-PDFs erstellen
    
    ### ORIGINAL CODE (EINGEFROREN) ###
    # for block in blocks:
    #     if block.get('type') == 'pair':
    #         if has_meter_markers(block.get('gr_tokens', [])):
    #             return True
    # return False

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

def _process_one_input(infile: str,
                       tag_config: dict = None,
                       force_meter: Optional[bool] = None,
                       hide_pipes: bool = False) -> None:
    if not os.path.isfile(infile):
        print(f"⚠ Datei fehlt: {infile} — übersprungen"); return

    print(f"\n{'='*60}")
    print(f"Verarbeite: {infile}")
    print(f"force_meter: {force_meter}")
    print(f"{'='*60}\n")

    base = base_from_input_path(Path(infile))
    print(f"→ Base-Name aus Datei: {base}")
    
    blocks = Poesie.process_input_file(infile)
    
    # Safe call to comment discovery (fall back on original blocks)
    final_blocks = list(blocks)
    try:
        cb = preprocess.discover_and_attach_comments(blocks)
        if cb:
            final_blocks = cb
    except Exception:
        logging.getLogger().exception("discover_and_attach_comments failed in poesie_pdf; proceeding without comments")
    
    # ensure comment fields exist
    for b in final_blocks:
        b.setdefault('comments', [])
        b.setdefault('comment_token_mask', [False] * len(b.get('gr_tokens', []) or []))
    
    print(f"→ Anzahl Blöcke: {len(blocks)}")

    # Erkenne Sprache aus Dateinamen
    ancient_lang_strength = _detect_language_from_filename(infile)
    print(f"  → Erkannte Sprache: {ancient_lang_strength}")

    # NEUE KONFIGURATION: 8 Varianten pro Input
    # - NORMAL (antike Sprache nicht fett) + FETT (antike Sprache fett)
    # - COLOR + BLACK_WHITE
    # - TAGS + NO_TAGS
    strengths = ("NORMAL", ancient_lang_strength)  # NORMAL + FETT (GR_FETT oder LAT_FETT)
    colors    = ("COLOR", "BLACK_WHITE")
    tags      = ("TAGS", "NO_TAGS")
    
    # Versmaß-Erkennung: tolerant gegenüber unterschiedlichen Schreibweisen
    # (z. B. _Versmaß, _Versmass, _Versma__, etc.)
    # WICHTIG: Wir normalisieren immer zu "Versmass" (mit ss) für URL-Sicherheit
    base_lower = base.lower()
    input_has_versmass_tag = bool(re.search(r"_versm[aä][sß]{1,2}", base_lower))
    
    # Normalisiere den base-Namen: ersetze alle Versmaß-Varianten durch "Versmass"
    # Regex: _Versm + (a|ä) + (s|ß){1,2} + optional weitere Buchstaben bis zum nächsten Unterstrich
    if input_has_versmass_tag:
        base = re.sub(r"_[Vv]ersm[aä][sß]{1,2}[a-zßA-Z]*(?=_|$)", "_Versmass", base)
        print(f"  → Normalisierter Base-Name: {base}")
    
    if force_meter is True:
        print("  → Versmaß durch Parameter erzwungen.")
        meters = (True,)
    elif force_meter is False:
        print("  → Kein Versmaß (Parameter).")
        meters = (False,)
    elif input_has_versmass_tag:
        print("  → _Versmaß-Tag im Dateinamen gefunden, erstelle Versmaß-PDFs.")
        meters = (True,)  # Nur Versmaß-PDFs (meter_on=True)
    else:
        print("  → Kein _Versmaß-Tag im Dateinamen, erstelle normale PDFs.")
        meters = (False,)  # Nur normale PDFs (meter_on=False)

    # Verwende die neue Standard-Farbkonfiguration basierend auf der Sprache
    default_poesie_tag_config = _get_default_tag_config(ancient_lang_strength)

    final_tag_config = tag_config if tag_config is not None else default_poesie_tag_config

    # DEBUG: Zeige tag_config-Struktur
    if final_tag_config:
        print(f"DEBUG poesie_pdf: tag_config keys: {list(final_tag_config.keys())[:10]}")
        hide_count = sum(1 for conf in final_tag_config.values() if isinstance(conf, dict) and (conf.get('hide') == True or conf.get('hide') == 'hide' or conf.get('hide') == 'true'))
        print(f"DEBUG poesie_pdf: {hide_count} Regeln mit hide=true gefunden")

    # ---- Stelle sicher, dass Kommentare erkannt und zugeordnet sind ----
    # WICHTIG: discover_and_attach_comments wurde bereits oben aufgerufen
    # Kommentare sind bereits in final_blocks['comments'] vorhanden
    
    # WICHTIG: Reihenfolge - Farben ZUERST (basierend auf ORIGINALEN Tags), dann Tags entfernen
    # WICHTIG: discover_and_attach_comments wurde bereits oben aufgerufen - nicht nochmal in der Loop!
    
    for strength, color_mode, tag_mode, meter_on in itertools.product(strengths, colors, tags, meters):
        
        # Pipeline: apply_colors -> apply_tag_visibility -> optional remove_all_tags (NO_TAGS)
        # WICHTIG: discover_and_attach_comments wurde bereits oben aufgerufen - nicht nochmal!
        try:
            disable_comment_bg_flag = (final_tag_config.get('disable_comment_bg', False) if isinstance(final_tag_config, dict) else False)
            blocks_with_colors = preprocess.apply_colors(blocks, final_tag_config, disable_comment_bg=disable_comment_bg_flag)
            hidden_by_wortart = (final_tag_config.get('hidden_tags_by_wortart') if isinstance(final_tag_config, dict) else None)
            blocks_after_visibility = preprocess.apply_tag_visibility(blocks_with_colors, final_tag_config, hidden_tags_by_wortart=hidden_by_wortart)
        except Exception:
            print("ERROR poesie_pdf: apply_colors/apply_tag_visibility failed:")
            traceback.print_exc()
            # try to continue with original blocks (best effort)
            blocks_after_visibility = blocks
        
        # 3) apply tag visibility (bereits im try-Block gesetzt für TAGS, nur NO_TAGS weiter verarbeiten)
        if tag_mode != "TAGS": # NO_TAGS
            blocks_after_visibility = preprocess.remove_all_tags(blocks_with_colors, final_tag_config)
            # Finally: if NO_TAGS variant requested, strip all tags now (but keep token_meta color decisions)
            for b in blocks_after_visibility:
                if b.get("type") not in ("pair", "flow"):
                    continue
                toks = b.get("gr_tokens", [])
                for ti, t in enumerate(toks):
                    if not t:
                        continue
                    b['gr_tokens'][ti] = preprocess.remove_all_tags_from_token(t)

        # Schritt 3: Entferne leere Übersetzungszeilen (wenn alle Übersetzungen ausgeblendet)
        # WICHTIG: Verwende blocks_after_visibility, nicht blocks_with_colors!
        blocks_no_empty_trans = preprocess.remove_empty_translation_lines(blocks_after_visibility)
        
        # Prüfe, ob alle Übersetzungen ausgeblendet sind (für _NoTrans Tag)
        has_no_translations = preprocess.all_blocks_have_no_translations(blocks_no_empty_trans)

        # Schritt 4: Farbsymbole entfernen (für _BlackWhite-Versionen)
        if color_mode == "BLACK_WHITE":
            final_blocks = preprocess.remove_all_color_symbols(blocks_no_empty_trans)
        else: # COLOR
            final_blocks = blocks_no_empty_trans

        # Schritt 5: PDF rendern
        name_no_meter = output_pdf_name(base, NameOpts(strength=strength, color_mode=color_mode, tag_mode=tag_mode))
        
        # Füge _NoTrans hinzu, wenn alle Übersetzungen ausgeblendet sind
        if has_no_translations:
            name_no_meter = _add_suffix_before_ext(name_no_meter, "_NoTrans")
        
        # Füge _Versmass zum Output-Namen hinzu, aber nur wenn:
        # 1. meter_on ist True (wir erstellen ein Versmaß-PDF)
        # 2. Der Input-Name NICHT bereits _Versmass enthält (sonst doppelt)
        # WICHTIG: Wir verwenden immer "Versmass" (mit ss) für URL-Sicherheit
        if meter_on and not input_has_versmass_tag:
            out_name = _add_suffix_before_ext(name_no_meter, "_Versmass")
        else:
            out_name = name_no_meter
            
        versmass_mode = "KEEP_MARKERS" if meter_on else "REMOVE_MARKERS"
        opts = PdfRenderOptions(strength=strength, color_mode=color_mode, tag_mode=tag_mode, versmass_mode=versmass_mode)
        
        create_pdf_unified("poesie", Poesie, final_blocks, out_name, opts, payload=None, tag_config=final_tag_config, hide_pipes=hide_pipes)
        print(f"✓ PDF erstellt → {out_name}")

def main():
    # Parse command line arguments for tag config
    import argparse
    parser = argparse.ArgumentParser(description='Poesie PDF Generator')
    parser.add_argument('input_files', nargs='*', help='Input files to process')
    parser.add_argument('--tag-config', help='JSON file with tag configuration')
    parser.add_argument('--force-meter', action='store_true', help='Versmaß-Ausgabe erzwingen')
    parser.add_argument('--force-no-meter', action='store_true', help='Versmaß deaktivieren')
    parser.add_argument('--hide-pipes', action='store_true', help='Hide pipe characters in translations')
    args = parser.parse_args()
    
    if args.force_meter and args.force_no_meter:
        print("⚠ --force-meter und --force-no-meter können nicht gemeinsam verwendet werden.")
        sys.exit(1)

    if args.force_meter:
        force_meter_flag: Optional[bool] = True
    elif args.force_no_meter:
        force_meter_flag = False
    else:
        force_meter_flag = None
    
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
            print("DEBUG poesie_pdf: geladene tag_config keys:", list(tag_config.keys())[:10])
            print("DEBUG poesie_pdf: tag_colors count:", len(tag_config.get("tag_colors", {})))
            print("DEBUG poesie_pdf: hidden_tags:", tag_config.get("hidden_tags"))
            # Prüfe hide-Regeln
            hide_count = sum(1 for conf in tag_config.values() if isinstance(conf, dict) and (conf.get('hide') == True or conf.get('hide') == 'hide' or conf.get('hide') == 'true'))
            print(f"DEBUG poesie_pdf: {hide_count} Regeln mit hide=true gefunden")
            # Zeige erste Regel mit hide=true
            for rule_id, conf in list(tag_config.items())[:5]:
                if isinstance(conf, dict):
                    hide_val = conf.get('hide')
                    if hide_val == True or hide_val == 'hide' or hide_val == 'true':
                        print(f"DEBUG poesie_pdf: Regel '{rule_id}' hat hide={hide_val}")
            print(f"Tag-Konfiguration geladen: {len(tag_config.get('sup_tags', []))} SUP, {len(tag_config.get('sub_tags', []))} SUB")
        except Exception as e:
            print(f"Fehler beim Laden der Tag-Konfiguration: {e}")
    
    for infile in inputs:
        print(f"→ Verarbeite: {infile}")
        try:
            _process_one_input(infile, tag_config, force_meter=force_meter_flag, hide_pipes=args.hide_pipes)
        except Exception as e:
            print(f"✗ Fehler bei {infile}: {e}")

if __name__ == "__main__":
    main()
# === LOWER TRANSITION =====================================================================
######## ENDE: poesie_pdf.py ########
