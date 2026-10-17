"""The files the unpack step takes from Skies of Arcadia (Dreamcast, USA MK-51052): the field scripts of one disc.

The disc's files under ``files/`` are written without that prefix, so ``FIELD/ME201A.SCT`` is the path in the project.
The scripts are written as they are on the disc (Dreamcast scripts are not compressed).
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from core.project_library import images

FILES = "files/"
SCRIPT_DIR = "FIELD/"


def is_script(disc_path: str) -> bool:
    """True for a field script of the disc's files folder (``files/FIELD/*.SCT``)."""
    return disc_path.startswith(FILES + SCRIPT_DIR) and disc_path.upper().endswith(".SCT")


def extract(base: str, target_dir: str, progress: Callable[[int, str], None],
            is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write the field scripts of the disc set ``base`` (a cue sheet) under ``target_dir``. None when cancelled."""
    game = Path(target_dir)
    with images.open_image(base) as image:
        entries = [entry for entry in image.entries() if is_script(entry.path)]
        for index, entry in enumerate(entries):
            if is_cancelled():
                return None
            progress(100 * index // max(1, len(entries)), entry.path)
            rel = entry.path[len(FILES):]
            out_path = game.joinpath(*rel.split("/"))
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(image.read(entry))
    progress(100, "")
    return str(target_dir)
