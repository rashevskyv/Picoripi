"""GameCube / Wii BTI (JUTTexture): a 0x20-byte header, an optional palette, the GX texels.

Header (big endian): u8 format, u8 alpha, u16 width, u16 height, u8 wrap S/T, u8 palette flag, u8
palette format (0 IA8, 1 RGB565, 2 RGB5A3), u16 palette entries, u32 palette offset, ..., u8 image
count (mip levels) at 0x18, u32 data offset at 0x1C; offsets count from the header. Levels follow
each other, each padded to whole GX tiles.

A palette texture (C4, C8, C14X2) keeps its palette when every colour of the new image is already
in it; otherwise a palette of the same size is made for the new image and written in place.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

FORMATS = {0: "I4", 1: "I8", 2: "IA4", 3: "IA8", 4: "RGB565", 5: "RGB5A3", 6: "RGBA8",
           8: "C4", 9: "C8", 10: "C14X2", 14: "CMPR"}
_PALETTE = {8: (4, (8, 8)), 9: (8, (8, 4)), 10: (16, (4, 4))}


def _header(data: bytes, at: int = 0) -> Dict[str, int]:
    fmt, _alpha, width, height = struct.unpack_from(">BBHH", data, at)
    pal_format, pal_count, pal_offset = struct.unpack_from(">BHI", data, at + 9)
    mips = max(1, data[at + 0x18])
    offset = struct.unpack_from(">I", data, at + 0x1C)[0] or 0x20
    if fmt not in FORMATS:
        raise ValueError(f"BTI pixel format {fmt} is not supported")
    return {"format": fmt, "width": width, "height": height, "pal_format": pal_format, "pal_count": pal_count,
            "pal_offset": at + pal_offset, "mips": mips, "data": at + offset}


def _palette(data: bytes, head: Dict[str, int]) -> List[tuple]:
    decode, _encode = pixels.gx_palette_format(head["pal_format"])
    values = struct.unpack_from(f">{head['pal_count']}H", data, head["pal_offset"])
    return [decode(v) for v in values]


def _codec(head: Dict[str, int], palette=None) -> pixels.Codec:
    fmt = head["format"]
    if fmt in _PALETTE:
        bits, tile = _PALETTE[fmt]
        return pixels.palette_codec(f"gx:{FORMATS[fmt]}", bits, palette, tile=tile)
    return pixels.codec(f"gx:{FORMATS[fmt]}")


def _levels(head: Dict[str, int], codec: pixels.Codec):
    """``(offset, width, height)`` of every mip level."""
    at, out = head["data"], []
    for level in range(head["mips"]):
        width, height = max(1, head["width"] >> level), max(1, head["height"] >> level)
        out.append((at, width, height))
        at += surface.surface_bytes(codec, width, height)
    return out


def read_image(data: bytes, head: Dict[str, int]) -> Image.Image:
    """Level 0 of the GX image ``head`` describes (``format``, ``width``, ``height``, ``data``, ``mips`` and,
    for a palette format, ``pal_format``, ``pal_count``, ``pal_offset``); TPL uses it too."""
    codec = _codec(head, _palette(data, head) if head["format"] in _PALETTE else None)
    return surface.read(data, head["data"], codec, head["width"], head["height"])


def write_image(out: bytearray, head: Dict[str, int], image: Image.Image) -> bool:
    """Store ``image`` and its mip levels into ``out``; False when nothing changes."""
    force = False
    palette = None
    mips = surface.mip_levels(image.convert("RGBA"), head["mips"])
    if head["format"] in _PALETTE:
        palette = _palette(out, head)
        used = {colour for level in mips for _n, colour in level.getcolors(maxcolors=1 << 20)}
        if not used <= set(palette):
            palette = _new_palette(out, head, mips)
            force = True
    codec = _codec(head, palette)
    levels = _levels(head, codec)
    if not force and surface.write(bytearray(out), levels[0][0], codec, levels[0][1], levels[0][2], image) == 0:
        return False
    for (at, width, height), level_image in zip(levels, mips):
        surface.write(out, at, codec, width, height, level_image, force=force)
    return True


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    head = _header(data)
    return [Texture("", read_image(data, head), FORMATS[head["format"]], head["mips"])]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    if 0 not in images:
        return data
    out = bytearray(data)
    return bytes(out) if write_image(out, _header(data), images[0]) else data


def _new_palette(out: bytearray, head: Dict[str, int], mips: List[Image.Image]) -> List[tuple]:
    """A palette for the new image (all its mip levels), written over the old one; returns its colours."""
    decode, encode = pixels.gx_palette_format(head["pal_format"])
    capacity = min(head["pal_count"], 1 << _PALETTE[head["format"]][0])
    colours = pixels.nearest_palette(mips[0], capacity)   # the smaller levels are made of the same colours
    values = [encode(*c) for c in colours] + [0] * (head["pal_count"] - len(colours))
    struct.pack_into(f">{head['pal_count']}H", out, head["pal_offset"], *values)
    return [decode(v) for v in values]

