"""Kompatibilitäts-Wrapper für die neue gr_build_prosa_drafts_adapter.py.

GitHub Actions und externe Skripte erwarten weiterhin build_prosa_drafts_adapter.py.
Wir delegieren einfach an das neue Modul, damit bestehende Workflows weiterlaufen.
"""

import os
import sys
import time
import traceback

# Try to make stdout line-buffered so CI sees prints immediately
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    # older Python or non-tty; ignore
    pass

print("build_prosa_drafts_adapter.py: starting pid=%s argv=%s" % (os.getpid(), sys.argv))
sys.stdout.flush()

from gr_build_prosa_drafts_adapter import main, run_one  # noqa: F401


if __name__ == "__main__":
    try:
        start = time.time()
        print("build_prosa_drafts_adapter.py: launching main()")
        sys.stdout.flush()
        main()
        print("build_prosa_drafts_adapter.py: main() finished (%.1fs)" % (time.time() - start))
        sys.stdout.flush()
    except Exception as e:
        print("build_prosa_drafts_adapter.py: ERROR in main():", str(e))
        traceback.print_exc()
        sys.stdout.flush()
        # re-raise to ensure CI step fails (so we can see logs)
        raise

