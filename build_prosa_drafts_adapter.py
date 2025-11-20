"""Kompatibilitäts-Wrapper für die neue gr_build_prosa_drafts_adapter.py.

GitHub Actions und externe Skripte erwarten weiterhin build_prosa_drafts_adapter.py.
Wir delegieren einfach an das neue Modul, damit bestehende Workflows weiterlaufen.
"""

from gr_build_prosa_drafts_adapter import main, run_one  # noqa: F401


if __name__ == "__main__":
    main()

