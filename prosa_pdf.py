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

import Prosa_Code as Prosa
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
    blocks_raw = Prosa.process_input_file(infile)
    # Tokenisierung direkt hier durchführen, um die Pipeline an Poesie anzugleichen
    blocks = Prosa.group_pairs_into_flows(blocks_raw)

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
    # Schritt 1: Farben basierend auf der finalen Konfiguration hinzufügen.
    # Das Ergebnis ist ein Block-Set mit allen Original-Tags UND den neuen Farbsymbolen.
    blocks_with_colors = preprocess.apply_colors(blocks, final_tag_config)
    
    for strength, color_mode, tag_mode in itertools.product(strengths, colors, tags):
        
        # Schritt 2: Tag-Sichtbarkeit anwenden (für _Tag-Versionen)
        # oder alle Tags entfernen (für _NoTag-Versionen).
        if tag_mode == "TAGS":
            # Bei _drafts wird die spezifische tag_config für die Sichtbarkeit verwendet,
            # bei standard die default config (die implizit alle Tags anzeigt).
            blocks_with_tags = preprocess.apply_tag_visibility(blocks_with_colors, final_tag_config)
        else: # NO_TAGS
            blocks_with_tags = preprocess.remove_all_tags(blocks_with_colors, final_tag_config)

        # Schritt 3: Entferne leere Übersetzungszeilen (wenn alle Übersetzungen ausgeblendet)
        blocks_no_empty_trans = preprocess.remove_empty_translation_lines(blocks_with_tags)
        
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
            print(f"DEBUG: Beispiele: {sample[:5]}")
        num_comments, comment_examples = _count_flow_comments(final_blocks)
        print(f"DEBUG: Anzahl gefundener Kommentare in final_blocks = {num_comments}. Beispiele: {comment_examples}")
        # --- Ende DEBUG ---
        
        # WICHTIG: Die unified_api wird jetzt nur noch für das Rendering aufgerufen.
        # Die Vorverarbeitung ist hier abgeschlossen. `tag_config` wird trotzdem durchgereicht,
        # falls der Renderer selbst noch Konfigurationsdetails benötigt (z.B. für Platzierung).
        create_pdf_unified("prosa", Prosa, final_blocks, out_name, opts, payload=None, tag_config=final_tag_config, hide_pipes=hide_pipes)
        print(f"✓ PDF erstellt → {out_name}")

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

