"""Grezzo CTXB texture files (Ocarina of Time 3D, Majora's Mask 3D): PICA textures named by GL enums.

``ctxb``, u32 file size, u32 chunk count, u32 0, u32 chunk offset, u32 data offset; the ``tex `` chunk:
u32 size, u32 count, then 36 bytes per texture: u32 data size, u16 mips, u8 is ETC, u8 cube, u16
width, u16 height, u16 GL format, u16 GL type, u32 data offset (from the data offset), 16-byte name.
Rows are stored top first (unlike BFLIM).

A CMB model (``cmb ``) keeps its textures the same way: one of its header's chunk offsets (up to the
first chunk, ``skl ``) points at ``tex ``, and the largest is the texture data offset (the last one
in OoT3D's v6 header; MM3D's v10 header has a 0 after it).

A CMAB animation (``cmab``) with a texture pattern carries its own textures in a ``txpt`` chunk
(Majora's Mask 3D title copyright): u32 count, 24 bytes per texture (the fields above up to the data
offset, then a u32 index into the ``strt`` name table); the data offset counts from the u32 at 0x1C.
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
    return data[:4] in (b"ctxb", b"cmb ") or (data[:4] == b"cmab" and _cmab_txpt(data) > 0)


def _cmab_txpt(data: bytes) -> int:
    """Offset of a CMAB's ``txpt`` chunk (texture pattern with its own textures), or -1."""
    return data.find(b"txpt", 0x20, struct.unpack_from("<I", data, 0x1C)[0]) if len(data) >= 0x20 else -1


def _cmab_entries(data: bytes) -> List[Tuple[Tuple, str]]:
    """``(entry fields, name)`` of a CMAB's textures: 24-byte entries (the CTXB fields, then a u32
    index into the ``strt`` string table); the data offset is relative to the u32 at 0x1C."""
    chunk = _cmab_txpt(data)
    if chunk < 0:
        raise ValueError("CMAB animation without textures")
    base = struct.unpack_from("<I", data, 0x1C)[0]
    strt = data.find(b"strt", chunk, base)
    names_at = strt + 8 + 4 * struct.unpack_from("<I", data, strt + 4)[0] if strt > 0 else -1
    out = []
    for index in range(struct.unpack_from("<I", data, chunk + 4)[0]):
        fields = struct.unpack_from("<IHBBHHHHII", data, chunk + 8 + 24 * index)
        name = ""
        if names_at > 0:
            at = names_at + struct.unpack_from("<I", data, strt + 8 + 4 * fields[-1])[0]
            name = data[at:data.index(b"\0", at)].decode("ascii", "replace")
        out.append(((*fields[:8], base + fields[8]), name))
    return out


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
    return chunk, max(header)


def _raw_entries(data: bytes) -> List[Tuple[Tuple, str]]:
    if data[:4] == b"cmab":
        return _cmab_entries(data)
    chunk, base = _chunks(data)
    out = []
    for index in range(struct.unpack_from("<I", data, chunk + 8)[0]):
        at = chunk + 12 + index * 36
        fields = struct.unpack_from("<IHBBHHHHI", data, at)
        out.append(((*fields[:8], base + fields[8]), data[at + 20:at + 36].split(b"\0")[0].decode("ascii", "replace")))
    return out


def _entries(data: bytes) -> List[Dict[str, Any]]:
    out = []
    for (_size, mips, _etc, _cube, width, height, gl_format, gl_type, at), name in _raw_entries(data):
        fmt = FORMATS.get((gl_format, gl_type)) or FORMATS.get((gl_format, 0))
        if fmt is None:
            raise ValueError(f"CTXB texture {name}: GL format {gl_format:#06x}/{gl_type:#06x} is not supported")
        out.append({"name": name, "format": fmt, "codec": pixels.codec("pica:" + fmt), "width": width,
                    "height": height, "at": at, "mips": max(1, mips)})
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
