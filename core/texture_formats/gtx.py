"""Wii U GTX textures (``Gfx2``): GX2 surfaces, e.g. the UI and model textures of Twilight Princess HD
(inside the TMPK ``*.pack.gz`` next to each archive).

File: ``Gfx2`` header (u32 header size, ...), then blocks: ``BLK{``, u32 header size, u32 x2 version, u32 type,
u32 data size, u32 x2. Type 0x0B is a GX2Texture (the GX2Surface: dim, width, height, depth, mip count,
format, aa, use, image size, ..., tile mode @0x30, swizzle @0x34, ..., mip offsets @0x40; channel selection
@0x84: four bytes, 0-3 = R G B A, 4 = zero, 5 = one); 0x0C the image of the texture before it, 0x0D its smaller
mip levels, 0x01 the end.

Mip levels (checked on the game's own textures): level 1 starts the 0x0D block, level n > 1 at mip offset
n - 1; a level is laid out on its size rounded up to powers of two, and a 2D-tiled texture goes 1D-tiled for
a level narrower than 32 x (256 / 8 / bits per element) elements or lower than 16.

The stored channels go through the channel selection to the picture (an R8 texture shown as grey and
alpha...), and back on write. Writing a texture draws its mip levels again from the new picture.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Sequence, Tuple

from PIL import Image

from core.texture_formats import Texture, gx2, pixels, surface

# GX2 format (low 6 bits) -> codec, the band of the decoded image that holds each stored channel, and whether
# band 0 is a luminance the codec repeats in R, G and B
_FORMATS: Dict[int, Tuple[str, Dict[int, int], bool]] = {
    0x01: ("R8", {0: 0}, False), 0x02: ("RG4", {0: 0, 1: 1}, False), 0x07: ("RG8", {0: 0, 1: 1}, False),
    0x08: ("RGB565", {0: 0, 1: 1, 2: 2}, False), 0x0A: ("RGB5A1", {0: 0, 1: 1, 2: 2, 3: 3}, False),
    0x0B: ("RGBA4", {0: 0, 1: 1, 2: 2, 3: 3}, False), 0x1A: ("RGBA8", {0: 0, 1: 1, 2: 2, 3: 3}, False),
    0x31: ("BC1", {0: 0, 1: 1, 2: 2, 3: 3}, False), 0x32: ("BC2", {0: 0, 1: 1, 2: 2, 3: 3}, False),
    0x33: ("BC3", {0: 0, 1: 1, 2: 2, 3: 3}, False), 0x34: ("BC4L", {0: 0}, True), 0x35: ("BC5LA", {0: 0, 1: 3}, True),
}
_NAMES = {0x01: "R8", 0x02: "R4G4", 0x07: "R8G8", 0x08: "R5G6B5", 0x0A: "RGB5A1", 0x0B: "RGBA4", 0x1A: "RGBA8",
          0x31: "BC1", 0x32: "BC2", 0x33: "BC3", 0x34: "BC4", 0x35: "BC5"}


def detect(data: bytes) -> bool:
    return data[:4] == b"Gfx2"


def _surfaces(data: bytes) -> List[Dict[str, Any]]:
    if not detect(data):
        raise ValueError("Not a GTX texture")
    at = struct.unpack_from(">I", data, 4)[0]
    found: List[Dict[str, Any]] = []
    info = None
    while at + 32 <= len(data):
        kind, size = struct.unpack_from(">II", data, at + 0x10)
        body = at + struct.unpack_from(">I", data, at + 4)[0]
        if kind == 0x0B:
            info = body
        elif kind == 0x0C and info is not None:
            width, height = struct.unpack_from(">II", data, info + 4)
            mips, fmt = struct.unpack_from(">II", data, info + 0x10)
            tile, swizzle = struct.unpack_from(">II", data, info + 0x30)
            found.append({"width": width, "height": height, "mips": max(1, mips), "format": fmt & 0x3F,
                          "tile": tile, "swizzle": swizzle, "select": data[info + 0x84:info + 0x88], "data": body,
                          "mip_offsets": struct.unpack_from(">13I", data, info + 0x40), "mip_data": None})
            info = None
        elif kind == 0x0D and found:
            found[-1]["mip_data"] = body
        elif kind == 0x01:
            break
        at = body + size
    return found


def _codec(head: Dict[str, Any]):
    if head["format"] not in _FORMATS:
        raise ValueError(f"GX2 format {head['format']:#x} is not supported")
    name, bands, grey = _FORMATS[head["format"]]
    return pixels.codec(name), bands, grey


def _pow2(value: int) -> int:
    return 1 << max(0, value - 1).bit_length()


def _levels(head: Dict[str, Any], codec: pixels.Codec) -> List[Tuple[int, int, int, Sequence[int]]]:
    """``(start, width, height, element offsets)`` of every level stored in the file."""
    bw, bh = codec.block
    bpp = codec.size * 8
    out = []
    for level in range(head["mips"] if head["mip_data"] is not None else 1):
        width, height = max(1, head["width"] >> level), max(1, head["height"] >> level)
        wide, high = -(-width // bw), -(-height // bh)
        if level == 0:
            out.append((head["data"], width, height,
                        gx2.element_offsets(wide, high, bpp, head["tile"], head["swizzle"])))
            continue
        start = head["mip_data"] + (0 if level == 1 else head["mip_offsets"][level - 1])
        padded_w, padded_h = -(-_pow2(width) // bw), -(-_pow2(height) // bh)
        tile = head["tile"]
        if tile == gx2.TILE_2D_THIN1 and (padded_w < 32 * max(1, 256 // bpp // 8) or padded_h < 16):
            tile = gx2.TILE_1D_THIN1
        full = gx2.element_offsets(padded_w, padded_h, bpp, tile, head["swizzle"])
        out.append((start, width, height, [full[y * padded_w + x] for y in range(high) for x in range(wide)]))
    return out


def _stored(data: bytes, head: Dict[str, Any], codec: pixels.Codec) -> Image.Image:
    start, width, height, offsets = _levels(head, codec)[0]
    return surface.read(data, start, codec, width, height, offsets)


def _shown(stored: Image.Image, head: Dict[str, Any]) -> Image.Image:
    _codec_, bands, _grey = _codec(head)
    planes = stored.split()
    zero, one = Image.new("L", stored.size, 0), Image.new("L", stored.size, 255)
    out = []
    for select in head["select"]:
        if select < 4:
            out.append(planes[bands[select]] if select in bands else (one if select == 3 else zero))
        else:
            out.append(zero if select == 4 else one)
    return Image.merge("RGBA", out)


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    textures = []
    for index, head in enumerate(_surfaces(data)):
        codec, _bands, _grey = _codec(head)
        textures.append(Texture(str(index), _shown(_stored(data, head, codec), head),
                                _NAMES.get(head["format"], hex(head["format"])), head["mips"]))
    return textures


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    heads = _surfaces(data)
    changed = False
    for index, image in images.items():
        head = heads[index]
        codec, bands, grey = _codec(head)
        planes = list(_stored(data, head, codec).split())
        shown = image.convert("RGBA").split()
        for channel, band in bands.items():
            if channel in head["select"]:
                plane = shown[bytes(head["select"]).index(channel)]
                for target in ((0, 1, 2) if grey and band == 0 else (band,)):
                    planes[target] = plane
        stored = Image.merge("RGBA", planes)
        levels = _levels(head, codec)
        start, width, height, offsets = levels[0]
        if surface.write(out, start, codec, width, height, stored, offsets) == 0:
            continue
        changed = True
        for (start, width, height, offsets), level in zip(levels[1:], surface.mip_levels(stored, len(levels))[1:]):
            surface.write(out, start, codec, width, height, level, offsets)
    return bytes(out) if changed else data
