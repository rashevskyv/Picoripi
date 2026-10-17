"""The message file behind a project block: its relative path, its line flags and its line labels (the ``.tbl`` beside it).

Shared by the Game Freak plugins whose lines are named by a ``.tbl`` (``AHTB``): the line's label is its index in that table.
The file is read off the UI thread (plugins/common/block_loader.py): ``cached`` answers from the plugin's memory.
"""
from pathlib import Path
from typing import Any, List, Optional, Tuple

from plugins.common import gfmsg
from plugins.common.block_loader import ReadThrough, source_of

Located = Tuple[str, List[int], List[str]]


def load(rel: str, path: Path) -> Located:
    """``(relative path, line flags, line labels)`` of one message file. Reads the disk: call it from a worker."""
    table = path.with_suffix(".tbl")
    labels = gfmsg.read_labels(table.read_bytes()) if table.is_file() else []
    flags = [flags for _units, flags in gfmsg.read(path.read_bytes())]
    return (rel, flags, labels)


def cached(reads: ReadThrough, mw: Any, block_idx: int) -> Optional[Located]:
    """The block's message file from ``reads``; None while it is read (or when the block has no message file)."""
    source = source_of(mw, block_idx)
    if source is None:
        return None
    rel, path = source
    return reads.get(block_idx, lambda: load(rel, path))
