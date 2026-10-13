"""The files the unpack step takes from Four Swords Anniversary Edition (DS, Europe): the same set as zt/nds.py.

``main.arm9`` is the ARM9 program from the cartridge header, which the image reader lists under that name.
"""
from typing import Callable, Optional

from core.project_library import images

SOURCE_FILES = ("eu.kmsg", "font_ltn.nftr", "manpages_narc_eu.blz", "subtask_eu_en.cmp", "zeldat_eu_en.bin",
                "zeldat.bin", "subtask.cmp", "main.arm9")


def wanted(path: str) -> bool:
    return path in SOURCE_FILES


def extract(base: str, target_dir: str, progress: Callable[[int, str], None],
            is_cancelled: Callable[[], bool]) -> Optional[str]:
    return images.extract(base, target_dir, progress, is_cancelled, select=wanted)
