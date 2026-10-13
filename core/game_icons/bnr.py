"""GameCube disc banner ``opening.bnr`` (BNR1 or BNR2): the 96x32 RGB5A3 picture at 0x20."""
from __future__ import annotations

from typing import Optional

from PIL import Image

from core.texture_formats import pixels

MAGICS = (b"BNR1", b"BNR2")
SIZE = 0x1960                   # the whole banner file; the picture is 0x1800 bytes at 0x20
IMAGE_AT, WIDTH, HEIGHT = 0x20, 96, 32


def read(data: bytes) -> Optional[Image.Image]:
    if data[:4] not in MAGICS or len(data) < IMAGE_AT + WIDTH * HEIGHT * 2:
        return None
    raw = data[IMAGE_AT:IMAGE_AT + WIDTH * HEIGHT * 2]
    return pixels.codec("gx:RGB5A3").decode(raw, WIDTH, HEIGHT)
