"""JTX textures of the Jade engine (Ubisoft Montreal) as Rayman Raving Rabbids TV Party (Wii) keeps them in its
world bins, written by the workspace as ``.jtx`` files: the bin's items, each u32 size, u32 0xEEFFC099, u32 key and
the item -- the texture's pixel item, then (paletted formats) its palette item.

A pixel item (little endian): u32 key, the TEX header (s32 -1, u16 flags, u8 type 10, u8 format, u16 width, u16
height, colour, font descriptor key, the codes CAD01234 FF00FF00 C0DEC0DE), then the JTX header -- u32 version,
u32 format, u32 width, u32 height, u32 mip count, f32 mip bias (version 3), u32 palette key (formats 1, 2) -- and
the pixels, level 0 then the mips (halved while above 8 pixels), top row first:

- 0 Raw32: BGRA; 1 / 2 Palette_8 / Palette_4: indices (4-bit: low nibble first) into the palette item (u32 key,
  256 or 16 RGBA colours);
- 5 S3TC: DXT1 (BC1) blocks; 12 S3TC_A: DXT1 colour, then a second DXT1 whose red is the alpha.

Writing changes the pixels: level 0 from the image, the mips from it scaled down; a paletted image is mapped to
the nearest colours of its palette (palettes are shared). An unchanged image writes the original bytes back.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.texture_formats import Texture, pixels

MAGIC = 0xEEFFC099
NAMES = {0: "BGRA8", 1: "C8", 2: "C4", 5: "DXT1", 12: "DXT1 + alpha"}


def detect(data: bytes) -> bool:
    return len(data) > 48 and struct.unpack_from("<I", data, 4)[0] == MAGIC and data[16:20] == b"\xff\xff\xff\xff"


def split(data: bytes) -> List[Tuple[int, bytes]]:
    out, at = [], 0
    while at + 12 <= len(data):
        size, magic, key = struct.unpack_from("<III", data, at)
        if magic != MAGIC:
            raise ValueError("Not a Jade JTX texture file")
        out.append((key, bytes(data[at + 12:at + 12 + size])))
        at += 12 + size
    return out


def join(items: List[Tuple[int, bytes]]) -> bytes:
    return b"".join(struct.pack("<III", len(item), MAGIC, key) + item for key, item in items)


def header(item: bytes) -> Dict[str, Any]:
    version, fmt, width, height, mips = struct.unpack_from("<5I", item, 36)
    at = 36 + 20 + (4 if version >= 3 else 0)
    palette = None
    if fmt in (1, 2):
        palette = struct.unpack_from("<I", item, at)[0]
        at += 4
    return {"version": version, "format": fmt, "width": width, "height": height, "mips": mips, "data": at,
            "palette": palette}


def _levels(width: int, height: int, mips: int) -> List[Tuple[int, int]]:
    out = [(width, height)]
    for _ in range(mips):
        width, height = (width >> 1 if width > 8 else width), (height >> 1 if height > 8 else height)
        out.append((width, height))
    return out


def _size(fmt: int, width: int, height: int) -> int:
    if fmt in (5, 12):
        return max(1, width // 4) * max(1, height // 4) * 8
    return width * height * {0: 4, 1: 1, 2: 1}[fmt] // (2 if fmt == 2 else 1)


def _codec(fmt: int, pal: bytes) -> pixels.Codec:
    if fmt in (1, 2):
        colours = [tuple(pal[i:i + 4]) for i in range(4, len(pal) - 3, 4)]
        return pixels.palette_codec(f"jtx:C{8 if fmt == 1 else 4}", 8 if fmt == 1 else 4, colours, low_first=True)
    if fmt == 0:
        return pixels.codec("RGBA8")
    return pixels.codec("BC1")


def decode(item: bytes, pal: bytes = b"") -> Image.Image:
    h = header(item)
    fmt, width, height = h["format"], h["width"], h["height"]
    if fmt not in NAMES:
        raise ValueError(f"JTX format {fmt} is not supported")
    image = _codec(fmt, pal).decode(item[h["data"]:], width, height)
    if fmt == 0:
        b, g, r, a = image.split()
        image = Image.merge("RGBA", (r, g, b, a))
    if fmt == 12:
        total = sum(_size(5, w, hh) for w, hh in _levels(width, height, h["mips"]))
        alpha = pixels.codec("BC1").decode(item[h["data"] + total:], width, height).getchannel("R")
        image.putalpha(alpha)
    return image


def encode(item: bytes, image: Image.Image, pal: bytes = b"") -> bytes:
    h = header(item)
    fmt, width, height = h["format"], h["width"], h["height"]
    image = image.convert("RGBA")
    if image.size != (width, height):
        raise ValueError(f"the image is {image.size}, the texture {width}x{height}")
    codec, colour, alpha = _codec(fmt, pal), bytearray(), bytearray()
    for w, hh in _levels(width, height, h["mips"]):
        level = image if (w, hh) == image.size else image.resize((w, hh), Image.Resampling.BOX)
        if fmt == 0:
            r, g, b, a = level.split()
            level = Image.merge("RGBA", (b, g, r, a))
        if fmt in (5, 12):
            pad = Image.new("RGBA", ((w + 3) // 4 * 4, (hh + 3) // 4 * 4))
            pad.paste(level, (0, 0))
            colour += codec.encode(pad.convert("RGB").convert("RGBA"))
            if fmt == 12:
                a = pad.getchannel("A")
                alpha += codec.encode(Image.merge("RGBA", (a, a, a, Image.new("L", pad.size, 255))))
        else:
            colour += codec.encode(level)
    data = bytes(colour + alpha)
    return item[:h["data"]] + data + item[h["data"] + len(data):]


def _parts(data: bytes) -> Tuple[List[Tuple[int, bytes]], int, bytes]:
    items = split(data)
    pal = items[1][1] if len(items) > 1 else b""
    return items, 0, pal


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    items, at, pal = _parts(data)
    item = items[at][1]
    h = header(item)
    return [Texture("", decode(item, pal), NAMES.get(h["format"], str(h["format"])), h["mips"] + 1)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    if 0 not in images:
        return bytes(data)
    items, at, pal = _parts(data)
    key, item = items[at]
    if images[0].convert("RGBA").tobytes() == decode(item, pal).tobytes():
        return bytes(data)
    items[at] = (key, encode(item, images[0], pal))
    return join(items)
