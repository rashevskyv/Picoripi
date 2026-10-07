"""GameCube / Wii J3D models (BMD / BDL, ``J3D2bmd3`` / ``J3D2bdl4``): the textures of the TEX1 section.

TEX1: magic, u32 size, u16 count, u16, u32 header table offset, u32 name table offset (both from the section
start). Each header is a 32-byte BTI header whose palette and data offsets count from that header, so the
pixels are the BTI ones (``bti``). Names: u16 count, u16, then (u16 hash, u16 offset) pairs, offsets from the
name table, null-terminated strings. Only the pixels change; the model and its other sections stay as they are.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.texture_formats import Texture, bti


def detect(data: bytes) -> bool:
    return data[:4] == b"J3D2" and data[4:8] in (b"bmd3", b"bdl4", b"bmd2")


def _tex1(data: bytes) -> Tuple[List[Dict[str, int]], List[str]]:
    if not detect(data):
        raise ValueError("Not a J3D model")
    at = 0x20
    while at + 8 <= len(data):
        tag, size = data[at:at + 4], struct.unpack_from(">I", data, at + 4)[0]
        if tag == b"TEX1":
            count, _pad, table, names_at = struct.unpack_from(">HHII", data, at + 8)
            heads = [bti._header(data, at + table + 32 * index) for index in range(count)]
            names = [""] * count
            if names_at:
                base = at + names_at
                for index in range(min(count, struct.unpack_from(">H", data, base)[0])):
                    offset = struct.unpack_from(">H", data, base + 4 + 4 * index + 2)[0]
                    end = data.index(b"\0", base + offset)
                    names[index] = data[base + offset:end].decode("ascii", "replace")
            return heads, names
        if size < 8:
            break
        at += size
    return [], []


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    heads, names = _tex1(data)
    return [Texture(name, bti.read_image(data, head), bti.FORMATS[head["format"]], head["mips"])
            for head, name in zip(heads, names)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    heads, _names = _tex1(data)
    out = bytearray(data)
    changed = False
    for index, image in images.items():
        changed = bti.write_image(out, heads[index], image) or changed
    return bytes(out) if changed else data
