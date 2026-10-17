"""The kinds of files a project's source folder holds: texts, fonts, textures and other files.

Only file names and sizes are read, never the content. The kind comes from the extension (the table below), unless
the game's ``classify_resource`` hook names the kind first. The hook is optional and runs on the caller's worker thread.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Dict, Optional

TEXT, FONT, TEXTURE, OTHER = "text", "font", "texture", "other"
KINDS = (TEXT, FONT, TEXTURE, OTHER)

_BY_EXTENSION = {
    **dict.fromkeys((".txt", ".json", ".bmg", ".msg", ".xml", ".csv", ".po", ".inc", ".asm", ".s"), TEXT),
    **dict.fromkeys((".bfn", ".cfnt", ".nftr", ".fnt", ".ttf", ".otf", ".bffnt", ".bcfnt", ".bfon"), FONT),
    **dict.fromkeys((".png", ".tga", ".bmp", ".dds", ".bti", ".tpl", ".bclim", ".gtx", ".ncgr", ".nclr", ".ncer",
                     ".ntft", ".ntfp", ".g1t", ".xt1"), TEXTURE),
}


def kind_of(name: str) -> str:
    """The resource kind of a file, from its name. Unknown extensions are OTHER."""
    return _BY_EXTENSION.get(os.path.splitext(name)[1].lower(), OTHER)


def count_resources(source: str | os.PathLike,
                    is_cancelled: Callable[[], bool] = lambda: False,
                    classify: Optional[Callable[[str], Optional[str]]] = None) -> Optional[Dict[str, Dict[str, int]]]:
    """``{kind: {"files": n, "bytes": n}}`` of every file under ``source`` (or of ``source`` when it is a file).

    ``classify(path)`` is asked first for each file's kind; a None, or a kind that is not in ``KINDS``, falls back to
    the extension rule. A missing source counts as empty. Symbolic links are not followed. Returns None when
    ``is_cancelled`` is true during the walk. Runs on a worker thread: it touches the disk.
    """
    totals = {kind: {"files": 0, "bytes": 0} for kind in KINDS}
    root = Path(source)
    if root.is_file():
        _add(totals, str(root), root.stat().st_size, classify)
        return totals
    stack = [os.fspath(root)] if root.is_dir() else []
    while stack:
        if is_cancelled():
            return None
        folder = stack.pop()
        try:
            entries = list(os.scandir(folder))
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
                elif entry.is_file(follow_symlinks=False):
                    _add(totals, entry.path, entry.stat(follow_symlinks=False).st_size, classify)
            except OSError:
                continue  # a file that vanished during the walk is not counted
    return totals


def kind_for(path: str, classify: Optional[Callable[[str], Optional[str]]] = None) -> str:
    """The kind of one file: the plugin's answer when it gives a known kind, else the extension rule."""
    if classify is not None:
        kind = classify(path)
        if kind in KINDS:
            return kind
    return kind_of(os.path.basename(path))


def _add(totals: Dict[str, Dict[str, int]], path: str, size: int,
         classify: Optional[Callable[[str], Optional[str]]] = None) -> None:
    bucket = totals[kind_for(path, classify)]
    bucket["files"] += 1
    bucket["bytes"] += size
