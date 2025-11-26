import logging
import os
from collections import defaultdict


class MessageThrottleFilter(logging.Filter):
    """
    Logging filter that throttles very frequent messages.
    - It will permit the first N occurrences of a message family (e.g. table width)
      and suppress subsequent ones.
    - Configurable via env LOG_MSG_LIMIT (default 200).
    """
    def __init__(self, limit=None):
        super().__init__()
        try:
            self.limit = int(limit if limit is not None else os.environ.get("LOG_MSG_LIMIT", "200"))
        except Exception:
            self.limit = 200
        self.counts = defaultdict(int)

    def filter(self, record):
        msg = record.getMessage() if record and record.getMessage else ""
        # Two families we throttle:
        #  - Table width warnings (German "Table-Breite zu groß")
        #  - Token-level "Tag entfernt..." debug lines (common spam)
        if "Table-Breite zu groß" in msg:
            key = "table_width"
            self.counts[key] += 1
            return self.counts[key] <= self.limit
        if "_process_pair_block_for_tags: Tag entfernt aus Token" in msg:
            key = "tag_removed_verbose"
            self.counts[key] += 1
            # allow a small number of concrete examples, then suppress
            return self.counts[key] <= max(50, self.limit // 4)
        # allow everything else
        return True


def setup_logging_throttle(root_logger=None, limit=None):
    """
    Attach throttle filter to root logger (or provided logger).
    Use env LOG_LEVEL to set minimum level if provided.
    """
    if root_logger is None:
        root_logger = logging.getLogger()
    # attach filter (only one)
    flt = MessageThrottleFilter(limit=limit)
    root_logger.addFilter(flt)
    # set level from env if present
    import os as _os
    level = _os.environ.get("LOG_LEVEL", None)
    if level:
        try:
            lvl = getattr(logging, level.upper())
            root_logger.setLevel(lvl)
        except Exception:
            pass
    return flt

