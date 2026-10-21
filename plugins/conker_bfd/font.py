"""The game's grayscale font: 95 run-length glyphs, decoded to 8-bit PGM sources for the Font Editor.

Record layout (big-endian, from the community decompilation's font notes): width byte, height byte, two
metadata bytes, then the u32 record size (header included). The run bytes that follow hold a 4-bit
intensity in the high nibble (0x00-0xF0) and a run length minus one in the low nibble. The runs fill the
glyph row by row. The table is followed by zero bytes up to its end offset.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import List, Optional

from .n64_archive import RomError

GLYPH_COUNT = 95
HEADER_SIZE = 8
MAX_RUN = 16


@dataclass(frozen=True)
class Glyph:
    index: int
    width: int
    height: int
    meta: bytes
    pixels: bytes  # row-major, intensity 0x00-0xF0 per pixel
    rle: bytes     # the run bytes exactly as stored


def decode_rle(width: int, height: int, rle: bytes) -> bytes:
    if width <= 0 or height <= 0:
        raise RomError("glyph dimensions must be positive")
    expected = width * height
    pixels = bytearray()
    for value in rle:
        pixels.extend([value & 0xF0] * ((value & 0x0F) + 1))
        if len(pixels) > expected:
            raise RomError("glyph runs exceed the declared size")
    if len(pixels) != expected:
        raise RomError(f"glyph runs fill {len(pixels)} pixels, expected {expected}")
    return bytes(pixels)


def encode_rle(width: int, height: int, pixels: bytes) -> bytes:
    """Inverse of decode_rle for 4-bit intensities. Runs stop at the row end and at 16 pixels."""
    if len(pixels) != width * height or any(value & 0x0F for value in pixels):
        raise ValueError("pixels must be width*height values with zero low nibbles")
    out = bytearray()
    pos = 0
    while pos < len(pixels):
        run = 1
        while (run < MAX_RUN and pos + run < len(pixels) and (pos + run) % width != 0
               and pixels[pos + run] == pixels[pos]):
            run += 1
        out.append(pixels[pos] | (run - 1))
        pos += run
    return bytes(out)


def parse_table(rom: bytes, start: int, end: int, count: int = GLYPH_COUNT) -> List[Glyph]:
    """Read ``count`` records from ``rom[start:end]``; the bytes after them must be zero."""
    if not 0 <= start < end <= len(rom):
        raise RomError("font table lies outside the ROM")
    glyphs: List[Glyph] = []
    pos = start
    for index in range(count):
        if pos + HEADER_SIZE > end:
            raise RomError(f"glyph {index} header is outside the table")
        width, height = rom[pos], rom[pos + 1]
        meta = bytes(rom[pos + 2:pos + 4])
        size = struct.unpack_from(">I", rom, pos + 4)[0]
        if size < HEADER_SIZE or pos + size > end:
            raise RomError(f"glyph {index} has an invalid record size")
        rle = bytes(rom[pos + HEADER_SIZE:pos + size])
        glyphs.append(Glyph(index=index, width=width, height=height, meta=meta,
                            pixels=decode_rle(width, height, rle), rle=rle))
        pos += size
    if any(rom[pos:end]):
        raise RomError("font table padding is not zero")
    return glyphs


def encode_record(glyph: Glyph) -> bytes:
    """Rebuild one record from its fields (used by the round-trip test)."""
    rle = encode_rle(glyph.width, glyph.height, glyph.pixels)
    size = HEADER_SIZE + len(rle)
    return bytes([glyph.width, glyph.height]) + glyph.meta + struct.pack(">I", size) + rle


SPACE = 0x20
MAP_DISTINCT = 93  # the 95 map bytes hold 93 distinct codes; the first occurrence wins


def read_glyph_map(data: bytes, offset: int) -> bytes:
    """The 95 input-byte codes whose positions are the glyph indices (checked against the known count)."""
    codes = bytes(data[offset:offset + GLYPH_COUNT])
    if len(codes) != GLYPH_COUNT or len(set(codes)) != MAP_DISTINCT:
        raise RomError("glyph map does not match the expected shape")
    return codes


def glyph_index(byte: int, glyph_map: bytes) -> Optional[int]:
    """Glyph index of one text byte: lowercase folds to uppercase, the space has no glyph (None)."""
    if byte == SPACE:
        return None
    if 0x61 <= byte <= 0x7A:
        byte -= 0x20
    found = glyph_map.find(bytes([byte]))
    return found if found >= 0 else None


def pgm_bytes(glyph: Glyph) -> bytes:
    """Portable graymap with maxval 255. Values are the stored intensities, unscaled."""
    header = f"P5\n{glyph.width} {glyph.height}\n255\n".encode("ascii")
    return header + glyph.pixels
