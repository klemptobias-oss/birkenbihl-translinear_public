"""Kompatibilitäts-Wrapper für gr_build_poesie_drafts_adapter.py."""

import os
import sys
import time
import traceback

# Line-buffer stdout for immediacy
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

print("build_poesie_drafts_adapter.py: starting pid=%s argv=%s" % (os.getpid(), sys.argv))
sys.stdout.flush()

from gr_build_poesie_drafts_adapter import main, run_one  # noqa: F401


if __name__ == "__main__":
    try:
        start = time.time()
        print("build_poesie_drafts_adapter.py: launching main()")
        sys.stdout.flush()
        main()
        print("build_poesie_drafts_adapter.py: main() finished (%.1fs)" % (time.time() - start))
        sys.stdout.flush()
    except Exception as e:
        print("build_poesie_drafts_adapter.py: ERROR in main():", str(e))
        traceback.print_exc()
        sys.stdout.flush()
        raise

