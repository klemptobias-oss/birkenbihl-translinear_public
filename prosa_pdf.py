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

    for strength, color, tag in itertools.product(strengths, colors, tags):
        out_name = output_pdf_name(base, NameOpts(strength=strength, color_mode=color, tag_mode=tag))
        opts = PdfRenderOptions(strength=strength, color_mode=color, tag_mode=tag, versmass_mode="REMOVE_MARKERS")
        create_pdf_unified("prosa", Prosa, blocks, out_name, opts, payload=None, tag_config=tag_config)
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
######## ENDE: prosa_pdf.py ########

