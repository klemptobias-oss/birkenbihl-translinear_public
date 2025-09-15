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


Strength = Literal["NORMAL", "GR_FETT", "DE_FETT"]
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
    - Versmaß-Darstellung: aktiv, wenn "_Versmaß" im Dateinamen steht.
    - placement_overrides werden 1:1 an den Renderer gereicht.
    """
    versmass_display = "_Versmaß" in out_pdf

    if opts.strength == "GR_FETT":
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
                tag_config: Optional[dict] = None):
    """
    Prosa:
    - Kein Versmaß-Rendering.
    - placement_overrides (hoch/tief/aus) jetzt ebenfalls durchreichen.
    - Die Signatur ist nun an _poesie_call angeglichen.
    """
    if opts.strength == "GR_FETT":
        return mod.create_pdf(
            blocks, out_pdf,
            strength="GR_FETT",
            color_mode=opts.color_mode,
            tag_mode=opts.tag_mode,
            placement_overrides=placement_overrides,
            tag_config=tag_config
        )

    if opts.strength == "NORMAL":
        return mod.create_pdf(
            blocks, out_pdf,
            strength="NORMAL",
            color_mode=opts.color_mode,
            tag_mode=opts.tag_mode,
            placement_overrides=placement_overrides,
            tag_config=tag_config
        )

    if opts.strength == "DE_FETT":
        return mod.create_pdf(
            blocks, out_pdf,
            strength="DE_FETT",
            color_mode=opts.color_mode,
            tag_mode=opts.tag_mode,
            placement_overrides=placement_overrides,
            tag_config=tag_config
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
                       tag_config: Optional[dict] = None):
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

    # 1) Vorverarbeitung (+ optionale UI-Payload)
    #    - Payload leer/None -> Standard apply(...)
    #    - Payload gesetzt   -> apply_from_payload(...) inkl. Normalisierung auf Extremfälle
    
    # NEU: Wenn tag_config übergeben wird, aber keine Payload,
    # erstelle eine Payload. Das vereinheitlicht den Drafts-Workflow.
    effective_payload = payload
    if effective_payload is None and tag_config is not None:
        effective_payload = {
            "color_mode": options.color_mode,
            "tag_config": tag_config,
            "versmass": options.versmass_mode,
            # 'place' overrides werden in Poesie-spezifischem Code erwartet,
            # hier vorerst nicht automatisch übernommen.
        }

    if effective_payload is not None:
        pre_blocks = preprocess.apply_from_payload(
            blocks,
            effective_payload,
            default_versmass_mode=options.versmass_mode
        )
        placement_overrides = effective_payload.get("place") or None
    else:
        # Standard-Vorverarbeitung: apply() direkt aufrufen
        pre_blocks = preprocess.apply(
            blocks,
            color_mode=options.color_mode,
            tag_mode=options.tag_mode,
            versmass_mode=options.versmass_mode,
            tag_config=tag_config # tag_config hier weitergeben
        )
        placement_overrides = None

    # 2) Renderer-spezifischer Aufruf
    if k == "poesie":
        return _poesie_call(mod, pre_blocks, out_pdf, options,
                            placement_overrides=placement_overrides,
                            tag_config=tag_config)
    if k == "prosa":
        return _prosa_call(mod, pre_blocks, out_pdf, options,
                           placement_overrides=placement_overrides,
                           tag_config=tag_config)

    # (sollte wegen Prüfung oben nie erreicht werden)
    raise ValueError(f"Unbekannter kind='{kind}'. Erwartet: poesie|prosa")

