"""Decode GameCube GX tiled textures (used by BTI and BFN) into a QImage, with the shared GX codecs.

The pixel formats live in ``core.texture_formats.pixels`` (``gx:*``: tiles of 8x8, 8x4 or 4x4, palette
formats C4/C8/C14X2 with an IA8/RGB565/RGB5A3 palette). Data cut short decodes as transparent.
"""
from __future__ import annotations

import struct

from PyQt6.QtGui import QImage

from core.texture_formats import bti, pixels, surface


def decode_gx(data: bytes, width: int, height: int, fmt: int,
              palette: bytes = b"", pal_fmt: int = 0) -> QImage:
    if fmt not in bti.FORMATS or width <= 0 or height <= 0:
        image = QImage(max(1, width), max(1, height), QImage.Format.Format_ARGB32)
        image.fill(0)
        return image
    name = f"gx:{bti.FORMATS[fmt]}"
    if fmt in bti._PALETTE:
        decode, _encode = pixels.gx_palette_format(pal_fmt if pal_fmt in (0, 1, 2) else 2)
        count = len(palette) // 2
        colours = [decode(v) for v in struct.unpack(f">{count}H", palette[:count * 2])]
        bits, tile = bti._PALETTE[fmt]
        colours += [(0, 0, 0, 0)] * ((1 << min(bits, 14)) - len(colours))
        codec = pixels.palette_codec(name, bits, colours, tile=tile)
    else:
        codec = pixels.codec(name)
    need = surface.surface_bytes(codec, width, height)
    data = bytes(data[:need]).ljust(need, b"\0")
    rgba = surface.read(data, 0, codec, width, height).tobytes()
    return QImage(rgba, width, height, width * 4, QImage.Format.Format_RGBA8888).convertToFormat(
        QImage.Format.Format_ARGB32)
