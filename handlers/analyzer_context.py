"""Scoped block and string index for a problem analyzer call."""
# handlers/analyzer_context.py
from contextlib import contextmanager
from typing import Any, Iterator

BLOCK_ATTR = "_current_scan_block_idx"
STRING_ATTR = "_current_scan_string_idx"


@contextmanager
def analyzer_string_context(analyzer: Any, block_idx: int, string_idx: int) -> Iterator[None]:
    """Tell the analyzer which string it checks; restore the previous indexes on exit.

    Plugins read these two attributes when they need string context. Every host caller that
    analyses a string must set them, or the plugin sees the last scanned string instead.
    On a GenericProblemAnalyzer the attributes are per thread: this call sets and restores
    only the current thread's values.
    """
    previous = (getattr(analyzer, BLOCK_ATTR, None), getattr(analyzer, STRING_ATTR, None))
    setattr(analyzer, BLOCK_ATTR, block_idx)
    setattr(analyzer, STRING_ATTR, string_idx)
    try:
        yield
    finally:
        setattr(analyzer, BLOCK_ATTR, previous[0])
        setattr(analyzer, STRING_ATTR, previous[1])
