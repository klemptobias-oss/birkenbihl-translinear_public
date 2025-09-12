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

def _process_one_input(infile: str) -> None:
    if not os.path.isfile(infile):
        print(f"⚠ Datei fehlt: {infile} — übersprungen"); return

    base = base_from_input_path(Path(infile))
    blocks = Prosa.process_input_file(infile)

    strengths = ("NORMAL", "GR_FETT", "DE_FETT")
    colors    = ("COLOR", "BLACK_WHITE")
    tags      = ("TAGS", "NO_TAGS")

    for strength, color, tag in itertools.product(strengths, colors, tags):
        out_name = output_pdf_name(base, NameOpts(strength=strength, color_mode=color, tag_mode=tag))
        opts = PdfRenderOptions(strength=strength, color_mode=color, tag_mode=tag, versmass_mode="REMOVE_MARKERS")
        create_pdf_unified("prosa", Prosa, blocks, out_name, opts)
        print(f"✓ PDF erstellt → {out_name}")

def main():
    inputs = _args_or_default()
    if not inputs:
        print("⚠ Keine .txt gefunden."); return
    for infile in inputs:
        print(f"→ Verarbeite: {infile}")
        try:
            _process_one_input(infile)
        except Exception as e:
            print(f"✗ Fehler bei {infile}: {e}")

if __name__ == "__main__":
    main()
# === LOWER TRANSITION =====================================================================
######## ENDE: prosa_pdf.py ########

