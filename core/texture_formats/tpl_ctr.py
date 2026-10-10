"""TPL files of the Xenoblade Chronicles 3D port (New 3DS): the Wii TPL layout little-endian (magic word
``0x0020AF30`` stored as ``30 AF 20 00``), each image a 3DS texture behind its own header.

Image header (LE): u16 height, u16 width (the Wii picture's size), u32 the Wii GX format, u32 offset of the
texture. Texture: ``!xtt``, u16 width, u16 height (powers of two, often smaller than the Wii picture), u8
mip count, u8 format code, u16 padding; ``xtrd``, u16 1, u16 4, u32 0x44, u32 data offset (counted from
``xtrd``), u32 data size. The data is a PICA texture stored bottom row first. Format codes: 0x23 RGBA4, 0x24 RGB565,
0x25 LA8, 0x28 ETC1, 0x2A A8 (the five the game uses). Sizes never change: a picture is written back into
its own texture.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

MAGIC = b"\x30\xaf\x20\x00"
CODES = {0x23: "RGBA4", 0x24: "RGB565", 0x25: "LA8", 0x28: "ETC1", 0x2A: "A8"}


def detect(data: bytes) -> bool:
    return data[:4] == MAGIC


def _textures(data: bytes) -> List[Dict[str, Any]]:
    if data[:4] != MAGIC:
        raise ValueError("Not a 3DS TPL")
    count, table = struct.unpack_from("<II", data, 4)
    out = []
    for index in range(count):
        head = struct.unpack_from("<I", data, table + 8 * index)[0]
        at = struct.unpack_from("<I", data, head + 8)[0]
        if data[at:at + 4] != b"!xtt":
            raise ValueError("3DS TPL image without its texture header")
        width, height, _mips, code = struct.unpack_from("<HHBB", data, at + 4)
        if code not in CODES:
            raise ValueError(f"3DS TPL texture code {code:#x} is not supported")
        base = at + 0x0C + struct.unpack_from("<I", data, at + 0x18)[0]
        out.append({"codec": pixels.codec("pica:" + CODES[code]), "format": CODES[code], "at": base,
                    "width": width, "height": height})
    return out


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    return [Texture(str(i), surface.read(data, t["at"], t["codec"], t["width"], t["height"])
                    .transpose(Image.Transpose.FLIP_TOP_BOTTOM), t["format"])
            for i, t in enumerate(_textures(data))]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    textures = _textures(data)
    changed = 0
    for index, image in images.items():
        t = textures[index]
        changed += surface.write(out, t["at"], t["codec"], t["width"], t["height"],
                                 image.convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM))
    return bytes(out) if changed else data
