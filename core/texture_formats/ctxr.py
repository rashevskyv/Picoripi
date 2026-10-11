"""Metal Gear Solid 2 / 3 Master Collection ``.ctxr`` pictures, Switch build: an NVN texture file (XTX).

``DFvN`` header (0x10), then blocks, each ``HBvN`` + u32 header size, u64 data size, u64 data offset (from the
block), u32 type: 2 = texture info, 3 = pixel data, 5 = an end mark. The info (0x78 bytes): u64 data size, u32
alignment, width, height, depth, target, NVN format, mip count, slice size, 17 u32 mip offsets (from the pixel
data), then (at 0x6C) the block height (log2) of the block-linear layout. Mips follow the same rule as BNTX. The PC build's
``.ctxr`` is another container (TXTR version 7, below).
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
        raise ValueError("Not a Switch .ctxr (no DFvN header)")
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


# -- PC (Steam) build: a "TXTR" container, big-endian header of 0x28 bytes, pixel data at 0x84 ---------------------
# Header: u32 "TXTR", u32 version 7, u16 width, u16 height, u16 depth, u16 ?, u16 pixel format, u16 ?, ... byte
# mip count at 0x26. At 0x80 (aligned) a big-endian u32 size; the pixel data follows at 0x84: A8R8G8B8 (BGRA, one
# level, rows in order) or DXT1/3/5 blocks with the mip levels one after another (DDS-like, as the codec reads them).
PC_FORMATS = {0x0: "BGRA8", 0x5: "BC1", 0x6: "BC2", 0x7: "BC3"}
PC_DATA = 0x84


def detect_pc(data: bytes) -> bool:
    return data[:4] == b"TXTR"


def _pc_texture(data: bytes) -> Dict[str, Any]:
    if data[:4] != b"TXTR" or struct.unpack_from(">I", data, 4)[0] != 7:
        raise ValueError("Not a PC .ctxr (TXTR version 7)")
    width, height = struct.unpack_from(">HH", data, 8)
    fmt = struct.unpack_from(">H", data, 16)[0]
    mips = max(1, data[0x26])
    if fmt not in PC_FORMATS:
        raise ValueError(f"PC .ctxr: pixel format {fmt:#x} is not supported yet")
    codec = pixels.codec(PC_FORMATS[fmt])
    levels, at = [], PC_DATA
    for level in range(mips):
        w, h = max(1, width >> level), max(1, height >> level)
        levels.append((at, w, h))
        if fmt == 0x0:
            at += w * h * 4
        else:
            at += max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * codec.size
    return {"format": fmt, "codec": codec, "levels": levels}


def _pc_read(data: bytes) -> List[Texture]:
    tex = _pc_texture(data)
    at, width, height = tex["levels"][0]
    image = surface.read(data, at, tex["codec"], width, height, None)
    return [Texture("", image, PC_FORMATS[tex["format"]], len(tex["levels"]))]


def _pc_write(data: bytes, images: Dict[int, Image.Image]) -> bytes:
    tex = _pc_texture(data)
    out = bytearray(data)
    for index, image in images.items():
        if index:
            raise ValueError("PC .ctxr holds one texture")
        at, width, height = tex["levels"][0]
        if surface.write(out, at, tex["codec"], width, height, image, None) == 0:
            continue
        for (lat, lw, lh), level in zip(tex["levels"][1:], surface.mip_levels(image.convert("RGBA"),
                                                                              len(tex["levels"]))[1:]):
            surface.write(out, lat, tex["codec"], lw, lh, level, None)
    return bytes(out)


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    if detect_pc(data):
        return _pc_read(data)
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
    if detect_pc(data):
        return _pc_write(data, images)
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
