"""A texture kept as a PNG file that a build tool turns into game data itself: the graphics sources of a
pret decompilation (``rgbgfx`` makes Game Boy tiles of ``gfx/*.png``) or the PNGs a workspace's
``1_unpack.bat`` decodes from Unity AssetBundles (Pokémon Brilliant Diamond / Shining Pearl; ``2_build.bat``
encodes an edited PNG back into ASTC, DXT5, ...).

One texture: the image as RGBA. Writing keeps the file's kind so the build tool reads it the same way: a
1-bit picture stays 1-bit; a greyscale picture stays greyscale with each pixel snapped to the nearest of the
``2 ** bit depth`` grey levels it can hold, or of ``params["levels"]`` evenly spaced greys when given (a Game
Boy 2-bit picture keeps its four greys, also once saved as 8-bit by this module); a transparent pixel turns
white in grey and palette pictures; a palette picture keeps its palette (nearest colour); anything else is
saved as RGBA. Writing the image ``read`` returned gives the original bytes back.
"""
from __future__ import annotations

import io
import struct
import zlib
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture

MAGIC = b"\x89PNG\r\n\x1a\n"


def detect(data: bytes) -> bool:
    return bytes(data[:8]) == MAGIC


def _open(data: bytes) -> Image.Image:
    if not detect(data):
        raise ValueError("Not a PNG file")
    return Image.open(io.BytesIO(bytes(data)))


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    image = _open(data)
    return [Texture("", image.convert("RGBA"), f"png:{image.mode}")]


def _grey_levels(count: int) -> List[int]:
    top = count - 1
    return [round(v * 255 / top) for v in range(count)]


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def _packed_png(size: tuple, depth: int, colour_type: int, samples: List[int], extra: List[bytes]) -> bytes:
    """A PNG of ``samples`` (one value per pixel, rows left to right) at the bit ``depth`` (1, 2, 4 or 8).
    ``extra`` are the chunks between IHDR and IDAT (PLTE, tRNS) as whole chunks."""
    if depth not in (1, 2, 4, 8):
        raise ValueError(f"Unsupported bit depth {depth} for a PNG")
    width, height = size
    per_byte = 8 // depth
    rows = bytearray()
    for y in range(height):
        row = samples[y * width:(y + 1) * width]
        packed = bytearray((width + per_byte - 1) // per_byte)
        for x, value in enumerate(row):
            packed[x // per_byte] |= value << ((per_byte - 1 - x % per_byte) * depth)
        rows.append(0)
        rows.extend(packed)
    header = struct.pack(">IIBBBBB", width, height, depth, colour_type, 0, 0, 0)
    return MAGIC + b"".join([_chunk(b"IHDR", header), *extra, _chunk(b"IDAT", zlib.compress(bytes(rows))),
                             _chunk(b"IEND", b"")])


def _indexed_png(original: Image.Image, depth: int, indices: List[int]) -> bytes:
    """A palette PNG at the bit ``depth`` of the original (Pillow picks the depth from the palette size, which
    would change how a build tool reads the tiles). The palette and transparency are the original's."""
    palette = bytes(original.getpalette() or [])
    palette = palette[:len(palette) - len(palette) % 3]
    trans = original.info.get("transparency")
    if isinstance(trans, int):
        trans = bytes([255] * trans + [0])
    extra = [_chunk(b"PLTE", palette)] + ([_chunk(b"tRNS", bytes(trans))] if trans else [])
    return _packed_png(original.size, depth, 3, indices, extra)


def _grey_png(size: tuple, depth: int, values: List[int]) -> bytes:
    """A greyscale PNG at the bit ``depth`` of the original: ``values`` are 8-bit greys already snapped to the
    levels the depth holds (a 4-bit picture stores 0 to 15, shown as 0 to 255 in steps of 17)."""
    if depth == 8:
        samples = values
    else:
        top = (1 << depth) - 1
        samples = [round(value * top / 255) for value in values]
    return _packed_png(size, depth, 0, samples, [])


def _palette_indices(original: Image.Image, new: Image.Image) -> List[int]:
    """The palette index of every pixel of ``new`` (RGBA): the index whose colour is exactly the pixel, else the
    palette colour nearest to it on white. ``original`` gives the palette and its transparent index."""
    palette = original.getpalette() or []
    count = len(palette) // 3
    if count == 0:
        raise ValueError("The indexed PNG has no palette")
    trans = original.info.get("transparency")
    alphas = [255] * count
    if isinstance(trans, int) and 0 <= trans < count:
        alphas[trans] = 0
    elif isinstance(trans, (bytes, bytearray)):
        for index, alpha in enumerate(bytes(trans)[:count]):
            alphas[index] = alpha
    colours = [tuple(palette[3 * i:3 * i + 3]) + (alphas[i],) for i in range(count)]
    exact: Dict[tuple, int] = {}
    for index, colour in enumerate(colours):
        exact.setdefault(colour, index)

    def on_white(rgba: tuple) -> tuple:
        red, green, blue, alpha = rgba
        return tuple((value * alpha + 255 * (255 - alpha)) / 255 for value in (red, green, blue))

    shown = [on_white(colour) for colour in colours]
    pixels = new.tobytes()
    before = original.convert("RGBA").tobytes()
    indices = original.tobytes()                  # one palette index per pixel of the original
    cache: Dict[tuple, int] = {}
    out: List[int] = []
    for start in range(0, len(pixels), 4):
        pixel = tuple(pixels[start:start + 4])
        if pixel == tuple(before[start:start + 4]):
            out.append(indices[start // 4])       # unchanged: the same index, even when colours repeat
            continue
        index = cache.get(pixel)
        if index is None:
            index = exact.get(pixel)
            if index is None:
                target = on_white(pixel)
                index = min(range(count), key=lambda i: sum((shown[i][j] - target[j]) ** 2 for j in range(3)))
            cache[pixel] = index
        out.append(index)
    return out


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    new = images.get(0)
    if new is None:
        return bytes(data)
    original = _open(data)
    new = new.convert("RGBA")
    if new.size != original.size:
        raise ValueError(f"The image is {new.width}x{new.height}, the PNG {original.width}x{original.height}")
    if new.tobytes() == original.convert("RGBA").tobytes():
        return bytes(data)
    white = Image.new("RGBA", new.size, (255, 255, 255, 255))
    flat = Image.alpha_composite(white, new)
    out = io.BytesIO()
    if original.mode in ("L", "LA", "1", "I", "I;16"):
        depth = min(data[24], 8) if original.mode != "1" else 1
        levels = _grey_levels(1 << depth)
        used = {value for _count, value in original.convert("L").getcolors(256)}
        if depth == 8 and used <= set(_grey_levels(4)):
            levels = _grey_levels(4)
        if int((params or {}).get("levels") or 0) > 1:
            levels = _grey_levels(int(params["levels"]))
        table = [min(levels, key=lambda level: abs(level - value)) for value in range(256)]
        grey = flat.convert("L").point(table)
        if original.mode == "1":
            grey = grey.convert("1", dither=Image.Dither.NONE)
        out.write(_grey_png(new.size, depth, list(grey.convert("L").tobytes())))
    elif original.mode == "P":
        # ponytail: an unchanged pixel keeps its index (exact RGBA match); an edited one takes the nearest colour
        # of the palette as it is shown on white. Quantizing the whole picture remapped transparent pixels to
        # white and changed other indices.
        indices = _palette_indices(original, new)
        out.write(_indexed_png(original, data[24], indices))
    else:
        new.save(out, format="PNG")
    return out.getvalue()
