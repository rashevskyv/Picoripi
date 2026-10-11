"""Uncompressed TGA (type 2, 24 or 32 bits per pixel), as the Silent Hill 2 Enhanced Edition font atlas (font000.tga).

The header and any trailing bytes are kept on write; only the pixel rows are replaced, so an unchanged image gives
the same bytes. Top-left and bottom-left origins are both handled (the file's descriptor bit 5).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture

HEADER = 18


def _info(data: bytes):
    idlen, cmap_type, image_type = data[0], data[1], data[2]
    if image_type != 2 or cmap_type != 0:
        raise ValueError("only uncompressed truecolor TGA is supported")
    width, height = struct.unpack_from("<HH", data, 12)
    depth = data[16]
    descriptor = data[17]
    if depth not in (24, 32):
        raise ValueError(f"TGA depth {depth} not supported")
    bpp = depth // 8
    start = HEADER + idlen
    size = width * height * bpp
    if start + size > len(data):
        raise ValueError("TGA pixel data is cut short")
    top_left = bool(descriptor & 0x20)
    return width, height, bpp, start, size, top_left


def detect(data: bytes) -> bool:
    return len(data) >= HEADER and data[2] == 2 and data[16] in (24, 32)


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    width, height, bpp, start, size, top_left = _info(data)
    mode, raw = ("RGBA", "BGRA") if bpp == 4 else ("RGB", "BGR")
    image = Image.frombytes(mode, (width, height), bytes(data[start:start + size]), "raw", raw)
    if not top_left:
        image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    fmt = "TGA 32-bit" if bpp == 4 else "TGA 24-bit"
    return [Texture("", image.convert("RGBA"), fmt)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    width, height, bpp, start, size, top_left = _info(data)
    if 0 not in images:
        return bytes(data)
    sheet = images[0].convert("RGBA")
    if sheet.size != (width, height):
        raise ValueError(f"The image is {sheet.width}x{sheet.height}, the texture {width}x{height}")
    if not top_left:
        sheet = sheet.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if bpp == 4:
        pixels = sheet.tobytes("raw", "BGRA")
    else:
        pixels = sheet.convert("RGB").tobytes("raw", "BGR")
    return bytes(data[:start]) + pixels + bytes(data[start + size:])
