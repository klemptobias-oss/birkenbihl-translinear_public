"""Shared utilities for Birkenbihl translinear system.

This package contains common functions used across the rendering pipeline.
"""
from __future__ import annotations

import shutil
from pathlib import Path


def clean_drafts(root_dir: Path | None = None) -> None:
    """Remove all generated draft artifacts while keeping folder structure.
    
    Keeps the top-level directories (texte_drafts/, pdf_drafts/) with a .gitkeep
    so git still tracks the empty structure, but deletes every nested file/folder.
    
    Args:
        root_dir: Repository root directory. If None, uses parent of shared/ folder.
        
    Example:
        >>> from shared import clean_drafts
        >>> clean_drafts()  # Cleans texte_drafts/ and pdf_drafts/
    """
    if root_dir is None:
        root_dir = Path(__file__).resolve().parent.parent
    
    targets = [root_dir / "texte_drafts", root_dir / "pdf_drafts"]
    
    for directory in targets:
        _clean_directory(directory)
        print(f"Bereinigt: {directory.relative_to(root_dir)}")


def _ensure_gitkeep(directory: Path) -> None:
    """Ensure a .gitkeep file exists in the directory."""
    directory.mkdir(parents=True, exist_ok=True)
    gitkeep = directory / ".gitkeep"
    gitkeep.touch()


def _clean_directory(directory: Path) -> None:
    """Clean all contents of a directory except .gitkeep."""
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
        _ensure_gitkeep(directory)
        return

    for entry in directory.iterdir():
        if entry.name == ".gitkeep":
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    _ensure_gitkeep(directory)


# Expose clean_drafts at package level
__all__ = ["clean_drafts"]
