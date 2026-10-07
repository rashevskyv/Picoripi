"""Retro Studios TXTR textures (Metroid Prime 4: Beyond, Prime Remastered), as ``1_unpack`` writes them.

A TXTR is an ``RFRM`` form with a ``HEAD`` chunk (u32 kind, u32 format, width, height, layers,
u32 channel swizzle, u32 mip count, one u32 linear size per mip, sampler bytes; Prime Remastered has a
u32 tile mode before the swizzle) and a ``GPU `` chunk.
In the game the GPU chunk holds compressed buffers (``core.containers.retro_pak.unpack_texture`` opens
them); here it is u32 0 and the whole surface: Tegra block-linear, mip after mip, each with the standard
block height for its size. Formats (``FORMATS``): R8, RGBA8, BC1-BC5, BC7 are read and written in place;
ASTC is read and an edited ASTC texture is stored as RGBA8 (``ASTC_TO``: the same sRGB-ness), which the
game's texture loader takes from the header. BC6H and the other formats are listed as not supported.
Rows are stored bottom up; images are given and taken the right way up.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.texture_formats import Texture, astc, pixels, surface, tegra

FORMATS = {0: "L8", 12: "RGBA8", 13: "RGBA8", 20: "BC1", 21: "BC1", 22: "BC2", 23: "BC2", 24: "BC3", 25: "BC3",
           26: "BC4", 27: "BC4", 28: "BC5", 29: "BC5", 83: "BC7", 84: "BC7"}
_ASTC_SIZES = ((4, 4), (5, 4), (5, 5), (6, 5), (6, 6), (8, 5), (8, 6), (8, 8), (10, 5), (10, 6), (10, 8), (10, 10),
               (12, 10), (12, 12))
ASTC = {53 + i: size for i, size in enumerate(_ASTC_SIZES)}
ASTC.update({67 + i: size for i, size in enumerate(_ASTC_SIZES)})
ASTC_TO = {**{53 + i: 12 for i in range(14)}, **{67 + i: 13 for i in range(14)}}
_NAMES = {**{k: f"ASTC{w}x{h}" for k, (w, h) in ASTC.items()}, 81: "BC6H", 82: "BC6H"}


def detect(data: bytes) -> bool:
    return data[:4] == b"RFRM" and data[20:24] == b"TXTR"


class _Txtr:
    def __init__(self, data: bytes):
        if not detect(data):
            raise ValueError("Not a TXTR texture")
        position, self.head_at, self.gpu_at = 0x20, None, None
        while position < len(data):
            kind, size, _unk, skip = struct.unpack_from("<4sQIQ", data, position)
            body = position + 24 + skip
            if kind == b"HEAD":
                self.head_at, self.head_size = body, size
            elif kind == b"GPU ":
                self.gpu_at, self.gpu_size = body, size
            position = body + size
        if self.head_at is None or self.gpu_at is None:
            raise ValueError("TXTR without HEAD or GPU chunk")
        (self.kind, self.format, self.width, self.height, self.layers, _swizzle,
         self.mips) = struct.unpack_from("<7I", data, self.head_at)
        self.sizes_at = 28                                  # the mip sizes in HEAD
        if self.head_size != 28 + 4 * self.mips + 10:       # Prime Remastered: a tile mode before the swizzle
            self.mips = struct.unpack_from("<I", data, self.head_at + 28)[0]
            self.sizes_at = 32
            if self.head_size != 32 + 4 * self.mips + 10:
                raise ValueError("TXTR header of an unknown layout")
        if struct.unpack_from("<I", data, self.gpu_at)[0] != 0:
            raise ValueError("The texture data is still compressed (unpack it with 1_unpack.bat)")
        self.data_at = self.gpu_at + 4

    @property
    def name(self) -> str:
        return FORMATS.get(self.format) or _NAMES.get(self.format, f"format {self.format}")


def _element(fmt: int) -> Tuple[int, int, int]:
    """(block width, block height, bytes per element) of a format."""
    if fmt in ASTC:
        return ASTC[fmt][0], ASTC[fmt][1], 16
    codec = pixels.codec(FORMATS[fmt])
    return codec.block[0], codec.block[1], codec.size


def _block_height_mip0(rows: int) -> int:
    rows += rows // 2
    for height, limit in ((16, 128), (8, 64), (4, 32), (2, 16)):
        if rows >= limit:
            return height
    return 1


def layout(fmt: int, width: int, height: int, mips: int) -> List[Tuple[int, int, int, int, int]]:
    """``(offset, width, height, block height, size)`` of every mip level in the block-linear surface."""
    bw, bh, bpp = _element(fmt)
    first = _block_height_mip0(-(-height // bh))
    out, offset = [], 0
    for level in range(mips):
        w, h = max(1, width >> level), max(1, height >> level)
        wide, high = -(-w // bw), -(-h // bh)
        block = first
        while high <= (block // 2) * 8 and block > 1:
            block //= 2
        size = -(-wide * bpp // 64) * 64 * -(-high // (8 * block)) * 8 * block
        out.append((offset, w, h, block, size))
        offset += size
    return out


def _decode_level(data: bytes, base: int, fmt: int, level) -> Image.Image:
    offset, w, h, block, _size = level
    bw, bh, bpp = _element(fmt)
    wide, high = -(-w // bw), -(-h // bh)
    offsets = tegra.block_addresses(wide, high, bpp, block)
    if fmt in ASTC:
        linear = b"".join(data[base + offset + o:base + offset + o + 16] for o in offsets)
        return astc.decode(linear, w, h, bw, bh)
    return surface.read(data, base + offset, pixels.codec(FORMATS[fmt]), w, h, offsets)


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    texture = _Txtr(data)
    if texture.format not in FORMATS and texture.format not in ASTC:
        image = Image.new("RGBA", (texture.width, texture.height))
        return [Texture("", image, texture.name + " (not supported)", texture.mips)]
    levels = layout(texture.format, texture.width, texture.height, texture.mips)
    image = _decode_level(data, texture.data_at, texture.format, levels[0]).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return [Texture("", image, texture.name, texture.mips)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    if 0 not in images:
        return bytes(data)
    texture = _Txtr(data)
    image = images[0].convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if texture.layers > 1:
        if read(data, params)[0].image.tobytes() == images[0].convert("RGBA").tobytes():
            return bytes(data)
        raise ValueError(f"TXTR with {texture.layers} layers (a cube map or array) cannot be written")
    if texture.format in ASTC:
        levels = layout(texture.format, texture.width, texture.height, texture.mips)
        if _decode_level(data, texture.data_at, texture.format, levels[0]).tobytes() == image.tobytes():
            return bytes(data)
        return _as_rgba8(data, texture, image)
    if texture.format not in FORMATS:
        raise ValueError(f"TXTR {texture.name} cannot be written yet")
    out = bytearray(data)
    codec = pixels.codec(FORMATS[texture.format])
    levels = layout(texture.format, texture.width, texture.height, texture.mips)
    for level, picture in zip(levels, surface.mip_levels(image, len(levels))):
        offset, w, h, block, _size = level
        bw, bh, bpp = _element(texture.format)
        offsets = tegra.block_addresses(-(-w // bw), -(-h // bh), bpp, block)
        if surface.write(out, texture.data_at + offset, codec, w, h, picture, offsets) == 0 and level is levels[0]:
            break
    return bytes(out)


def _as_rgba8(data: bytes, texture: _Txtr, image: Image.Image) -> bytes:
    """The texture stored as RGBA8 (same size, mip count and sRGB-ness), every mip from ``image``."""
    fmt = ASTC_TO[texture.format]
    levels = layout(fmt, texture.width, texture.height, texture.mips)
    surface_data = bytearray(sum(level[4] for level in levels))
    codec = pixels.codec("RGBA8")
    for level, picture in zip(levels, surface.mip_levels(image, len(levels))):
        offset, w, h, block, _size = level
        offsets = tegra.block_addresses(w, h, 4, block)
        surface.write(surface_data, offset, codec, w, h, picture, offsets, force=True)
    head = bytearray(data[texture.head_at:texture.head_at + texture.head_size])
    struct.pack_into("<I", head, 4, fmt)
    for level, (_offset, w, h, _block, _size) in enumerate(levels):
        struct.pack_into("<I", head, texture.sizes_at + 4 * level, w * h * 4)
    out = bytearray(data[:texture.head_at]) + head + bytearray(data[texture.head_at + texture.head_size:texture.gpu_at])
    out += struct.pack("<I", 0) + surface_data
    struct.pack_into("<Q", out, texture.gpu_at - 24 + 4, 4 + len(surface_data))
    struct.pack_into("<Q", out, 4, len(out) - 0x20)
    return bytes(out)
