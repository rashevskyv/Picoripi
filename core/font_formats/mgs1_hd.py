"""Metal Gear Solid Master Collection: M2's high-resolution (4x) copy of the PlayStation text font.

``us_hankaku_4x.bin``: 112 records of 578 bytes -- ``u16`` (little endian) width (low byte) and rows drawn
below the line top (high byte), then 576 bytes: ``width`` x 48 pixels of 2 bits, one after another, high
bits first (the rest of the record is zero). Characters 0x20..0x7F are the first 96 glyphs; the last 16 are
the game's extra symbols. ``us_zenkaku_4x.bin``: 48 symbols of 48 x 48 pixels, 576 bytes each, no header
(the 4x copies of the ``font.res`` zenkaku symbols).

The editor sheet has one 48 x 64 cell per glyph; each hankaku glyph keeps its row offset (``ROWS1``).
Packing an unedited model gives the file back.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries

FIRST, CHARS = 0x20, 96
SIZE, CELL_W, CELL_H, COLUMNS = 48, 48, 64, 16
PIXELS = SIZE * SIZE // 4
RECORD = PIXELS + 2


def kind(data: bytes) -> str:
    """``hankaku`` (records with a width) or ``zenkaku`` (plain 48 x 48 cells)."""
    if data and len(data) % RECORD == 0:
        return "hankaku"
    if data and len(data) % PIXELS == 0:
        return "zenkaku"
    raise ValueError("Not a Metal Gear Solid HD font (size)")


def _glyphs(data: bytes) -> List[Tuple[int, int, int]]:
    """``[(rows below the top, width, pixel offset)]``"""
    if kind(data) == "zenkaku":
        return [(0, SIZE, i * PIXELS) for i in range(len(data) // PIXELS)]
    out = []
    for i in range(len(data) // RECORD):
        head = struct.unpack_from("<H", data, i * RECORD)[0]
        if head & 0xFF > SIZE:
            raise ValueError("Not a Metal Gear Solid HD font (width)")
        out.append((head >> 8, head & 0xFF, i * RECORD + 2))
    return out


def _bits(data: bytes, start: int, count: int) -> List[int]:
    return [data[start + i // 4] >> (6 - 2 * (i % 4)) & 3 for i in range(count)]


def _bytes(values: List[int], size: int) -> bytes:
    out = bytearray(size)
    for i, value in enumerate(values):
        out[i // 4] |= (value & 3) << (6 - 2 * (i % 4))
    return bytes(out)


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    glyphs = _glyphs(data)
    total = len(glyphs)
    rows = (total + COLUMNS - 1) // COLUMNS
    sheet = Image.new("L", (COLUMNS * CELL_W, rows * CELL_H))
    pixels = sheet.load()
    for i, (top, width, offset) in enumerate(glyphs):
        cx, cy = i % COLUMNS * CELL_W, i // COLUMNS * CELL_H
        for k, value in enumerate(_bits(data, offset, width * SIZE)):
            y = top + k // width
            if y < CELL_H:
                pixels[cx + k % width, cy + y] = value * 85
    chars = CHARS if kind(data) == "hankaku" else 0
    pairs = [(char_code(chr(FIRST + i)), i) for i in range(min(chars, total)) if chr(FIRST + i).isprintable()]
    metadata = {
        "header": {"signature": "MGS1HD" + kind(data)[0].upper(), "num_chunks": 4},
        "INF1": [{"encoding": 0, "ascent": 40, "descent": 8, "width": 24, "leading": 56,
                  "fallback_code": char_code("?"), "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": total - 1, "cell_width": CELL_W, "cell_height": CELL_H,
                  "texture_format": 0, "glyph_horizontal_count": COLUMNS, "glyph_vertical_count": rows,
                  "texture_width": COLUMNS * CELL_W, "texture_height": rows * CELL_H}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": total,
                  "packets": [{"kerning": 0, "width": g[1]} for g in glyphs]}],
        "ROWS1": [g[0] for g in glyphs],
    }
    return metadata, [grey_sheet(sheet)]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    glyphs = _glyphs(original)
    hankaku = kind(original) == "hankaku"
    ink = coverage(sheets[0])
    pixels = ink.load()
    packets = (metadata.get("WID1") or [{}])[0].get("packets", [])
    tops = metadata.get("ROWS1") or [g[0] for g in glyphs]

    def level(x: int, y: int) -> int:
        return min(3, (pixels[x, y] + 42) // 85) if x < ink.width and y < ink.height else 0

    out = bytearray(original)
    for i, (old_top, old_width, offset) in enumerate(glyphs):
        width = int(packets[i]["width"]) if hankaku and i < len(packets) else old_width
        top = int(tops[i]) if hankaku and i < len(tops) else old_top
        if not 0 <= width <= SIZE or not 0 <= top <= CELL_H - SIZE:
            raise ValueError(f"Glyph {i}: width {width} / row {top} out of range")
        cx, cy = i % COLUMNS * CELL_W, i // COLUMNS * CELL_H
        values = [level(cx + k % width, cy + top + k // width) for k in range(width * SIZE)] if width else []
        if (top, width) == (old_top, old_width) and values == _bits(original, offset, width * SIZE):
            continue
        out[offset:offset + PIXELS] = _bytes(values, PIXELS)
        if hankaku:
            struct.pack_into("<H", out, offset - 2, top << 8 | width)
    return bytes(out) if out != original else original
