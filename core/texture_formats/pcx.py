"""Metal Gear Solid (PlayStation) PCX textures: ZSoft PCX with the game's VRAM place in the header.

Header (128 bytes, little endian): ``0A 05 01 bpp``, ``min_x, min_y, max_x, max_y``, a 16-colour palette
at 0x10, planes at 0x41, bytes per line at 0x42 and at 0x4A the game's info: ``u16 12345, u16 flag``
(bit 0: 8-bit), VRAM ``x, y`` of the pixels and of the palette, ``u16`` colour count. A 4-bit texture is
4 bit planes per row (one run-length stream per row); an 8-bit one is one stream of ``w * h`` bytes,
then ``0x0C`` and a 256-colour palette. A run is ``0xC0 + n, byte``; any byte up to 0xC0 stands for
itself. The game turns black (0,0,0) into transparent.

Writing keeps the header and the palette: the image is mapped to the nearest palette colour (a
transparent pixel to black) and compressed again. An unchanged image gives the original bytes back.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.texture_formats import Texture

STAMP = 12345
HEADER = 128


def detect(data: bytes) -> bool:
    return len(data) > HEADER and data[0] == 0x0A and struct.unpack_from("<H", data, 0x4A)[0] == STAMP


def _head(data: bytes) -> Dict[str, int]:
    if not detect(data):
        raise ValueError("Not a Metal Gear Solid PCX texture")
    min_x, min_y, max_x, max_y = struct.unpack_from("<4H", data, 4)
    flag = struct.unpack_from("<H", data, 0x4C)[0]
    colors = struct.unpack_from("<H", data, 0x56)[0]
    return {"width": max_x - min_x + 1, "height": max_y - min_y + 1, "eight": flag & 1,
            "stride": struct.unpack_from("<H", data, 0x42)[0], "colors": colors}


def _unpack(data: bytes, pos: int, count: int) -> Tuple[bytearray, int]:
    out = bytearray()
    while len(out) < count:
        code = data[pos]
        pos += 1
        if code <= 0xC0:
            out.append(code)
        else:
            out += bytes([data[pos]]) * (code - 0xC0)
            pos += 1
    return out, pos


def _pack(raw: bytes) -> bytes:
    out = bytearray()
    pos, n = 0, len(raw)
    while pos < n:
        value = raw[pos]
        run = 1
        while pos + run < n and raw[pos + run] == value and run < 63:
            run += 1
        if run == 1 and value <= 0xC0:
            out.append(value)
        else:
            out += bytes((0xC0 + run, value))
        pos += run
    return bytes(out)


def _indices(data: bytes, head: Dict[str, int]) -> Tuple[bytes, List[Tuple[int, int, int]], int]:
    """Palette index of every pixel, the palette, and where the pixel data ends."""
    width, height = head["width"], head["height"]
    if head["eight"]:
        pixels, end = _unpack(data, HEADER, width * height)
        if data[end] != 0x0C:
            raise ValueError("8-bit PCX without its palette")
        pal = data[end + 1:end + 1 + 768]
        palette = [tuple(pal[i * 3:i * 3 + 3]) for i in range(256)]
        return bytes(pixels[:width * height]), palette, end
    stride = head["stride"]
    out = bytearray()
    pos = HEADER
    for _row in range(height):
        planes, pos = _unpack(data, pos, stride * 4)
        for x in range(width):
            bit = 0x80 >> (x & 7)
            byte = x >> 3
            out.append(sum(1 << plane for plane in range(4) if planes[plane * stride + byte] & bit))
    palette = [tuple(data[0x10 + i * 3:0x13 + i * 3]) for i in range(16)]
    return bytes(out), palette, pos


def _rgba(index_bytes: bytes, palette, size) -> Image.Image:
    lut = [palette[i] + ((0,) if palette[i] == (0, 0, 0) else (255,)) for i in range(len(palette))]
    flat = bytearray()
    for index in index_bytes:
        flat += bytes(lut[index])
    return Image.frombytes("RGBA", size, bytes(flat))


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    head = _head(data)
    indices, palette, _end = _indices(data, head)
    image = _rgba(indices, palette, (head["width"], head["height"]))
    return [Texture("", image, "PCX 8-bit" if head["eight"] else "PCX 4-bit")]


def _nearest(image: Image.Image, palette) -> bytes:
    usable = range(len(palette))
    black = next((i for i in usable if palette[i] == (0, 0, 0)), None)
    cache: Dict[Tuple[int, int, int, int], int] = {}
    out = bytearray()
    for pixel in image.convert("RGBA").getdata():
        index = cache.get(pixel)
        if index is None:
            r, g, b, a = pixel
            if a < 128 and black is not None:
                index = black
            else:
                index = min((i for i in usable if palette[i] != (0, 0, 0) or black is None),
                            key=lambda i: (palette[i][0] - r) ** 2 + (palette[i][1] - g) ** 2 + (palette[i][2] - b) ** 2,
                            default=0)
            cache[pixel] = index
        out.append(index)
    return bytes(out)


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    image = images.get(0)
    if image is None:
        return data
    head = _head(data)
    old, palette, end = _indices(data, head)
    size = (head["width"], head["height"])
    if image.size != size:
        raise ValueError(f"The image is {image.width}x{image.height}, the texture {size[0]}x{size[1]}")
    if image.convert("RGBA").tobytes() == _rgba(old, palette, size).tobytes():
        return data
    new = _nearest(image, palette[:max(head["colors"], 16)] if not head["eight"] else palette[:head["colors"] or 256])
    if new == old:
        return data
    width, height = size
    if head["eight"]:
        body = _pack(new)
        return data[:HEADER] + body + data[end:]
    stride = head["stride"]
    body = bytearray()
    for y in range(height):
        planes = bytearray(stride * 4)
        for x in range(width):
            value = new[y * width + x]
            for plane in range(4):
                if value >> plane & 1:
                    planes[plane * stride + (x >> 3)] |= 0x80 >> (x & 7)
        body += _pack(bytes(planes))
    return data[:HEADER] + bytes(body) + data[end:]
