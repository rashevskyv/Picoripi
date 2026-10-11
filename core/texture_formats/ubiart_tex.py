"""UbiArt Framework ``.tga.ckd`` / ``.png.ckd`` textures of the 3DS builds (Gravity Falls: Legend of the Gnome Gemulets).

A cooked texture is a big-endian header of 0x34 bytes (u32 0x17, ``TEX\\0``, u32 0x34, u32 RGBA size, u32
``width << 16 | height`` as authored, u32 0x12000 / 0x11800, u32 RGBA size, ...), a little-endian GPU header (u32
width, u32 height, u32 format, u32 mip count, padded with zeros up to 0x74) and the PICA pixels from 0x74 to the
end: 0x1021 = ETC1A4, 0x1011 = ETC1, one level, 8x8 Morton tiles with the bottom row first as the console wants
them, which makes the picture upside down when read like the other 3DS formats; ``read`` returns it upright.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image, ImageOps

from core.texture_formats import Texture, pixels, surface

PICA = {0x1021: "ETC1A4", 0x1011: "ETC1"}
DATA_AT = 0x74


def detect(data: bytes) -> bool:
    return len(data) > DATA_AT and data[:8] == b"\x00\x00\x00\x17TEX\x00"


def _info(data: bytes) -> Dict[str, Any]:
    if not detect(data):
        raise ValueError("Not an UbiArt TEX texture")
    width, height, fmt, mips = struct.unpack_from("<4I", data, 0x34)
    if fmt not in PICA:
        raise ValueError(f"UbiArt TEX pixel format {fmt:#x} is not supported")
    codec = pixels.codec("pica:" + PICA[fmt])
    if mips != 1 or DATA_AT + surface.surface_bytes(codec, width, height) != len(data):
        raise ValueError("UbiArt TEX sizes do not match the file")
    return {"codec": codec, "format": PICA[fmt], "width": width, "height": height}


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    tex = _info(data)
    image = surface.read(data, DATA_AT, tex["codec"], tex["width"], tex["height"])
    return [Texture("", ImageOps.flip(image.convert("RGBA")), tex["format"], 1)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    tex = _info(data)
    image = images.get(0)
    if image is None:
        return bytes(out)
    surface.write(out, DATA_AT, tex["codec"], tex["width"], tex["height"], ImageOps.flip(image.convert("RGBA")))
    return bytes(out)
