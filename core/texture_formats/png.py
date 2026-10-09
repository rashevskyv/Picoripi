"""PNG pictures that a build turns into game data itself (pret decompilations: ``rgbgfx`` makes Game Boy tiles).

One texture: the image. Writing keeps the file's kind so the build tool reads it the same way: a greyscale
picture stays greyscale with each pixel snapped to the nearest of the ``2 ** bit depth`` grey levels it can
hold (a Game Boy 2-bit picture keeps its four greys, also once saved as 8-bit by this module; a transparent
pixel turns white), a palette picture
keeps its palette (nearest colour), anything else is saved as RGBA. Writing the image ``read`` returned gives
the original bytes back.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture

_MAGIC = b"\x89PNG\r\n\x1a\n"


def detect(data: bytes) -> bool:
    return data[:8] == _MAGIC


def _open(data: bytes) -> Image.Image:
    if not detect(data):
        raise ValueError("Not a PNG file")
    return Image.open(io.BytesIO(data))


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    image = _open(data)
    return [Texture("", image.convert("RGBA"), f"png:{image.mode}")]


def _grey_levels(depth: int) -> List[int]:
    top = (1 << depth) - 1
    return [round(v * 255 / top) for v in range(top + 1)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    new = images.get(0)
    if new is None:
        return data
    original = _open(data)
    new = new.convert("RGBA")
    if new.size != original.size:
        raise ValueError(f"The image is {new.width}x{new.height}, the PNG {original.width}x{original.height}")
    if new.tobytes() == original.convert("RGBA").tobytes():
        return data
    white = Image.new("RGBA", new.size, (255, 255, 255, 255))
    flat = Image.alpha_composite(white, new)
    out = io.BytesIO()
    if original.mode in ("L", "LA", "1", "I", "I;16"):
        depth = min(data[24], 8) if original.mode != "1" else 1
        levels = _grey_levels(depth)
        used = {value for _count, value in original.convert("L").getcolors(256)}
        if depth == 8 and used <= set(_grey_levels(2)):
            levels = _grey_levels(2)
        table = [min(levels, key=lambda level: abs(level - value)) for value in range(256)]
        flat.convert("L").point(table).save(out, format="PNG")
    elif original.mode == "P":
        palette = Image.new("P", (1, 1))
        palette.putpalette(original.getpalette())
        flat.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE).save(out, format="PNG")
    else:
        new.save(out, format="PNG")
    return out.getvalue()
