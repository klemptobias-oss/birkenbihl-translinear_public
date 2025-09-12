#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shared/unified_api.py (v3, 3.12-robust)
---------------------------------------
Einheitliche Render-Schnittstelle für Epos / Prosa / Drama / Platon.

Neu: Vorverarbeitung (Color/Tags) via shared.preprocess.apply(...)
"""

from __future__ import annotations
from typing import Any, Literal, Optional

# ==== Optionen / Typen ====
Strength  = Literal["NORMAL", "GR_FETT", "DE_FETT"]
ColorMode = Literal["COLOR", "BLACK_WHITE"]
TagMode   = Literal["TAGS", "NO_TAGS"]
VersmassMode = Literal["NORMAL", "REMOVE_MARKERS", "KEEP_MARKERS"]

class PdfRenderOptions:
    __slots__ = ("strength", "color_mode", "tag_mode", "versmass_mode")
    def __init__(self,
                 strength: Strength = "NORMAL",
                 color_mode: ColorMode = "COLOR",
                 tag_mode: TagMode = "TAGS",
                 versmass_mode: VersmassMode = "NORMAL") -> None:
        self.strength   = strength
        self.color_mode = color_mode
        self.tag_mode   = tag_mode
        self.versmass_mode = versmass_mode

# ==== Preprocess import ====
try:
    from shared import preprocess  # via sys.path im Orchestrator
except Exception:
    # Fallback: relative Import, falls direkt ohne Orchestrator ausgeführt
    import importlib
    preprocess = importlib.import_module("preprocess")  # type: ignore

# ==== Familien-spezifische Adapter ====

def _epos_call(mod: Any, blocks, out_pdf: str, opts: PdfRenderOptions):
    # Epos benötigt eine cfg-Struktur (FETT/NORMAL); DE_FETT noch nicht implementiert
    # Versmaß-Darstellung: Aktiv wenn "_Versmaß" IM Dateinamen
    versmass_display = "_Versmaß" in out_pdf

    if opts.strength == "GR_FETT":
        # Verwende tag_mode-spezifische CFG
        get_fett_cfg = getattr(mod, "get_fett_cfg", None)
        if get_fett_cfg:
            cfg = get_fett_cfg(opts.tag_mode)
        else:
            cfg = getattr(mod, "FETT", getattr(mod, "CFG", None))
            if cfg is None:
                raise RuntimeError("Epos: FETT/CFG-Konfiguration nicht gefunden.")
        return mod.create_pdf(blocks, out_pdf, cfg, versmass_display=versmass_display, tag_mode=opts.tag_mode)

    if opts.strength == "NORMAL":
        # Verwende tag_mode-spezifische CFG
        get_normal_cfg = getattr(mod, "get_normal_cfg", None)
        if get_normal_cfg:
            cfg = get_normal_cfg(opts.tag_mode)
        else:
            cfg = getattr(mod, "NORMAL", None)
            if cfg is None:
                # Fallback: wie FETT, aber GR_BOLD=False überschreiben
                base = getattr(mod, "FETT", getattr(mod, "CFG", None))
                if base is None:
                    raise RuntimeError("Epos: NORMAL-Konfiguration nicht gefunden.")
                cfg = dict(base, GR_BOLD=False)
        return mod.create_pdf(blocks, out_pdf, cfg, versmass_display=versmass_display, tag_mode=opts.tag_mode)

    if opts.strength == "DE_FETT":
        # Verwende tag_mode-spezifische CFG für DE_FETT
        get_de_fett_cfg = getattr(mod, "get_de_fett_cfg", None)
        if get_de_fett_cfg:
            cfg = get_de_fett_cfg(opts.tag_mode)
        else:
            cfg = getattr(mod, "DE_FETT", getattr(mod, "CFG", None))
            if cfg is None:
                raise RuntimeError("Epos: DE_FETT-Konfiguration nicht gefunden.")
        return mod.create_pdf(blocks, out_pdf, cfg, versmass_display=versmass_display, tag_mode=opts.tag_mode)

    raise ValueError(f"Epos: Unbekannte strength={opts.strength!r}")

def _prosa_call(mod: Any, blocks, out_pdf: str, opts: PdfRenderOptions):
    if opts.strength == "GR_FETT":
        gr_size = getattr(mod, "REVERSE_GR_SIZE", getattr(mod, "NORMAL_GR_SIZE", 9.0))
        de_size = getattr(mod, "REVERSE_DE_SIZE", getattr(mod, "NORMAL_DE_SIZE", 8.0))
        return mod.create_pdf(blocks, out_pdf,
                              strength="GR_FETT",
                              gr_size=gr_size, de_size=de_size,
                              color_mode=opts.color_mode, tag_mode=opts.tag_mode)
    if opts.strength == "NORMAL":
        gr_size = getattr(mod, "NORMAL_GR_SIZE", 9.0)
        de_size = getattr(mod, "NORMAL_DE_SIZE", 8.0)
        return mod.create_pdf(blocks, out_pdf,
                              strength="NORMAL",
                              gr_size=gr_size, de_size=de_size,
                              color_mode=opts.color_mode, tag_mode=opts.tag_mode)
    if opts.strength == "DE_FETT":
        gr_size = getattr(mod, "NORMAL_GR_SIZE", 9.0)
        de_size = getattr(mod, "NORMAL_DE_SIZE", 8.0)
        return mod.create_pdf(blocks, out_pdf,
                              strength="DE_FETT",
                              gr_size=gr_size, de_size=de_size,
                              color_mode=opts.color_mode, tag_mode=opts.tag_mode)
    raise ValueError(f"Prosa: Unbekannte strength={opts.strength!r}")

def _drama_call(mod: Any, blocks, out_pdf: str, opts: PdfRenderOptions):
    # Versmaß-Darstellung: Aktiv wenn "_Versmaß" IM Dateinamen
    versmass_display = "_Versmaß" in out_pdf

    if opts.strength == "GR_FETT":
        return mod.create_pdf(blocks, out_pdf, gr_bold=True, de_bold=False, versmass_display=versmass_display, tag_mode=opts.tag_mode)
    if opts.strength == "NORMAL":
        return mod.create_pdf(blocks, out_pdf, gr_bold=False, de_bold=False, versmass_display=versmass_display, tag_mode=opts.tag_mode)
    if opts.strength == "DE_FETT":
        return mod.create_pdf(blocks, out_pdf, gr_bold=False, de_bold=True, versmass_display=versmass_display, tag_mode=opts.tag_mode)
    raise ValueError(f"Drama/Komödie: Unbekannte strength={opts.strength!r}")

def _platon_call(mod: Any, blocks, out_pdf: str, opts: PdfRenderOptions):
    if opts.strength == "GR_FETT":
        return mod.create_pdf(blocks, out_pdf, gr_bold=True, de_bold=False, tag_mode=opts.tag_mode)
    if opts.strength == "NORMAL":
        return mod.create_pdf(blocks, out_pdf, gr_bold=False, de_bold=False, tag_mode=opts.tag_mode)
    if opts.strength == "DE_FETT":
        return mod.create_pdf(blocks, out_pdf, gr_bold=False, de_bold=True, tag_mode=opts.tag_mode)
    raise ValueError(f"Platon: Unbekannte strength={opts.strength!r}")

# ==== Öffentliche API ====

def create_pdf_unified(kind: str, mod: Any, blocks, out_pdf: str,
                       opts: Optional[PdfRenderOptions] = None):
    """
    Einheitlicher Aufruf über alle Familien.
    Wendet vorab eine NICHT-destruktive Vorverarbeitung an (Color/Tags).
    """
    k = (kind or "").strip().lower()
    options = opts or PdfRenderOptions()

    # 1) Vorverarbeitung (kopiert die Struktur; Original bleibt unangetastet)
    pre_blocks = preprocess.apply(
        blocks,
        color_mode=options.color_mode,
        tag_mode=options.tag_mode,
        versmass_mode=options.versmass_mode,
    )

    # 2) Renderer-spezifischer Aufruf
    if k == "epos":
        return _epos_call(mod, pre_blocks, out_pdf, options)
    if k == "prosa":
        return _prosa_call(mod, pre_blocks, out_pdf, options)
    if k == "drama":
        return _drama_call(mod, pre_blocks, out_pdf, options)
    if k == "platon":
        return _platon_call(mod, pre_blocks, out_pdf, options)

    raise ValueError(f"Unbekannter kind='{kind}'. Erwartet: epos|prosa|drama|platon")

