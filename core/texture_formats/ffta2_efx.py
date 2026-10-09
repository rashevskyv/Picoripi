"""Final Fantasy Tactics A2 (DS) effect files ``*.efx`` (``EFX0010``): the DS 3D textures they hold.

The title logo (``effect/common/c_all_title_eu.efx``), the company and licence logos and the battle effects
live in these files. Layout (little endian): ``EFX0010\\0``, f32 1.0, u32 size, then chunks from 0x10. A
texture chunk: u32 chunk size, u32 flags, u32 data size, u16 0, u8 ``0x52``, u8 number, u16 format,
u16 palette colours, u16 width, u16 height, u16 width, u16 height, u32 0, the BGR555 palette, the texels.
Chunks with other tag bytes (palettes, animation, particles) are skipped. Formats: ``7`` = A3I5 (a byte per
texel: palette index in bits 0-4, alpha in bits 5-7), ``6`` = A5I3 (index in bits 0-2, alpha in bits 3-7).

Writing keeps the byte of every texel whose colour did not change; a changed texel takes the nearest palette
colour and the nearest alpha level. The palette and the file size never change.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.texture_formats import Texture

MAGIC = b"EFX0010\x00"
TEXTURE_TAG = 0x52
# format -> (name, index bits)
FORMATS = {7: ("A3I5", 5), 6: ("A5I3", 3)}


def detect(data: bytes) -> bool:
    return bytes(data[:8]) == MAGIC


def chunks(data: bytes) -> List[Dict[str, Any]]:
    """The texture chunks: ``{at, format, colours, width, height, palette, texels}`` (offsets in ``data``)."""
    if not detect(data):
        raise ValueError("Not an FFTA2 effect file (EFX0010)")
    out, at = [], 0x10
    while at + 0x10 <= len(data):
        size = struct.unpack_from("<I", data, at)[0]
        if size < 0x10 or at + size > len(data):
            break
        if data[at + 0xE] != TEXTURE_TAG or size < 0x20:
            at += size
            continue
        fmt, colours, width, height = struct.unpack_from("<4H", data, at + 0x10)
        palette = at + 0x20
        out.append({"at": at, "number": data[at + 0xF], "format": fmt, "colours": colours, "width": width,
                    "height": height, "palette": palette, "texels": palette + 2 * colours, "end": at + size})
        at += size
    return out


def _colours(data: bytes, chunk: Dict[str, Any]) -> List[Tuple[int, int, int]]:
    out = []
    for (value,) in struct.iter_unpack("<H", data[chunk["palette"]:chunk["texels"]]):
        r, g, b = value & 31, value >> 5 & 31, value >> 10 & 31
        out.append((r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2))
    return out


def _decode(value: int, bits: int, colours) -> Tuple[int, int, int, int]:
    index, alpha = value & ((1 << bits) - 1), value >> bits
    top = (1 << (8 - bits)) - 1
    rgb = colours[index] if index < len(colours) else (0, 0, 0)
    return rgb + (alpha * 255 // top,)


def _usable(data: bytes) -> List[Dict[str, Any]]:
    return [chunk for chunk in chunks(data) if chunk["format"] in FORMATS
            and chunk["texels"] + chunk["width"] * chunk["height"] <= chunk["end"]]


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    out = []
    for chunk in _usable(data):
        name, bits = FORMATS[chunk["format"]]
        colours = _colours(data, chunk)
        count = chunk["width"] * chunk["height"]
        texels = data[chunk["texels"]:chunk["texels"] + count]
        pixels = b"".join(bytes(_decode(v, bits, colours)) for v in texels)
        image = Image.frombytes("RGBA", (chunk["width"], chunk["height"]), pixels)
        out.append(Texture(f"texture {chunk['number']}", image, name))
    return out


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    usable = _usable(data)
    for index, image in images.items():
        chunk = usable[index]
        size = (chunk["width"], chunk["height"])
        if image.size != size:
            raise ValueError(f"The image is {image.width}x{image.height}, the texture {size[0]}x{size[1]}")
        _name, bits = FORMATS[chunk["format"]]
        colours = _colours(data, chunk)
        top = (1 << (8 - bits)) - 1
        cache: Dict[Tuple[int, int, int, int], int] = {}
        start = chunk["texels"]
        for at, pixel in enumerate(image.convert("RGBA").getdata()):
            old = out[start + at]
            if _decode(old, bits, colours) == pixel:
                continue
            if pixel not in cache:
                nearest = min(range(len(colours)),
                              key=lambda i: sum((p - q) ** 2 for p, q in zip(colours[i], pixel[:3])))
                cache[pixel] = (round(pixel[3] * top / 255) << bits) | nearest
            out[start + at] = cache[pixel]
    return bytes(out)
