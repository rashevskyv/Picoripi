"""Level-5 ``ztex`` picture files of Fantasy Life (3DS): one or more PICA textures with their source file names.

Header (little endian): ``ztex``, u16 texture count, u16 version (2), u32 flags; then 0x58 bytes per texture from
0x0C: 0x40 bytes of name, u32 hash, u32 data offset, u32 0, u32 data size, u16 width, u16 height, u8 mip count,
u8 format, u8 0xFF, u8 0. The levels follow each other at the data offset, top row first.

Format byte: 0x01 RGB565, 0x03 RGB8, 0x05 RGBA4, 0x07 RGBA5551, 0x09 RGBA8, 0x18 ETC1, 0x19 ETC1A4; the 4 and 8
bit ones (0x0B A4, 0x0D L8, 0x11 A8, 0x13 LA4) and 0x15 (LA8) are taken from the sizes and the picture names:
the pictures with words use the first ones.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

FORMATS = {0x01: "RGB565", 0x03: "RGB8", 0x05: "RGBA4", 0x07: "RGBA5551", 0x09: "RGBA8", 0x0B: "A4", 0x0D: "L8",
           0x11: "A8", 0x13: "LA4", 0x15: "LA8", 0x18: "ETC1", 0x19: "ETC1A4"}
ENTRY = 0x58


def detect(data: bytes) -> bool:
    return data[:4] == b"ztex"


def _entries(data: bytes) -> List[Dict[str, Any]]:
    if data[:4] != b"ztex":
        raise ValueError("Not a ztex file")
    count = struct.unpack_from("<H", data, 4)[0]
    out = []
    for i in range(count):
        at = 0x0C + ENTRY * i
        if at + ENTRY > len(data):
            raise ValueError("ztex header runs past the file end")
        name = data[at:at + 0x40].split(b"\0")[0].decode("latin1")
        _hash, offset, _zero, size, width, height, mips, fmt = struct.unpack_from("<IIIIHHBB", data, at + 0x40)
        if fmt not in FORMATS:
            raise ValueError(f"ztex pixel format 0x{fmt:02X} is not supported")
        out.append({"name": name, "codec": pixels.codec("pica:" + FORMATS[fmt]), "format": FORMATS[fmt],
                    "at": offset, "width": width, "height": height, "mips": max(1, mips), "size": size})
    return out


def _levels(entry: Dict[str, Any]):
    at, out = entry["at"], []
    for level in range(entry["mips"]):
        width, height = max(8, entry["width"] >> level), max(8, entry["height"] >> level)
        out.append((at, width, height))
        at += surface.surface_bytes(entry["codec"], width, height)
    return out


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    return [Texture(e["name"], surface.read(data, e["at"], e["codec"], e["width"], e["height"]), e["format"], e["mips"])
            for e in _entries(data)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    entries = _entries(data)
    for index, image in images.items():
        entry = entries[index]
        levels = _levels(entry)
        at, width, height = levels[0]
        if surface.write(out, at, entry["codec"], width, height, image) == 0:
            continue
        for (at, width, height), level in zip(levels[1:], surface.mip_levels(image.convert("RGBA"), len(levels))[1:]):
            surface.write(out, at, entry["codec"], width, height, level.resize((width, height)))
    return bytes(out)
