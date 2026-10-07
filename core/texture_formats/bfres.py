"""Wii U BFRES (``FRES`` 3.x, big endian) textures: the ``FTEX`` entries of the texture index group, e.g. the
UI pictures of Paper Mario: Color Splash (``Graphics/UI/**/*.bfres``).

Header: ``FRES``, version, BOM, ..., 12 index group offsets at 0x20 (each relative to its own field; group 1 holds
the textures). An index group: u32 size, s32 count, then count + 1 nodes of 16 bytes (the first is the root):
u32 search value, u16 left, u16 right, s32 name offset, s32 data offset (both relative to their field).
``FTEX``: the GX2Surface at +4 (dim, width, height, depth, mip count, format, ..., tile mode @+0x34, swizzle
@+0x38, mip offsets @+0x44), channel selection @+0x88, then name @+0xA8, image @+0xB0 and mip data @+0xB4
(relative offsets). The surface is the GTX one, so ``gtx`` draws and writes it (mip levels redrawn).

Listed are the plain 2D textures (UNORM / SRGB); a cube map or an SNORM texture (normal maps) is left out.
Writing changes the pixel data in place; the file keeps its size and every other byte.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, gtx

_SNORM = 0x200


def detect(data: bytes) -> bool:
    return data[:4] == b"FRES" and data[8:10] == b"\xfe\xff"


def _rel(data: bytes, at: int) -> int:
    return at + struct.unpack_from(">i", data, at)[0]


def _heads(data: bytes) -> List[Dict[str, Any]]:
    if not detect(data):
        raise ValueError("Not a Wii U BFRES file")
    if not struct.unpack_from(">i", data, 0x24)[0]:
        return []
    group = _rel(data, 0x24)
    heads = []
    for node in range(group + 8 + 16, group + 8 + 16 * (struct.unpack_from(">i", data, group + 4)[0] + 1), 16):
        at = _rel(data, node + 12)
        if data[at:at + 4] != b"FTEX":
            raise ValueError("BFRES texture entry is not an FTEX")
        dim, width, height, _depth, mips, fmt = struct.unpack_from(">6I", data, at + 4)
        if dim != 1 or fmt & _SNORM:
            continue
        name_at = _rel(data, at + 0xA8)
        mip_size = struct.unpack_from(">I", data, at + 4 + 0x28)[0]
        heads.append({"name": data[name_at:data.index(b"\0", name_at)].decode("utf-8", "replace"),
                      "width": width, "height": height, "mips": max(1, mips), "format": fmt & 0x3F,
                      "tile": struct.unpack_from(">I", data, at + 0x34)[0],
                      "swizzle": struct.unpack_from(">I", data, at + 0x38)[0],
                      "select": data[at + 0x88:at + 0x8C], "data": _rel(data, at + 0xB0),
                      "mip_offsets": struct.unpack_from(">13I", data, at + 0x44),
                      "mip_data": _rel(data, at + 0xB4) if mip_size and mips > 1 else None})
    return heads


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    return gtx.read_surfaces(data, _heads(data))


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    return gtx.write_surfaces(data, _heads(data), images)
