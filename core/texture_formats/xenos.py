"""Xbox 360 (Xenos) pictures in 2D tiles, in the 32-byte-header ``.bin`` files of Hard Corps: Uprising.

Header, big endian: width, height, a format word, the data size, and four more words the game does not
read here (kept as they are). Format word ``0x400``: an 8-bit palette picture; the 256 palette entries (bytes
A, R, G, B) follow the header and the indices start at byte ``0x420``. Format word ``0``: 32-bit texels whose
bytes are A, R, G, B, starting at byte ``0x20``. Index 0 of a palette is transparent.

The data size is the tiled surface: width and height rounded up to 32 texels, times the bytes per texel,
rounded up to 4096. The picture is stored upside down: the texel of picture row ``y`` lies at
``tiled_offset(x, height - 1 - y, pitch, bytes_per_texel)`` from the data start, where ``pitch`` is the width
rounded up to 32 (the Xenia ``texture_address::Tiled2D`` rule, BSD-3-Clause:
https://github.com/xenia-project/xenia). The flip was proved on the game's own boot pictures (the KONAMI
and Arc System Works logos and the copyright line are upright in the game and only upright after the flip).
Writing keeps the palette, the header, the padding and every texel that was not changed.

Params: ``name`` (the texture's name, optional).
"""
from __future__ import annotations

import functools
import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.texture_formats import Texture, pixels, surface

HEADER = 0x20
PALETTE_FORMAT = 0x400
PALETTE_BYTES = 256 * 4
PALETTE_DATA = HEADER + PALETTE_BYTES


def tiled_offset(x: int, y: int, pitch: int, bytes_per_texel: int) -> int:
    """Byte offset of texel (x, y) in a 2D tiled surface whose row is ``pitch`` texels (a multiple of 32)."""
    log2 = bytes_per_texel.bit_length() - 1
    outer = (((y >> 5) * (pitch >> 5)) + (x >> 5)) << 6
    inner = (((y >> 1) & 0b111) << 3) | (x & 0b111)
    outer_inner = (outer | inner) << log2
    bank = (y >> 4) & 1
    pipe = ((x >> 3) & 0b11) ^ (((y >> 3) & 1) << 1)
    return (((y & 1) << 4) | (pipe << 6) | (bank << 11) | (outer_inner & 0b1111)
            | (((outer_inner >> 4) & 1) << 5) | (((outer_inner >> 5) & 0b111) << 8) | ((outer_inner >> 8) << 12))


def _align(value: int, to: int) -> int:
    return (value + to - 1) // to * to


@functools.lru_cache(maxsize=512)
def _offsets(width: int, height: int, bytes_per_texel: int) -> Tuple[int, ...]:
    """Byte offset of each picture texel, row by row from the top; the stored rows run bottom-up.

    The same arithmetic as ``tiled_offset``, written inline: a picture of the game is read once per listing,
    and a call per texel made the listing of the project slow (``tests`` check the two stay equal)."""
    pitch_tiles = _align(width, 32) >> 5
    shift = bytes_per_texel.bit_length() - 1
    out = []
    append = out.append
    for y in range(height):
        row = height - 1 - y
        outer_row = (row >> 5) * pitch_tiles
        inner_row = ((row >> 1) & 7) << 3
        y_lsb = (row & 1) << 4
        bank = ((row >> 4) & 1) << 11
        pipe_y = ((row >> 3) & 1) << 1
        for x in range(width):
            oi = ((((outer_row + (x >> 5)) << 6) | inner_row | (x & 7)) << shift)
            append(y_lsb | ((((x >> 3) & 3) ^ pipe_y) << 6) | bank | (oi & 0xF) | (((oi >> 4) & 1) << 5)
                   | (((oi >> 5) & 7) << 8) | ((oi >> 8) << 12))
    return tuple(out)


def _header(data: bytes) -> Dict[str, Any]:
    if len(data) < HEADER:
        raise ValueError("Xenos texture: the file is shorter than its header")
    width, height, flag, size = struct.unpack_from(">4I", data, 0)
    if not (1 <= width <= 4096 and 1 <= height <= 4096):
        raise ValueError(f"Xenos texture: implausible size {width}x{height}")
    if flag == PALETTE_FORMAT:
        base, bpt = PALETTE_DATA, 1
    elif flag == 0:
        base, bpt = HEADER, 4
    else:
        raise ValueError(f"Xenos texture: unknown format word {flag:#x}")
    expected = _align(_align(width, 32) * _align(height, 32) * bpt, 4096)
    if size != expected:
        raise ValueError(f"Xenos texture: data size {size:#x} is not the tiled size {expected:#x}")
    if base + size > len(data):
        raise ValueError("Xenos texture: the data is cut short")
    return {"width": width, "height": height, "flag": flag, "base": base, "bpt": bpt}


def _argb_decode(value: int):
    a, r, g, b = value.to_bytes(4, "big")
    return r, g, b, a


def _argb_encode(r: int, g: int, b: int, a: int) -> int:
    return int.from_bytes(bytes((a, r, g, b)), "big")


def _codec(data: bytes, info: Dict[str, Any]) -> pixels.Codec:
    if info["flag"] == 0:
        return pixels.value_codec("xenos:ARGB8", 32, _argb_decode, _argb_encode)
    colours = [(0, 0, 0, 0)]                      # index 0 is transparent
    for i in range(1, 256):
        a, r, g, b = data[HEADER + 4 * i:HEADER + 4 * i + 4]
        colours.append((r, g, b, a))
    return pixels.palette_codec("xenos:P8", 8, colours)


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    info = _header(data)
    codec = _codec(data, info)
    width, height, bpt, base = info["width"], info["height"], info["bpt"], info["base"]
    offsets = _offsets(width, height, bpt)
    if bpt == 1:
        raw = bytes(map(data.__getitem__, [base + o for o in offsets]))
    else:
        raw = bytes(map(data.__getitem__, [base + o + k for o in offsets for k in range(bpt)]))
    image = codec.decode(raw, width, height)
    fmt = codec.name
    return [Texture(name=str(params.get("name") or ""), image=image, pixel_format=fmt, mipmaps=1)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    info = _header(data)
    out = bytearray(data)
    image = images.get(0)
    if image is None:
        return bytes(out)
    codec = _codec(data, info)
    offsets = _offsets(info["width"], info["height"], info["bpt"])
    surface.write(out, info["base"], codec, info["width"], info["height"], image, offsets)
    return bytes(out)
