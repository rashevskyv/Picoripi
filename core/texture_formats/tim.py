"""PlayStation TIM pictures (``10 00 00 00``): 4- or 8-bit with a palette (CLUT), or 15-bit colour.

Header: u32 magic 0x10, u32 flags (bits 0-1: 0 = 4-bit, 1 = 8-bit, 2 = 15-bit; bit 3: a CLUT block
follows). Each block: u32 length (with this 12-byte head), u16 x, u16 y, u16 width, u16 height (in
16-bit VRAM units), then the data. A colour is 15-bit BGR with the STP bit 15; 0x0000 is transparent.
The first palette row draws the picture. A TIM whose CLUT block is empty (the game loads the palette
from elsewhere) shows its indices as grey levels.

Writing keeps the header and palette: a pixel that did not change keeps its index, any other takes the
nearest palette colour (15-bit pictures are written as they are).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.texture_formats import Texture

MAGIC = b"\x10\x00\x00\x00"
_BITS = {0: 4, 1: 8, 2: 16}


def detect(data: bytes) -> bool:
    return data[:4] == MAGIC and len(data) >= 8 and (data[4] & 7) in _BITS


def _rgba(value: int) -> Tuple[int, int, int, int]:
    if value == 0:
        return 0, 0, 0, 0
    r, g, b = value & 31, (value >> 5) & 31, (value >> 10) & 31
    return (r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2, 255)


def _color(r: int, g: int, b: int, a: int) -> int:
    if a < 128:
        return 0
    value = (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10
    return value or 0x8000                               # black that is not transparent: the STP bit set


def _layout(data: bytes) -> Dict[str, Any]:
    if not detect(data):
        raise ValueError("Not a PlayStation TIM picture")
    flags = struct.unpack_from("<I", data, 4)[0]
    bits = _BITS[flags & 7]
    pos, palette = 8, []
    if flags & 8:
        length, _x, _y, width, height = struct.unpack_from("<IHHHH", data, pos)
        count = width * height
        if count:
            palette = list(struct.unpack_from(f"<{min(count, 1 << bits)}H", data, pos + 12))
        pos += length
    _length, _x, _y, width, height = struct.unpack_from("<IHHHH", data, pos)
    pixels = width * 16 // bits
    if not palette and bits < 16:
        step = 255 // ((1 << bits) - 1)
        palette = [-(i * step) - 1 for i in range(1 << bits)]      # grey levels, see _palette_rgba
    return {"bits": bits, "palette": palette, "data": pos + 12, "width": pixels, "height": height}


def _palette_rgba(palette: List[int]) -> List[Tuple[int, int, int, int]]:
    out = []
    for value in palette:
        if value < 0:                                    # no palette in the file: grey level -value - 1
            grey = -value - 1
            out.append((grey, grey, grey, 255))
        else:
            out.append(_rgba(value))
    return out


def _indices(data: bytes, layout: Dict[str, Any]) -> List[int]:
    count = layout["width"] * layout["height"]
    raw = data[layout["data"]:layout["data"] + count * layout["bits"] // 8]
    if layout["bits"] == 8:
        return list(raw)
    out = []
    for byte in raw:
        out += (byte & 15, byte >> 4)
    return out


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    layout = _layout(bytes(data))
    size = (layout["width"], layout["height"])
    if layout["bits"] == 16:
        values = struct.unpack_from(f"<{size[0] * size[1]}H", data, layout["data"])
        image = Image.new("RGBA", size)
        image.putdata([_rgba(v) for v in values])
        return [Texture("", image, "PSX 15-bit")]
    colours = _palette_rgba(layout["palette"])
    image = Image.new("RGBA", size)
    image.putdata([colours[i] if i < len(colours) else (0, 0, 0, 0) for i in _indices(data, layout)])
    return [Texture("", image, f"PSX {layout['bits']}-bit")]


def _nearest(colour: Tuple[int, int, int, int], colours: List[Tuple[int, int, int, int]], cache: Dict) -> int:
    found = cache.get(colour)
    if found is None:
        r, g, b, a = colour
        if a < 128:
            transparent = [i for i, c in enumerate(colours) if c[3] == 0]
            if transparent:
                cache[colour] = transparent[0]
                return transparent[0]
        found = min(range(len(colours)), key=lambda i: (colours[i][3] == 0) * 10 ** 6 + (colours[i][0] - r) ** 2
                    + (colours[i][1] - g) ** 2 + (colours[i][2] - b) ** 2)
        cache[colour] = found
    return found


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    image = images.get(0)
    if image is None:
        return bytes(data)
    layout = _layout(bytes(data))
    size = (layout["width"], layout["height"])
    image = image.convert("RGBA")
    if image.size != size:
        raise ValueError(f"TIM picture is {size[0]}x{size[1]}, the new image {image.size[0]}x{image.size[1]}")
    out = bytearray(data)
    new = list(image.getdata())
    if layout["bits"] == 16:
        old = struct.unpack_from(f"<{size[0] * size[1]}H", data, layout["data"])
        values = [v if _rgba(v) == pixel else _color(*pixel) for v, pixel in zip(old, new)]
        struct.pack_into(f"<{len(values)}H", out, layout["data"], *values)
        return bytes(out)
    colours = _palette_rgba(layout["palette"])
    old = _indices(data, layout)
    cache: Dict = {}
    indices = [i if i < len(colours) and colours[i] == pixel else _nearest(pixel, colours, cache)
               for i, pixel in zip(old, new)]
    if layout["bits"] == 8:
        raw = bytes(indices)
    else:
        raw = bytes(indices[k] | indices[k + 1] << 4 for k in range(0, len(indices), 2))
    out[layout["data"]:layout["data"] + len(raw)] = raw
    return bytes(out)
