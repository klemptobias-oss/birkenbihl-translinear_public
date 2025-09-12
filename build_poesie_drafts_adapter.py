#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from pathlib import Path
import json
import traceback

# Module aus deinem Repo
import Poesie_Code as Poesie
from shared.unified_api import create_pdf_unified, PdfRenderOptions
from shared.naming import base_from_input_path, output_pdf_name, PdfRenderOptions as NameOpts

ROOT = Path(__file__).parent.resolve()

DRAFTS_ROOT = ROOT / "texte_drafts" / "poesie_drafts"
OUT_ROOT    = ROOT / "pdf_drafts"   / "draft_poesie_pdf"

# ---------- Hilfen ----------

def _load_payload_for(draft: Path) -> dict | None:
    """
    Lade optional eine Payload:
      1) <stem>.json neben der .txt
      2) payload.json im selben Ordner
    """
    cand1 = draft.with_suffix(".json")
    cand2 = draft.parent / "payload.json"
    for c in (cand1, cand2):
        if c.exists() and c.is_file():
            try:
                return json.loads(c.read_text(encoding="utf-8"))
            except Exception:
                print(f"⚠ Payload ungültig (ignoriert): {c}")
    return None

def _ensure_outdir_for(draft: Path) -> Path:
    """Zielordner: pdf_drafts/draft_poesie_pdf/<Autor>/"""
    author = draft.parent.name  # Autor-Ordner
    outdir = OUT_ROOT / author
    outdir.mkdir(parents=True, exist_ok=True)
    return outdir

def _versmass_suffix(versmass_mode: str) -> str:
    return "_Versmaß" if versmass_mode == "KEEP_MARKERS" else ""

def _opts_from_payload(payload: dict | None) -> PdfRenderOptions:
    """
    Übersetze UI-Payload in PdfRenderOptions.
    (apply_from_payload in unified_api kümmert sich später um die inhaltliche Normalisierung.)
    """
    if not payload:
        return PdfRenderOptions(
            strength="NORMAL",
            color_mode="COLOR",
            tag_mode="TAGS",
            versmass_mode="NORMAL",
        )
    strength = payload.get("strength", "NORMAL")
    show_colors = bool(payload.get("show_colors", True))
    show_tags   = bool(payload.get("show_tags",   True))
    color_mode  = "COLOR" if show_colors else "BLACK_WHITE"
    tag_mode    = "TAGS"  if show_tags   else "NO_TAGS"
    versmass    = payload.get("versmass", "NORMAL")
    return PdfRenderOptions(
        strength=strength,
        color_mode=color_mode,
        tag_mode=tag_mode,
        versmass_mode=versmass,
    )

def _discover_latest_txts_per_author() -> list[Path]:
    """
    Durchläuft autoren-Ordner unter DRAFTS_ROOT und wählt je Autor die
    zuletzt geänderte .txt-Datei (mtime) aus.
    """
    latest: list[Path] = []
    if not DRAFTS_ROOT.exists():
        return latest

    for author_dir in sorted([p for p in DRAFTS_ROOT.iterdir() if p.is_dir()]):
        txts = sorted(author_dir.glob("*.txt"))
        if not txts:
            continue
        newest = max(txts, key=lambda p: p.stat().st_mtime)
        latest.append(newest)
    return latest

# ---------- Hauptlogik ----------

def _process_one(draft_txt: Path) -> None:
    try:
        if not draft_txt.exists():
            print(f"⚠ fehlt: {draft_txt}")
            return

        payload = _load_payload_for(draft_txt)
        opts    = _opts_from_payload(payload)

        # 1) Parsen
        blocks = Poesie.process_input_file(str(draft_txt))

        # 2) Name bauen (Standard-Namensschema) + Versmaß-Suffix
        base = base_from_input_path(draft_txt)  # nutzt auch Autor/Filename
        name_no_meter = output_pdf_name(
            base,
            NameOpts(
                strength=opts.strength,
                color_mode=opts.color_mode,
                tag_mode=opts.tag_mode,
            ),
        )
        out_name = Path(name_no_meter).with_suffix(".pdf").stem + _versmass_suffix(opts.versmass_mode) + ".pdf"

        # 3) Zielordner
        outdir = _ensure_outdir_for(draft_txt)
        out_pdf = outdir / out_name

        # 4) Rendern über unified_api (mit Payload → placement_overrides fließen mit ein)
        create_pdf_unified(
            "poesie",
            Poesie,
            blocks,
            str(out_pdf),
            options=opts,
            payload=payload,   # darf None sein
        )
        print(f"✓ Draft → {out_pdf}")
    except Exception as e:
        print(f"✗ Fehler bei {draft_txt.name}: {e}")
        traceback.print_exc()

def main():
    drafts = _discover_latest_txts_per_author()
    if not drafts:
        print("✗ Keine Poesie-Drafts gefunden (je Autor keine .txt).")
        return
    for p in drafts:
        print(f"→ Verarbeite jüngsten Entwurf für Autor '{p.parent.name}': {p.name}")
        _process_one(p)

if __name__ == "__main__":
    main()

