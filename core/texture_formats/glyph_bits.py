"""1-bit glyph cells inside a file: ``count`` glyphs of ``width`` x ``height`` pixels, one after another at ``offset``.

Each row is a little-endian 16-bit word, bit 0 the left pixel; a glyph is ``height`` rows. The picture is the
glyphs side by side: ink is opaque white, the rest transparent. Writing takes a pixel as ink when its alpha is
128 or more and rewrites the low ``width`` bits of each row word; the bits above the width and the bytes outside
the table keep their value. The caption's private glyphs of the Symphony of the Night prologue use it
(``plugins/castlevania_sotn/scroll.py``).

Params: ``offset``, ``count`` (default 1), ``width`` (default 12), ``height`` (default 16).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _layout(params: Dict[str, Any]):
    return (_int(params["offset"]), _int(params.get("count", 1)), _int(params.get("width", 12)),
            _int(params.get("height", 16)))


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    offset, count, width, height = _layout(params)
    sheet = Image.new("RGBA", (count * width, height), (0, 0, 0, 0))
    pixels = sheet.load()
    for glyph in range(count):
        base = offset + glyph * height * 2
        for row in range(height):
            word = struct.unpack_from("<H", data, base + 2 * row)[0]
            for column in range(width):
                if (word >> column) & 1:
                    pixels[glyph * width + column, row] = (255, 255, 255, 255)
    return [Texture(str(params.get("name") or ""), sheet, "bits:1")]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    offset, count, width, height = _layout(params)
    out = bytearray(data)
    image = images.get(0)
    if image is None:
        return bytes(out)
    image = image.convert("RGBA")
    if image.size != (count * width, height):
        raise ValueError(f"The image is {image.width}x{image.height}, the glyphs need {count * width}x{height}")
    pixels = image.load()
    mask = (1 << width) - 1
    for glyph in range(count):
        base = offset + glyph * height * 2
        for row in range(height):
            word = 0
            for column in range(width):
                if pixels[glyph * width + column, row][3] >= 128:
                    word |= 1 << column
            # the bits above the width are not pixels: they keep their value, so an unedited table is the same bytes
            kept = struct.unpack_from("<H", out, base + 2 * row)[0] & ~mask & 0xFFFF
            struct.pack_into("<H", out, base + 2 * row, kept | word)
    return bytes(out)
