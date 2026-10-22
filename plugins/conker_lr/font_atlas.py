"""Conker: Live & Reloaded font atlas (``dvddata/aid/font/ConkerFont/default.bin``): the glyph texture as a grey PNG.

The bank is a CAFF file with a ``.data`` section and a ``.gpu`` section. The ``.gpu`` section is the texture memory: a
linear 8-bit luminance texture, 256 x 240 (D3DFMT_LIN_L8, 0x13 in the xboxrecomp D3D8 headers). It is not swizzled, so a
PNG row is a texture row. Export and import are exact: a PNG written from the bytes reads back to the same bytes.
"""
from __future__ import annotations

import struct
import zlib
from typing import List, Tuple

from . import caff_text

GPU_SECTION = b".gpu"
ATLAS_WIDTH = 256
ATLAS_HEIGHT = 240
ATLAS_BYTES = ATLAS_WIDTH * ATLAS_HEIGHT  # one byte a pixel: 61440, the size of the .gpu section
SECTION_ENTRY = 0x40
SECTION_ENTRY_SIZE = 0x28
SIZE_FIELD = 0x10
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class AtlasError(ValueError):
    """The bank or the PNG is not a Conker font atlas this module reads."""


def _sections(bank: bytes) -> List[Tuple[bytes, int]]:
    """The (name, size) of each section entry in the header, in table order."""
    out: List[Tuple[bytes, int]] = []
    for at in range(SECTION_ENTRY, caff_text.SECTION_BASE, SECTION_ENTRY_SIZE):
        name = bank[at:at + 8].rstrip(b"\x00")
        if not name:
            break
        out.append((name, struct.unpack_from("<I", bank, at + SIZE_FIELD)[0]))
    return out


def gpu_range(bank: bytes) -> Tuple[int, int]:
    """The file offset and size of the ``.gpu`` section. Sections sit one after another from 0x180."""
    if not bank.startswith(caff_text.MAGIC):
        raise AtlasError("not a CAFF file")
    offset = caff_text.SECTION_BASE
    for name, size in _sections(bank):
        if name == GPU_SECTION:
            if offset + size != len(bank):
                raise AtlasError("the .gpu section does not end at the end of the file")
            if size != ATLAS_BYTES:
                raise AtlasError(f"the .gpu section is {size} bytes, a 256 x 240 atlas is {ATLAS_BYTES}")
            return offset, size
        offset += size
    raise AtlasError("no .gpu section")


def atlas_pixels(bank: bytes) -> bytes:
    """The 256 x 240 luminance bytes of the atlas (row by row, top row first)."""
    offset, size = gpu_range(bank)
    return bytes(bank[offset:offset + size])


def replace_pixels(bank: bytes, pixels: bytes) -> bytes:
    """The bank with its atlas bytes replaced. The length must not change: the section sizes stay the same."""
    if len(pixels) != ATLAS_BYTES:
        raise AtlasError(f"an atlas is {ATLAS_BYTES} bytes, got {len(pixels)}")
    offset, size = gpu_range(bank)
    out = bytearray(bank)
    out[offset:offset + size] = pixels
    return bytes(out)


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def encode_png(pixels: bytes) -> bytes:
    """A grey 8-bit PNG of the atlas (no filtering, one filter byte 0 a row)."""
    if len(pixels) != ATLAS_BYTES:
        raise AtlasError(f"an atlas is {ATLAS_BYTES} bytes, got {len(pixels)}")
    rows = b"".join(b"\x00" + pixels[y * ATLAS_WIDTH:(y + 1) * ATLAS_WIDTH] for y in range(ATLAS_HEIGHT))
    header = struct.pack(">IIBBBBB", ATLAS_WIDTH, ATLAS_HEIGHT, 8, 0, 0, 0, 0)
    return PNG_SIGNATURE + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(rows, 9)) + _chunk(b"IEND", b"")


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def decode_png(png: bytes) -> bytes:
    """The luminance bytes of a 256 x 240, 8-bit grey, non-interlaced PNG (all five filter types are read)."""
    if not png.startswith(PNG_SIGNATURE):
        raise AtlasError("not a PNG file")
    at = len(PNG_SIGNATURE)
    width = height = None
    idat = bytearray()
    while at + 8 <= len(png):
        length, kind = struct.unpack_from(">I4s", png, at)
        body = png[at + 8:at + 8 + length]
        if len(body) != length or at + 12 + length > len(png):
            raise AtlasError("a PNG chunk runs past the end of the file")
        if zlib.crc32(kind + body) & 0xFFFFFFFF != struct.unpack_from(">I", png, at + 8 + length)[0]:
            raise AtlasError(f"bad CRC in the {kind!r} chunk")
        if kind == b"IHDR":
            width, height, depth, colour, _comp, _filt, interlace = struct.unpack(">IIBBBBB", body)
            if (depth, colour, interlace) != (8, 0, 0):
                raise AtlasError("the atlas PNG must be 8-bit grey, not interlaced")
        elif kind == b"IDAT":
            idat += body
        at += 12 + length
    if (width, height) != (ATLAS_WIDTH, ATLAS_HEIGHT):
        raise AtlasError(f"the atlas PNG is {width} x {height}, expected {ATLAS_WIDTH} x {ATLAS_HEIGHT}")
    raw = zlib.decompress(bytes(idat))
    stride = ATLAS_WIDTH
    if len(raw) != ATLAS_HEIGHT * (stride + 1):
        raise AtlasError("the atlas PNG data has the wrong length")
    out = bytearray()
    prev = bytearray(stride)
    for y in range(ATLAS_HEIGHT):
        kind = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for x in range(stride):
            left = line[x - 1] if x else 0
            up = prev[x]
            upleft = prev[x - 1] if x else 0
            if kind == 0:
                pass
            elif kind == 1:
                line[x] = (line[x] + left) & 0xFF
            elif kind == 2:
                line[x] = (line[x] + up) & 0xFF
            elif kind == 3:
                line[x] = (line[x] + ((left + up) >> 1)) & 0xFF
            elif kind == 4:
                line[x] = (line[x] + _paeth(left, up, upleft)) & 0xFF
            else:
                raise AtlasError(f"unknown PNG filter {kind}")
        out += line
        prev = line
    return bytes(out)
