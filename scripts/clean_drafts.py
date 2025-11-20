#!/usr/bin/env python3
"""Utility to remove all generated draft artifacts.

It keeps the top-level directories (texte_drafts/, pdf_drafts/) with a .gitkeep
so git still tracks the empty structure, but deletes every nested file/folder.
Run from the repository root:

    python scripts/clean_drafts.py
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = [ROOT / "texte_drafts", ROOT / "pdf_drafts"]


def ensure_gitkeep(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    gitkeep = directory / ".gitkeep"
    gitkeep.touch()


def clean_directory(directory: Path) -> None:
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
        ensure_gitkeep(directory)
        return

    for entry in directory.iterdir():
        if entry.name == ".gitkeep":
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    ensure_gitkeep(directory)


def main() -> None:
    for target in TARGETS:
        clean_directory(target)
        print(f"Bereinigt: {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
