"""Retro Studios TXTR of the GameCube / Wii Metroid Prime games (Prime 1-3, Trilogy), decompressed.

Header (big endian): u32 format, u16 width, u16 height, u32 mip count; a palette format (C4, C8, C14X2) then has
u32 palette format (0 IA8, 1 RGB565, 2 RGB5A3), u16 palette width, u16 palette height and the palette entries;
then the GX texels of every mip level (``bti``). Retro numbers the formats its own way (``FORMATS``).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, bti

# Retro format id -> GX format id
FORMATS = {0: 0, 1: 1, 2: 2, 3: 3, 4: 8, 5: 9, 6: 10, 7: 4, 8: 5, 9: 6, 10: 14}


def _head(data: bytes) -> Dict[str, int]:
    fmt, width, height, mips = struct.unpack_from(">IHHI", data)
    if fmt not in FORMATS:
        raise ValueError(f"TXTR format {fmt} is not supported")
    head = {"format": FORMATS[fmt], "width": width, "height": height, "mips": max(1, mips), "data": 12,
            "pal_format": 0, "pal_count": 0, "pal_offset": 0}
    if head["format"] in (8, 9, 10):
        pal_format, pal_w, pal_h = struct.unpack_from(">IHH", data, 12)
        head.update(pal_format=pal_format, pal_count=pal_w * pal_h, pal_offset=20, data=20 + 2 * pal_w * pal_h)
    return head


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    head = _head(data)
    return [Texture("", bti.read_image(data, head), bti.FORMATS[head["format"]], head["mips"])]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    if 0 not in images:
        return data
    out = bytearray(data)
    return bytes(out) if bti.write_image(out, _head(data), images[0]) else data
