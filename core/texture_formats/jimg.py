"""Ganbarion ``jIMG`` pictures (One Piece: Unlimited World Red, 3DS): ``.jtex`` files and the picture inside a
``.jfnt`` font.

A 0x80-byte header (``jIMG``, u32 file size, u16 width, u16 height, byte pixel format at 0x0C; the rest is
flags and a hash), then one surface in the console's tiled layout, no mip levels, top row first. Pixel formats:
8 = ETC1 (4 bits per pixel), 11 = ETC1A4 (8 bits), 16 = A8. A texture is written in place; unchanged blocks keep
their bytes.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

MAGIC = b"jIMG"
HEADER = 0x80
FORMATS = {8: "pica:ETC1", 11: "pica:ETC1A4", 16: "pica:A8"}


def detect(data: bytes) -> bool:
    return bytes(data[:4]) == MAGIC


def header(data: bytes, at: int = 0):
    """``(width, height, codec)`` of the picture whose header is at ``at``."""
    if bytes(data[at:at + 4]) != MAGIC:
        raise ValueError("not a jIMG picture")
    width, height = struct.unpack_from("<HH", data, at + 8)
    code = data[at + 12]
    if code not in FORMATS:
        raise ValueError(f"unsupported jIMG pixel format {code}")
    codec = pixels.codec(FORMATS[code])
    if len(data) < at + HEADER + surface.surface_bytes(codec, width, height):
        raise ValueError("jIMG picture is cut short")
    return width, height, codec


def read_at(data: bytes, at: int = 0) -> Image.Image:
    width, height, codec = header(data, at)
    return surface.read(data, at + HEADER, codec, width, height)


def write_at(out: bytearray, at: int, image: Image.Image) -> int:
    width, height, codec = header(bytes(out), at)
    return surface.write(out, at + HEADER, codec, width, height, image.convert("RGBA"))


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    _w, _h, codec = header(data)
    return [Texture("", read_at(data), codec.name.split(":")[-1], 1)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    for index, image in images.items():
        if index != 0:
            raise ValueError("a jIMG file holds one picture")
        write_at(out, 0, image)
    return bytes(out)
