"""Policenauts (PlayStation) fonts: ``KANJIFNT.MDB``, ``KANJIFNT.RB`` and ``KPRFONT.*`` of ``FONT.DPK`` (and the
shooting game's ``KANJIFNT.*`` in ``SHOTPAC.DPK``).

A file starts with the proportional font the English patch draws its text with (big-endian)::

    u32 start of the glyph pixels (8 + 4 * glyph count), u32 end of the proportional part,
    per glyph: u8 width, u24 offset of its pixels from that start,
    pixels: 12 rows of ``width`` pixels, 2 bits each (0 = empty .. 3 = full ink), high bits first,
    rows back to back (3 * width bytes a glyph, glyph after glyph).

Glyph ``n`` is character 0x20 + n; a font of 158 glyphs has 0x20-0x7E and then the half-width katakana
0xA1-0xDF (Unicode U+FF61-U+FF9F). The Japanese kanji font follows and is kept as it is.

The editor sees 16 x 12 cells, 16 a row; a glyph's width is its advance. Packing lays the glyphs out
again in order; they may not grow past the end of the proportional part. Unedited, it gives the file back
byte for byte.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries

CELL_W, CELL_H, COLUMNS = 16, 12, 16
KATAKANA_FONT = 158


def _layout(data: bytes) -> Tuple[int, int, List[Tuple[int, int]]]:
    if len(data) < 16:
        raise ValueError("Not a Policenauts font")
    start, end = struct.unpack_from(">II", data, 0)
    count = (start - 8) // 4
    if start < 12 or (start - 8) % 4 or not start < end <= len(data):
        raise ValueError("Not a Policenauts font (bad header)")
    glyphs = [(data[8 + 4 * i], int.from_bytes(data[9 + 4 * i:12 + 4 * i], "big")) for i in range(count)]
    if any(start + offset + 3 * width > end for width, offset in glyphs):
        raise ValueError("Not a Policenauts font (glyph past the end)")
    return start, end, glyphs


def characters(count: int) -> List[str]:
    """Character of each glyph."""
    if count == KATAKANA_FONT:
        return [chr(0x20 + i) for i in range(95)] + [chr(0xFF61 + i) for i in range(count - 95)]
    return [chr(0x20 + i) for i in range(count)]


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    start, _end, glyphs = _layout(data)
    rows = (len(glyphs) + COLUMNS - 1) // COLUMNS
    width, height = COLUMNS * CELL_W, rows * CELL_H
    ink = bytearray(width * height)
    for index, (w, offset) in enumerate(glyphs):
        bits = int.from_bytes(data[start + offset:start + offset + 3 * w], "big")
        total = 24 * w
        x0, y0 = (index % COLUMNS) * CELL_W, (index // COLUMNS) * CELL_H
        for y in range(CELL_H):
            for x in range(min(w, CELL_W)):
                shift = total - 2 * (y * w + x) - 2
                ink[(y0 + y) * width + x0 + x] = ((bits >> shift) & 3) * 85
    sheet = grey_sheet(Image.frombytes("L", (width, height), bytes(ink)))
    chars = characters(len(glyphs))
    metadata = {
        "header": {"signature": "PNFT", "num_chunks": 4},
        "INF1": [{"encoding": 0, "ascent": 10, "descent": 2, "width": 8, "leading": 12,
                  "fallback_code": char_code("?"), "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": len(glyphs) - 1, "cell_width": CELL_W, "cell_height": CELL_H,
                  "page_data_size": 0, "texture_format": 0, "glyph_horizontal_count": COLUMNS,
                  "glyph_vertical_count": rows, "texture_width": width, "texture_height": height}],
        "MAP1": [map_entries([(char_code(c), i) for i, c in enumerate(chars)])],
        "WID1": [{"first_code_included": 0, "last_code_included": len(glyphs),
                  "packets": [{"kerning": 0, "width": w} for w, _offset in glyphs]}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    start, end, glyphs = _layout(original)
    packets = (metadata.get("WID1") or [{}])[0].get("packets", [])
    ink = coverage(sheets[0]).tobytes()
    sheet_w = sheets[0].width
    out = bytearray(original)
    pixels = bytearray()
    for index, (old_w, _offset) in enumerate(glyphs):
        w = int(packets[index].get("width", old_w)) if index < len(packets) else old_w
        if not 1 <= w <= CELL_W:
            raise ValueError(f"Glyph {index}: width {w} (1-{CELL_W})")
        x0, y0 = (index % COLUMNS) * CELL_W, (index // COLUMNS) * CELL_H
        value = 0
        for y in range(CELL_H):
            for x in range(w):
                at = (y0 + y) * sheet_w + x0 + x
                level = ink[at] if at < len(ink) else 0
                value = value << 2 | min(3, (level + 42) // 85)
        out[8 + 4 * index] = w
        out[9 + 4 * index:12 + 4 * index] = len(pixels).to_bytes(3, "big")
        pixels += value.to_bytes(3 * w, "big")
    if start + len(pixels) > end:
        raise ValueError(f"The glyphs are {start + len(pixels) - end} bytes wider than the font's space")
    out[start:end] = bytes(pixels) + bytes(end - start - len(pixels))
    return bytes(out)
