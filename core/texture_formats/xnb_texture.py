"""A MonoGame ``Texture2D`` in an uncompressed ``.xnb`` file (the game's menu pictures, e.g. Link's Awakening DX HD).

One texture, one mip. The surface format is RGBA8 (MonoGame Color, format 0) or DXT3 (format 5); other formats
raise. Writing keeps the file's bytes except the pixels that changed: an unedited picture writes the same bytes.
"""
from __future__ import annotations

from typing import Any, Dict, List

from PIL import Image

from core.containers import xnb
from core.texture_formats import Texture, pixels, surface

_CODECS = {0: "RGBA8", 5: "BC2"}


def _open(data: bytes):
    """The parsed file and its Texture2D, or ValueError when the file is not a Texture2D."""
    parsed = xnb.open_xnb(bytes(data))
    top = parsed.reader.v7()
    if "Texture2DReader" not in parsed.type_of(top):
        raise ValueError("not a Texture2D")
    texture = xnb.read_texture2d(parsed.reader)
    if parsed.reader.pos != len(data):
        raise ValueError("the Texture2D file has more data than one texture")
    if texture.surface_format not in _CODECS:
        raise ValueError(f"surface format {texture.surface_format} is not read here")
    return parsed.head + xnb.write7(top), texture


def detect(data: bytes) -> bool:
    try:
        _open(data)
    except (ValueError, IndexError):
        return False
    return True


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    _, texture = _open(data)
    codec = pixels.codec(_CODECS[texture.surface_format])
    image = surface.read(texture.mip, 0, codec, texture.width, texture.height).convert("RGBA")
    return [Texture("", image, f"xnb:{texture.surface_format}")]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    new = images.get(0)
    if new is None:
        return bytes(data)
    prefix, texture = _open(data)
    if new.size != (texture.width, texture.height):
        raise ValueError(f"The image is {new.width}x{new.height}, the texture {texture.width}x{texture.height}")
    codec = pixels.codec(_CODECS[texture.surface_format])
    mip = bytearray(texture.mip)
    surface.write(mip, 0, codec, texture.width, texture.height, new.convert("RGBA"))
    out = bytearray(prefix)
    out += xnb.write_texture2d(xnb.Texture2D(texture.surface_format, texture.width, texture.height, bytes(mip)))
    return xnb.finish(out)
