"""Metal Gear Solid (PlayStation) text font: ``font.res`` of the ``init`` stage (STAGE.DIR).

Big endian: ``u32`` end of the glyph table (where the hankaku glyphs start), ``u32`` offset of the
zenkaku glyphs, then one ``u32`` per character 0x20..0x7F: bits 28-31 how many rows the glyph is drawn
below the line top, bits 24-27 its width (= advance), bits 0-23 the offset of its pixels from the
end of the table. A glyph is ``width`` x 12 pixels of 2 bits, one after another, high bits first. The
zenkaku glyphs (symbols of codes 0x81xx) are 12 x 12, 36 bytes each.

The editor sheet has one 12 x 16 cell per glyph: the 96 characters, then the zenkaku symbols (not
mapped to characters). Each glyph keeps its row offset (``ROWS1``). Packing an unedited model gives
the file back; an edited one is laid out again (a glyph may change its width).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries

FIRST, COUNT = 0x20, 96
ROWS, CELL_W, CELL_H, COLUMNS = 12, 12, 16, 16
ZEN = 36


def _parse(data: bytes) -> Tuple[List[Tuple[int, int, int]], int, int]:
    """``[(row offset, width, pixel offset)]``, table end, zenkaku offset."""
    if len(data) < 8 + COUNT * 4:
        raise ValueError("Not a Metal Gear Solid font (too short)")
    table_end, zen = struct.unpack_from(">II", data, 0)
    if table_end != 8 + COUNT * 4 or not table_end <= zen <= len(data):
        raise ValueError("Not a Metal Gear Solid font")
    glyphs = []
    for i in range(COUNT):
        entry = struct.unpack_from(">I", data, 8 + i * 4)[0]
        glyphs.append((entry >> 28, entry >> 24 & 0xF, entry & 0xFFFFFF))
    return glyphs, table_end, zen


def _bits(data: bytes, start: int, count: int) -> List[int]:
    out = []
    for i in range(count):
        byte = data[start + i // 4] if start + i // 4 < len(data) else 0
        out.append(byte >> (6 - 2 * (i % 4)) & 3)
    return out


def _bytes(values: List[int]) -> bytes:
    out = bytearray((len(values) + 3) // 4)
    for i, value in enumerate(values):
        out[i // 4] |= (value & 3) << (6 - 2 * (i % 4))
    return bytes(out)


def _zen_count(data: bytes, zen: int) -> int:
    return (len(data) - zen) // ZEN


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    glyphs, table_end, zen = _parse(data)
    total = COUNT + _zen_count(data, zen)
    rows = (total + COLUMNS - 1) // COLUMNS
    sheet = Image.new("L", (COLUMNS * CELL_W, rows * CELL_H))
    pixels = sheet.load()
    for i, (top, width, offset) in enumerate(glyphs):
        values = _bits(data, table_end + offset, width * ROWS)
        cx, cy = i % COLUMNS * CELL_W, i // COLUMNS * CELL_H
        for k, value in enumerate(values):
            y = top + k // width
            if y < CELL_H:
                pixels[cx + k % width, cy + y] = value * 85
    for z in range(total - COUNT):
        i = COUNT + z
        values = _bits(data, zen + z * ZEN, CELL_W * ROWS)
        cx, cy = i % COLUMNS * CELL_W, i // COLUMNS * CELL_H
        for k, value in enumerate(values):
            pixels[cx + k % CELL_W, cy + k // CELL_W] = value * 85
    pairs = [(char_code(chr(FIRST + i)), i) for i in range(COUNT) if chr(FIRST + i).isprintable()]
    metadata = {
        "header": {"signature": "MGS1FONT", "num_chunks": 4},
        "INF1": [{"encoding": 0, "ascent": 10, "descent": 2, "width": 6, "leading": 14,
                  "fallback_code": char_code("?"), "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": total - 1, "cell_width": CELL_W, "cell_height": CELL_H,
                  "texture_format": 0, "glyph_horizontal_count": COLUMNS, "glyph_vertical_count": rows,
                  "texture_width": COLUMNS * CELL_W, "texture_height": rows * CELL_H}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": total,
                  "packets": [{"kerning": 0, "width": g[1]} for g in glyphs] +
                             [{"kerning": 0, "width": CELL_W}] * (total - COUNT)}],
        "ROWS1": [g[0] for g in glyphs],
    }
    return metadata, [grey_sheet(sheet)]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    glyphs, table_end, zen = _parse(original)
    ink = coverage(sheets[0])
    pixels = ink.load()
    packets = (metadata.get("WID1") or [{}])[0].get("packets", [])
    tops = metadata.get("ROWS1") or [g[0] for g in glyphs]

    def level(x: int, y: int) -> int:
        return min(3, (pixels[x, y] + 42) // 85) if x < ink.width and y < ink.height else 0

    table = bytearray()
    body = bytearray()
    for i in range(COUNT):
        width = int(packets[i]["width"]) if i < len(packets) else glyphs[i][1]
        top = int(tops[i]) if i < len(tops) else glyphs[i][0]
        if not 0 <= width <= CELL_W or not 0 <= top <= CELL_H - ROWS:
            raise ValueError(f"Glyph {chr(FIRST + i)!r}: width {width} / row {top} out of range")
        cx, cy = i % COLUMNS * CELL_W, i // COLUMNS * CELL_H
        values = [level(cx + k % width, cy + top + k // width) for k in range(width * ROWS)] if width else []
        old_top, old_width, old_offset = glyphs[i]
        if (top, width) == (old_top, old_width) and values == _bits(original, table_end + old_offset, width * ROWS):
            raw = original[table_end + old_offset:table_end + old_offset + (width * ROWS + 3) // 4]
        else:
            raw = _bytes(values)
        offset = len(body) if width else old_offset
        table += struct.pack(">I", top << 28 | width << 24 | offset)
        body += raw
    zen_part = bytearray(original[zen:])
    for z in range(_zen_count(original, zen)):
        i = COUNT + z
        cx, cy = i % COLUMNS * CELL_W, i // COLUMNS * CELL_H
        zen_part[z * ZEN:(z + 1) * ZEN] = _bytes([level(cx + k % CELL_W, cy + k // CELL_W) for k in range(CELL_W * ROWS)])
    out = struct.pack(">II", table_end, table_end + len(body)) + table + body + zen_part
    return out if out != original else original
