"""Level-5 G4TX texture sets (Switch: Yo-kai Watch 4++, Yo-kai Academy Y): NXTCH textures, block-linear layout.

G4TX: a 0x60-byte header (u32 size of the tables after it at 0x0C, u16 texture count at 0x20, u16 count of
textures + sub-images at 0x22, u32 size of the texture data at 0x2C; the data follows the tables, aligned to 16
-- one file of the English Yo-kai Watch 4 mod has a wrong data size), a 0x30-byte entry per texture (u32
offset and u32 size of its NXTCH inside the data at +4), a 0x18-byte entry per sub-image (a rectangle of
a texture), then, aligned to 16, a CRC32 per name, one byte per name, and u16 offsets of the names
(textures first, then sub-images).

NXTCH: a 0x100-byte header, then the pixels: u32 size at 0x08, width at 0x14, height at 0x18, NVN format
at 0x24, mip count at 0x28, mip offsets (from the pixels) at 0x30, block height log2 at 0x74.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface
from core.texture_formats.bntx import _layouts as block_linear_layouts   # the same Tegra mip walk

FORMATS = {0x25: "RGBA8", 0x42: "BC1", 0x44: "BC3", 0x4D: "BC7"}   # NVN numbers seen in the games, checked by eye


def detect(data: bytes) -> bool:
    return data[:4] == b"G4TX"


def _names(data: bytes, count: int, total: int) -> List[str]:
    at = (0x60 + 0x30 * count + 0x18 * (total - count) + 15) & ~15
    at = (at + 5 * total + 3) & ~3                    # past the CRC32s and the byte per name
    names = []
    for index in range(total):
        start = at + struct.unpack_from("<H", data, at + 2 * index)[0]
        names.append(data[start:data.index(b"\0", start)].decode("utf-8", "replace"))
    return names


def _textures(data: bytes) -> List[Dict[str, Any]]:
    if data[:4] != b"G4TX":
        raise ValueError("Not a G4TX texture set")
    count, total = struct.unpack_from("<HH", data, 0x20)
    area = (0x60 + struct.unpack_from("<I", data, 0x0C)[0] + 15) & ~15   # the data follows the tables
    try:
        names = _names(data, count, total)
    except (struct.error, ValueError):
        names = [str(index) for index in range(count)]
    out = []
    for index in range(count):
        nxtch = area + struct.unpack_from("<I", data, 0x60 + 0x30 * index + 4)[0]
        if data[nxtch:nxtch + 8] != b"NXTCH000":
            raise ValueError(f"G4TX texture {index}: no NXTCH header")
        width, height = struct.unpack_from("<II", data, nxtch + 0x14)
        fmt, mips = struct.unpack_from("<II", data, nxtch + 0x24)
        mips = max(1, mips)
        pixels_at = nxtch + 0x100
        levels = [pixels_at + struct.unpack_from("<I", data, nxtch + 0x30 + 4 * level)[0] for level in range(mips)]
        out.append({"name": names[index], "format": fmt, "width": width, "height": height, "levels": levels,
                    "block_log2": struct.unpack_from("<I", data, nxtch + 0x74)[0]})
    return out


def _codec(texture: Dict[str, Any]) -> pixels.Codec:
    if texture["format"] not in FORMATS:
        raise ValueError(f"G4TX texture {texture['name']}: NVN format {texture['format']:#x} is not supported yet")
    return pixels.codec(FORMATS[texture["format"]])


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    out = []
    for texture in _textures(data):
        if texture["format"] not in FORMATS:
            out.append(Texture(texture["name"], Image.new("RGBA", (texture["width"], texture["height"])),
                               f"{texture['format']:#x} (not supported)", len(texture["levels"])))
            continue
        codec = _codec(texture)
        at, width, height, offsets = block_linear_layouts(texture, codec)[0]
        out.append(Texture(texture["name"], surface.read(data, at, codec, width, height, offsets),
                           FORMATS[texture["format"]], len(texture["levels"])))
    return out


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    textures = _textures(data)
    for index, image in images.items():
        texture = textures[index]
        codec = _codec(texture)
        levels = block_linear_layouts(texture, codec)
        at, width, height, offsets = levels[0]
        if surface.write(out, at, codec, width, height, image, offsets) == 0:
            continue
        for (at, width, height, offsets), level in zip(levels[1:], surface.mip_levels(image.convert("RGBA"),
                                                                                      len(levels))[1:]):
            surface.write(out, at, codec, width, height, level, offsets)
    return bytes(out)
