"""Capcom MT Framework Mobile ``TEX`` textures (3DS: Monster Hunter 3 Ultimate, 4 Ultimate, Stories).

Header (little endian, 16 bytes): ``TEX\\0``; u32 version and flags; u32 ``mips | width << 6 | height << 19``
(6, 13 and 13 bits); u32 with the pixel format in bits 8-15. Then one u32 per mip level: its offset from the end
of this table. Levels are PICA textures, top row first, 8x8 Morton tiles. Pixel formats: 1 RGBA4, 2 RGBA5551,
3 RGBA8, 4 RGB565, 5 A8, 6 L8, 7 LA8, 11 ETC1, 12 ETC1A4, 14 A4, 15 L4, 16 LA4, 17 RGB8. Cube maps (six faces,
the sizes do not add up) are not read.

The Switch version (Monster Hunter Stories) has the version word ``0xB0A3 | 0x20 << 24`` and the same shape word.
The table that follows is the byte size of all levels and then one offset per level (from the end of the table).
Levels are Tegra block-linear surfaces (block height from the number of block rows, as the BNTX rule), top row
first. Pixel formats (bits 8-15 of the fourth word): 19 BC1, 42 and 54 BC7, 7 RGBA8.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface, tegra

SWITCH_VERSION = 0x2000B0A3
NX_FORMATS = {19: "BC1", 42: "BC7", 54: "BC7", 7: "RGBA8"}

PICA = {1: "RGBA4", 2: "RGBA5551", 3: "RGBA8", 4: "RGB565", 5: "A8", 6: "L8", 7: "LA8", 11: "ETC1", 12: "ETC1A4",
        14: "A4", 15: "L4", 16: "LA4", 17: "RGB8"}


def detect(data: bytes) -> bool:
    return data[:4] == b"TEX\0" and len(data) >= 0x14


def _block_height(rows: int) -> int:
    height = 1
    while height < 16 and height * 8 < rows:
        height *= 2
    return height


def _nx_levels(data: bytes) -> Dict[str, Any]:
    shape, info = struct.unpack_from("<II", data, 8)
    mips, width, height, fmt = shape & 0x3F, (shape >> 6) & 0x1FFF, (shape >> 19) & 0x1FFF, (info >> 8) & 0xFF
    if fmt not in NX_FORMATS:
        raise ValueError(f"MT TEX pixel format {fmt} is not supported")
    if not mips or not width or not height:
        raise ValueError("MT TEX without a picture")
    codec = pixels.codec(NX_FORMATS[fmt])
    total, *offsets = struct.unpack_from(f"<{mips + 1}I", data, 16)
    base = 16 + 4 * (mips + 1)
    if base + total != len(data):
        raise ValueError("MT TEX sizes do not match the file (a cube map?)")
    bw_, bh_ = codec.block
    levels = []
    for level in range(mips):
        w, h = max(1, width >> level), max(1, height >> level)
        wide, high = -(-w // bw_), -(-h // bh_)
        addresses = tegra.block_addresses(wide, high, codec.size, _block_height(high))
        if base + offsets[level] + max(addresses) + codec.size > len(data):
            raise ValueError("MT TEX level does not fit the file")
        levels.append((base + offsets[level], w, h, addresses))
    return {"codec": codec, "format": NX_FORMATS[fmt], "width": width, "height": height, "levels": levels, "nx": True}


def _levels(data: bytes) -> Dict[str, Any]:
    if not detect(data):
        raise ValueError("Not an MT Framework TEX texture")
    if struct.unpack_from("<I", data, 4)[0] == SWITCH_VERSION:
        return _nx_levels(data)
    shape, info = struct.unpack_from("<II", data, 8)
    mips, width, height, fmt = shape & 0x3F, (shape >> 6) & 0x1FFF, (shape >> 19) & 0x1FFF, (info >> 8) & 0xFF
    if fmt not in PICA:
        raise ValueError(f"MT TEX pixel format {fmt} is not supported")
    if not mips or not width or not height:
        raise ValueError("MT TEX without a picture")
    codec = pixels.codec("pica:" + PICA[fmt])
    base = 16 + 4 * mips
    offsets = struct.unpack_from(f"<{mips}I", data, 16)
    levels = [(base + offsets[level], max(8, width >> level), max(8, height >> level)) for level in range(mips)]
    at, w, h = levels[-1]
    if at + surface.surface_bytes(codec, w, h) != len(data):
        raise ValueError("MT TEX sizes do not match the file (a cube map?)")
    return {"codec": codec, "format": PICA[fmt], "width": width, "height": height, "levels": levels}


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    tex = _levels(data)
    if tex.get("nx"):
        at, w, h, addresses = tex["levels"][0]
        image = surface.read(data, at, tex["codec"], w, h, addresses)
    else:
        at, _w, _h = tex["levels"][0]
        image = surface.read(data, at, tex["codec"], tex["width"], tex["height"])
    return [Texture("", image, tex["format"], len(tex["levels"]))]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    tex = _levels(data)
    image = images.get(0)
    if image is None:
        return bytes(out)
    if tex.get("nx"):
        (at, width, height, addresses), rest = tex["levels"][0], tex["levels"][1:]
        if surface.write(out, at, tex["codec"], width, height, image, addresses) == 0:
            return bytes(out)
        for (at, width, height, addresses), level in zip(
                rest, surface.mip_levels(image.convert("RGBA"), len(tex["levels"]))[1:]):
            surface.write(out, at, tex["codec"], width, height, level.resize((width, height)), addresses, force=True)
        return bytes(out)
    (at, width, height), rest = tex["levels"][0], tex["levels"][1:]
    if surface.write(out, at, tex["codec"], tex["width"], tex["height"], image) == 0:
        return bytes(out)
    for (at, width, height), level in zip(rest, surface.mip_levels(image.convert("RGBA"), len(tex["levels"]))[1:]):
        surface.write(out, at, tex["codec"], width, height, level.resize((width, height)))
    return bytes(out)
