"""Dragon Quest VII (3DS) ``DMP`` textures: a 16-byte header and one PICA-tiled surface.

Header: ``DMP`` + a version byte, a 4-character pixel format (``8888``, ``5551``, ``5650``...), then u16 picture
width and height (the part the game shows) and u16 surface width and height (powers of two). The screens
(``SCREENTEX``) are cut into 64x64 tiles kept in ``FPT0`` packs; the layout textures (``LAYOUTTEX``) are whole.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

FORMATS = {b"8888": "RGBA8", b"8880": "RGB8", b"5551": "RGBA5551", b"5650": "RGB565", b"4444": "RGBA4",
           b"LA88": "LA8", b"LA44": "LA4", b"L8  ": "L8", b"A8  ": "A8", b"L4  ": "L4", b"A4  ": "A4",
           b"ETC1": "ETC1", b"ETCA": "ETC1A4"}


def detect(data: bytes) -> bool:
    return len(data) >= 16 and data[:3] == b"DMP" and data[4:8] in FORMATS


def _info(data: bytes) -> Dict[str, Any]:
    if not detect(data):
        raise ValueError("Not a DMP texture")
    width, height, stored_w, stored_h = struct.unpack_from("<HHHH", data, 8)
    name = FORMATS[data[4:8]]
    return {"width": width, "height": height, "stored_w": stored_w, "stored_h": stored_h, "format": name,
            "codec": pixels.codec("pica:" + name)}


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    info = _info(data)
    full = surface.read(data, 16, info["codec"], info["stored_w"], info["stored_h"])
    return [Texture("", full.crop((0, 0, info["width"], info["height"])), info["format"])]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    image = images.get(0)
    if image is None:
        return data
    info = _info(data)
    full = surface.read(data, 16, info["codec"], info["stored_w"], info["stored_h"])
    full.paste(image.convert("RGBA"), (0, 0))
    out = bytearray(data)
    surface.write(out, 16, info["codec"], info["stored_w"], info["stored_h"], full)
    return bytes(out)
