"""3DS CTPK texture packages: several named PICA textures, top row first.

Header (little endian): ``CTPK``, u16 version, u16 texture count, u32 offset of the texture data.
A 0x20-byte entry per texture from 0x20: u32 name offset, u32 data size, u32 data offset (from the
texture data), u32 PICA format, u16 width, u16 height, u8 mip count. Mip levels follow level 0.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

PICA = {0: "RGBA8", 1: "RGB8", 2: "RGBA5551", 3: "RGB565", 4: "RGBA4", 5: "LA8", 6: "HILO8", 7: "L8",
        8: "A8", 9: "LA4", 10: "L4", 11: "A4", 12: "ETC1", 13: "ETC1A4"}


def detect(data: bytes) -> bool:
    return data[:4] == b"CTPK"


def _entries(data: bytes) -> List[Dict[str, Any]]:
    if data[:4] != b"CTPK":
        raise ValueError("Not a CTPK texture package")
    count, base = struct.unpack_from("<HI", data, 6)
    out = []
    for index in range(count):
        name_at, _size, offset, fmt, width, height, mips = struct.unpack_from("<IIIIHHB", data, 0x20 + index * 0x20)
        if fmt not in PICA:
            raise ValueError(f"CTPK pixel format {fmt} is not supported")
        name = data[name_at:data.index(b"\0", name_at)].decode("utf-8", "replace")
        out.append({"name": name, "codec": pixels.codec("pica:" + PICA[fmt]), "format": PICA[fmt],
                    "at": base + offset, "width": width, "height": height, "mips": max(1, mips)})
    return out


def _levels(entry: Dict[str, Any]):
    at, out = entry["at"], []
    for level in range(entry["mips"]):
        width, height = max(8, entry["width"] >> level), max(8, entry["height"] >> level)
        out.append((at, width, height))
        at += surface.surface_bytes(entry["codec"], width, height)
    return out


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    return [Texture(e["name"], surface.read(data, e["at"], e["codec"], e["width"], e["height"]), e["format"],
                    e["mips"]) for e in _entries(data)]


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
