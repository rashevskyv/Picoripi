"""The files the unpack step takes from Infinite Space (DS, Europe): the same set as zt/isdq.py ``is_wanted``."""
import re
from typing import Callable, Optional

from core.project_library import images

TEXT = "data/Event/SpaceShip.scx"
TEXTURES = re.compile(r"data/Cg/Texture/(D\d+|1106|0400|0401|0348)\.tex$")


def wanted(path: str) -> bool:
    return (path == TEXT or path.startswith(("data/Cg/Bgd/", "data/Cg/Obd/"))
            or TEXTURES.fullmatch(path) is not None)


def extract(base: str, target_dir: str, progress: Callable[[int, str], None],
            is_cancelled: Callable[[], bool]) -> Optional[str]:
    return images.extract(base, target_dir, progress, is_cancelled, select=wanted)
