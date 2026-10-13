"""The files the unpack step takes from Final Fantasy XII: Revenant Wings (DS, Europe).

The same set as zt/ffds.py ``rw_wanted``: the English text (the ``E`` folders), the fonts, the title screen.
"""
from typing import Callable, Optional

from core.project_library import images

RW_EXTRA = ("data/FontPack.dpk", "data/Shellscreen/title/bg_pack.narc", "data/Shellscreen/title/party_pack.narc",
            "data/Shellscreen/title/title_obj_choice.narc")
RW_SKIP = (".sdat", ".vx", ".sadl", ".bse")


def wanted(path: str) -> bool:
    return ("/E/" in path and not path.lower().endswith(RW_SKIP)) or path in RW_EXTRA


def extract(base: str, target_dir: str, progress: Callable[[int, str], None],
            is_cancelled: Callable[[], bool]) -> Optional[str]:
    return images.extract(base, target_dir, progress, is_cancelled, select=wanted)
