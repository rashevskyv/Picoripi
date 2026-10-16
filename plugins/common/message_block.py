"""The message file behind a project block: its relative path, its line flags and its line labels (the ``.tbl`` beside it).

Shared by the Game Freak plugins whose lines are named by a ``.tbl`` (``AHTB``): the line's label is its index in that table.
"""
from pathlib import Path
from typing import List, Optional, Tuple

from plugins.common import gfmsg
from utils.logging_utils import log_debug


def locate(mw, block_idx: int, plugin: str) -> Optional[Tuple[str, List[int], List[str]]]:
    """``(relative path, line flags, line labels)`` of a block of the open project; None when it has no message file."""
    try:
        pm = getattr(mw, "project_manager", None)
        block_map = getattr(mw, "block_to_project_file_map", None) or {}
        block = pm.project.blocks[block_map.get(block_idx, block_idx)]
        path = Path(pm.get_absolute_path(block.source_file))
        table = path.with_suffix(".tbl")
        labels = gfmsg.read_labels(table.read_bytes()) if table.is_file() else []
        flags = [flags for _units, flags in gfmsg.read(path.read_bytes())]
        return (str(block.source_file).replace("\\", "/"), flags, labels)
    except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
        log_debug(f"{plugin}: no message file behind block {block_idx}: {error}")
        return None
