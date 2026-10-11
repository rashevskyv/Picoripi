"""Silent Hill 3 (PC) ``.tex`` textures from ``pic.arc``: PS2 GS swizzled 8-bit (palette) and 32-bit pictures.

A file holds one texture. Its header is the run ``FF FF FF FF 00 00 00 00 00`` (found by search). Fields from the
header: width (+8, u16), height (+10, u16), bit count (+12, u8: 8 = palette, 24 = 32-bit RGBA), data size (+16,
u32). The pixel data starts 0x40 bytes after the header. An 8-bit texture has a palette header 0x20 bytes after
its data (palette size u32, bytes per entry at +12, block size at +14) and the palette 0x30 bytes after that.
A 32-bit texture has no palette.

Pixels are PS2 GS storage: 8-bit indices in PSMT8 order (the layout of the SH3X texture tool, checked on
``pic/_work/ura0000.tex``), 32-bit RGBA in PSMCT32 order (page 64x32, block 8x8, column of 2 rows). The palette is
read in 256-byte blocks, 16 colours per block, with the 8-entry groups swapped every 32 colours. A PS2 alpha of
0x80 is opaque: the image alpha is min(255, 2 * a).

Writing keeps every pixel whose colour is unchanged, so an unedited file gives back its own bytes. A changed pixel
takes the palette index with the nearest colour (8-bit) or its own colour (32-bit).
Confidence: the 8-bit and 32-bit layouts were checked by eye on game pictures. 4-bit textures and the other header
kinds are not decoded: ``read`` raises ValueError for them.
"""
from __future__ import annotations

import struct
from functools import lru_cache
from typing import Dict, List, Tuple

from PIL import Image

from core.texture_formats import Texture

MAGIC = b"\xff\xff\xff\xff\x00\x00\x00\x00\x00"
PALETTE_BLOCK = 256
_BLOCK = [0, 1, 4, 5, 16, 17, 20, 21, 2, 3, 6, 7, 18, 19, 22, 23, 8, 9, 12, 13, 24, 25, 28, 29, 10, 11, 14, 15, 26, 27, 30, 31]
_COLUMN_WORD32 = [0, 1, 4, 5, 8, 9, 12, 13, 2, 3, 6, 7, 10, 11, 14, 15]
Colour = Tuple[int, int, int, int]


def _header(data: bytes) -> int:
    at = data.find(MAGIC)
    if at < 0:
        raise ValueError("no texture header in this file")
    return at


@lru_cache(maxsize=32)
def _order8(width: int, height: int) -> Tuple[int, ...]:
    """Pixel index (y * width + x) -> byte offset of its index in the swizzled 8-bit data."""
    out = [0] * (width * height)
    for y in range(height):
        for x in range(width):
            block_location = (y & ~0xF) * width + (x & ~0xF) * 2
            swap_selector = (((y + 2) >> 2) & 0x1) * 4
            pos_y = (((y & ~3) >> 1) + (y & 1)) & 0x7
            column_location = pos_y * width * 2 + ((x + swap_selector) & 0x7) * 4
            byte_num = ((y >> 1) & 1) + ((x >> 2) & 2)
            out[y * width + x] = block_location + column_location + byte_num
    return tuple(out)


@lru_cache(maxsize=32)
def _order32(width: int, height: int) -> Tuple[int, ...]:
    """Pixel index -> byte offset of its 4 bytes in the swizzled 32-bit data (PSMCT32)."""
    dbw = width // 64
    out = [0] * (width * height)
    for y in range(height):
        for x in range(width):
            page_x, page_y = x // 64, y // 32
            page = page_x + page_y * dbw
            px, py = x - page_x * 64, y - page_y * 32
            block_x, block_y = px // 8, py // 8
            block = _BLOCK[block_x + block_y * 8]
            bx, by = px - block_x * 8, py - block_y * 8
            column = by // 2
            cy = by - column * 2
            word = page * 2048 + block * 64 + column * 16 + _COLUMN_WORD32[bx + cy * 8]
            out[y * width + x] = word * 4
    return tuple(out)


def _alpha_in(a: int) -> int:
    return min(255, 2 * a)


def _alpha_out(a: int) -> int:
    return min(128, (a + 1) // 2)


def _palette(data: bytes, at: int, size: int, entry: int) -> List[Colour]:
    colours: List[Colour] = []
    for block in range(size // PALETTE_BLOCK):
        start = at + block * PALETTE_BLOCK
        chunk = data[start:start + entry]
        for i in range(0, len(chunk) - 3, 4):
            colours.append((chunk[i], chunk[i + 1], chunk[i + 2], _alpha_in(chunk[i + 3])))
    for i in range(8, len(colours) - 8, 32):
        colours[i:i + 8], colours[i + 8:i + 16] = colours[i + 8:i + 16], colours[i:i + 8]
    return colours


def _describe(data: bytes) -> Dict[str, int]:
    at = _header(data)
    width, height, bits = struct.unpack_from("<HHB", data, at + 8)
    size = struct.unpack_from("<I", data, at + 16)[0]
    info = {"width": width, "height": height, "bits": bits, "size": size, "pixels": at + 0x40}
    if bits == 8:
        if size != width * height:
            raise ValueError("8-bit texture: data size does not match width x height")
        pal = info["pixels"] + size + 0x20
        psize = struct.unpack_from("<I", data, pal)[0]
        bypp, entry = data[pal + 12], data[pal + 14]
        if bypp != 4 or psize % PALETTE_BLOCK or not 0 < entry <= PALETTE_BLOCK:
            raise ValueError("8-bit texture: palette header not recognised")
        info.update({"palette_at": pal + 0x30, "palette_size": psize, "entry": entry})
    elif bits == 24 and size == width * height * 4:
        pass
    else:
        raise ValueError(f"texture layout not supported yet (bit count {bits}, data {size:#x} bytes)")
    return info


def read(data: bytes, params: Dict[str, object]) -> List[Texture]:
    """The texture of the file as RGBA; raises ValueError for the layouts not decoded yet."""
    info = _describe(data)
    width, height, pixels = info["width"], info["height"], info["pixels"]
    tex = data[pixels:pixels + info["size"]]
    if info["bits"] == 8:
        palette = _palette(data, info["palette_at"], info["palette_size"], info["entry"])
        colours = [palette[tex[o]] if tex[o] < len(palette) else (0, 0, 0, 0) for o in _order8(width, height)]
        fmt = "PS2 PSMT8"
    else:
        colours = []
        for o in _order32(width, height):
            colours.append((tex[o], tex[o + 1], tex[o + 2], _alpha_in(tex[o + 3])))
        fmt = "PS2 PSMCT32"
    image = Image.new("RGBA", (width, height))
    image.putdata(colours)
    return [Texture(name="", image=image, pixel_format=fmt, mipmaps=1)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, object]) -> bytes:
    """The file with its texture replaced by ``images[0]`` (same size). Unchanged pixels keep their bytes."""
    if 0 not in images:
        return data
    info = _describe(data)
    width, height, base = info["width"], info["height"], info["pixels"]
    image = images[0].convert("RGBA")
    if image.size != (width, height):
        raise ValueError(f"image is {image.size}, the texture is {(width, height)}")
    new = bytearray(data)
    wanted = list(image.getdata())
    if info["bits"] == 8:
        palette = _palette(data, info["palette_at"], info["palette_size"], info["entry"])
        order = _order8(width, height)
        nearest: Dict[Colour, int] = {}
        for i, colour in enumerate(wanted):
            o = base + order[i]
            current = data[o]
            if current < len(palette) and palette[current] == colour:
                continue
            if colour not in nearest:
                nearest[colour] = min(range(len(palette)), key=lambda k: _distance(palette[k], colour))
            new[o] = nearest[colour]
    else:
        order = _order32(width, height)
        for i, colour in enumerate(wanted):
            o = base + order[i]
            if (data[o], data[o + 1], data[o + 2], _alpha_in(data[o + 3])) == colour:
                continue
            new[o:o + 4] = bytes((colour[0], colour[1], colour[2], _alpha_out(colour[3])))
    return bytes(new)


def _distance(a: Colour, b: Colour) -> int:
    return sum((x - y) ** 2 for x, y in zip(a, b))
