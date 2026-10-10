"""PhyreEngine texture files (``RYHP`` ... ``NXGL``; Dragon Quest Builders 1, Switch): one texture per file.

The file is a Phyre cluster: a header (class table, the asset name, the texture record, fix-up tables) and, as
the last bytes, the pixels. The record sits right before the class name ``PTexture2D`` that is followed by the
format name: (a marker byte), u32 highest mip level, u32 and u32 size hints, u32 width, u32 height, u32 1, ``0x00``.
Formats: ``ARGB8`` (bytes B, G, R, A), ``ARGB4444`` (u16 0xARGB), ``DXT5`` (BC3), ``DXT1`` (BC1). Mip levels
follow level 0, each half the size; rows are stored bottom-up (OpenGL), so the image is flipped.

Files that pack many textures (the UI sprite packs ``uitex``/``uiicon``) keep each texture's format in the
cluster's fix-up tables and are not read.
"""
from __future__ import annotations

import re
import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

MAGIC = b"RYHP"
NUL = bytes(1)
FORMATS = {"ARGB8": "BGRA8", "ARGB4444": "ARGB4", "DXT5": "BC3", "DXT1": "BC1"}
_NAME = re.compile(rb"PTexture2D\x00([A-Za-z0-9]+)\x00")


def detect(data: bytes) -> bool:
    return bytes(data[:4]) == MAGIC and b"PTexture2D\x00" in bytes(data[:0x3000]) and _record(bytes(data)) is not None


def _record(data: bytes):
    """(format name, mip count, width, height, offset of the first pixel) or None."""
    section = 84 + struct.unpack_from("<I", data, 8)[0]
    found = [m for m in _NAME.finditer(data, section, section + 0x4000)]
    if len(found) != 1:
        return None
    at = found[0].start()
    if at < 25 or data.count(b".dds" + NUL, section, at) != 1:     # a pack of textures: not one file's texture
        return None
    mip, _b, _c, width, height, depth = struct.unpack_from("<6I", data, at - 25)
    name = found[0].group(1).decode()
    if name not in FORMATS or depth != 1 or not (1 <= width <= 8192 and 1 <= height <= 8192):
        return None
    codec = pixels.codec(FORMATS[name])
    levels = mip + 1
    total = sum(surface.surface_bytes(codec, max(1, width >> n), max(1, height >> n)) for n in range(levels))
    start = len(data) - total
    if start < at:
        return None
    return name, levels, width, height, start


def _levels(width: int, height: int, count: int, start: int, codec):
    at, out = start, []
    for n in range(count):
        w, h = max(1, width >> n), max(1, height >> n)
        out.append((at, w, h))
        at += surface.surface_bytes(codec, w, h)
    return out


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    record = _record(bytes(data))
    if record is None:
        raise ValueError("Not a single-texture Phyre file")
    name, mips, width, height, start = record
    codec = pixels.codec(FORMATS[name])
    image = surface.read(data, start, codec, width, height).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return [Texture("", image, name, mips)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    record = _record(bytes(data))
    if record is None:
        raise ValueError("Not a single-texture Phyre file")
    name, mips, width, height, start = record
    new = images.get(0)
    if new is None:
        return bytes(data)
    codec = pixels.codec(FORMATS[name])
    out = bytearray(data)
    flipped = new.convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    levels = _levels(width, height, mips, start, codec)
    at, w, h = levels[0]
    if surface.write(out, at, codec, w, h, flipped) == 0:
        return bytes(data)                       # nothing redrawn: the stored mip levels stay
    for (at, w, h), level in zip(levels[1:], surface.mip_levels(flipped, len(levels))[1:]):
        surface.write(out, at, codec, w, h, level)
    return bytes(out)
