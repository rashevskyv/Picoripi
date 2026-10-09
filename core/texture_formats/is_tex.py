"""Infinite Space (DS) ``data/Cg/Texture/*.tex``: one 3D texture with its palette (``is_tex``).

Header (little endian): u32 kind, u16 width, u16 height, u32 pixel offset, u32 pixel bytes, 12 bytes 0, u32 flags,
u32 palette offset, u32 palette bytes. Kinds: 0 four colours (2 bits a pixel), 1 sixteen colours (4 bits),
2 256 colours (8 bits), 6 direct colour (BGR555 with the top bit as alpha); pixels in rows from the top left,
low bits first; palette entries BGR555. (Kinds 4 and 5, the translucent A3I5 / A5I3 textures, are not read: the
game's textures with text do not use them.)

Writing keeps every pixel whose colour did not change and gives a changed one the nearest palette colour (the
palette is not rewritten); an unchanged picture writes back the same bytes.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.texture_formats import Texture

BITS = {0: 2, 1: 4, 2: 8}
DIRECT = 6


def _colour(value: int, alpha: int = 255) -> Tuple[int, int, int, int]:
    r, g, b = value & 31, value >> 5 & 31, value >> 10 & 31
    return (r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2, alpha)


def _head(data: bytes):
    kind, width, height, offset, size = struct.unpack_from("<IHHII", data, 0)
    pal_at, pal_size = struct.unpack_from("<II", data, 0x20)
    if kind not in BITS and kind != DIRECT:
        raise ValueError(f"Texture kind {kind} is not supported")
    return kind, width, height, offset, size, pal_at, pal_size


def _palette(data: bytes, pal_at: int, pal_size: int) -> List[Tuple[int, int, int, int]]:
    return [_colour(v) for (v,) in struct.iter_unpack("<H", data[pal_at:pal_at + pal_size])]


def _indices(data: bytes, kind: int, offset: int, count: int) -> List[int]:
    bits = BITS[kind]
    mask = (1 << bits) - 1
    return [(data[offset + i * bits // 8] >> (i * bits % 8)) & mask for i in range(count)]


def _rgba(image: Image.Image) -> List[Tuple[int, int, int, int]]:
    raw = image.convert("RGBA").tobytes()
    return [tuple(raw[i:i + 4]) for i in range(0, len(raw), 4)]


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    kind, width, height, offset, _size, pal_at, pal_size = _head(data)
    if kind == DIRECT:
        values = struct.unpack_from(f"<{width * height}H", data, offset)
        pixels = [_colour(v, 255 if v & 0x8000 else 0) for v in values]
        name = "direct"
    else:
        palette = _palette(data, pal_at, pal_size) or [(0, 0, 0, 255)]
        pixels = [palette[i % len(palette)] for i in _indices(data, kind, offset, width * height)]
        name = f"{1 << BITS[kind]} colours"
    image = Image.new("RGBA", (width, height))
    image.putdata(pixels)
    return [Texture("", image, name)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    if 0 not in images:
        return bytes(data)
    kind, width, height, offset, _size, pal_at, pal_size = _head(data)
    image = images[0].convert("RGBA")
    if image.size != (width, height):
        raise ValueError(f"The picture must be {width}x{height}")
    old = _rgba(read(data, params)[0].image)
    new = _rgba(image)
    out = bytearray(data)
    if kind == DIRECT:
        for i, (was, now) in enumerate(zip(old, new)):
            if was != now:
                r, g, b, a = now
                struct.pack_into("<H", out, offset + 2 * i, (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10 | (a >= 128) << 15)
        return bytes(out)
    palette = _palette(data, pal_at, pal_size)
    bits = BITS[kind]
    cache: Dict[Tuple, int] = {}
    for i, (was, now) in enumerate(zip(old, new)):
        if was == now:
            continue
        if now not in cache:
            cache[now] = min(range(len(palette)), key=lambda k: sum((p - q) ** 2 for p, q in zip(palette[k][:3], now[:3])))
        at, shift = offset + i * bits // 8, i * bits % 8
        mask = ((1 << bits) - 1) << shift
        out[at] = (out[at] & ~mask) | (cache[now] << shift)
    return bytes(out)
