"""Textures of the Jade engine (Ubisoft Montpellier) as Rayman Raving Rabbids 1 and 2 (Wii) keep them in their
texture bins, written by the workspace as ``.jtex`` / ``.jfnt`` files: the bin's own items, each u32 size + bytes.

A ``.jtex`` is the texture item, then (4/8-bit textures) its palette item; a ``.jfnt`` (a font, see
``core.font_formats.jade``) starts with the FONTDESC item, then the same two. A texture item is a TEX header
(32 bytes, little endian: s32 -1, u16 flags, u8 type, u8 format, u16 width, u16 height, u32 colour, u32 font
descriptor key, the codes CAD01234 FF00FF00 C0DEC0DE) and its pixels, bottom row first except DDS:

- type 6, format 0x50 / 0x40: 4-bit (high nibble first) / 8-bit indices into the palette item: 16 or 256
  colours of 3 (RGB) or 4 (RGBA) bytes;
- type 1: an 18-byte TGA header and 24- or 32-bit RGB(A);
- type 11: a DDS file (``DDS ``, 124-byte header) of DXT1/3/5 (BC1/2/3) blocks with its mip levels.

Writing changes the pixels only: a 4/8-bit image is mapped to the nearest colours of its palette (palettes are
shared by several textures and stay as they are); a DDS gets its mip levels again. An unchanged image writes
the original bytes back.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels


def detect(data: bytes) -> bool:
    return len(data) > 40 and bytes(data[4:8]) in (b"\xff\xff\xff\xff", b"FONT") and \
        struct.unpack_from("<I", data)[0] <= len(data) - 4


def split(data: bytes) -> List[bytes]:
    """The items of a ``.jtex`` / ``.jfnt`` file."""
    out, at = [], 0
    while at + 4 <= len(data):
        size = struct.unpack_from("<I", data, at)[0]
        out.append(bytes(data[at + 4:at + 4 + size]))
        at += 4 + size
    if at != len(data):
        raise ValueError("Not a Jade texture file (item sizes do not add up)")
    return out


def join(items: List[bytes]) -> bytes:
    return b"".join(struct.pack("<I", len(item)) + item for item in items)


def _texture_items(items: List[bytes]) -> List[bytes]:
    return items[1:] if items and items[0][:8] == b"FONTDESC" else items


def palette(item: bytes) -> List[tuple]:
    step = 3 if len(item) in (48, 768) else 4
    return [tuple(item[i:i + 3]) + ((255,) if step == 3 else (item[i + 3],)) for i in range(0, len(item), step)]


def _indexed(item: bytes, pal: bytes) -> pixels.Codec:
    bits = 4 if item[7] == 0x50 else 8
    return pixels.palette_codec(f"jade:C{bits}", bits, palette(pal))


def _dds(item: bytes):
    """``(BC codec name, mip count, data offset)`` of a DDS item."""
    head = item[32:32 + 128]
    if head[:4] != b"DDS ":
        raise ValueError("Jade DDS texture without a DDS header")
    mips = max(1, struct.unpack_from("<I", head, 28)[0])
    four = head[84:88]
    names = {b"DXT1": "BC1", b"DXT3": "BC2", b"DXT5": "BC3"}
    if four not in names:
        raise ValueError(f"Jade DDS texture: {four!r} is not supported")
    return names[four], mips, 32 + 128


def _size(item: bytes):
    return struct.unpack_from("<HH", item, 8)


def decode(item: bytes, pal: bytes = b"") -> Image.Image:
    """The RGBA image of a texture item (top row first)."""
    kind, width, height = item[6], *_size(item)
    if kind == 6:
        image = _indexed(item, pal).decode(item[32:], width, height)
        return image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if kind == 1:
        bpp = item[32 + 16]
        mode = "RGBA" if bpp == 32 else "RGB"
        image = Image.frombytes(mode, (width, height), item[32 + 18:32 + 18 + width * height * bpp // 8])
        return image.convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if kind == 11:
        name, _mips, at = _dds(item)
        return pixels.codec(name).decode(item[at:], width, height)
    raise ValueError(f"Jade texture type {kind} is not supported")


def encode(item: bytes, image: Image.Image, pal: bytes = b"") -> bytes:
    """``item`` with ``image`` as its pixels (same size)."""
    kind, width, height = item[6], *_size(item)
    image = image.convert("RGBA")
    if image.size != (width, height):
        raise ValueError(f"the image is {image.size}, the texture {width}x{height}")
    if kind == 6:
        data = _indexed(item, pal).encode(image.transpose(Image.Transpose.FLIP_TOP_BOTTOM))
        return item[:32] + data + item[32 + len(data):]
    if kind == 1:
        bpp = item[32 + 16]
        flipped = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        data = (flipped if bpp == 32 else flipped.convert("RGB")).tobytes()
        return item[:32 + 18] + data + item[32 + 18 + len(data):]
    if kind == 11:
        name, mips, at = _dds(item)
        codec, out, level = pixels.codec(name), bytearray(), image
        for _ in range(mips):
            w, h = level.size
            padded = Image.new("RGBA", ((w + 3) // 4 * 4, (h + 3) // 4 * 4))
            padded.paste(level, (0, 0))
            out += codec.encode(padded)
            level = level.resize((max(1, w // 2), max(1, h // 2)), Image.Resampling.BOX)
        return item[:at] + bytes(out) + item[at + len(out):]
    raise ValueError(f"Jade texture type {kind} is not supported")


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    items = _texture_items(split(data))
    item, pal = items[0], (items[1] if len(items) > 1 else b"")
    fmt = {6: f"C{4 if item[7] == 0x50 else 8}", 1: "RGBA8 (TGA)", 11: "DXT (DDS)"}.get(item[6], str(item[6]))
    return [Texture("", decode(item, pal), fmt)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    if 0 not in images:
        return bytes(data)
    items = split(data)
    first = 1 if items[0][:8] == b"FONTDESC" else 0
    item, pal = items[first], (items[first + 1] if len(items) > first + 1 else b"")
    if images[0].convert("RGBA").tobytes() == decode(item, pal).tobytes():
        return bytes(data)
    items[first] = encode(item, images[0], pal)
    return join(items)
