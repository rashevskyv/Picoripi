"""GameCube GX pictures for No More Heroes: I4 pixels, one-image TPL files, the glyph grid fonts the Font Editor opens
(``texture_grid``), and the GCT0 pictures of the disc as TPL and back.

A glyph is ``(width, height, pixels)``: ``pixels`` one byte per pixel, 0..255 coverage, row by row. A grid font is a
TPL (I4) of cells ``cell`` = (width, height), ``columns`` per row, glyph i in cell i, top-left in its cell.
"""
from __future__ import annotations

import struct

from core.i18n import tr

TPL_MAGIC = b"\x00\x20\xaf\x30"
I4, I8 = 0, 1
GCT_HEADER = 0x40

# GX block width, height and bytes per block of each format (the sizes of the disc's GCT0 pictures).
_BLOCK = {I4: (8, 8, 32), I8: (8, 4, 32), 2: (8, 4, 32), 3: (4, 4, 32), 4: (4, 4, 32), 5: (4, 4, 32),
          6: (4, 4, 64), 14: (8, 8, 32)}


def i4_decode(raw: bytes, w: int, h: int) -> bytearray:
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
                            px[y * w + x] = (b >> 4) * 17
                        if x + 1 < w:
                            px[y * w + x + 1] = (b & 15) * 17
    return px


def i4_encode(px, w: int, h: int) -> bytes:
    out = bytearray()
    for ty in range(0, h, 8):
        for tx in range(0, w, 8):
            for y in range(ty, ty + 8):
                for x in range(tx, tx + 8, 2):
                    a = px[y * w + x] if y < h and x < w else 0
                    b = px[y * w + x + 1] if y < h and x + 1 < w else 0
                    out.append(((a + 8) // 17) << 4 | ((b + 8) // 17))
    return bytes(out)


def tpl(fmt: int, w: int, h: int, data: bytes, mips: int = 1) -> bytes:
    """A TPL with one image: ``data`` is already in GX ``fmt`` (all mip levels)."""
    data_at = 0x40
    out = bytearray(TPL_MAGIC + struct.pack(">IIII", 1, 0xC, 0x14, 0))
    out += struct.pack(">HHIIIIIIfBBBB", h, w, fmt, data_at, 0, 0, 1 if mips == 1 else 5, 1, 0.0, 0, 0, mips - 1, 0)
    out += bytes(data_at - len(out))
    return bytes(out + data)


def tpl_image(blob: bytes) -> dict:
    """``{format, width, height, data, mips}`` of the first image of a one-image TPL."""
    if blob[:4] != TPL_MAGIC:
        raise ValueError(tr("not a TPL picture"))
    head_at = struct.unpack_from(">II", blob, struct.unpack_from(">I", blob, 8)[0])[0]
    h, w, fmt, data_at = struct.unpack_from(">HHII", blob, head_at)
    return {"format": fmt, "width": w, "height": h, "data": blob[data_at:], "mips": blob[head_at + 0x22] + 1}


def crop(px, w: int, x: int, y: int, cw: int, ch: int) -> bytes:
    return b"".join(bytes(px[(y + r) * w + x:(y + r) * w + x + cw]) for r in range(ch))


def ink_box(cell: bytes, cw: int, ch: int) -> tuple:
    """``(right, bottom)``: one past the last column and row with ink (0, 0 for an empty cell)."""
    right = bottom = 0
    for y in range(ch):
        row = cell[y * cw:(y + 1) * cw]
        if any(row):
            bottom = y + 1
            right = max(right, max(i for i, v in enumerate(row) if v) + 1)
    return right, bottom


def grid_write(glyphs: list, cell: tuple, columns: int) -> bytes:
    """An I4 TPL with ``glyphs`` (``(w, h, pixels)`` or None for an empty cell) in a grid."""
    cw, ch = cell
    rows = max(1, (len(glyphs) + columns - 1) // columns)
    w = (columns * cw + 7) & ~7
    h = (rows * ch + 7) & ~7
    px = bytearray(w * h)
    for i, g in enumerate(glyphs):
        if not g:
            continue
        gw, gh, gp = g
        ox, oy = (i % columns) * cw, (i // columns) * ch
        for r in range(min(gh, ch)):
            px[(oy + r) * w + ox:(oy + r) * w + ox + min(gw, cw)] = gp[r * gw:r * gw + min(gw, cw)]
    return tpl(I4, w, h, i4_encode(px, w, h))


def grid_read(blob: bytes, cell: tuple, columns: int, count: int) -> list:
    """The ``count`` cells of an I4 or I8 grid font as ``(cw, ch, pixels)``."""
    img = tpl_image(blob)
    w, h = img["width"], img["height"]
    if img["format"] == I4:
        px = i4_decode(img["data"], w, h)
    elif img["format"] == I8:
        px = bytearray(w * h)
        i = 0
        for ty in range(0, h, 4):
            for tx in range(0, w, 8):
                for y in range(ty, ty + 4):
                    for x in range(tx, tx + 8):
                        if y < h and x < w:
                            px[y * w + x] = img["data"][i]
                        i += 1
    else:
        raise ValueError(tr("grid font: GX format {0} is not supported", img["format"]))
    cw, ch = cell
    out = []
    for i in range(count):
        ox, oy = (i % columns) * cw, (i // columns) * ch
        out.append((cw, ch, crop(px, w, ox, oy, cw, ch)) if ox + cw <= w and oy + ch <= h else (cw, ch, bytes(cw * ch)))
    return out


def pack(sizes: list, width: int, gap: int = 1) -> tuple:
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


def gct_size(fmt: int, w: int, h: int, mips: int) -> int:
    bw, bh, bb = _BLOCK.get(fmt, (8, 8, 32))
    total = 0
    for _ in range(mips):
        total += ((w + bw - 1) // bw) * ((h + bh - 1) // bh) * bb
        w, h = max(1, w // 2), max(1, h // 2)
    return total


def gct_to_tpl(blob: bytes) -> bytes | None:
    """The TPL of a GCT0 picture (header 0x40 bytes, then GX data), or None for a format it does not know."""
    fmt, w, h = struct.unpack_from(">IHH", blob, 4)
    if fmt not in _BLOCK or struct.unpack_from(">I", blob, 0x10)[0] != GCT_HEADER:
        return None
    mips = 1
    for n in range(1, 12):
        if gct_size(fmt, w, h, n) == len(blob) - GCT_HEADER:
            mips = n
            break
    else:
        if gct_size(fmt, w, h, 1) > len(blob) - GCT_HEADER:
            return None
    return tpl(fmt, w, h, blob[GCT_HEADER:GCT_HEADER + gct_size(fmt, w, h, mips)], mips)


def tpl_to_gct(tpl_blob: bytes, old: bytes) -> bytes:
    """``old`` (a GCT0 picture) with the pixels of the TPL ``tpl_blob``: the format and size must match."""
    img = tpl_image(tpl_blob)
    fmt, w, h = struct.unpack_from(">IHH", old, 4)
    data = img["data"]
    if (img["format"], img["width"], img["height"]) != (fmt, w, h):
        raise ValueError(tr("the picture changed its format or size; it does not fit the game"))
    if len(data) < len(old) - GCT_HEADER:
        raise ValueError(tr("the picture is shorter than the original"))
    return old[:GCT_HEADER] + data[:len(old) - GCT_HEADER]
