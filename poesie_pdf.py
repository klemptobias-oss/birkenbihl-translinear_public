######## START: poesie_pdf.py ########
# === UPPER TRANSITION (Poesie-Orchestrator mit optionalen Datei-Argumenten) ===============
"""
poesie_pdf.py
Orchestrator für Poesie (Tragödie/Komödie/Epos).

- Standard: verarbeitet ALLE .txt im Projekt-Root.
- Wenn Dateipfade als Argumente übergeben werden (sys.argv[1:]),
  verarbeitet er GENAU diese Dateien (egal wo sie liegen).

Erzeugt 24 Varianten pro Input:
Strength (NORMAL|GR_FETT|DE_FETT) × Color (COLOR|BLACK_WHITE)
× Tags (TAGS|NO_TAGS) × Versmaß (AUS|AN).

Versmaß-Darstellung wird über Suffix "_Versmaß" im Dateinamen aktiviert.
"""

from __future__ import annotations
from pathlib import Path
import os, re, itertools, sys

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
    """Prüft, ob irgendein gr_tokens-Block in der Datei Versmaß-Marker enthält."""
    for block in blocks:
        if block.get('type') == 'pair':
            if has_meter_markers(block.get('gr_tokens', [])):
                return True
    return False

def _process_one_input(infile: str, tag_config: dict = None) -> None:
    if not os.path.isfile(infile):
        print(f"⚠ Datei fehlt: {infile} — übersprungen"); return

    base = base_from_input_path(Path(infile))
    blocks = Poesie.process_input_file(infile)

    strengths = ("NORMAL", "GR_FETT", "DE_FETT")
    colors    = ("COLOR", "BLACK_WHITE")
    tags      = ("TAGS", "NO_TAGS")
    
    # NEU: Prüfe, ob die Input-Datei überhaupt Versmaß-Infos enthält
    input_contains_meter = _input_has_meter_info(blocks)
    if input_contains_meter:
        print("  → Versmaß-Informationen gefunden, _Versmaß-PDFs werden erstellt.")
        meters = (False, True)
    else:
        print("  → Keine Versmaß-Informationen gefunden, _Versmaß-PDFs werden übersprungen.")
        meters    = (False,) # Nur die Variante OHNE Versmaß-Suffix erstellen

    default_poesie_tag_config = {
        # Nomen rot
        "nomen": {"color": "red"},
        "nomen_N": {"color": "red"}, "nomen_G": {"color": "red"}, "nomen_D": {"color": "red"}, "nomen_A": {"color": "red"}, "nomen_V": {"color": "red"},
        # Verben grün
        "verb": {"color": "green"},
        "verb_Prä": {"color": "green"}, "verb_Imp": {"color": "green"}, "verb_Aor": {"color": "green"}, "verb_AorS": {"color": "green"}, "verb_Per": {"color": "green"}, "verb_Plq": {"color": "green"}, "verb_Fu": {"color": "green"},
        "verb_Akt": {"color": "green"}, "verb_Med": {"color": "green"}, "verb_Pas": {"color": "green"}, "verb_MP": {"color": "green"}, "verb_Inf": {"color": "green"}, "verb_Op": {"color": "green"}, "verb_Knj": {"color": "green"}, "verb_Imv": {"color": "green"},
        # Adjektive & Partizipien blau
        "adjektiv": {"color": "blue"},
        "adjektiv_N": {"color": "blue"}, "adjektiv_G": {"color": "blue"}, "adjektiv_D": {"color": "blue"}, "adjektiv_A": {"color": "blue"}, "adjektiv_V": {"color": "blue"}, "adjektiv_Kmp": {"color": "blue"}, "adjektiv_Sup": {"color": "blue"},
        "partizip": {"color": "blue"},
        "partizip_Pra": {"color": "blue"}, "partizip_Imp": {"color": "blue"}, "partizip_Aor": {"color": "blue"}, "partizip_AorS": {"color": "blue"}, "partizip_Per": {"color": "blue"}, "partizip_Plq": {"color": "blue"}, "partizip_Fu": {"color": "blue"},
        "partizip_N": {"color": "blue"}, "partizip_G": {"color": "blue"}, "partizip_D": {"color": "blue"}, "partizip_A": {"color": "blue"}, "partizip_V": {"color": "blue"},
        "partizip_Akt": {"color": "blue"}, "partizip_Med": {"color": "blue"}, "partizip_Pas": {"color": "blue"}, "partizip_MP": {"color": "blue"},
    }

    final_tag_config = tag_config if tag_config is not None else default_poesie_tag_config

    # Schritt 1: Farben basierend auf der finalen Konfiguration hinzufügen.
    blocks_with_colors = preprocess.apply_colors(blocks, final_tag_config)

    for strength, color_mode, tag_mode, meter_on in itertools.product(strengths, colors, tags, meters):
        
        # Schritt 2: Tag-Sichtbarkeit anwenden
        if tag_mode == "TAGS":
            blocks_with_tags = preprocess.apply_tag_visibility(blocks_with_colors, final_tag_config)
        else: # NO_TAGS
            blocks_with_tags = preprocess.remove_all_tags(blocks_with_colors)

        # Schritt 3: Farbsymbole entfernen (für _BlackWhite-Versionen)
        if color_mode == "BLACK_WHITE":
            final_blocks = preprocess.remove_all_color_symbols(blocks_with_tags)
        else: # COLOR
            final_blocks = blocks_with_tags

        # Schritt 4: PDF rendern
        name_no_meter = output_pdf_name(base, NameOpts(strength=strength, color_mode=color_mode, tag_mode=tag_mode))
        out_name = _add_suffix_before_ext(name_no_meter, "_Versmaß") if meter_on else name_no_meter
        versmass_mode = "KEEP_MARKERS" if meter_on else "REMOVE_MARKERS"
        opts = PdfRenderOptions(strength=strength, color_mode=color_mode, tag_mode=tag_mode, versmass_mode=versmass_mode)
        
        create_pdf_unified("poesie", Poesie, final_blocks, out_name, opts, payload=None, tag_config=final_tag_config)
        print(f"✓ PDF erstellt → {out_name}")

def main():
    # Parse command line arguments for tag config
    import argparse
    parser = argparse.ArgumentParser(description='Poesie PDF Generator')
    parser.add_argument('input_files', nargs='*', help='Input files to process')
    parser.add_argument('--tag-config', help='JSON file with tag configuration')
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
            print(f"Tag-Konfiguration geladen: {len(tag_config.get('sup_tags', []))} SUP, {len(tag_config.get('sub_tags', []))} SUB")
        except Exception as e:
            print(f"Fehler beim Laden der Tag-Konfiguration: {e}")
    
    for infile in inputs:
        print(f"→ Verarbeite: {infile}")
        try:
            _process_one_input(infile, tag_config)
        except Exception as e:
            print(f"✗ Fehler bei {infile}: {e}")

if __name__ == "__main__":
    main()
# === LOWER TRANSITION =====================================================================
######## ENDE: poesie_pdf.py ########
