"""Grezzo CTXB texture files (Ocarina of Time 3D, Majora's Mask 3D): PICA textures named by GL enums.

``ctxb``, u32 file size, u32 chunk count, u32 0, u32 chunk offset, u32 data offset; the ``tex `` chunk:
u32 size, u32 count, then 36 bytes per texture: u32 data size, u16 mips, u8 is ETC, u8 cube, u16
width, u16 height, u16 GL format, u16 GL type, u32 data offset (from the data offset), 16-byte name.
Rows are stored top first (unlike BFLIM).

A CMB model (``cmb ``) keeps its textures the same way: its header's chunk offsets end with the
texture data offset (the u32 before the first chunk, ``skl ``), and one of them points at ``tex ``.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.texture_formats import Texture, pixels, surface

FORMATS = {(0x6752, 0x1401): "RGBA8", (0x6752, 0x8033): "RGBA4", (0x6752, 0x8034): "RGBA5551",
           (0x6754, 0x1401): "RGB8", (0x6754, 0x8363): "RGB565", (0x6756, 0x1401): "A8", (0x6757, 0x1401): "L8",
           (0x6758, 0x1401): "LA8", (0x6758, 0x6760): "LA4", (0x6757, 0x6761): "L4", (0x6756, 0x6761): "A4",
           (0x675A, 0x1401): "ETC1", (0x675B, 0x1401): "ETC1A4", (0x675A, 0): "ETC1", (0x675B, 0): "ETC1A4"}


def detect(data: bytes) -> bool:
    return data[:4] in (b"ctxb", b"cmb ")


def _chunks(data: bytes) -> Tuple[int, int]:
    """``(tex chunk offset, texture data offset)`` of a CTXB file or a CMB model."""
    if data[:4] == b"ctxb":
        return struct.unpack_from("<II", data, 0x10)
    if data[:4] != b"cmb ":
        raise ValueError("Not a CTXB texture file or CMB model")
    first = struct.unpack_from("<I", data, 0x24)[0]     # the skeleton chunk follows the header
    header = struct.unpack_from(f"<{(first - 0x24) // 4}I", data, 0x24)
    chunk = next((at for at in header if data[at:at + 4] == b"tex "), None)
    if chunk is None:
        raise ValueError("CMB model without a texture chunk")
    return chunk, header[-1]


def _entries(data: bytes) -> List[Dict[str, Any]]:
    chunk, base = _chunks(data)
    count = struct.unpack_from("<I", data, chunk + 8)[0]
    out = []
    for index in range(count):
        at = chunk + 12 + index * 36
        _size, mips, _etc, _cube, width, height, gl_format, gl_type, offset = struct.unpack_from("<IHBBHHHHI", data, at)
        name = data[at + 20:at + 36].split(b"\0")[0].decode("ascii", "replace")
        fmt = FORMATS.get((gl_format, gl_type)) or FORMATS.get((gl_format, 0))
        if fmt is None:
            raise ValueError(f"CTXB texture {name}: GL format {gl_format:#06x}/{gl_type:#06x} is not supported")
        out.append({"name": name, "format": fmt, "codec": pixels.codec("pica:" + fmt), "width": width,
                    "height": height, "at": base + offset, "mips": max(1, mips)})
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
