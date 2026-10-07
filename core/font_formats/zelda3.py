"""Zelda: A Link to the Past PC port (snesrev/zelda3) dialogue font: the port's own ``font.png``.

The port's ``assets/restool.py`` writes the font as an indexed PNG, 143x136: 16 columns of 8x16 glyph cells,
9 px apart, 8 rows 17 px apart. The row above each cell is its width marker: index 255 at column ``width - 1``
(no marker = width 8). Glyph pixels are 2bpp colour ``v`` stored as index ``base + v`` (base 96); the
port's compiler reads ``index & 3`` and the markers back. Glyph ``j`` is character ``chars[j]`` (params:
``chars``, the game's alphabet in glyph order; entries longer than one character are icons, kept unmapped).

The sheet shows colour ``v`` as grey ``85 * v`` (0 transparent); packing an unedited model gives the
original bytes back.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries

COLUMNS, ROWS = 16, 8
CELL_W, CELL_H = 8, 16
STRIDE_X, STRIDE_Y = 9, 17
SIZE = (143, 136)
MARKER = 255
GLYPHS = COLUMNS * ROWS


def _open(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    if image.mode != "P" or image.size != SIZE:
        raise ValueError(f"Not a zelda3 font.png: {image.mode} {image.size[0]}x{image.size[1]}, expected P {SIZE}")
    return image


def _cell(glyph: int) -> Tuple[int, int]:
    """Top-left pixel of a glyph's 8x16 cell (its marker row is the row above)."""
    return glyph % COLUMNS * STRIDE_X, glyph // COLUMNS * STRIDE_Y + 1


def _widths(px: bytes) -> List[int]:
    out = []
    for glyph in range(GLYPHS):
        x0, y0 = _cell(glyph)
        row = (y0 - 1) * SIZE[0] + x0
        out.append(next((x + 1 for x in range(CELL_W) if px[row + x] == MARKER), CELL_W))
    return out


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    px = _open(data).tobytes()
    ink = bytearray(COLUMNS * CELL_W * ROWS * CELL_H)
    stride = COLUMNS * CELL_W
    for glyph in range(GLYPHS):
        x0, y0 = _cell(glyph)
        tx, ty = glyph % COLUMNS * CELL_W, glyph // COLUMNS * CELL_H
        for y in range(CELL_H):
            for x in range(CELL_W):
                ink[(ty + y) * stride + tx + x] = (px[(y0 + y) * SIZE[0] + x0 + x] & 3) * 85
    sheet = grey_sheet(Image.frombytes("L", (stride, ROWS * CELL_H), bytes(ink)))
    chars = list(params.get("chars") or [])
    pairs = [(char_code(ch), glyph) for glyph, ch in enumerate(chars[:GLYPHS]) if len(ch) == 1]
    widths = _widths(px)
    space = widths[chars.index(" ")] if " " in chars else CELL_W
    metadata = {
        "header": {"signature": "zelda3 font.png", "num_chunks": 4},
        "INF1": [{"encoding": 0, "ascent": 12, "descent": CELL_H - 12, "width": space, "leading": CELL_H,
                  "fallback_code": char_code("?"), "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": GLYPHS - 1, "cell_width": CELL_W, "cell_height": CELL_H,
                  "page_data_size": GLYPHS * 32, "texture_format": 0,
                  "glyph_horizontal_count": COLUMNS, "glyph_vertical_count": ROWS,
                  "texture_width": stride, "texture_height": ROWS * CELL_H}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": GLYPHS,
                  "packets": [{"kerning": 0, "width": w} for w in widths]}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    image = _open(original)
    px = bytearray(image.tobytes())
    ink = coverage(sheets[0]).tobytes()
    stride = sheets[0].width
    for glyph in range(GLYPHS):
        x0, y0 = _cell(glyph)
        tx, ty = glyph % COLUMNS * CELL_W, glyph // COLUMNS * CELL_H
        for y in range(CELL_H):
            for x in range(CELL_W):
                at = (y0 + y) * SIZE[0] + x0 + x
                px[at] = (px[at] & ~3) | min(3, (ink[(ty + y) * stride + tx + x] + 42) // 85)
    old_widths = _widths(bytes(px))
    packets = metadata["WID1"][0]["packets"]
    for glyph in range(min(GLYPHS, len(packets))):
        width = max(1, min(CELL_W, int(packets[glyph]["width"])))
        if width != old_widths[glyph]:
            x0, y0 = _cell(glyph)
            row = (y0 - 1) * SIZE[0] + x0
            for x in range(CELL_W):
                if px[row + x] == MARKER:
                    px[row + x] = 0
            px[row + width - 1] = MARKER
    if bytes(px) == image.tobytes():
        return bytes(original)
    out = Image.frombytes("P", SIZE, bytes(px))
    out.putpalette(image.getpalette())
    stream = io.BytesIO()
    out.save(stream, "PNG")
    return stream.getvalue()
