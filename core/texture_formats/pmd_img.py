"""Spike Chunsoft 3DS ``.img`` textures (Pokémon Mystery Dungeon: Gates to Infinity, Super Mystery Dungeon).

Header (128 bytes, little endian): ``\\0cte``, u32 format id, u32 width, u32 height, u32 bits per pixel, u32 0,
u32 data offset (0x80), zeros. The surface is one PICA-tiled image stored bottom row first (the picture is flipped
on read and again on write). Format ids: 2 RGB8, 3 RGBA8, 4 ETC1, 5 ETC1A4, 6 and 9 RGBA4, 8 one 8-bit channel
(the font atlases: alpha). Ids 1 and 7 are the same pixels laid out linearly (``*_win.img`` files of the Windows
build the 3DS never loads) and are not read.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

MAGIC = b"\0cte"
FORMATS = {2: "RGB8", 3: "RGBA8", 4: "ETC1", 5: "ETC1A4", 6: "RGBA4", 8: "A8", 9: "RGBA4"}


def detect(data: bytes) -> bool:
    return len(data) >= 0x80 and data[:4] == MAGIC


def _info(data: bytes) -> Dict[str, Any]:
    if not detect(data):
        raise ValueError("Not a Mystery Dungeon .img texture")
    fmt, width, height, _bpp, _zero, offset = struct.unpack_from("<6I", data, 4)
    if fmt not in FORMATS:
        raise ValueError(f"Mystery Dungeon .img format {fmt} is not supported")
    name = FORMATS[fmt]
    return {"width": width, "height": height, "offset": offset, "format": name, "codec": pixels.codec("pica:" + name)}


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    info = _info(data)
    image = surface.read(data, info["offset"], info["codec"], info["width"], info["height"])
    return [Texture("", image.transpose(Image.FLIP_TOP_BOTTOM), info["format"])]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    image = images.get(0)
    if image is None:
        return data
    info = _info(data)
    out = bytearray(data)
    flipped = image.convert("RGBA").transpose(Image.FLIP_TOP_BOTTOM)
    surface.write(out, info["offset"], info["codec"], info["width"], info["height"], flipped)
    return bytes(out)
