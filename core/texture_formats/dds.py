"""DDS textures (block-compressed, with mip levels) at a place in a file: a standalone .dds (offset 0) or one inside a
container (``params["offset"]``).

Formats: DX10 DXGI 71 (BC1), 74 (BC2), 77 (BC3), 98 (BC7); legacy fourCC DXT1 / DXT3 / DXT5. A file has one texture.
The pixels are read and written by ``surface`` (the codec of the format): writing an image changes only the blocks
whose pixels changed; when level 0 changes, the smaller mip levels are made again from it. Writing the image read
gives the original bytes back.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageChops

from core.texture_formats import Texture, surface, pixels

DXGI_CODEC = {71: "BC1", 74: "BC2", 77: "BC3", 98: "BC7"}
FOURCC_CODEC = {b"DXT1": "BC1", b"DXT3": "BC2", b"DXT5": "BC3"}


def _header(data: bytes, offset: int) -> Tuple[int, int, int, str, int]:
    """(width, height, mips, codec name, pixel data offset) of the DDS at ``offset``."""
    if data[offset:offset + 4] != b"DDS " or struct.unpack_from("<I", data, offset + 4)[0] != 124:
        raise ValueError("not a DDS texture")
    height, width = struct.unpack_from("<II", data, offset + 12)
    mips = max(1, struct.unpack_from("<I", data, offset + 28)[0])
    fourcc = data[offset + 84:offset + 88]
    if fourcc == b"DX10":
        dxgi = struct.unpack_from("<I", data, offset + 128)[0]
        if dxgi not in DXGI_CODEC:
            raise ValueError(f"DXGI format {dxgi} is not supported")
        return width, height, mips, DXGI_CODEC[dxgi], offset + 148
    if fourcc not in FOURCC_CODEC:
        raise ValueError(f"fourCC {fourcc!r} is not supported")
    return width, height, mips, FOURCC_CODEC[fourcc], offset + 128


def _levels(width: int, height: int, mips: int) -> List[Tuple[int, int]]:
    return [(max(1, width >> level), max(1, height >> level)) for level in range(mips)]


def _offsets(codec: pixels.Codec, levels: List[Tuple[int, int]], base: int) -> List[int]:
    at, out = base, []
    for w, h in levels:
        out.append(at)
        at += (-(-w // codec.block[0])) * (-(-h // codec.block[1])) * codec.size
    return out


def detect(data: bytes) -> bool:
    return len(data) >= 128 and data[:4] == b"DDS " and struct.unpack_from("<I", data, 4)[0] == 124


def _params(params: Dict[str, Any]) -> int:
    return int(params.get("offset", 0))


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    offset = _params(params)
    width, height, mips, name, base = _header(data, offset)
    codec = pixels.codec(name)
    image = surface.read(data, base, codec, width, height)
    return [Texture(name="", image=image, pixel_format=name, mipmaps=mips)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    """The file with texture 0 replaced by ``images[0]``. Only the blocks of the changed area are encoded: the
    changed rectangle of level 0 is followed down the mip chain (each level's rectangle is the level-0 rectangle
    divided by 2**level, with a margin of one texel)."""
    if 0 not in images or images[0] is None:
        return data
    offset = _params(params)
    width, height, mips, name, base = _header(data, offset)
    codec = pixels.codec(name)
    image = images[0].convert("RGBA")
    before = surface.read(data, base, codec, width, height)
    box = ImageChops.difference(before, image).getbbox()
    if box is None:
        return data
    out = bytearray(data)
    surface.write(out, base, codec, width, height, image)
    if mips <= 1:
        return bytes(out)
    levels = _levels(width, height, mips)
    starts = _offsets(codec, levels, base)
    prev = surface.read(bytes(out), base, codec, width, height)
    x0, y0, x1, y1 = box
    for level in range(1, mips):
        w, h = levels[level]
        scale = 1 << level
        rx0, ry0 = max(0, x0 // scale - 1), max(0, y0 // scale - 1)
        rx1, ry1 = min(w, -(-x1 // scale) + 1), min(h, -(-y1 // scale) + 1)
        if rx1 <= rx0 or ry1 <= ry0:
            prev = surface.read(bytes(out), starts[level], codec, w, h)
            continue
        pw, ph = prev.size
        part = prev.crop((min(pw - 1, rx0 * 2), min(ph - 1, ry0 * 2), min(pw, rx1 * 2), min(ph, ry1 * 2)))
        part = part.resize((rx1 - rx0, ry1 - ry0), Image.Resampling.LANCZOS)
        level_image = surface.read(bytes(out), starts[level], codec, w, h)
        level_image.paste(part, (rx0, ry0))
        surface.write(out, starts[level], codec, w, h, level_image)
        prev = level_image
    return bytes(out)
