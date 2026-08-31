"""Decode GameCube GX tiled textures (used by BTI and BFN)."""
from __future__ import annotations

import struct
from typing import List, Tuple

from PyQt6.QtGui import QImage, QColor


def _s3tc_rgb(c: int) -> Tuple[int, int, int]:
    r = ((c >> 11) & 0x1F) * 255 // 31
    g = ((c >> 5) & 0x3F) * 255 // 63
    b = (c & 0x1F) * 255 // 31
    return r, g, b


def _rgb5a3(c: int) -> Tuple[int, int, int, int]:
    if c & 0x8000:
        r = ((c >> 10) & 0x1F) * 255 // 31
        g = ((c >> 5) & 0x1F) * 255 // 31
        b = (c & 0x1F) * 255 // 31
        return r, g, b, 255
    a = ((c >> 12) & 0x07) * 255 // 7
    r = ((c >> 8) & 0x0F) * 255 // 15
    g = ((c >> 4) & 0x0F) * 255 // 15
    b = (c & 0x0F) * 255 // 15
    return r, g, b, a


def _rgb565(c: int) -> Tuple[int, int, int, int]:
    r, g, b = _s3tc_rgb(c)
    return r, g, b, 255


def decode_gx(data: bytes, width: int, height: int, fmt: int,
              palette: bytes = b"", pal_fmt: int = 0) -> QImage:
    img = QImage(width, height, QImage.Format.Format_ARGB32)
    img.fill(0)
    src = memoryview(data)

    def put(x, y, r, g, b, a):
        if 0 <= x < width and 0 <= y < height:
            img.setPixel(x, y, QColor(r, g, b, a).rgba())

    def pal_color(index: int) -> Tuple[int, int, int, int]:
        if pal_fmt == 0:  # IA8
            off = index * 2
            if off + 1 >= len(palette):
                return 255, 255, 255, 255
            a, i = palette[off], palette[off + 1]
            return i, i, i, a
        if pal_fmt == 1:  # RGB565
            if index * 2 + 1 >= len(palette):
                return 255, 255, 255, 255
            c = struct.unpack_from(">H", palette, index * 2)[0]
            return _rgb565(c)
        if index * 2 + 1 >= len(palette):
            return 255, 255, 255, 255
        c = struct.unpack_from(">H", palette, index * 2)[0]
        return _rgb5a3(c)

    i = 0
    if fmt == 0:  # I4
        for ty in range(0, height, 8):
            for tx in range(0, width, 8):
                for y in range(8):
                    for x in range(0, 8, 2):
                        if i >= len(src):
                            return img
                        val = src[i]
                        i += 1
                        a = (val >> 4) * 17
                        b = (val & 0x0F) * 17
                        put(tx + x, ty + y, a, a, a, a)
                        put(tx + x + 1, ty + y, b, b, b, b)
    elif fmt == 1:  # I8
        for ty in range(0, height, 4):
            for tx in range(0, width, 8):
                for y in range(4):
                    for x in range(8):
                        if i >= len(src):
                            return img
                        v = src[i]
                        i += 1
                        put(tx + x, ty + y, v, v, v, v)
    elif fmt == 2:  # IA4
        for ty in range(0, height, 4):
            for tx in range(0, width, 8):
                for y in range(4):
                    for x in range(8):
                        if i >= len(src):
                            return img
                        val = src[i]
                        i += 1
                        a = (val >> 4) * 17
                        v = (val & 0x0F) * 17
                        put(tx + x, ty + y, v, v, v, a)
    elif fmt == 3:  # IA8
        for ty in range(0, height, 4):
            for tx in range(0, width, 8):
                for y in range(4):
                    for x in range(8):
                        if i + 1 >= len(src):
                            return img
                        a, v = src[i], src[i + 1]
                        i += 2
                        put(tx + x, ty + y, v, v, v, a)
    elif fmt == 4:  # RGB565
        for ty in range(0, height, 4):
            for tx in range(0, width, 8):
                for y in range(4):
                    for x in range(8):
                        if i + 1 >= len(src):
                            return img
                        c = struct.unpack_from(">H", src, i)[0]
                        i += 2
                        put(tx + x, ty + y, *_rgb565(c))
    elif fmt == 5:  # RGB5A3
        for ty in range(0, height, 4):
            for tx in range(0, width, 8):
                for y in range(4):
                    for x in range(8):
                        if i + 1 >= len(src):
                            return img
                        c = struct.unpack_from(">H", src, i)[0]
                        i += 2
                        put(tx + x, ty + y, *_rgb5a3(c))
    elif fmt == 6:  # RGBA8
        for ty in range(0, height, 4):
            for tx in range(0, width, 4):
                ar: List[Tuple[int, int]] = []
                gb: List[Tuple[int, int]] = []
                for _ in range(16):
                    if i + 1 >= len(src):
                        return img
                    ar.append((src[i], src[i + 1]))
                    i += 2
                for _ in range(16):
                    if i + 1 >= len(src):
                        return img
                    gb.append((src[i], src[i + 1]))
                    i += 2
                n = 0
                for y in range(4):
                    for x in range(4):
                        a, r = ar[n]
                        g, b = gb[n]
                        n += 1
                        put(tx + x, ty + y, r, g, b, a)
    elif fmt == 8:  # C4
        for ty in range(0, height, 8):
            for tx in range(0, width, 8):
                for y in range(8):
                    for x in range(0, 8, 2):
                        if i >= len(src):
                            return img
                        val = src[i]
                        i += 1
                        put(tx + x, ty + y, *pal_color(val >> 4))
                        put(tx + x + 1, ty + y, *pal_color(val & 0x0F))
    elif fmt == 9:  # C8
        for ty in range(0, height, 4):
            for tx in range(0, width, 8):
                for y in range(4):
                    for x in range(8):
                        if i >= len(src):
                            return img
                        put(tx + x, ty + y, *pal_color(src[i]))
                        i += 1
    elif fmt == 14:  # CMPR
        for ty in range(0, height, 8):
            for tx in range(0, width, 8):
                for by in (0, 4):
                    for bx in (0, 4):
                        if i + 8 > len(src):
                            return img
                        c0, c1 = struct.unpack_from(">HH", src, i)
                        bits = struct.unpack_from(">I", src, i + 4)[0]
                        i += 8
                        p0 = _s3tc_rgb(c0) + (255,)
                        p1 = _s3tc_rgb(c1) + (255,)
                        if c0 > c1:
                            p2 = tuple((2 * p0[k] + p1[k]) // 3 for k in range(4))
                            p3 = tuple((p0[k] + 2 * p1[k]) // 3 for k in range(4))
                        else:
                            p2 = tuple((p0[k] + p1[k]) // 2 for k in range(3)) + (255,)
                            p3 = (0, 0, 0, 0)
                        palette = (p0, p1, p2, p3)
                        for y in range(4):
                            for x in range(4):
                                shift = 30 - (y * 4 + x) * 2
                                put(tx + bx + x, ty + by + y, *palette[(bits >> shift) & 3])
    else:
        return img
    return img
