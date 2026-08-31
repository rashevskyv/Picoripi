"""BTI (JUTTexture) reader. Files in TP layouts are often Yaz0-wrapped."""
from __future__ import annotations

import struct

from PyQt6.QtGui import QImage

from core.containers.yaz0 import decompress

from .gx_texture import decode_gx


def _maybe_yaz0(data: bytes) -> bytes:
    if data[:4] == b"Yaz0":
        return decompress(data)
    return data


def bti_to_qimage(data: bytes) -> QImage:
    raw = _maybe_yaz0(data)
    if len(raw) < 0x20:
        return QImage()
    fmt, _alpha, width, height = struct.unpack_from(">BBHH", raw, 0)
    pal_fmt, ncolors, pal_off = struct.unpack_from(">HHI", raw, 8)
    data_off = struct.unpack_from(">I", raw, 0x1C)[0]
    if data_off <= 0 or data_off >= len(raw):
        data_off = 0x20
    palette = b""
    if ncolors and pal_off and pal_off < len(raw):
        palette = raw[pal_off:pal_off + ncolors * 2]
    return decode_gx(raw[data_off:], width, height, fmt, palette, pal_fmt)
