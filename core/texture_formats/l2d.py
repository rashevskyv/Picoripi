"""Kingdom Hearts 3D: Dream Drop Distance ``.l2d`` layouts (``L2D@``): the ``CTRT`` pictures kept inside.

A layout file (menus, the title screen, help pages; format after OpenKH's ``docs/bbs/file/type/l2d.md``) holds
sprite, sequence and layout tables and the pictures themselves as complete ``CTRT`` files (``core.texture_formats.ctrt``)
one after another, each at a multiple of 0x80. A picture's size is its 0x80-byte header plus the pixel bytes, so the
pictures are found by walking the file for ``CTRT`` at 0x80 steps whose header is consistent. Pictures are written
back in place; the file keeps its size and every table.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, ctrt, pixels, surface
from core.texture_formats.ctpk import PICA

MAGIC = b"L2D@"


def detect(data: bytes) -> bool:
    return data[:4] == MAGIC


def _blocks(data: bytes) -> List[Dict[str, Any]]:
    if data[:4] != MAGIC:
        raise ValueError("Not an L2D layout")
    out = []
    at = 0
    while True:
        at = data.find(ctrt.MAGIC, at)
        if at < 0:
            break
        if at % 0x10 == 0 and at + 0x24 <= len(data):
            pixel_at, size, fmt = struct.unpack_from("<I", data, at + 0x0C)[0], struct.unpack_from("<I", data, at + 0x14)[0], \
                struct.unpack_from("<I", data, at + 0x1C)[0]
            width, height = struct.unpack_from("<HH", data, at + 0x20)
            if fmt in PICA and pixel_at == 0x80 and 0 < width <= 2048 and 0 < height <= 2048:
                codec = pixels.codec("pica:" + PICA[fmt])
                if size == surface.surface_bytes(codec, width, height) and at + pixel_at + size <= len(data):
                    out.append({"at": at, "pixels": at + pixel_at, "codec": codec, "format": PICA[fmt],
                                "width": width, "height": height})
                    at += pixel_at + size
                    continue
        at += 4
    return out


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    return [Texture(f"{b['at']:X}", surface.read(data, b["pixels"], b["codec"], b["width"], b["height"]), b["format"], 1)
            for b in _blocks(data)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    blocks = _blocks(data)
    for index, image in images.items():
        b = blocks[index]
        surface.write(out, b["pixels"], b["codec"], b["width"], b["height"], image)
    return bytes(out)
