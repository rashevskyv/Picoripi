"""Dragon Quest IX (DS) ``*.spr`` pictures (``dq9_spr``): one image with its palette.

Header (little endian): u16 1, u16 depth (3: 16 colours, 4 bits a pixel; 4: 256 colours, 8 bits), u16 width,
u16 height, u16 count of 8-byte cell records, 6 bytes 0; the cell records; the pixels, in rows from the top
left (4-bit pixels low nibble first); the palette (BGR555, 16 or 256 entries; the first, magenta, is the
transparent colour); then the leftovers of the tool that wrote the file (kept).

Writing keeps every pixel whose colour did not change and gives a changed one the nearest palette colour (the
palette is not rewritten); an unchanged picture writes back the same bytes.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.texture_formats import Texture

BITS = {3: 4, 4: 8}


def _layout(data: bytes):
    one, depth, width, height, cells = struct.unpack_from("<5H", data, 0)
    if one != 1 or depth not in BITS or not width or not height:
        raise ValueError("Not a Dragon Quest IX spr picture")
    bits = BITS[depth]
    pixels_at = 16 + 8 * cells
    palette_at = pixels_at + width * height * bits // 8
    colours = 1 << bits
    if palette_at + 2 * colours > len(data):
        raise ValueError("The spr picture is cut short")
    return bits, width, height, pixels_at, palette_at, colours


def _colour(value: int, index: int) -> Tuple[int, int, int, int]:
    r, g, b = value & 31, value >> 5 & 31, value >> 10 & 31
    return (r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2, 0 if index == 0 else 255)


def _palette(data: bytes, at: int, count: int) -> List[Tuple[int, int, int, int]]:
    return [_colour(v, i) for i, (v,) in enumerate(struct.iter_unpack("<H", data[at:at + 2 * count]))]


def _indices(data: bytes, bits: int, at: int, count: int) -> List[int]:
    if bits == 8:
        return list(data[at:at + count])
    return [(data[at + i // 2] >> (4 * (i & 1))) & 15 for i in range(count)]


def _rgba(image: Image.Image) -> List[Tuple[int, int, int, int]]:
    raw = image.convert("RGBA").tobytes()
    return [tuple(raw[i:i + 4]) for i in range(0, len(raw), 4)]


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    bits, width, height, pixels_at, palette_at, colours = _layout(data)
    palette = _palette(data, palette_at, colours)
    image = Image.new("RGBA", (width, height))
    image.putdata([palette[i] for i in _indices(data, bits, pixels_at, width * height)])
    return [Texture("", image, f"{colours} colours")]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    if 0 not in images:
        return bytes(data)
    bits, width, height, pixels_at, palette_at, colours = _layout(data)
    image = images[0].convert("RGBA")
    if image.size != (width, height):
        raise ValueError(f"The picture must be {width}x{height}")
    palette = _palette(data, palette_at, colours)
    old = _rgba(read(data, params)[0].image)
    out = bytearray(data)
    cache: Dict[Tuple, int] = {}
    for i, (was, now) in enumerate(zip(old, _rgba(image))):
        if was == now or (was[3] == 0 and now[3] < 128):
            continue
        if now[3] < 128:
            index = 0
        else:
            if now not in cache:
                cache[now] = min(range(1, colours), key=lambda k: sum((p - q) ** 2 for p, q in zip(palette[k][:3], now[:3])))
            index = cache[now]
        if bits == 8:
            out[pixels_at + i] = index
        else:
            at, shift = pixels_at + i // 2, 4 * (i & 1)
            out[at] = (out[at] & ~(15 << shift)) | index << shift
    return bytes(out)
