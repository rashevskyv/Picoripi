"""Koei Tecmo G1T texture sets (``GT1G``; Hyrule Warriors DE, Age of Calamity), linear layout.

Header: ``GT1G`` + version, u32 file size, u32 offset of the texture table, u32 texture count. A
texture: u8 mip count (high nibble), u8 format, u8 size (log2 width | log2 height << 4), flags; when
the last flag byte has 0x01 or 0x10 an extended header follows (u32 size first). Mip levels follow
level 0. Formats: BC1-BC5, BC7 and RGBA8.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

FORMATS = {0x01: "RGBA8", 0x09: "RGBA8", 0x59: "BC1", 0x5A: "BC2", 0x5B: "BC3", 0x5C: "BC4", 0x5D: "BC5",
           0x5F: "BC7"}


def detect(data: bytes) -> bool:
    return data[:4] == b"GT1G"


def _textures(data: bytes) -> List[Dict[str, Any]]:
    if data[:4] != b"GT1G":
        raise ValueError("Not a G1T texture set")
    table, count = struct.unpack_from("<II", data, 0x0C)
    out = []
    for index in range(count):
        at = table + struct.unpack_from("<I", data, table + 4 * index)[0]
        mips, fmt, dims = data[at] >> 4, data[at + 1], data[at + 2]
        header = 8 + (struct.unpack_from("<I", data, at + 8)[0] if data[at + 7] & 0x11 else 0)
        out.append({"format": fmt, "width": 1 << (dims & 0xF), "height": 1 << (dims >> 4),
                    "mips": max(1, mips), "at": at + header})
    return out


def _codec(texture: Dict[str, Any]) -> pixels.Codec:
    if texture["format"] not in FORMATS:
        raise ValueError(f"G1T texture format {texture['format']:#04x} is not supported")
    return pixels.codec(FORMATS[texture["format"]])


def _levels(texture: Dict[str, Any], codec: pixels.Codec):
    at, out = texture["at"], []
    for level in range(texture["mips"]):
        width, height = max(1, texture["width"] >> level), max(1, texture["height"] >> level)
        out.append((at, width, height))
        at += surface.surface_bytes(codec, width, height)
    return out


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    out = []
    for index, texture in enumerate(_textures(data)):
        name = str(index)
        if texture["format"] not in FORMATS:
            out.append(Texture(name, Image.new("RGBA", (texture["width"], texture["height"])),
                               f"{texture['format']:#04x} (not supported)", texture["mips"]))
            continue
        codec = _codec(texture)
        out.append(Texture(name, surface.read(data, texture["at"], codec, texture["width"], texture["height"]),
                           FORMATS[texture["format"]], texture["mips"]))
    return out


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    textures = _textures(data)
    for index, image in images.items():
        codec = _codec(textures[index])
        levels = _levels(textures[index], codec)
        at, width, height = levels[0]
        if surface.write(out, at, codec, width, height, image) == 0:
            continue
        for (at, width, height), level in zip(levels[1:], surface.mip_levels(image.convert("RGBA"), len(levels))[1:]):
            surface.write(out, at, codec, width, height, level)
    return bytes(out)
