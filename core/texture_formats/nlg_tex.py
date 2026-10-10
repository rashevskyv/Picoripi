"""Next Level Games 3DS texture bundles (Luigi's Mansion: Dark Moon): a ``.data`` / ``.dict`` pair's texture table
and pixel member joined as one file.

The workspace's ``1_unpack.bat`` writes a bundle as ``<name>.data/bundle.nlgb``: ``NLGB``, u32 size of the table
member, u32 size of the pixel member, the table member, the pixel member. The table member starts with 0x38-byte
``Powe`` entries (magic ``0xE977D350``, u32 id, u32 byte length with mip levels, u32 id again, u16 width and
u16 height at 0x18, byte ``0x11 * levels`` at 0x1F, byte format at 0x34: 12 ETC1, 13 ETC1A4); what follows is the
bundle's other data (a font bundle's glyph description, see ``core.font_formats.nlg_font``). The pixel member holds
the textures one after the other, each with its mip levels, stored bottom row first. Writing changes pixels in
place; mip levels are made again from a changed picture.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.texture_formats import Texture, pixels, surface

MAGIC = b"NLGB"
POWE = struct.pack("<I", 0xE977D350)
ENTRY = 0x38
_FORMATS = {12: "pica:ETC1", 13: "pica:ETC1A4"}


def is_bundle(data: bytes) -> bool:
    return bytes(data[:4]) == MAGIC


detect = is_bundle


def split(data: bytes) -> Tuple[bytes, bytes]:
    """``(table member, pixel member)`` of a bundle file."""
    if not is_bundle(data):
        raise ValueError("not a Next Level Games bundle (NLGB)")
    size2, size3 = struct.unpack_from("<II", data, 4)
    return bytes(data[12:12 + size2]), bytes(data[12 + size2:12 + size2 + size3])


def join(table: bytes, pixels_member: bytes) -> bytes:
    return MAGIC + struct.pack("<II", len(table), len(pixels_member)) + table + pixels_member


def entries(table: bytes) -> List[Dict[str, Any]]:
    """The textures of a table member: id, width, height, mip levels, format code, offset in the pixel member."""
    out, at, offset = [], 0, 0
    while table[at:at + 4] == POWE and at + ENTRY <= len(table):
        _magic, tid, length, _again = struct.unpack_from("<IIII", table, at)
        width, height = struct.unpack_from("<HH", table, at + 0x18)
        out.append({"id": tid, "width": width, "height": height, "levels": max(1, table[at + 0x1F] // 0x11),
                    "format": table[at + 0x34], "length": length, "offset": offset, "at": at})
        offset += length
        at += ENTRY
    return out


def table_end(table: bytes) -> int:
    """Offset in the table member just past the ``Powe`` entries."""
    return len(entries(table)) * ENTRY


def _codec(entry: Dict[str, Any]) -> pixels.Codec:
    try:
        return pixels.codec(_FORMATS[entry["format"]])
    except KeyError:
        raise ValueError(f"unsupported Next Level Games texture format {entry['format']}") from None


def _levels(entry: Dict[str, Any]) -> List[Tuple[int, int, int, int]]:
    """``(offset in the pixel member, width, height, bytes)`` per mip level."""
    codec, at, out = _codec(entry), entry["offset"], []
    for level in range(entry["levels"]):
        w, h = max(8, entry["width"] >> level), max(8, entry["height"] >> level)
        size = surface.surface_bytes(codec, w, h)
        out.append((at, w, h, size))
        at += size
    return out


def read_texture(entry: Dict[str, Any], pixel_member: bytes) -> Image.Image:
    at, w, h, _size = _levels(entry)[0]
    return surface.read(pixel_member, at, _codec(entry), w, h).transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def write_texture(out: bytearray, entry: Dict[str, Any], image: Image.Image) -> bool:
    """Draw ``image`` (upright) into the pixel member ``out``; the lower mip levels are made again. True if changed."""
    codec = _codec(entry)
    levels = _levels(entry)
    flipped = image.convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    at, w, h, _size = levels[0]
    if flipped.size != (w, h):
        raise ValueError(f"The image is {flipped.size[0]}x{flipped.size[1]}, the texture {w}x{h}")
    changed = surface.write(out, at, codec, w, h, flipped)
    if changed:
        for (lat, lw, lh, _s), level_image in zip(levels[1:], surface.mip_levels(flipped, len(levels))[1:]):
            surface.write(out, lat, codec, lw, lh, level_image.resize((lw, lh)), force=True)
    return bool(changed)


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    table, pixel_member = split(data)
    return [Texture(f"{e['id']:08x}", read_texture(e, pixel_member), _FORMATS[e["format"]].split(":")[-1], e["levels"])
            for e in entries(table)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    table, pixel_member = split(data)
    listed = entries(table)
    out = bytearray(pixel_member)
    changed = False
    for index, image in images.items():
        changed |= write_texture(out, listed[index], image)
    return join(table, bytes(out)) if changed else bytes(data)
