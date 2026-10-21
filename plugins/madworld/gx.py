"""GameCube / Wii GX pixels and TPL pictures for MadWorld: C4 and IA8 codecs, one-picture TPLs, glyph grids.

A glyph is ``(width, height, pixels)`` with one byte per pixel, row by row. A grid font is a TPL of cells ``cell`` =
(width, height), ``columns`` per row, glyph i in cell i, top-left corner of the cell. Only the formats MadWorld uses
are decoded here; the rest of a TPL is copied as it is.
"""
from __future__ import annotations

import struct
from typing import List, Optional, Tuple

TPL_MAGIC = b"\x00\x20\xaf\x30"
IA8, C4 = 3, 8
# GX format -> (block width, block height, bits per pixel): the size of a block-coded image.
_BLOCKS = {0: (8, 8, 4), 1: (8, 4, 8), 2: (8, 4, 8), 3: (4, 4, 16), 4: (4, 4, 16), 5: (4, 4, 16), 6: (4, 4, 32),
           8: (8, 8, 4), 9: (8, 4, 8), 14: (8, 8, 4)}


def c4_decode(raw: bytes, w: int, h: int) -> bytearray:
    """Palette indices (0..15), one byte per pixel."""
    px = bytearray(w * h)
    i = 0
    for ty in range(0, h, 8):
        for tx in range(0, w, 8):
            for y in range(ty, ty + 8):
                for x in range(tx, tx + 8, 2):
                    b = raw[i]
                    i += 1
                    if y < h:
                        if x < w:
                            px[y * w + x] = b >> 4
                        if x + 1 < w:
                            px[y * w + x + 1] = b & 15
    return px


def c4_encode(idx, w: int, h: int) -> bytes:
    out = bytearray()
    for ty in range(0, h, 8):
        for tx in range(0, w, 8):
            for y in range(ty, ty + 8):
                for x in range(tx, tx + 8, 2):
                    a = idx[y * w + x] if y < h and x < w else 0
                    b = idx[y * w + x + 1] if y < h and x + 1 < w else 0
                    out.append((a & 15) << 4 | (b & 15))
    return bytes(out)


def ia8_decode(raw: bytes, w: int, h: int) -> Tuple[bytearray, bytearray]:
    """``(alpha, intensity)``, one byte per pixel each."""
    a, i = bytearray(w * h), bytearray(w * h)
    k = 0
    for ty in range(0, h, 4):
        for tx in range(0, w, 4):
            for y in range(ty, ty + 4):
                for x in range(tx, tx + 4):
                    if y < h and x < w:
                        a[y * w + x], i[y * w + x] = raw[k], raw[k + 1]
                    k += 2
    return a, i


def ia8_encode(alpha, inten, w: int, h: int) -> bytes:
    out = bytearray()
    for ty in range(0, h, 4):
        for tx in range(0, w, 4):
            for y in range(ty, ty + 4):
                for x in range(tx, tx + 4):
                    inside = y < h and x < w
                    out += bytes((alpha[y * w + x], inten[y * w + x]) if inside else (0, 0))
    return bytes(out)


def tpl_size(data: bytes, at: int = 0) -> Optional[int]:
    """Byte size of the TPL at ``at`` (palettes included), None when it is not one."""
    try:
        if data[at:at + 4] != TPL_MAGIC:
            return None
        count, table = struct.unpack_from(">II", data, at + 4)
        if table != 0xC or not 0 < count < 512:
            return None
        end = 0
        for i in range(count):
            image, palette = struct.unpack_from(">II", data, at + 12 + 8 * i)
            height, width, fmt, start = struct.unpack_from(">HHII", data, at + image)
            if fmt not in _BLOCKS or not (0 < width <= 4096 and 0 < height <= 4096):
                return None
            bw, bh, bpp = _BLOCKS[fmt]
            lod = data[at + image + 0x22]
            size, w, h = 0, width, height
            for _ in range(lod + 1 if lod < 12 else 1):
                size += -(-w // bw) * bw * -(-h // bh) * bh * bpp // 8
                w, h = max(1, w // 2), max(1, h // 2)
            end = max(end, start + size)
            if palette:
                n, _u, _p, _f, pal_at = struct.unpack_from(">HBBII", data, at + palette)
                end = max(end, pal_at + 2 * n)
        return end if at + end <= len(data) else None
    except struct.error:
        return None


def tpl(fmt: int, w: int, h: int, data: bytes, palette: bytes = b"", pal_fmt: int = 0) -> bytes:
    """A one-image TPL: ``data`` already in GX ``fmt`` (one mip level), an optional palette."""
    pal_head = 0x38 if palette else 0
    pal_at = 0x60 if palette else 0
    data_at = (pal_at + len(palette) + 0x1F) & ~0x1F if palette else 0x40
    out = bytearray(TPL_MAGIC + struct.pack(">IIII", 1, 0xC, 0x14, pal_head))
    out += struct.pack(">HHIIIIIIfBBBB", h, w, fmt, data_at, 0, 0, 1, 1, 0.0, 0, 0, 0, 0)
    out += bytes(data_at - len(out))
    if palette:
        out[pal_head:pal_head + 12] = struct.pack(">HBBII", len(palette) // 2, 0, 0, pal_fmt, pal_at)
        out[pal_at:pal_at + len(palette)] = palette
    return bytes(out + data)


def tpl_image(blob: bytes) -> dict:
    """``{format, width, height, data, palette, pal_format}`` of the first image of a TPL."""
    if blob[:4] != TPL_MAGIC:
        raise ValueError("not a TPL picture")
    table = struct.unpack_from(">I", blob, 8)[0]
    head_at, pal_head = struct.unpack_from(">II", blob, table)
    h, w, fmt, data_at = struct.unpack_from(">HHII", blob, head_at)
    out = {"format": fmt, "width": w, "height": h, "data": blob[data_at:], "palette": b"", "pal_format": 0}
    if pal_head:
        n, _u, _p, pal_fmt, pal_at = struct.unpack_from(">HBBII", blob, pal_head)
        out.update(palette=blob[pal_at:pal_at + 2 * n], pal_format=pal_fmt)
    return out


def crop(px, w: int, x: int, y: int, cw: int, ch: int) -> bytes:
    return b"".join(bytes(px[(y + r) * w + x:(y + r) * w + x + cw]) for r in range(ch))


def ink_box(cell: bytes, cw: int, ch: int) -> Tuple[int, int]:
    """``(right, bottom)``: one past the last column and row with ink (0, 0 for an empty cell)."""
    right = bottom = 0
    for y in range(ch):
        row = cell[y * cw:(y + 1) * cw]
        if any(row):
            bottom = y + 1
            right = max(right, max(i for i, v in enumerate(row) if v) + 1)
    return right, bottom


def grid_write_ia(glyphs: List, cell: Tuple[int, int], columns: int) -> bytes:
    """An IA8 TPL grid of ``glyphs`` ``(w, h, alpha, intensity)`` (or None for an empty cell)."""
    cw, ch = cell
    rows = max(1, (len(glyphs) + columns - 1) // columns)
    w, h = (columns * cw + 3) & ~3, (rows * ch + 3) & ~3
    a, i = bytearray(w * h), bytearray(w * h)
    for n, g in enumerate(glyphs):
        if not g:
            continue
        gw, gh, ga_, gi = g
        ox, oy = (n % columns) * cw, (n // columns) * ch
        for r in range(min(gh, ch)):
            span = min(gw, cw)
            a[(oy + r) * w + ox:(oy + r) * w + ox + span] = ga_[r * gw:r * gw + span]
            i[(oy + r) * w + ox:(oy + r) * w + ox + span] = gi[r * gw:r * gw + span]
    return tpl(IA8, w, h, ia8_encode(a, i, w, h))


def grid_read_ia(blob: bytes, cell: Tuple[int, int], columns: int, count: int) -> List[Tuple]:
    """The ``count`` cells of an IA8 grid as ``(cw, ch, alpha, intensity)``."""
    img = tpl_image(blob)
    w, h = img["width"], img["height"]
    if img["format"] != IA8:
        raise ValueError(f"font grid: GX format {img['format']} is not IA8")
    a, i = ia8_decode(img["data"], w, h)
    cw, ch = cell
    out = []
    for n in range(count):
        ox, oy = (n % columns) * cw, (n // columns) * ch
        out.append((cw, ch, crop(a, w, ox, oy, cw, ch), crop(i, w, ox, oy, cw, ch)))
    return out


def pack(sizes: List[Tuple[int, int]], width: int, gap: int = 1) -> Tuple[List[Tuple[int, int]], int]:
    """Shelf packing of ``sizes`` [(w, h)] left to right in rows of ``width``: ``([(x, y)], used height)``."""
    x = y = row = 0
    out = []
    for w, h in sizes:
        if x and x + w > width:
            x, y, row = 0, y + row + gap, 0
        out.append((x, y))
        x += w + gap
        row = max(row, h)
    return out, y + row


def pow2(n: int, low: int = 8) -> int:
    v = low
    while v < n:
        v *= 2
    return v
