"""Lunar (PlayStation) fonts: 1-bit glyphs 16 pixels wide, one u16 a row.

The unpacked program (``SLUS_006.28`` of the translation workspace) holds two glyph tables, 32 bytes a
glyph: 16 rows of a big-endian u16, the high bit the leftmost pixel (the game draws the first 15 rows and
adds the outline itself). Text characters 0x20-0x7A are glyphs 0-90 of the table at 0xA197C; the table
at 0x9FB5C holds 241 symbols the text writes as two-byte codes 0x9908-0x99F8. Codes outside both tables
come from the console's BIOS kanji font.

The game measures each glyph by its ink, so there is no width table: the model's widths are the ink
width plus the outline, for the preview only, and packing writes pixels alone.

Lunar 2: Eternal Blue Complete keeps its font in a data file: 15 rows a glyph (30 bytes), each row a
little-endian u16, and a width table of 4-bit entries (two a byte, high nibble first; entry 0 is the
space, glyph ``i`` is entry ``i + 1``); the game advances the pen by that width.

Params: ``offset`` (of the table in the file), ``count``, ``chars`` (a string: the character of each
glyph, in order) or ``first_code`` (glyph ``i`` is character ``first_code + i``; default U+E000);
``rows`` (default 16), ``row_order`` (``big``, the default, or ``little``), ``widths_offset`` (the
4-bit width table; without it widths come from the ink and are not written) and ``widths_first`` (the
entry of glyph 0).
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries

CELL = 16
GLYPH = 32
COLUMNS = 16
SPACE_WIDTH = 5


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _chars(params: Dict[str, Any], count: int) -> List[str]:
    if params.get("chars"):
        chars = list(str(params["chars"]))
        if len(chars) != count:
            raise ValueError(f"Lunar font: {len(chars)} characters for {count} glyphs")
        return chars
    first = _int(params.get("first_code", 0xE000))
    return [chr(first + i) for i in range(count)]


def _table(data: bytes, params: Dict[str, Any]) -> Tuple[int, int, int, str]:
    """``(offset, count, rows, byte order)``."""
    offset, count = _int(params["offset"]), _int(params["count"])
    rows, order = _int(params.get("rows", CELL)), str(params.get("row_order", "big"))
    if offset < 0 or offset + count * rows * 2 > len(data) or not 1 <= rows <= CELL:
        raise ValueError("Lunar font table outside the file")
    return offset, count, rows, order


def _nibble(data: bytes, params: Dict[str, Any], glyph: int) -> Tuple[int, int]:
    """``(byte offset, shift)`` of a glyph's width entry (entries hold two to a byte, high nibble first)."""
    table, entry = _int(params["widths_offset"]), glyph + _int(params.get("widths_first", 0))
    if table + entry // 2 >= len(data):
        raise ValueError(f"Lunar font: no width entry for glyph {glyph}")
    return table + entry // 2, 0 if entry & 1 else 4


def _width(rows: List[int]) -> int:
    ink = 0
    for row in rows:
        ink |= row
    if not ink:
        return SPACE_WIDTH
    left = max(bit for bit in range(16) if ink >> bit & 1)
    right = min(bit for bit in range(16) if ink >> bit & 1)
    return left - right + 1 + 2


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    offset, count, glyph_rows, order = _table(data, params)
    rows_total = -(-count // COLUMNS)
    width, height = COLUMNS * CELL, rows_total * CELL
    ink = bytearray(width * height)
    widths = []
    chars = _chars(params, count)
    table = params.get("widths_offset")
    for glyph in range(count):
        base = offset + glyph * glyph_rows * 2
        rows = [int.from_bytes(data[base + 2 * y:base + 2 * y + 2], order) for y in range(glyph_rows)]
        if table is None:
            widths.append(_width(rows))
        else:
            at, shift = _nibble(data, params, glyph)
            widths.append(data[at] >> shift & 15)
        x0, y0 = (glyph % COLUMNS) * CELL, (glyph // COLUMNS) * CELL
        for y, row in enumerate(rows):
            for x in range(CELL):
                if row >> (15 - x) & 1:
                    ink[(y0 + y) * width + x0 + x] = 255
    sheet = grey_sheet(Image.frombytes("L", (width, height), bytes(ink)))
    metadata = {
        "header": {"signature": "LUNF", "num_chunks": 4},
        "INF1": [{"encoding": 0, "ascent": 12, "descent": 3, "width": SPACE_WIDTH, "leading": 16,
                  "fallback_code": char_code("?"), "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": CELL, "cell_height": CELL,
                  "page_data_size": count * GLYPH, "texture_format": 0,
                  "glyph_horizontal_count": COLUMNS, "glyph_vertical_count": rows_total,
                  "texture_width": width, "texture_height": height}],
        "MAP1": [map_entries([(char_code(char), index) for index, char in enumerate(chars)])],
        "WID1": [{"first_code_included": 0, "last_code_included": count,
                  "packets": [{"kerning": 0, "width": value} for value in widths]}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    offset, count, glyph_rows, order = _table(original, params)
    out = bytearray(original)
    ink = coverage(sheets[0]).tobytes()
    width = sheets[0].width
    for glyph in range(count):
        x0, y0 = (glyph % COLUMNS) * CELL, (glyph // COLUMNS) * CELL
        if y0 + CELL > sheets[0].height:
            break
        base = offset + glyph * glyph_rows * 2
        for y in range(glyph_rows):
            row = 0
            for x in range(CELL):
                if ink[(y0 + y) * width + x0 + x] >= 128:
                    row |= 1 << (15 - x)
            out[base + 2 * y:base + 2 * y + 2] = row.to_bytes(2, order)
    table = params.get("widths_offset")
    if table is not None:
        packets = metadata["WID1"][0]["packets"]
        for glyph in range(min(count, len(packets))):
            at, shift = _nibble(original, params, glyph)
            value = max(0, min(15, int(packets[glyph]["width"])))
            out[at] = out[at] & ~(15 << shift) & 0xFF | value << shift
    return bytes(out)
