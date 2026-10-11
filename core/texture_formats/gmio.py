"""``GMIO`` textures of Digimon World: Re:Digitize Decode (3DS): one PICA texture behind a 0x80-byte header.

Header (little endian): ``GMIO``, u32 6, ...; u16 width, u16 height of the picture at 0x14; the type bytes at
0x1A / 0x1B / 0x1E (type, kind, bits per pixel) and u16 width, u16 height of the stored (power of two) texture at
0x24. The pixels follow the header, top row first in 8x8 tiles: ``01 10 / 32`` RGBA8, ``02 10 / 24`` RGB8,
``03 10 / 16`` RGB565, ``02 11 / 8`` L8.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

HEADER = 0x80
FORMATS = {(0x01, 0x10, 32): "RGBA8", (0x02, 0x10, 24): "RGB8", (0x03, 0x10, 16): "RGB565", (0x02, 0x11, 8): "L8"}


def detect(data: bytes) -> bool:
    return data[:4] == b"GMIO" and len(data) > HEADER


def _layout(data: bytes):
    if not detect(data):
        raise ValueError("Not a GMIO texture")
    kind = (data[0x1A], data[0x1B], data[0x1E])
    name = FORMATS.get(kind)
    if name is None:
        raise ValueError(f"GMIO pixel format {kind} is not supported")
    width, height = struct.unpack_from("<HH", data, 0x24)
    codec = pixels.codec("pica:" + name)
    if HEADER + surface.surface_bytes(codec, width, height) != len(data):
        raise ValueError("GMIO size does not match its header")
    return name, codec, width, height


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    name, codec, width, height = _layout(data)
    return [Texture("", surface.read(data, HEADER, codec, width, height), name, 1)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    name, codec, width, height = _layout(data)
    out = bytearray(data)
    if 0 in images:
        surface.write(out, HEADER, codec, width, height, images[0])
    return bytes(out)
