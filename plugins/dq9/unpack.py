"""The files the unpack step takes from Dragon Quest IX (DS, Europe): the same set as zt/isdq.py ``dq_wanted``.

The English text, the fonts and the pictures: every GPC2 archive (``*.gp2``) that has an English member (a name
ending ``_en.bin``, ``_en.nat``, ``_en.pac`` or ``_en.spr``), the loose files in ``LOOSE`` and every picture
``data/ani/*.pac`` or ``data/menu/*.pac``. Each file keeps its NitroFS path.
"""
import re
from typing import Callable, Optional

from core.containers.image_files import ImageFile
from core.project_library import images

from .gpc2 import open_gpc2

LOOSE = ("data/evspt_lv5/staffroll.bin", "data/bin/keyboard_cm.bin", "data/bin/keyboard_cs.bin",
         "data/bin/keyboard_pr.bin", "data/prm/actname.nat", "data/bin/res.nat",
         "data/pack_lv5/fi_me.bin", "data/pack_lv5/fd_me.bin", "data/pack_lv5/fi_s7.bin", "data/pack_lv5/fd_s7.bin")
PICTURE = re.compile(r"data/(ani|menu)/[^/]+\.pac")
ENGLISH = re.compile(r"_en\.(bin|nat|pac|spr)$")


def _wanted(entry: ImageFile, read: Callable[[ImageFile], bytes]) -> bool:
    if entry.path in LOOSE or PICTURE.fullmatch(entry.path):
        return True
    if not entry.path.endswith(".gp2"):
        return False
    archive = open_gpc2(read(entry))
    return archive is not None and any(ENGLISH.search(name) for name in archive.names)


def extract(base: str, target_dir: str, progress: Callable[[int, str], None],
            is_cancelled: Callable[[], bool]) -> Optional[str]:
    with images.open_image(base) as image:
        chosen = [entry for entry in image.entries() if _wanted(entry, image.read)]
        if not images.write_entries(image, chosen, target_dir, progress, is_cancelled):
            return None
    return str(target_dir)
