"""PSP EBOOT.PBP (PS1 Classic and PSP packages): the ICON0 picture, a PNG, between the 2nd and 3rd offset."""
from __future__ import annotations

import io
import struct
from typing import Optional

from PIL import Image

from core.game_icons.common import FileSource

MAGIC = b"\0PBP"
ICON0_INDEX = 1                 # the offsets start at 0x08; ICON0 is the 2nd, so it spans [0x0C, 0x10)


def read(src: FileSource) -> Optional[Image.Image]:
    if src.size < 0x28 or src.take(0, 4) != MAGIC:
        return None
    start, end = struct.unpack("<II", src.take(8 + 4 * ICON0_INDEX, 8))
    if not (0x28 <= start < end <= src.size):
        return None
    return Image.open(io.BytesIO(src.take(start, end - start)))
