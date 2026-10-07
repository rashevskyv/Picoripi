"""Switch BNTX: a texture container (``BNTX`` + ``NX  ``) of BRTI textures in block-linear layout.

``NX  `` at 0x20: u32 texture count, u64 offset of the BRTI pointer table. BRTI: u16 mip count at
0x16, u32 format at 0x1C (high byte the pixel format, low byte its type), width, height, depth,
layers and layout (block height log2 in the low bits) at 0x24, u64 name at 0x60, u64 offset of the
mip-level pointer table at 0x70. Offsets count from the start of the BNTX. A mip level shorter than
a block uses smaller blocks (the block height halves once per such level).

ASTC 4x4 reads and writes; ASTC 8x8 and 12x12 (TotK's map tiles) only read; BC6H and the other ASTC
block sizes are listed but cannot be decoded yet.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface, tegra

_ASTC = {0x2D + i: f"ASTC{w}x{h}" for i, (w, h) in enumerate(
    ((4, 4), (5, 4), (5, 5), (6, 5), (6, 6), (8, 5), (8, 6), (8, 8), (10, 5), (10, 6), (10, 8), (10, 10),
     (12, 10), (12, 12)))}
FORMATS = {0x02: "L8", 0x07: "RGB565", 0x09: "LA8", 0x0B: "RGBA8", 0x0C: "BGRA8", 0x1A: "BC1", 0x1B: "BC2",
           0x1C: "BC3", 0x1D: "BC4", 0x1E: "BC5", 0x20: "BC7",
           **{fmt: name for fmt, name in _ASTC.items() if name in ("ASTC4x4", "ASTC8x8", "ASTC12x12")}}
_UNSUPPORTED = {0x1F: "BC6H", **{fmt: name for fmt, name in _ASTC.items() if fmt not in FORMATS}}


def detect(data: bytes) -> bool:
    return data[:4] == b"BNTX"


def _textures(data: bytes) -> List[Dict[str, Any]]:
    if data[:4] != b"BNTX":
        raise ValueError("Not a BNTX texture container")
    count, table = struct.unpack_from("<IQ", data, 0x24)
    out = []
    for index in range(count):
        brti = struct.unpack_from("<Q", data, table + 8 * index)[0]
        mips = struct.unpack_from("<H", data, brti + 0x16)[0]
        fmt = struct.unpack_from("<I", data, brti + 0x1C)[0] >> 8
        width, height, _depth, _layers, layout = struct.unpack_from("<iiiii", data, brti + 0x24)
        name_at = struct.unpack_from("<Q", data, brti + 0x60)[0]
        name = data[name_at + 2:name_at + 2 + struct.unpack_from("<H", data, name_at)[0]].decode("utf-8", "replace")
        pointers = struct.unpack_from("<Q", data, brti + 0x70)[0]
        levels = [struct.unpack_from("<Q", data, pointers + 8 * level)[0] for level in range(max(1, mips))]
        out.append({"name": name, "format": fmt, "width": width, "height": height, "levels": levels,
                    "block_log2": layout & 7})
    return out


def _codec(texture: Dict[str, Any]) -> pixels.Codec:
    fmt = texture["format"]
    if fmt not in FORMATS:
        raise ValueError(f"BNTX texture {texture['name']}: {_UNSUPPORTED.get(fmt, hex(fmt))} is not supported yet")
    return pixels.codec(FORMATS[fmt])


def _layouts(texture: Dict[str, Any], codec: pixels.Codec):
    """``(offset, width, height, element offsets)`` of every mip level."""
    bw, bh = codec.block
    lines = 8 << texture["block_log2"]
    shift, out = 0, []
    for level, at in enumerate(texture["levels"]):
        width, height = max(1, texture["width"] >> level), max(1, texture["height"] >> level)
        wide, high = -(-width // bw), -(-height // bh)
        if level and 1 << (high - 1).bit_length() < lines:
            shift += 1
        block_height = 1 << max(0, texture["block_log2"] - shift)
        out.append((at, width, height, tegra.block_addresses(wide, high, codec.size, block_height)))
    return out


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    out = []
    for texture in _textures(data):
        fmt = texture["format"]
        if fmt not in FORMATS:
            image = Image.new("RGBA", (texture["width"], texture["height"]))
            out.append(Texture(texture["name"], image, _UNSUPPORTED.get(fmt, hex(fmt)) + " (not supported)",
                               len(texture["levels"])))
            continue
        codec = _codec(texture)
        at, width, height, offsets = _layouts(texture, codec)[0]
        out.append(Texture(texture["name"], surface.read(data, at, codec, width, height, offsets),
                           FORMATS[fmt], len(texture["levels"])))
    return out


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    textures = _textures(data)
    for index, image in images.items():
        texture = textures[index]
        codec = _codec(texture)
        levels = _layouts(texture, codec)
        at, width, height, offsets = levels[0]
        if surface.write(out, at, codec, width, height, image, offsets) == 0:
            continue
        for (at, width, height, offsets), level in zip(levels[1:], surface.mip_levels(image.convert("RGBA"),
                                                                                      len(levels))[1:]):
            surface.write(out, at, codec, width, height, level, offsets)
    return bytes(out)
