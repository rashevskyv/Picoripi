"""GameCube / Wii J3D models (BMD, BDL): the textures of the TEX1 section, e.g. a title logo drawn as a model.

File: ``J3D2bmd3`` / ``J3D2bdl4``, u32 size, u32 section count, then sections from 0x20 (tag, u32 size).
TEX1: u16 texture count, u32 header table offset, u32 name table offset (both from the section start).
Each texture header is a 0x20-byte BTI header whose palette and data offsets count from that header, so the
pixels are the BTI ones (``bti``). Name table: u16 count, pad, (u16 hash, u16 offset) per name, offsets from
the table start. Two headers may share one image; writing either changes both.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, bti


def detect(data: bytes) -> bool:
    return data[:4] == b"J3D2" and data[4:8] in (b"bmd2", b"bmd3", b"bdl4")


def _heads(data: bytes) -> List[tuple]:
    """``(name, BTI header)`` of every texture of the TEX1 section."""
    if not detect(data):
        raise ValueError("Not a J3D model (BMD / BDL)")
    at = 0x20
    for _ in range(struct.unpack_from(">I", data, 0xC)[0]):
        tag, size = struct.unpack_from(">4sI", data, at)
        if tag == b"TEX1":
            break
        at += size
    else:
        return []
    count, = struct.unpack_from(">H", data, at + 8)
    table, names_at = struct.unpack_from(">II", data, at + 0xC)
    names = []
    for index in range(count):
        offset = struct.unpack_from(">H", data, at + names_at + 6 + 4 * index)[0]
        start = at + names_at + offset
        names.append(data[start:data.index(b"\0", start)].decode("shift_jis", "replace"))
    return [(names[i], bti._header(data, at + table + 0x20 * i)) for i in range(count)]


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    return [Texture(name, bti.read_image(data, head), bti.FORMATS[head["format"]], head["mips"])
            for name, head in _heads(data)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    heads = _heads(data)
    changed = False
    for index, image in images.items():
        changed = bti.write_image(out, heads[index][1], image) or changed
    return bytes(out) if changed else data
