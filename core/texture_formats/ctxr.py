"""Metal Gear Solid 2 / 3 Master Collection ``.ctxr`` pictures, Switch build: an NVN texture file (XTX).

``DFvN`` header (0x10), then blocks, each ``HBvN`` + u32 header size, u64 data size, u64 data offset (from the
block), u32 type: 2 = texture info, 3 = pixel data, 5 = an end mark. The info (0x78 bytes): u64 data size, u32
alignment, width, height, depth, target, NVN format, mip count, slice size, 17 u32 mip offsets (from the pixel
data), then (at 0x6C) the block height (log2) of the block-linear layout. Mips follow the same rule as BNTX. The PC build's
``.ctxr`` is another container and is not read here.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface, tegra

_ASTC = {0x79 + i: f"ASTC{w}x{h}" for i, (w, h) in enumerate(pixels.ASTC_BLOCKS)}
_ASTC.update({0x79 + len(pixels.ASTC_BLOCKS) + i: name for i, name in enumerate(list(_ASTC.values()))})   # sRGB
FORMATS = {0x01: "L8", 0x25: "RGBA8", 0x38: "RGBA8", 0x6D: "RGBA8", 0x42: "BC1", 0x43: "BC2", 0x44: "BC3",
           0x46: "BC1", 0x47: "BC2", 0x48: "BC3", 0x49: "BC4", 0x4B: "BC5", 0x4D: "BC7", 0x4E: "BC7", **_ASTC}


def detect(data: bytes) -> bool:
    return data[:4] == b"DFvN"


def _blocks(data: bytes):
    """``[(type, data offset, data size)]``."""
    if data[:4] != b"DFvN":
        raise ValueError("Not a Switch .ctxr (no DFvN header): the PC .ctxr is not supported yet")
    out, at = [], struct.unpack_from("<I", data, 4)[0]
    while at + 0x24 <= len(data) and data[at:at + 4] == b"HBvN":
        size, offset = struct.unpack_from("<QQ", data, at + 8)
        kind = struct.unpack_from("<I", data, at + 0x18)[0]
        out.append((kind, at + offset, size))
        at += offset + size
    return out


def _textures(data: bytes) -> List[Dict[str, Any]]:
    blocks = _blocks(data)
    infos = [b for b in blocks if b[0] == 2]
    pixels_at = [b for b in blocks if b[0] == 3]
    out = []
    for (_kind, info, _size), (_k, base, _s) in zip(infos, pixels_at):
        width, height, _depth, _target, fmt, mips = struct.unpack_from("<IIIIII", data, info + 0xC)
        offsets = struct.unpack_from("<17I", data, info + 0x28)
        block_log2 = struct.unpack_from("<I", data, info + 0x6C)[0] & 7
        out.append({"format": fmt, "width": width, "height": height, "block_log2": block_log2,
                    "levels": [base + offsets[level] for level in range(max(1, mips))]})
    return out


def _codec(texture: Dict[str, Any]) -> pixels.Codec:
    fmt = texture["format"]
    if fmt not in FORMATS:
        raise ValueError(f".ctxr: NVN format {fmt:#x} is not supported yet")
    return pixels.codec(FORMATS[fmt])


def _layouts(texture: Dict[str, Any], codec: pixels.Codec):
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
            out.append(Texture("", Image.new("RGBA", (texture["width"], texture["height"])),
                               f"NVN {fmt:#x} (not supported)", len(texture["levels"])))
            continue
        codec = _codec(texture)
        at, width, height, offsets = _layouts(texture, codec)[0]
        out.append(Texture("", surface.read(data, at, codec, width, height, offsets), FORMATS[fmt],
                           len(texture["levels"])))
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
