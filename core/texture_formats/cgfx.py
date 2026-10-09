"""3DS CGFX (``.bcres``, Fire Emblem Awakening ``.r`` telops): the ``TXOB`` textures of the DATA block.

``CGFX`` header (u16 header size at 6), then ``DATA``: 16 (count, self-relative DICT pointer) pairs; pair 1 is the
textures. A DICT entry (16 bytes from DICT+0x1C) points at the name and the object. An image texture object
(``TXOB``, type flags 0x20000011): height at +0x18, width +0x1C, PICA format +0x34, image pointer +0x38 -> height,
width, data size, self-relative data pointer. Level 0 is written back in place; smaller mips are regenerated.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface
from core.texture_formats.ctpk import PICA


def detect(data: bytes) -> bool:
    return data[:4] == b"CGFX"


def _pointer(data: bytes, at: int) -> int:
    value = struct.unpack_from("<I", data, at)[0]
    return at + value if value else 0


def _entries(data: bytes) -> List[Dict[str, Any]]:
    if data[:4] != b"CGFX":
        raise ValueError("Not a CGFX file")
    block = struct.unpack_from("<H", data, 6)[0]
    if data[block:block + 4] != b"DATA":
        raise ValueError("CGFX without a DATA block")
    count = struct.unpack_from("<I", data, block + 8 + 8)[0]
    dictionary = _pointer(data, block + 8 + 12)
    out = []
    for index in range(count if dictionary else 0):
        entry = dictionary + 0x1C + index * 0x10
        name_at, obj = _pointer(data, entry + 8), _pointer(data, entry + 12)
        name = data[name_at:data.index(b"\0", name_at)].decode("utf-8", "replace")
        if data[obj + 4:obj + 8] != b"TXOB":
            continue
        height, width = struct.unpack_from("<II", data, obj + 0x18)
        mips = struct.unpack_from("<I", data, obj + 0x28)[0]
        fmt = struct.unpack_from("<I", data, obj + 0x34)[0]
        image = _pointer(data, obj + 0x38)
        if fmt not in PICA:
            raise ValueError(f"CGFX pixel format {fmt} is not supported")
        out.append({"name": name, "codec": pixels.codec("pica:" + PICA[fmt]), "format": PICA[fmt],
                    "at": _pointer(data, image + 12), "width": width, "height": height, "mips": max(1, mips)})
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
