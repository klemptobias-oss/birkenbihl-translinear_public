# shared/unified_api.py
# -*- coding: utf-8 -*-
"""
Vereinheitlichte PDF-Orchestrierung (bereinigt):
- Kinds: "poesie" (Tragödie/Komödie/Epos zusammengelegt) und "prosa"
- Payload-Support aus der UI (Custom-Farben/Tags + placement_overrides für Hoch/Tief/Aus)
- Vorverarbeitung via shared.preprocess (apply/apply_from_payload)

Erwartete Renderer-Signaturen:
- Poesie (mod = Poesie_Code):
    create_pdf(blocks, out_pdf, *,
               gr_bold: bool,
               de_bold: bool = False,
               versmass_display: bool = False,
               tag_mode: str = "TAGS",
               placement_overrides: dict[str, str] | None = None)
- Prosa (mod = Prosa_Code):
    create_pdf(blocks, out_pdf, *,
               gr_bold: bool,
               de_bold: bool = False,
               tag_mode: str = "TAGS")
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional, Literal

from . import preprocess


Strength = Literal["NORMAL", "GR_FETT", "LAT_FETT", "DE_FETT"]
ColorMode = Literal["COLOR", "BLACK_WHITE"]
TagMode = Literal["TAGS", "NO_TAGS"]
VersmassMode = Literal["NORMAL", "KEEP_MARKERS", "REMOVE_MARKERS"]


@dataclass
class PdfRenderOptions:
    """Optionen, die sowohl fürs Preprocess als auch fürs Benennen/Rendern genutzt werden."""
    strength: Strength = "NORMAL"
    color_mode: ColorMode = "COLOR"
    tag_mode: TagMode = "TAGS"
    # Für Prosa ignoriert, für Poesie relevant:
    versmass_mode: VersmassMode = "NORMAL"


# --------------------------------------------------------------------------------------
# Intern: Renderer-spezifische Calls
# --------------------------------------------------------------------------------------

def _poesie_call(mod: Any, blocks, out_pdf: str, opts: PdfRenderOptions,
                 placement_overrides: Optional[dict] = None,
                 tag_config: Optional[dict] = None):
    """
    Poesie (Drama/Komödie/Epos-Layout):
    - Versmaß-Darstellung: aktiv, wenn versmass_mode="KEEP_MARKERS"
    - placement_overrides werden 1:1 an den Renderer gereicht.
    - LAT_FETT wird wie GR_FETT behandelt (antike Sprache fett)
    """
    versmass_display = (opts.versmass_mode == "KEEP_MARKERS")

    if opts.strength == "GR_FETT" or opts.strength == "LAT_FETT":
        return mod.create_pdf(
            blocks, out_pdf,
            gr_bold=True, de_bold=False,
            versmass_display=versmass_display,
            tag_mode=opts.tag_mode,
            placement_overrides=placement_overrides,
            tag_config=tag_config
        )

    if opts.strength == "NORMAL":
        return mod.create_pdf(
            blocks, out_pdf,
            gr_bold=False, de_bold=False,
            versmass_display=versmass_display,
            tag_mode=opts.tag_mode,
            placement_overrides=placement_overrides,
            tag_config=tag_config
        )

    if opts.strength == "DE_FETT":
        return mod.create_pdf(
            blocks, out_pdf,
            gr_bold=False, de_bold=True,
            versmass_display=versmass_display,
            tag_mode=opts.tag_mode,
            placement_overrides=placement_overrides,
            tag_config=tag_config
        )

    raise ValueError(f"Poesie: Unbekannte strength={opts.strength!r}")


def _prosa_call(mod: Any, blocks, out_pdf: str, opts: PdfRenderOptions,
                placement_overrides: Optional[dict] = None,
                tag_config: Optional[dict] = None,
                hide_pipes: bool = False):  # NEU: Pipes (|) in Übersetzungen verstecken
    """
    Prosa:
    - Kein Versmaß-Rendering.
    - placement_overrides (hoch/tief/aus) jetzt ebenfalls durchreichen.
    - Die Signatur ist nun an _poesie_call angeglichen.
    - LAT_FETT wird wie GR_FETT behandelt (antike Sprache fett)
    """
    if opts.strength == "GR_FETT" or opts.strength == "LAT_FETT":
        return mod.create_pdf(
            blocks, out_pdf,
            strength=opts.strength,  # Übergebe die tatsächliche Strength
            color_mode=opts.color_mode,
            tag_mode=opts.tag_mode,
            placement_overrides=placement_overrides,
            tag_config=tag_config,
            hide_pipes=hide_pipes
        )

    if opts.strength == "NORMAL":
        return mod.create_pdf(
            blocks, out_pdf,
            strength="NORMAL",
            color_mode=opts.color_mode,
            tag_mode=opts.tag_mode,
            placement_overrides=placement_overrides,
            tag_config=tag_config,
            hide_pipes=hide_pipes
        )

    if opts.strength == "DE_FETT":
        return mod.create_pdf(
            blocks, out_pdf,
            strength="DE_FETT",
            color_mode=opts.color_mode,
            tag_mode=opts.tag_mode,
            placement_overrides=placement_overrides,
            tag_config=tag_config,
            hide_pipes=hide_pipes
        )
    
    raise ValueError(f"Prosa: Unbekannte strength={opts.strength!r}")



# --------------------------------------------------------------------------------------
# Öffentliche Orchestrator-Funktion
# --------------------------------------------------------------------------------------

def create_pdf_unified(kind: Literal["poesie", "prosa"],
                       mod: Any,
                       blocks,
                       out_pdf: str,
                       options: PdfRenderOptions,
                       payload: Optional[dict] = None,
                       tag_config: Optional[dict] = None,
                       hide_pipes: bool = False):  # NEU: Pipes (|) in Übersetzungen verstecken
    """
    Orchestriert:
      1) Vorverarbeitung (mit optionaler UI-Payload —> Custom-Farben/Tags)
      2) Renderer-spezifischer Aufruf (poesie/prosa)

    payload (optional), typ. aus HTML:
      {
        "show_colors": bool,
        "show_tags":   bool,
        "color_pos":   [ "Adj","Pt","Prp","Adv","Kon","Art","Pr","ij" ],
        "sup_keep":    [ "N","D","G","A","V","Adj","Pt","Prp","Adv","Kon","Art","≈","Kmp","Sup","ij" ],
        "sub_keep":    [ "Prä","Imp","Aor","AorS","Per","Plq","Inf","Imv","Akt","Med","Pas","Knj","Op","Pr","M/P" ],
        "versmass":    "NORMAL" | "KEEP_MARKERS" | "REMOVE_MARKERS",
        "place":       { "Tag":"sup|sub|off", ... }    # Hoch/Tief/Aus – nur Poesie
      }
    """
    k = kind.lower().strip()
    if k not in {"poesie", "prosa"}:
        raise ValueError(f"Unbekannter kind='{kind}'. Erwartet: poesie|prosa")

    # HINWEIS: Die Vorverarbeitung wurde nach `prosa_pdf.py` verlagert, um eine
    # granulare Steuerung pro PDF-Variante zu ermöglichen. Diese Funktion dient
    # jetzt primär als Hülle für den Renderer-Aufruf. Die übergebenen `blocks`
    # sollten bereits vollständig vorverarbeitet sein.
    pre_blocks = blocks
    placement_overrides = payload.get("place") if payload else None
    
    # 2) Renderer-spezifischer Aufruf
    if k == "poesie":
        return _poesie_call(mod, pre_blocks, out_pdf, options,
                            placement_overrides=placement_overrides,
                            tag_config=tag_config)
    if k == "prosa":
        return _prosa_call(mod, pre_blocks, out_pdf, options,
                           placement_overrides=placement_overrides,
                           tag_config=tag_config,
                           hide_pipes=hide_pipes)

    # (sollte wegen Prüfung oben nie erreicht werden)
    raise ValueError(f"Unbekannter kind='{kind}'. Erwartet: poesie|prosa")

