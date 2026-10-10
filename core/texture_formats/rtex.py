"""Agatsuma ``RTEX`` textures (Code of Princess, 3DS ``.rtx``): a 0x20-byte header and one PICA texture.

Header (little endian): ``RTEX``, u32 0, u16 width, height (the picture), u16 stored width, height (the texture:
powers of two), u32 data offset (0x20), u32 data size, u16 pixel format (13: RGBA4, 0x1002: ETC1A4), u16 0x10,
u32 pitch, u32 average colour. The texture is stored bottom row first, so the picture is the top-left
``width`` x ``height`` of the flipped texture.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

FORMATS = {13: "RGBA4", 0x1002: "ETC1A4"}


def detect(data: bytes) -> bool:
    return len(data) >= 0x20 and data[:4] == b"RTEX" and struct.unpack_from("<H", data, 0x18)[0] in FORMATS


def _info(data: bytes) -> Dict[str, Any]:
    if not detect(data):
        raise ValueError("Not an RTEX texture of a known pixel format")
    width, height, stored_w, stored_h, at, _size, fmt = struct.unpack_from("<HHHHIIH", data, 8)
    name = FORMATS[fmt]
    return {"width": width, "height": height, "stored_w": stored_w, "stored_h": stored_h, "at": at,
            "format": name, "codec": pixels.codec("pica:" + name)}


def _full(data: bytes, info: Dict[str, Any]) -> Image.Image:
    return surface.read(data, info["at"], info["codec"], info["stored_w"], info["stored_h"]).transpose(
        Image.Transpose.FLIP_TOP_BOTTOM)


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    info = _info(data)
    full = _full(data, info)
    return [Texture("", full.crop((0, 0, info["width"], info["height"])), info["format"])]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    image = images.get(0)
    if image is None:
        return data
    info = _info(data)
    full = _full(data, info)
    full.paste(image.convert("RGBA"), (0, 0))
    out = bytearray(data)
    surface.write(out, info["at"], info["codec"], info["stored_w"], info["stored_h"],
                  full.transpose(Image.Transpose.FLIP_TOP_BOTTOM))
    return bytes(out)
