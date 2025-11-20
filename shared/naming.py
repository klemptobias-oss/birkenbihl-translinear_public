#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shared/naming.py
----------------
Zentrale, einheitliche Namenslogik für PDF-Ausgaben.

Varianten & Suffixe:
- Stärke/Fettung:  NORMAL → _Normal  |  GR_FETT → _GR_Fett  |  LAT_FETT → _LAT_Fett  |  DE_FETT → _DE_Fett
- Farbmodus:       COLOR  → _Colour  |  BLACK_WHITE → _BlackWhite
- Tagmodus:        TAGS   → _Tag     |  NO_TAGS → _NoTags

Benennung:
Basename aus Eingabedatei (ohne Relikt 'Input' am Anfang) + Suffixe
in dieser Reihenfolge:  _<Stärke> + _<Farbe> + _<Tags>  + ".pdf".
"""

from __future__ import annotations
from pathlib import Path
from typing import Literal

# ----- Typen -----
Strength  = Literal["NORMAL", "GR_FETT", "LAT_FETT", "DE_FETT"]
ColorMode = Literal["COLOR", "BLACK_WHITE"]
TagMode   = Literal["TAGS", "NO_TAGS"]

PDF_EXT = ".pdf"


class PdfRenderOptions:
    """
    Einfache, 3.12-kompatible Optionsstruktur (ohne dataclasses).
    """
    __slots__ = ("strength", "color_mode", "tag_mode")

    def __init__(self,
                 strength: Strength = "NORMAL",
                 color_mode: ColorMode = "COLOR",
                 tag_mode: TagMode = "TAGS") -> None:
        self.strength = strength
        self.color_mode = color_mode
        self.tag_mode = tag_mode


# ----- Basisnamen-Logik -----
def sanitize_base_name(stem: str) -> str:
    """
    Vereinheitlicht den Basisnamen:
      - schneidet führendes 'Input' ab (organisches Relikt)
      - ersetzt unzulässige Zeichen durch '_'
      - verhindert leeren Namen → 'Output'
    """
    base = stem or ""
    if base.startswith("Input"):
        base = base[len("Input"):]
    safe = "".join(ch if ch.isalnum() or ch in ("_", "-", ".", " ") else "_" for ch in base).strip()
    return safe or "Output"


def base_from_input_path(input_path: Path) -> str:
    """Liest den Stem des Inputs und wendet sanitize_base_name an."""
    return sanitize_base_name(Path(input_path).stem)


# ----- Suffixe -----
def _suffix_for_strength(s: Strength) -> str:
    if s == "GR_FETT": return "_GR_Fett"
    if s == "LAT_FETT": return "_LAT_Fett"
    if s == "DE_FETT": return "_DE_Fett"
    return "_Normal"  # NORMAL


def _suffix_for_color(c: ColorMode) -> str:
    if c == "BLACK_WHITE": return "_BlackWhite"
    return "_Colour"  # COLOR


def _suffix_for_tags(t: TagMode) -> str:
    if t == "NO_TAGS": return "_NoTags"
    return "_Tag"  # TAGS


# ----- Ausgabe-Namen -----
def output_pdf_name(base: str, opts: PdfRenderOptions) -> str:
    """
    Baut den endgültigen PDF-Dateinamen (ohne Pfad) aus Basisname + Suffixen + '.pdf'.
    Reihenfolge: Stärke → Farbe → Tags.
    """
    name = (
        base
        + _suffix_for_strength(opts.strength)
        + _suffix_for_color(opts.color_mode)
        + _suffix_for_tags(opts.tag_mode)
    )
    return (name or "Output") + PDF_EXT


def output_pdf_path(out_dir: Path, base: str, opts: PdfRenderOptions) -> Path:
    """Wie output_pdf_name, aber als vollständiger Pfad in out_dir."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / output_pdf_name(base, opts)


# ----- (Optionale) Parser für spätere Rückwärtskompatibilität -----
def parse_strength_token(token: str) -> Strength:
    tok = (token or "").strip().lower()
    if tok in {"gr_fett", "gr-fett", "grbold", "boldgr"}:
        return "GR_FETT"
    if tok in {"lat_fett", "lat-fett", "latbold", "boldlat"}:
        return "LAT_FETT"
    if tok in {"de_fett", "de-fett", "debold", "boldde"}:
        return "DE_FETT"
    return "NORMAL"


def parse_color_token(token: str) -> ColorMode:
    tok = (token or "").strip().lower()
    if tok in {"black_white", "blackwhite", "bw", "b/w"}:
        return "BLACK_WHITE"
    return "COLOR"


def parse_tags_token(token: str) -> TagMode:
    tok = (token or "").strip().lower()
    if tok in {"no_tags", "notags", "no-tag", "ohnetags"}:
        return "NO_TAGS"
    return "TAGS"

