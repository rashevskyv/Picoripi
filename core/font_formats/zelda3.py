"""Zelda: A Link to the Past PC port (snesrev/zelda3) dialogue font: the port's own ``font.png``.

The port's ``assets/restool.py`` writes the font as an indexed PNG 143 px wide: 16 columns of 8x16 glyph cells,
9 px apart, in rows 17 px apart (8 rows for the port's 128 glyphs; the Ukrainian workspace font has 16 rows, 256
glyphs). The row above each cell is its width marker: index 255 at column ``width - 1`` (no marker = width 8).
Glyph pixels are 2bpp colour ``v`` stored as index ``base + v`` (base 96); the port's compiler reads ``index & 3``
and the markers back. Glyph ``j`` is character ``chars[j]`` (params: ``chars``, the game's alphabet in glyph order;
entries longer than one character are icons and empty ones free cells, both kept unmapped).

The sheet shows colour ``v`` as grey ``85 * v`` (0 transparent); packing an unedited model gives the
original bytes back.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries

COLUMNS = 16
CELL_W, CELL_H = 8, 16
STRIDE_X, STRIDE_Y = 9, 17
WIDTH = 143
MARKER = 255


def _open(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    if image.mode != "P" or image.width != WIDTH or not image.height or image.height % STRIDE_Y:
        raise ValueError(f"Not a zelda3 font.png: {image.mode} {image.width}x{image.height}")
    return image


def _cell(glyph: int) -> Tuple[int, int]:
    """Top-left pixel of a glyph's 8x16 cell (its marker row is the row above)."""
    return glyph % COLUMNS * STRIDE_X, glyph // COLUMNS * STRIDE_Y + 1


def _widths(px: bytes, glyphs: int) -> List[int]:
    out = []
    for glyph in range(glyphs):
        x0, y0 = _cell(glyph)
        row = (y0 - 1) * WIDTH + x0
        out.append(next((x + 1 for x in range(CELL_W) if px[row + x] == MARKER), CELL_W))
    return out


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    image = _open(data)
    px, rows = image.tobytes(), image.height // STRIDE_Y
    glyphs = rows * COLUMNS
    stride = COLUMNS * CELL_W
    ink = bytearray(stride * rows * CELL_H)
    for glyph in range(glyphs):
        x0, y0 = _cell(glyph)
        tx, ty = glyph % COLUMNS * CELL_W, glyph // COLUMNS * CELL_H
        for y in range(CELL_H):
            for x in range(CELL_W):
                ink[(ty + y) * stride + tx + x] = (px[(y0 + y) * WIDTH + x0 + x] & 3) * 85
    sheet = grey_sheet(Image.frombytes("L", (stride, rows * CELL_H), bytes(ink)))
    chars = list(params.get("chars") or [])
    pairs = [(char_code(ch), glyph) for glyph, ch in enumerate(chars[:glyphs]) if len(ch) == 1]
    widths = _widths(px, glyphs)
    space = widths[chars.index(" ")] if " " in chars else CELL_W
    metadata = {
        "header": {"signature": "zelda3 font.png", "num_chunks": 4},
        "INF1": [{"encoding": 0, "ascent": 12, "descent": CELL_H - 12, "width": space, "leading": CELL_H,
                  "fallback_code": char_code("?"), "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": glyphs - 1, "cell_width": CELL_W, "cell_height": CELL_H,
                  "page_data_size": glyphs * 32, "texture_format": 0,
                  "glyph_horizontal_count": COLUMNS, "glyph_vertical_count": rows,
                  "texture_width": stride, "texture_height": rows * CELL_H}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": glyphs,
                  "packets": [{"kerning": 0, "width": w} for w in widths]}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    image = _open(original)
    px = bytearray(image.tobytes())
    glyphs = image.height // STRIDE_Y * COLUMNS
    ink = coverage(sheets[0]).tobytes()
    stride = sheets[0].width
    for glyph in range(glyphs):
        x0, y0 = _cell(glyph)
        tx, ty = glyph % COLUMNS * CELL_W, glyph // COLUMNS * CELL_H
        for y in range(CELL_H):
            for x in range(CELL_W):
                at = (y0 + y) * WIDTH + x0 + x
                px[at] = (px[at] & ~3) | min(3, (ink[(ty + y) * stride + tx + x] + 42) // 85)
    old_widths = _widths(bytes(px), glyphs)
    packets = metadata["WID1"][0]["packets"]
    for glyph in range(min(glyphs, len(packets))):
        width = max(1, min(CELL_W, int(packets[glyph]["width"])))
        if width != old_widths[glyph]:
            x0, y0 = _cell(glyph)
            row = (y0 - 1) * WIDTH + x0
            for x in range(CELL_W):
                if px[row + x] == MARKER:
                    px[row + x] = 0
            px[row + width - 1] = MARKER
    if bytes(px) == image.tobytes():
        return bytes(original)
    out = Image.frombytes("P", image.size, bytes(px))
    out.putpalette(image.getpalette())
    stream = io.BytesIO()
    out.save(stream, "PNG")
    return stream.getvalue()
