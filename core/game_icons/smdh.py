"""Nintendo 3DS SMDH (the ``icon`` file of ExeFS): the 48x48 large icon in RGB565, 8x8 tiles in Morton order."""
from __future__ import annotations

from typing import Optional

from PIL import Image

from core.game_icons.common import FileSource
from core.texture_formats import pixels

MAGIC = b"SMDH"
LARGE_AT, LARGE_SIDE = 0x24C0, 48


def read(src: FileSource) -> Optional[Image.Image]:
    if src.take(0, 4) != MAGIC:
        return None
    raw = src.take(LARGE_AT, LARGE_SIDE * LARGE_SIDE * 2)
    return pixels.codec("pica:RGB565").decode(raw, LARGE_SIDE, LARGE_SIDE)
