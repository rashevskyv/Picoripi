"""Ganbarion and Arc System Works ``jIMG`` pictures (3DS): ``.jtex`` files and the atlas inside a ``.jfnt`` font.

A 0x80-byte little-endian header (``jIMG``, u32 file size, u16 width, u16 height, u8 pixel format at 0x0C; the rest
is flags and a hash), then one PICA texture level of 8x8 Morton tiles, top row first, from 0x80 to the end. Pixel
formats: 0 RGBA8, 1 RGB8, 5 RGBA4, 8 ETC1, 0x0B ETC1A4, 0x10 A8 (font atlases), 0x12 L8 (a shadow gradient).
One Piece Unlimited World Red uses 8, 0x0B and 0x10; Dragon Ball Fusions uses the others too.
A texture is written in place; unchanged blocks keep their bytes.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

MAGIC = b"jIMG"
HEADER = 0x80
DATA_AT = HEADER
PICA = {0: "RGBA8", 1: "RGB8", 5: "RGBA4", 8: "ETC1", 0x0B: "ETC1A4", 0x10: "A8", 0x12: "L8"}


def detect(data: bytes) -> bool:
    return bytes(data[:4]) == MAGIC and len(data) > DATA_AT


def info(data: bytes, base: int = 0) -> Dict[str, Any]:
    """Format, size and codec of the jIMG at ``base`` of ``data``."""
    if bytes(data[base:base + 4]) != MAGIC:
        raise ValueError("not a jIMG picture")
    total, width, height = struct.unpack_from("<IHH", data, base + 4)
    fmt = data[base + 12]
    if fmt not in PICA:
        raise ValueError(f"jIMG pixel format {fmt:#x} is not supported")
    codec = pixels.codec("pica:" + PICA[fmt])
    if base + DATA_AT + surface.surface_bytes(codec, width, height) > len(data):
        raise ValueError("jIMG picture is cut short")
    return {"codec": codec, "format": PICA[fmt], "width": width, "height": height,
            "at": base + DATA_AT, "total": total}


def header(data: bytes, at: int = 0):
    """``(width, height, codec)`` of the picture whose header is at ``at``."""
    t = info(data, at)
    return t["width"], t["height"], t["codec"]


def read_at(data: bytes, at: int = 0) -> Image.Image:
    t = info(data, at)
    return surface.read(data, t["at"], t["codec"], t["width"], t["height"])


def write_at(out: bytearray, at: int, image: Image.Image) -> int:
    t = info(bytes(out), at)
    return surface.write(out, t["at"], t["codec"], t["width"], t["height"], image.convert("RGBA"))


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    t = info(data)
    return [Texture("", read_at(data), t["format"], 1)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    for index, image in images.items():
        if index != 0:
            raise ValueError("a jIMG file holds one picture")
        write_at(out, 0, image)
    return bytes(out)
