"""PNG pictures used as they are: the graphics sources of a decompilation (pret pokered's ``gfx/*.png``,
which its build turns into Game Boy tiles with rgbgfx).

Read: the picture as RGBA. Write: the picture saved in the original's colour mode, so the game's tool reads
it the same way: a 1-bit picture stays 1-bit; a grey one stays grey, each pixel rounded to one of
``params["levels"]`` evenly spaced greys when given (4 for the Game Boy's shades); a palette picture takes
the nearest colour of its palette; transparent pixels count as white in grey and 1-bit pictures. An
unchanged picture gives the original bytes back.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture

MAGIC = b"\x89PNG\r\n\x1a\n"


def _is_png(data: bytes) -> bool:
    return data[:8] == MAGIC


def _open(data: bytes) -> Image.Image:
    if not _is_png(data):
        raise ValueError("Not a PNG file")
    return Image.open(io.BytesIO(data))


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    image = _open(data)
    return [Texture("", image.convert("RGBA"), f"PNG {image.mode}")]


def _on_white(image: Image.Image) -> Image.Image:
    white = Image.new("RGBA", image.size, (255, 255, 255, 255))
    return Image.alpha_composite(white, image.convert("RGBA"))


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    image = images.get(0)
    if image is None:
        return data
    old = _open(data)
    if image.size != old.size:
        raise ValueError(f"The image is {image.width}x{image.height}, the texture {old.width}x{old.height}")
    if image.convert("RGBA").tobytes() == old.convert("RGBA").tobytes():
        return data
    if old.mode == "1":
        new = _on_white(image).convert("L").point(lambda v: 255 if v >= 128 else 0).convert("1")
    elif old.mode in ("L", "LA", "I", "I;16"):
        new = _on_white(image).convert("L")
        levels = int(params.get("levels") or 0)
        if levels > 1:
            step = 255 / (levels - 1)
            new = new.point(lambda v: int(round(round(v / step) * step)))
    elif old.mode == "P":
        new = _on_white(image).convert("RGB").quantize(palette=old, dither=Image.Dither.NONE)
    else:
        new = image.convert(old.mode)
    stream = io.BytesIO()
    new.save(stream, "PNG")
    return stream.getvalue()
