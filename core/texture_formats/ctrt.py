"""Kingdom Hearts 3D: Dream Drop Distance ``.ctt`` pictures (``CTRT``): one PICA texture behind a 0x80-byte header.

Header (little endian): ``CTRT``, u32 0, u32 0x10, u32 offset of the pixels (0x80), u32 0, u32 pixel bytes, u32 0,
u32 PICA format (0 RGBA8 ... 12 ETC1, 13 ETC1A4, as in CTPK), u16 width, u16 height. The pixels are the one
level 0 surface in the console's tiling, so the picture is written back in place and the file keeps its size.
Layout from OpenKH's ``docs/ddd`` (Apache-2.0).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface
from core.texture_formats.ctpk import PICA

MAGIC = b"CTRT"


def detect(data: bytes) -> bool:
    return data[:4] == MAGIC


def _entry(data: bytes) -> Dict[str, Any]:
    if data[:4] != MAGIC or len(data) < 0x24:
        raise ValueError("Not a CTRT picture")
    at, size = struct.unpack_from("<II", data, 0x0C)[0], struct.unpack_from("<I", data, 0x14)[0]
    fmt = struct.unpack_from("<I", data, 0x1C)[0]
    width, height = struct.unpack_from("<HH", data, 0x20)
    if fmt not in PICA:
        raise ValueError(f"CTRT pixel format {fmt} is not supported")
    codec = pixels.codec("pica:" + PICA[fmt])
    if at + surface.surface_bytes(codec, width, height) > len(data):
        raise ValueError("The picture data is cut short")
    return {"codec": codec, "format": PICA[fmt], "at": at, "width": width, "height": height, "size": size}


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    e = _entry(data)
    return [Texture("", surface.read(data, e["at"], e["codec"], e["width"], e["height"]), e["format"], 1)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    e = _entry(data)
    for index, image in images.items():
        if index != 0:
            raise ValueError("A CTRT picture holds one texture")
        surface.write(out, e["at"], e["codec"], e["width"], e["height"], image)
    return bytes(out)
