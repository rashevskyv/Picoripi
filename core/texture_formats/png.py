"""A texture kept as a PNG file by the workspace scripts (the game's own encoding is done when the game is built).

Unity games (Pokémon Brilliant Diamond / Shining Pearl) keep their textures inside AssetBundles; ``1_unpack.bat``
decodes each one to a PNG with UnityPy and ``2_build.bat`` encodes an edited PNG back into the texture's own
format (ASTC, DXT5, ...). Here a PNG is one RGBA texture; writing an unchanged image gives the original bytes back.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture

MAGIC = b"\x89PNG\r\n\x1a\n"


def detect(data: bytes) -> bool:
    return bytes(data[:8]) == MAGIC


def _image(data: bytes) -> Image.Image:
    if not detect(data):
        raise ValueError("Not a PNG file")
    return Image.open(io.BytesIO(data)).convert("RGBA")


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    return [Texture("", _image(data), "PNG RGBA")]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    image = images.get(0)
    if image is None:
        return bytes(data)
    current = _image(data)
    image = image.convert("RGBA")
    if image.size != current.size:
        raise ValueError(f"The image is {image.width}x{image.height}, the texture {current.width}x{current.height}")
    if image.tobytes() == current.tobytes():
        return bytes(data)
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()
