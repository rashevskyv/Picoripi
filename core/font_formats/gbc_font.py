"""Game Boy Color Oracles font (Ages, Seasons): 256 glyph cells of 8 x 16 pixels, 1 bit per pixel, in one ROM.

Cell n is 16 bytes at ``font_offset + 16 * n``: the top 8x8 tile (rows 0-7), then the bottom tile (rows 8-15),
one byte per row, bit 7 the left pixel, a set bit is ink. The editor sheet is 16 x 16 cells in image order
(cell n at column n % 16, row n // 16), so cell n is glyph n and character code n.

Parameters (from the plugin's font source): ``font_offset`` (file offset of cell 0). Packing writes only the
font block back into the ROM bytes; everything else of the ROM stays as it was. Round trip of an unedited
model gives the original bytes.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, coverage, grey_sheet, map_entries

CELLS = 256
CELL_BYTES = 16
COLUMNS = 16
CELL_W, CELL_H = 8, 16
IMAGE_W, IMAGE_H = COLUMNS * CELL_W, (CELLS // COLUMNS) * CELL_H
FONT_BYTES = CELLS * CELL_BYTES


def _offset(params: Dict[str, Any]) -> int:
    value = params.get("font_offset")
    if value is None:
        raise ValueError("gbc_font needs font_offset in the font source parameters")
    return int(value, 0) if isinstance(value, str) else int(value)


def _check(data: bytes, offset: int) -> None:
    if offset < 0 or offset + FONT_BYTES > len(data):
        raise ValueError("the font block lies outside the ROM")


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    offset = _offset(params)
    _check(data, offset)
    ink = bytearray(IMAGE_W * IMAGE_H)
    for cell in range(CELLS):
        x0, y0 = (cell % COLUMNS) * CELL_W, (cell // COLUMNS) * CELL_H
        base = offset + cell * CELL_BYTES
        for row in range(CELL_H):
            byte = data[base + row]
            for x in range(CELL_W):
                if (byte >> (7 - x)) & 1:
                    ink[(y0 + row) * IMAGE_W + x0 + x] = 255
    sheet = grey_sheet(Image.frombytes("L", (IMAGE_W, IMAGE_H), bytes(ink)))
    pairs = [(cell, cell) for cell in range(CELLS)]
    metadata: Metadata = {
        "header": {"signature": "GBC Oracles font", "num_chunks": 4},
        "INF1": [{"encoding": 0, "ascent": 12, "descent": CELL_H - 12, "width": CELL_W, "leading": CELL_H,
                  "fallback_code": 0x20, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": CELLS - 1, "cell_width": CELL_W, "cell_height": CELL_H,
                  "page_data_size": FONT_BYTES, "texture_format": 0,
                  "glyph_horizontal_count": COLUMNS, "glyph_vertical_count": CELLS // COLUMNS,
                  "texture_width": IMAGE_W, "texture_height": IMAGE_H}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": CELLS,
                  "packets": [{"kerning": 0, "width": CELL_W} for _ in range(CELLS)]}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    offset = _offset(params)
    _check(original, offset)
    if len(sheets) != 1 or sheets[0].size != (IMAGE_W, IMAGE_H):
        raise ValueError(f"the font sheet must be {IMAGE_W} x {IMAGE_H} pixels")
    ink = coverage(sheets[0]).tobytes()
    font = bytearray(FONT_BYTES)
    for cell in range(CELLS):
        x0, y0 = (cell % COLUMNS) * CELL_W, (cell // COLUMNS) * CELL_H
        for row in range(CELL_H):
            value = 0
            for x in range(CELL_W):
                if ink[(y0 + row) * IMAGE_W + x0 + x] >= 128:
                    value |= 1 << (7 - x)
            font[cell * CELL_BYTES + row] = value
    rom = bytearray(original)
    rom[offset:offset + FONT_BYTES] = font
    return bytes(rom)


def cell_map(pairs: List[Tuple[int, int]]) -> Dict[str, Any]:
    """The MAP1 entries for explicit (code, glyph) pairs (used by tests and the Ukrainian slot map)."""
    return map_entries(pairs)
