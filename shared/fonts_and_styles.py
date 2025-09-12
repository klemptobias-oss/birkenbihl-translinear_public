#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shared/fonts_and_styles.py
--------------------------
Minimaler, wiederverwendbarer Font-/Style-Baustein für alle vier Renderer.

Ziele:
- Einmalige Registrierung der DejaVu-Schrift (Regular + Bold), robust gegen Mehrfachaufrufe.
- Keine "Layout-Entscheidungen": Wir liefern nur generische ParagraphStyles.
- Bewusst geringe Vorgaben; alle Details (Abstände, Ausrichtung etc.) bleiben den Renderern überlassen.

Öffentliche API:
- register_dejavu(font_dir: str | Path | None = None) -> dict[str, str]
- make_paragraph_style(name, *, font_name, font_size, leading=None, **kwargs) -> ParagraphStyle
- make_gr_de_styles(gr_size: float, de_size: float, *, bold_gr=False, family=None, base=None, **kwargs)
    -> tuple[ParagraphStyle, ParagraphStyle]   # (gr_style, de_style)

Konventionen:
- Font-Familie im ReportLab-Register: "DejaVu" (Regular) und "DejaVu-Bold" (Bold).
- Standard-Suchpfad:  ../shared/fonts/ relativ zu dieser Datei.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

# ========================== Modulzustand / Defaults ==========================

DEFAULT_FAMILY = {
    "regular": "DejaVu",
    "bold": "DejaVu-Bold",
}

DEFAULT_FILES = {
    "regular": "DejaVuSans.ttf",
    "bold": "DejaVuSans-Bold.ttf",
}

_already_registered: bool = False


# =============================== Helper =====================================

def _resolve_font_dir(font_dir: Optional[Path]) -> Path:
    if font_dir is not None:
        return Path(font_dir).expanduser().resolve()
    here = Path(__file__).resolve().parent
    return (here / "fonts").resolve()

def _font_files_exist(font_dir: Path) -> Tuple[Path, Path]:
    reg = font_dir / DEFAULT_FILES["regular"]
    bld = font_dir / DEFAULT_FILES["bold"]
    missing = [p.name for p in (reg, bld) if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "DejaVu-Schriftdateien nicht gefunden. Erwartet im Ordner:\n"
            f"  {font_dir}\n"
            f"- {DEFAULT_FILES['regular']}\n"
            f"- {DEFAULT_FILES['bold']}\n"
            "Lege die Dateien dorthin (oder gib font_dir explizit beim Aufruf an)."
        )
    return reg, bld

def _is_registered(font_name: str) -> bool:
    try:
        pdfmetrics.getFont(font_name)
        return True
    except Exception:
        return False


# =============================== Public API =================================

def register_dejavu(font_dir: Optional[str | Path] = None) -> Dict[str, str]:
    """
    Registriert DejaVu Regular/Bold bei ReportLab **einmalig**.
    Rückgabe: {"regular": "DejaVu", "bold": "DejaVu-Bold"}
    """
    global _already_registered
    family = DEFAULT_FAMILY.copy()

    if _already_registered and all(_is_registered(n) for n in family.values()):
        return family

    if all(_is_registered(n) for n in family.values()):
        _already_registered = True
        return family

    fdir = _resolve_font_dir(Path(font_dir) if font_dir is not None else None)
    reg_ttf, bld_ttf = _font_files_exist(fdir)

    pdfmetrics.registerFont(TTFont(family["regular"], str(reg_ttf)))
    pdfmetrics.registerFont(TTFont(family["bold"],    str(bld_ttf)))

    try:
        from reportlab.pdfbase.pdfmetrics import registerFontFamily
        registerFontFamily(
            familyName=family["regular"],
            normal=family["regular"],
            bold=family["bold"],
            italic=family["regular"],
            boldItalic=family["bold"],
        )
    except Exception:
        pass

    _already_registered = True
    return family


def make_paragraph_style(
    name: str,
    *,
    font_name: str,
    font_size: float,
    leading: Optional[float] = None,
    **kwargs: Any,
) -> ParagraphStyle:
    """
    Schlanker ParagraphStyle-Builder ohne Layout-Dogmen.
    leading default: 1.2 * font_size
    """
    base = getSampleStyleSheet()["Normal"]
    st = ParagraphStyle(
        name=name,
        parent=base,
        fontName=font_name,
        fontSize=float(font_size),
        leading=(1.2 * float(font_size)) if leading is None else float(leading),
        **kwargs,
    )
    return st


def make_gr_de_styles(
    gr_size: float,
    de_size: float,
    *,
    bold_gr: bool = False,
    family: Optional[Dict[str, str]] = None,
    base: Optional[ParagraphStyle] = None,
    **kwargs: Any,
) -> tuple[ParagraphStyle, ParagraphStyle]:
    """
    Erzeugt **nur zwei** ParagraphStyles für GR/DE mit gewünschten Größen.
    - bold_gr: True → GR fett; False → GR normal.
    - family: {"regular": "...", "bold": "..."}; None → register_dejavu().
    - base: optionaler Parent-Stil.
    - kwargs: z. B. alignment, spaceBefore/After etc. (für beide identisch).
    """
    fam = family or register_dejavu()
    gr_font = fam["bold"] if bold_gr else fam["regular"]
    de_font = fam["regular"]

    if base is not None:
        base_kwargs = dict(
            leftIndent=base.leftIndent,
            rightIndent=base.rightIndent,
            firstLineIndent=base.firstLineIndent,
            alignment=base.alignment,
            spaceBefore=base.spaceBefore,
            spaceAfter=base.spaceAfter,
        )
        base_kwargs.update(kwargs)
        gr = ParagraphStyle(
            name="GR",
            parent=base,
            fontName=gr_font,
            fontSize=float(gr_size),
            leading=1.2 * float(gr_size),
            **base_kwargs,
        )
        de = ParagraphStyle(
            name="DE",
            parent=base,
            fontName=de_font,
            fontSize=float(de_size),
            leading=1.2 * float(de_size),
            **base_kwargs,
        )
        return gr, de

    gr = make_paragraph_style("GR", font_name=gr_font, font_size=float(gr_size), **kwargs)
    de = make_paragraph_style("DE", font_name=de_font, font_size=float(de_size), **kwargs)
    return gr, de

