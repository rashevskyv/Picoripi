"""PlayStation TIM images, one or several back to back (a TIM file, Vagrant Story's ``*.DIS``).

A TIM: ``u32 0x10``, ``u32 flags`` (bits 0-2: 0 4-bit, 1 8-bit, 2 16-bit, 3 24-bit; bit 3: a CLUT
follows), then the CLUT block and the pixel block, each ``u32 length, u16 x, y, w, h`` and data (w in
16-bit VRAM words). The textures of a file are its TIMs from ``offset`` (default 0) until the next
bytes are not a TIM; an indexed one is shown with CLUT row ``clut_row`` (default 0). Writing keeps
the CLUT (new colours take the nearest entry) and changes only the pixels that differ.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

MAGIC = 0x10
_BITS = {0: 4, 1: 8, 2: 16}


def detect(data: bytes) -> bool:
    return len(data) >= 20 and struct.unpack_from("<II", data, 0) in ((MAGIC, f) for f in (0, 1, 2, 8, 9))


def _tims(data: bytes, start: int) -> List[Dict[str, Any]]:
    out, at = [], start
    while at + 20 <= len(data):
        magic, flags = struct.unpack_from("<II", data, at)
        if magic != MAGIC or flags & 7 not in _BITS or flags & ~0xF:
            break
        pos, clut = at + 8, None
        if flags & 8:
            length, _x, _y, width, height = struct.unpack_from("<I4H", data, pos)
            clut = (pos + 12, width * height)
            pos += length
        length, _x, _y, words, height = struct.unpack_from("<I4H", data, pos)
        bits = _BITS[flags & 7]
        out.append({"bits": bits, "clut": clut, "pixels": pos + 12, "width": words * 16 // bits, "height": height})
        at = pos + length
    return out


def _codec(data: bytes, tim: Dict[str, Any], row: int) -> pixels.Codec:
    bits = tim["bits"]
    if bits == 16:
        return pixels.codec("psx:RGB555")
    if tim["clut"] is None:
        return pixels.codec(f"psx:{bits}bpp")
    start, count = tim["clut"]
    size = 1 << bits
    row = min(row, max(0, count // size - 1))
    decode, _encode = pixels.psx_clut()
    words = struct.unpack_from(f"<{min(size, count)}H", data, start + row * size * 2)
    return pixels.palette_codec(f"psx:CI{bits}", bits, [decode(v) for v in words], endian="<", low_first=True)


def _list(data: bytes, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    start = params.get("offset", 0)
    found = _tims(data, int(start, 0) if isinstance(start, str) else int(start))
    if not found:
        raise ValueError("Not a TIM image")
    return found


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    row = int(params.get("clut_row", 0))
    return [Texture(str(i), surface.read(data, t["pixels"], _codec(data, t, row), t["width"], t["height"]),
                    f"TIM {t['bits']}-bit") for i, t in enumerate(_list(data, params))]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    tims = _list(data, params)
    row = int(params.get("clut_row", 0))
    for index, image in images.items():
        t = tims[index]
        surface.write(out, t["pixels"], _codec(data, t, row), t["width"], t["height"], image)
    return bytes(out)
