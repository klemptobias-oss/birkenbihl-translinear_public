######## START: prosa_pdf.py ########
# === UPPER TRANSITION (Prosa-Orchestrator mit optionalen Datei-Argumenten) ================
"""
prosa_pdf.py
Orchestrator für Prosa (Platon/Aristoteles/Thukydides/…).

- Standard: verarbeitet ALLE .txt im Projekt-Root.
- Wenn Dateipfade als Argumente übergeben werden (sys.argv[1:]),
  verarbeitet er GENAU diese Dateien (egal wo sie liegen).

Erzeugt 12 Varianten pro Input (ohne Versmaß):
Strength (NORMAL|GR_FETT|DE_FETT) × Color (COLOR|BLACK_WHITE) × Tags (TAGS|NO_TAGS).
"""

from __future__ import annotations
from pathlib import Path
import os, itertools, sys

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

def _process_one_input(infile: str, tag_config: dict = None) -> None:
    if not os.path.isfile(infile):
        print(f"⚠ Datei fehlt: {infile} — übersprungen"); return

    base = base_from_input_path(Path(infile))
    blocks_raw = Prosa.process_input_file(infile)
    # Tokenisierung direkt hier durchführen, um die Pipeline an Poesie anzugleichen
    blocks = Prosa.group_pairs_into_flows(blocks_raw)

    strengths = ("NORMAL", "GR_FETT", "DE_FETT")
    colors    = ("COLOR", "BLACK_WHITE")
    tags      = ("TAGS", "NO_TAGS")

    # Standard-Farbkonfiguration für den Prosa-Adapter
    # Diese wird verwendet, wenn keine spezifische Konfiguration (z.B. aus einem Draft) kommt.
    default_prosa_tag_config = {
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
            blocks_with_tags = preprocess.remove_all_tags(blocks_with_colors)

        # Schritt 3: Farbsymbole entfernen (für _BlackWhite-Versionen).
        if color_mode == "BLACK_WHITE":
            final_blocks = preprocess.remove_all_color_symbols(blocks_with_tags)
        else: # COLOR
            final_blocks = blocks_with_tags

        # Schritt 4: PDF rendern mit dem final prozessierten Block-Set.
        out_name = output_pdf_name(base, NameOpts(strength=strength, color_mode=color_mode, tag_mode=tag_mode))
        opts = PdfRenderOptions(strength=strength, color_mode=color_mode, tag_mode=tag_mode, versmass_mode="REMOVE_MARKERS")
        
        # WICHTIG: Die unified_api wird jetzt nur noch für das Rendering aufgerufen.
        # Die Vorverarbeitung ist hier abgeschlossen. `tag_config` wird trotzdem durchgereicht,
        # falls der Renderer selbst noch Konfigurationsdetails benötigt (z.B. für Platzierung).
        create_pdf_unified("prosa", Prosa, final_blocks, out_name, opts, payload=None, tag_config=final_tag_config)
        print(f"✓ PDF erstellt → {out_name}")

def main():
    # Parse command line arguments for tag config
    import argparse
    parser = argparse.ArgumentParser(description='Prosa PDF Generator')
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
            _process_one_input(infile, tag_config)
        except Exception as e:
            print(f"✗ Fehler bei {infile}: {e}")

if __name__ == "__main__":
    main()
# === LOWER TRANSITION =====================================================================
######## ENDE: prosa_pdf.py ########

