"""Silent Hill 2 (PC) textures: .tex and .tbn2 files (magic 01 09 99 19).

Layout, checked on the real files (pic\\etc\\title.tex, pic\\carbon.tex, etc\\effect\\fog.tex, etc\\effect\\footmark.tbn2):

* u16 width and height at 0x14 (repeated at 0x18); pixel data starts at 0x60.
* 8 bits per pixel, one byte per pixel = an index into a palette of 256 BGRA entries.
  - files with a palette: 256 entries (4 bytes each, B G R 00) at ``size - 16 - 1024``; the 16 bytes after it are zero
    (verified on carbon.tex: the rendered image is the typewriter from the game).
  - files without a trailing palette (fog.tex: size = 0x60 + w*h): the palette is not in the file. The index is shown
    as a grey ramp and the palette is marked unresolved.
* 4 bits per pixel: files whose size is 0x60 + w*h/2 (title.tex is 512x512). Two pixels per byte; the low nibble first is an
  assumption, not verified. The palette is not in the file, so the nibble is shown as a grey ramp (idx * 17).

Writing: an unchanged pixel keeps its original index, so an unchanged image gives the same bytes. A changed pixel takes the
nearest palette entry (8-bit with palette), or the grey index (8-bit without a palette and 4-bit).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture

MAGIC = b"\x01\x09\x99\x19"
HEADER = 0x60
PALETTE_BYTES = 1024
PALETTE_TAIL = 16


def detect(data: bytes) -> bool:
    return len(data) >= HEADER and data[:4] == MAGIC


def _size(data: bytes):
    w, h = struct.unpack_from("<HH", data, 0x14)
    if w == 0 or h == 0:
        raise ValueError("SH2 texture without a size")
    return w, h


def _layout(data: bytes):
    """(width, height, bits, palette offset or None). Raises for a layout not seen in the game files."""
    w, h = _size(data)
    pixels = w * h
    rest = len(data) - HEADER
    if rest == pixels:
        return w, h, 8, None
    if rest == pixels // 2 and pixels % 2 == 0:
        return w, h, 4, None
    pal = len(data) - PALETTE_TAIL - PALETTE_BYTES
    if rest - pixels >= PALETTE_BYTES + PALETTE_TAIL and pal >= HEADER + pixels:
        return w, h, 8, pal
    raise ValueError(f"SH2 texture layout not known: {w}x{h}, {len(data)} bytes")


def _index_at(data: bytes, w: int, bits: int, x: int, y: int) -> int:
    n = y * w + x
    if bits == 8:
        return data[HEADER + n]
    byte = data[HEADER + n // 2]
    return (byte & 0x0F) if n % 2 == 0 else (byte >> 4)


def _palette(data: bytes, pal_off):
    if pal_off is None:
        return None
    return [(data[pal_off + i * 4 + 2], data[pal_off + i * 4 + 1], data[pal_off + i * 4]) for i in range(256)]


def _rgb_of(index: int, bits: int, pal) -> tuple:
    if pal is not None:
        return pal[index]
    value = index * 17 if bits == 4 else index
    return (value, value, value)


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    w, h, bits, pal_off = _layout(data)
    pal = _palette(data, pal_off)
    image = Image.new("RGB", (w, h))
    px = image.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = _rgb_of(_index_at(data, w, bits, x, y), bits, pal)
    fmt = f"SH2 {bits}-bit indexed" + ("" if pal is not None else " (palette not in file: grey)")
    return [Texture("", image.convert("RGBA"), fmt)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    w, h, bits, pal_off = _layout(data)
    pal = _palette(data, pal_off)
    if 0 not in images:
        return bytes(data)
    sheet = images[0].convert("RGBA")
    if sheet.size != (w, h):
        raise ValueError(f"The image is {sheet.width}x{sheet.height}, the texture {w}x{h}")
    out = bytearray(data)
    sp = sheet.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = sp[x, y]
            index = _index_at(data, w, bits, x, y)
            if (r, g, b) == _rgb_of(index, bits, pal):
                continue                             # unchanged: keep the original index
            if pal is not None:
                index = min(range(256), key=lambda i: (pal[i][0] - r) ** 2 + (pal[i][1] - g) ** 2 + (pal[i][2] - b) ** 2)
            elif bits == 8:
                index = (r + g + b) // 3
            else:
                index = min(15, ((r + g + b) // 3) // 17)
            n = y * w + x
            if bits == 8:
                out[HEADER + n] = index
            else:
                pos = HEADER + n // 2
                out[pos] = (out[pos] & 0xF0) | index if n % 2 == 0 else (out[pos] & 0x0F) | (index << 4)
    return bytes(out)
