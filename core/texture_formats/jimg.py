"""Arc System Works ``jIMG`` textures (3DS: Dragon Ball Fusions ``.jtex``, and the atlas inside a ``.jfnt`` font).

A 0x80-byte little-endian header (``jIMG``, u32 file size, u16 width, u16 height, u8 pixel format, 03 04 11, ...)
and one PICA texture level of 8x8 Morton tiles, top row first, from 0x80 to the end. Pixel formats: 0 RGBA8,
1 RGB8, 5 RGBA4, 8 ETC1, 0x0B ETC1A4, 0x10 A8 (the font atlases), 0x12 L8 (a shadow gradient).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

PICA = {0: "RGBA8", 1: "RGB8", 5: "RGBA4", 8: "ETC1", 0x0B: "ETC1A4", 0x10: "A8", 0x12: "L8"}
DATA_AT = 0x80


def detect(data: bytes) -> bool:
    return data[:4] == b"jIMG" and len(data) > DATA_AT


def info(data: bytes, base: int = 0) -> Dict[str, Any]:
    """Format, size and codec of the jIMG at ``base`` of ``data``."""
    if data[base:base + 4] != b"jIMG":
        raise ValueError("Not a jIMG texture")
    total, width, height = struct.unpack_from("<IHH", data, base + 4)
    fmt = data[base + 12]
    if fmt not in PICA:
        raise ValueError(f"jIMG pixel format {fmt:#x} is not supported")
    codec = pixels.codec("pica:" + PICA[fmt])
    if base + DATA_AT + surface.surface_bytes(codec, width, height) > len(data):
        raise ValueError("jIMG data is cut short")
    return {"codec": codec, "format": PICA[fmt], "width": width, "height": height, "at": base + DATA_AT, "total": total}


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    t = info(data)
    return [Texture("", surface.read(data, t["at"], t["codec"], t["width"], t["height"]), t["format"], 1)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    t = info(data)
    image = images.get(0)
    if image is not None:
        surface.write(out, t["at"], t["codec"], t["width"], t["height"], image)
    return bytes(out)
