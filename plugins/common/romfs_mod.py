"""Loose-file mods of a Switch game: the changed files of a project, written at their romfs paths for each title id.

The mod folder is ``atmosphere\\contents\\<title id>\\romfs\\<romfs path>`` (Atmosphere LayeredFS). The source folder of a
project is the romfs tree: a file's path in ``source`` is its romfs path.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterable

SKIP_SUFFIXES = (".tmp", ".bak")
SKIP_NAMES = ("desktop.ini", "thumbs.db")


def changed_files(source_dir: str | os.PathLike, translation_dir: str | os.PathLike) -> Dict[str, bytes]:
    """{romfs path: bytes} of each translation file that is new or differs from the same path in the source."""
    source, translation = Path(source_dir), Path(translation_dir)
    changes: Dict[str, bytes] = {}
    if not translation.is_dir():
        return changes
    for path in sorted(translation.rglob("*")):
        if not path.is_file() or path.name.lower() in SKIP_NAMES or path.name.endswith(SKIP_SUFFIXES):
            continue
        rel = path.relative_to(translation).as_posix()
        data = path.read_bytes()
        original = source / rel
        if not original.is_file() or original.read_bytes() != data:
            changes[rel] = data
    return changes


def write_title(out_root: str | os.PathLike, title: str, files: Dict[str, bytes]) -> None:
    """Write ``files`` (romfs path -> bytes) under ``out_root/contents/<title>/romfs``; each file goes through a temp file."""
    romfs = Path(out_root) / "contents" / title / "romfs"
    for rel, data in files.items():
        target = romfs.joinpath(*rel.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_bytes(data)
        os.replace(temporary, target)


def write_titles(out_root: str | os.PathLike, titles: Iterable[str], files: Dict[str, bytes]) -> None:
    """``write_title`` for each title id: one romfs of the same files for every game that shares it."""
    for title in titles:
        write_title(out_root, title, files)
