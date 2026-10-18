"""Midway IMG libraries of WWF WrestleMania (arcade, Wolf Unit, REV 1.30): images and palettes read from the file bytes.

Layout follows ``docs/IMG_FORMAT.md`` and ``src/assets/img.c`` of the recompiled port (wwfmania_recomp_public, GPL-3.0):
a 28-byte header, the image records at ``oset``, then the palette records, then the pixel data. Pixels are one byte per
palette index, rows padded to 4 bytes; index 0 is transparent. Colours are 15-bit ``xRRRRRGGGGGBBBBB``. All values are
little-endian. Pixel and colour offsets are absolute file offsets.

A port override (``<LABEL>.png``) holds palette indices, not colours: the same size as the original times a whole
number k, indexed (or 8-bit grey with the indices as values), index 0 transparent. ``check_override`` tests that rule.
"""
import struct
from dataclasses import dataclass
from typing import List, Optional, Tuple

HEADER_SIZE = 28
IMAGE_RECORD = 50
IMAGE_RECORD_V0 = 42
PALETTE_RECORD = 26
BUILTIN_PALETTES = 3
MAX_OVERRIDE_SCALE = 8


class FormatError(ValueError):
    pass


@dataclass(frozen=True)
class Palette:
    name: str
    bits: int
    colors: Tuple[int, ...]


@dataclass(frozen=True)
class Image:
    name: str
    width: int
    height: int
    anix: int
    aniy: int
    palette: Optional[int]     # index into the library's palettes, None when the record names a built-in one
    pixels: bytes              # width * height palette indices, rows without padding


def _name(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("ascii", "replace")


def parse(data: bytes) -> Tuple[List[Image], List[Palette]]:
    """Every image and palette of one IMG library. Raises FormatError when a table or pixel block runs past the file."""
    if len(data) < HEADER_SIZE:
        raise FormatError(f"file too small ({len(data)} bytes)")
    count, pal_count = struct.unpack_from("<HH", data, 0)
    oset = struct.unpack_from("<I", data, 4)[0]
    version = struct.unpack_from("<H", data, 8)[0]
    record = IMAGE_RECORD_V0 if version == 0 else IMAGE_RECORD
    npal = max(pal_count - BUILTIN_PALETTES, 0)
    pal_table = oset + count * record
    if oset > len(data) or pal_table + npal * PALETTE_RECORD > len(data):
        raise FormatError("record tables run past the file")
    palettes: List[Palette] = []
    for i in range(npal):
        at = pal_table + i * PALETTE_RECORD
        ncolors = struct.unpack_from("<H", data, at + 12)[0]
        coff = struct.unpack_from("<I", data, at + 14)[0]
        if coff + ncolors * 2 > oset:
            raise FormatError(f"palette {i} colours run past the table")
        colors = struct.unpack_from(f"<{ncolors}H", data, coff) if ncolors else ()
        palettes.append(Palette(_name(data[at:at + 10]), data[at + 11], tuple(colors)))
    images: List[Image] = []
    for i in range(count):
        at = oset + i * record
        if version == 0:      # no flags field: the anchor starts at 16
            anix, aniy, width, height, palind = struct.unpack_from("<hhHHH", data, at + 16)
            pix = struct.unpack_from("<I", data, at + 26)[0]
        else:                 # flags at 16, anchor at 18
            anix, aniy, width, height, palind = struct.unpack_from("<hhHHH", data, at + 18)
            pix = struct.unpack_from("<I", data, at + 28)[0]
        stride = (width + 3) & ~3
        if pix + stride * height > oset:
            raise FormatError(f"image {i} pixels run past the table")
        pixels = b"".join(data[pix + y * stride:pix + y * stride + width] for y in range(height))
        palette = palind - BUILTIN_PALETTES if BUILTIN_PALETTES <= palind < BUILTIN_PALETTES + npal else None
        images.append(Image(_name(data[at:at + 16]), width, height, anix, aniy, palette, pixels))
    return images, palettes


def rgb_of(colour15: int) -> Tuple[int, int, int]:
    """A 15-bit colour as 8-bit RGB (5 bits scaled to 0..255)."""
    return tuple((value * 255) // 31 for value in ((colour15 >> 10) & 31, (colour15 >> 5) & 31, colour15 & 31))


def check_override(width: int, height: int, override_size: Tuple[int, int]) -> Optional[str]:
    """None when an override of ``override_size`` fits an image of ``width`` x ``height``, else the reason."""
    ow, oh = override_size
    if ow % width or oh % height:
        return f"{ow}x{oh} is not a whole multiple of {width}x{height}"
    scale_w, scale_h = ow // width, oh // height
    if scale_w != scale_h or not 1 <= scale_w <= MAX_OVERRIDE_SCALE:
        return f"scale {scale_w}x{scale_h} is not one whole number up to {MAX_OVERRIDE_SCALE}"
    return None
