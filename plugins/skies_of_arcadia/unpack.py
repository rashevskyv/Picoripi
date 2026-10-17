"""The files the unpack step takes from Skies of Arcadia Legends (GameCube, USA GEAE8P).

Everything under ``files/`` of the disc is written without that prefix, so ``source\game\`` is the disc's file tree.
The text scripts ``field/*.sct`` (AKLZ) are written decompressed, so the editor reads their bytecode and text pages;
``core.containers.aklz`` compresses them again on build. Every other file is written as it is.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from core.containers import aklz
from core.project_library import images

FILES = "files/"
SCRIPT_DIR = "field/"


def extract(base: str, target_dir: str, progress: Callable[[int, str], None],
            is_cancelled: Callable[[], bool]) -> Optional[str]:
    game = Path(target_dir)
    with images.open_image(base) as image:
        entries = [entry for entry in image.entries() if entry.path.startswith(FILES)]
        for index, entry in enumerate(entries):
            if is_cancelled():
                return None
            progress(100 * index // max(1, len(entries)), entry.path)
            rel = entry.path[len(FILES):]
            data = image.read(entry)
            if rel.startswith(SCRIPT_DIR) and rel.endswith(".sct") and data[:4] == aklz.MAGIC:
                data = aklz.decode(data)
            out_path = game.joinpath(*rel.split("/"))
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(data)
    progress(100, "")
    return str(target_dir)
