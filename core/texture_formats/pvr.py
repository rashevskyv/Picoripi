"""Dreamcast PVR textures: a ``GBIX`` block (optional) and a ``PVRT`` block, the texels in Morton (twiddled) order.

A PVRT block: ``PVRT``, ``u32`` size (the bytes after it), ``u8`` pixel format (0 ARGB1555, 1 RGB565, 2 ARGB4444),
``u8`` data type (1: square twiddled, the one read here), 2 bytes, ``u16`` width, ``u16`` height, then the texels.
A texel of square twiddled data is a 16-bit little-endian value; its stored index interleaves the bits of x and y
(x in the odd bits, y in the even bits). Facts from the owner's Grandia II disc: the title textures of
``WINDOW/TITLE_DATA.AFS`` entry 12 (ARGB1555, 512x512) and ``0GDTEX.PVR`` (ARGB4444, 256x256) read this way.

Reading gives the one texture of the block; writing changes only the texels that differ (see ``surface``), so
an unchanged block writes the same bytes. Other data types (palettes, rectangles, mip levels, VQ) are refused here.
"""
from __future__ import annotations

import struct
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from core.texture_formats import Texture, pixels, surface

PVRT = b"PVRT"
HEADER = 16          # "PVRT", size, format, data type, 2 bytes, width, height
FORMATS = {0: "pvr:ARGB1555", 1: "pvr:RGB565", 2: "pvr:ARGB4444"}
SQUARE_TWIDDLED = 1


def detect(data: bytes) -> bool:
    return data[:4] == PVRT or (data[:4] == b"GBIX" and PVRT in data[:32])


def _block(data: bytes) -> Tuple[int, str, int, int]:
    """(offset of the PVRT block, codec name, data type, width, height) of the first PVRT block."""
    at = data.find(PVRT)
    if at < 0 or at + HEADER > len(data):
        raise ValueError("no PVRT block in the texture data")
    fmt = data[at + 8]
    if fmt not in FORMATS:
        raise ValueError(f"PVR pixel format {fmt} is not supported")
    dtype = data[at + 9]
    width, height = struct.unpack_from("<HH", data, at + 12)
    return at, FORMATS[fmt], dtype, width, height


@lru_cache(maxsize=8)
def twiddled_offsets(width: int, height: int) -> Tuple[int, ...]:
    """Byte offset (in 16-bit texels, times 2) of each texel in row order, for a square twiddled surface."""
    bits = width.bit_length() - 1
    out = [0] * (width * height)
    for y in range(height):
        for x in range(width):
            index = 0
            for b in range(bits):
                index |= ((y >> b) & 1) << (2 * b)
                index |= ((x >> b) & 1) << (2 * b + 1)
            out[y * width + x] = 2 * index
    return tuple(out)


RECTANGLE = 9          # row-major texels (the title background of TITLE_DATA entry 13: 1024x512 RGB565)


def _layout(dtype: int, width: int, height: int) -> Optional[Tuple[int, ...]]:
    """Element offsets of a surface (None for row-major data), or ValueError for a type not read here."""
    if dtype == RECTANGLE:
        return None
    if dtype != SQUARE_TWIDDLED:
        raise ValueError(f"PVR data type {dtype} is not read yet (square twiddled is 1, rectangle is 9)")
    if width != height or width & (width - 1):
        raise ValueError(f"PVR texture {width}x{height} is not a square of a power of two")
    return twiddled_offsets(width, height)


def read(data: bytes, params: Optional[Dict[str, Any]] = None) -> List[Texture]:
    data = bytes(data)
    at, name, dtype, width, height = _block(data)
    image = surface.read(data, at + HEADER, pixels.codec(name), width, height, _layout(dtype, width, height))
    return [Texture(name="", image=image, pixel_format=name, mipmaps=1)]


def write(data: bytes, images: Dict[int, Image.Image], params: Optional[Dict[str, Any]] = None) -> bytes:
    out = bytearray(data)
    at, name, dtype, width, height = _block(bytes(data))
    image = images.get(0)
    if image is not None:
        surface.write(out, at + HEADER, pixels.codec(name), width, height, image, _layout(dtype, width, height))
    return bytes(out)
