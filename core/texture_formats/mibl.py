"""Monolith Soft MIBL textures (Switch Xenoblade games: ``.witex``, the textures inside ``.wilay`` layouts and
``.wifnt`` fonts): Tegra block-linear image data followed, at the end of the last 4096-byte page, by a 40-byte
footer: image size, alignment (4096), width, height, depth, view dimension, format, mip count, version 10001,
``LBIM``. Mip levels follow each other in the image data, each swizzled with its own block height (the
``tegra_swizzle`` rules: 16 GOBs for a tall level, halving while the level is short).

One texture per block; the block keeps its size on write (same image size, same mips, regenerated).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.texture_formats import Texture, pixels, surface, tegra

FOOTER = struct.Struct("<9I4s")
MAGIC = b"LBIM"
PAGE = 4096
FORMATS = {1: "R8", 37: "RGBA8", 66: "BC1", 68: "BC3", 73: "BC4", 75: "BC5", 77: "BC7", 109: "BGRA8"}


def detect(data: bytes) -> bool:
    return len(data) >= FOOTER.size and bytes(data[-4:]) == MAGIC and struct.unpack_from("<I", data, len(data) - 8)[0] == 10001


def footer(data: bytes) -> Dict[str, int]:
    (size, alignment, width, height, depth, dimension, fmt, mips, version, magic) = FOOTER.unpack_from(data, len(data) - FOOTER.size)
    if magic != MAGIC or version != 10001:
        raise ValueError("Not a MIBL texture")
    return {"size": size, "alignment": alignment, "width": width, "height": height, "depth": depth,
            "dimension": dimension, "format": fmt, "mips": mips}


def block_size(info: Dict[str, int]) -> int:
    """Bytes of the whole block from its footer: the image size (page-padded mip data) and, only when the
    footer does not fit in the padding after the last mip level, one more page for it."""
    levels_total = image_size(info["width"], info["height"], codec_of(info["format"]), info["mips"])
    size = -(-info["size"] // PAGE) * PAGE
    return size if info["size"] - levels_total >= FOOTER.size else size + PAGE


def _block_height_mip0(rows: int) -> int:
    tall = rows + rows // 2
    return 16 if tall >= 128 else 8 if tall >= 64 else 4 if tall >= 32 else 2 if tall >= 16 else 1


def levels(width: int, height: int, codec: pixels.Codec, mips: int) -> List[Tuple[int, int, int, int, Tuple[int, ...]]]:
    """``(offset, width, height, swizzled size, element offsets)`` of every mip level."""
    bw, bh = codec.block
    base = _block_height_mip0(-(-height // bh))
    out, at = [], 0
    for level in range(mips):
        w, h = max(1, width >> level), max(1, height >> level)
        wide, high = -(-w // bw), -(-h // bh)
        block_height = base
        while high <= (block_height // 2) * 8 and block_height > 1:
            block_height //= 2
        size = -(-wide * codec.size // 64) * 64 * (-(-high // (block_height * 8)) * block_height * 8)
        out.append((at, w, h, size, tegra.block_addresses(wide, high, codec.size, block_height)))
        at += size
    return out


def image_size(width: int, height: int, codec: pixels.Codec, mips: int = 1) -> int:
    return sum(size for _at, _w, _h, size, _o in levels(width, height, codec, mips))


def codec_of(fmt: int) -> pixels.Codec:
    if fmt not in FORMATS:
        raise ValueError(f"MIBL format {fmt} is not supported yet")
    return pixels.codec(FORMATS[fmt])


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    info = footer(data)
    codec = codec_of(info["format"])
    at, width, height, _size, offsets = levels(info["width"], info["height"], codec, info["mips"])[0]
    return [Texture("", surface.read(data, at, codec, width, height, offsets), FORMATS[info["format"]], info["mips"])]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    image = images.get(0)
    if image is None:
        return bytes(data)
    info = footer(data)
    codec = codec_of(info["format"])
    out = bytearray(data)
    mips = levels(info["width"], info["height"], codec, info["mips"])
    at, width, height, _size, offsets = mips[0]
    if surface.write(out, at, codec, width, height, image, offsets) == 0:
        return bytes(data)
    for (at, width, height, _size, offsets), level in zip(mips[1:], surface.mip_levels(image.convert("RGBA"), len(mips))[1:]):
        surface.write(out, at, codec, width, height, level, offsets)
    return bytes(out)


def build(image: Image.Image, fmt: int, mips: int = 1) -> bytes:
    """A whole MIBL block of a new image (its data, padding and footer)."""
    codec = codec_of(fmt)
    plan = levels(image.width, image.height, codec, mips)
    size = -(-sum(s for _a, _w, _h, s, _o in plan) // PAGE) * PAGE
    info = {"size": size, "width": image.width, "height": image.height, "format": fmt, "mips": mips}
    out = bytearray(block_size(info))
    for (at, width, height, _s, offsets), level in zip(plan, surface.mip_levels(image.convert("RGBA"), mips)):
        surface.write(out, at, codec, width, height, level, offsets, force=True)
    FOOTER.pack_into(out, len(out) - FOOTER.size, size, PAGE, image.width, image.height, 1, 1, fmt, mips, 10001, MAGIC)
    return bytes(out)
