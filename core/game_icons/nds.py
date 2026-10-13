"""Nintendo DS ROM banner: the 32x32 4bpp icon (8x8 tiles, 4x4 layout) and its 16-colour BGR555 palette."""
from __future__ import annotations

import struct
from typing import Optional

from PIL import Image

from core.game_icons.common import FileSource
from core.texture_formats import pixels

BANNER_AT_FIELD = 0x68          # u32 in the ROM header: file offset of the banner
BANNER_SIZE = 0x240             # version, CRC, reserved, bitmap, palette, titles (only the icon is read)
BANNER_VERSIONS = (1, 2, 3, 0x103)
BITMAP_AT, PALETTE_AT, SIDE = 0x20, 0x220, 32


def _colour(value: int, index: int) -> tuple:
    if index == 0:
        return (0, 0, 0, 0)     # palette entry 0 is transparent
    r, g, b = value & 31, (value >> 5) & 31, (value >> 10) & 31
    return (r * 255 // 31, g * 255 // 31, b * 255 // 31, 255)


def read(src: FileSource) -> Optional[Image.Image]:
    if src.size < BANNER_AT_FIELD + 4:
        return None
    (banner_at,) = struct.unpack("<I", src.take(BANNER_AT_FIELD, 4))
    if banner_at == 0 or banner_at + BANNER_SIZE > src.size:
        return None
    banner = src.take(banner_at, BANNER_SIZE)
    (version,) = struct.unpack_from("<H", banner, 0)
    if version not in BANNER_VERSIONS:
        return None
    palette = [_colour(struct.unpack_from("<H", banner, PALETTE_AT + 2 * i)[0], i) for i in range(16)]
    codec = pixels.palette_codec("nds:4bpp-banner", 4, palette, tile=(8, 8), endian="<", low_first=True)
    return codec.decode(banner[BITMAP_AT:BITMAP_AT + 512], SIDE, SIDE)
