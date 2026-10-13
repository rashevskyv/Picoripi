"""The files the unpack step takes from The World Ends with You (DS, Europe): the same set as zt/twewy.py.

The text is written as ``Apl_Fuk/mestxt.mes``, so Picoripi opens it by that extension; the index file is not kept.
"""
import os
from pathlib import Path
from typing import Callable, Optional

from core.containers.nds import ARM9_NAME
from core.project_library import images

TEXT = "Apl_Fuk/mestxt.bin"
TEXT_FILE = "Apl_Fuk/mestxt.mes"
INDEX = "Apl_Fuk/mestable.bin"
SKIP = (".adx", ".sdat")          # sound: nothing to translate


def wanted(path: str) -> bool:
    return not path.lower().endswith(SKIP) and path not in (INDEX, ARM9_NAME)


def extract(base: str, target_dir: str, progress: Callable[[int, str], None],
            is_cancelled: Callable[[], bool]) -> Optional[str]:
    folder = images.extract(base, target_dir, progress, is_cancelled, select=wanted)
    if folder is not None:
        os.replace(Path(folder, *TEXT.split("/")), Path(folder, *TEXT_FILE.split("/")))
    return folder
