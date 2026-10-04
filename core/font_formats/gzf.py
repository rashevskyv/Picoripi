"""Grezzo GZFX bitmap font (Majora's Mask 3D ``message/ltn16.gzf``).

Layout (little endian): ``GZFX`` header of 0x30 bytes (u32 sheet count at 0x10, u32 glyph count at
0x14, u16 cell width at 0x22, u32 cell height at 0x28); per sheet u32 data offset, u16 width, u16
height; per character, sorted by code: u32 code, u16 advance, u16 sheet, u16 left (cell columns
skipped: the glyph is drawn at ``pen - left``), u16 ``row << 8 | column``; then the sheets, 4-bit
PICA textures (8x8 Morton tiles, low nibble first), each at a 0x80 boundary.

The model has one grid per sheet, as many cell rows as the tallest sheet holds; cells below a short
sheet's last row cannot hold a glyph. Adding a character adds a table record; when the table outgrows
the room before the first sheet, the sheets move to the next 0x80 boundary.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, map_entries
from core.font_formats.bcfnt import A4, decode, encode, texture_size
from core.font_formats.qbf import edited_entries, primary_metrics

HEADER = 0x30
RECORD = 12
ALIGN = 0x80


def _parse(data: bytes) -> Dict[str, Any]:
    if data[:4] != b"GZFX":
        raise ValueError("Not a GZFX font")
    sheet_count, glyph_count = struct.unpack_from("<II", data, 0x10)
    cell_w, cell_h = struct.unpack_from("<H", data, 0x22)[0], struct.unpack_from("<I", data, 0x28)[0]
    sheets = [struct.unpack_from("<IHH", data, HEADER + 8 * index) for index in range(sheet_count)]
    table = HEADER + 8 * sheet_count
    records = [struct.unpack_from("<IHHHH", data, table + RECORD * index) for index in range(glyph_count)]
    if not sheets or not cell_w or not cell_h:
        raise ValueError("GZFX without sheets or cell size")
    columns = max(width for _off, width, _h in sheets) // cell_w
    rows = max(height for _off, _w, height in sheets) // cell_h
    return {"sheets": sheets, "records": records, "table": table, "cell_w": cell_w, "cell_h": cell_h,
            "columns": columns, "rows": rows}


def _glyph(font: Dict[str, Any], sheet: int, row: int, column: int) -> int:
    return sheet * font["columns"] * font["rows"] + row * font["columns"] + column


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    font = _parse(data)
    width, height = font["columns"] * font["cell_w"], font["rows"] * font["cell_h"]
    sheets = []
    for offset, sheet_w, sheet_h in font["sheets"]:
        sheet = Image.new("RGBA", (width, height))
        sheet.paste(decode(data[offset:], A4, sheet_w, sheet_h).crop((0, 0, min(width, sheet_w), min(height, sheet_h))))
        sheets.append(sheet)
    count = len(sheets) * font["columns"] * font["rows"]
    entries = [(code, _glyph(font, sheet, cell >> 8, cell & 0xFF), left, advance)
               for code, advance, sheet, left, cell in font["records"]]
    packets = [{"kerning": 0, "width": 0} for _ in range(count)]
    for glyph, (kerning, advance) in primary_metrics(entries).items():
        if glyph < count:
            packets[glyph] = {"kerning": kerning, "width": advance}
    space = next((advance for code, _g, _left, advance in entries if code == 0x20), font["cell_w"] // 2)
    metadata = {
        "header": {"signature": "GZFX", "num_chunks": 4, "unicode_map": True},
        "INF1": [{"encoding": 1, "ascent": font["cell_h"] * 2 // 3, "descent": font["cell_h"] - font["cell_h"] * 2 // 3,
                  "width": space, "leading": font["cell_h"], "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": font["cell_w"], "cell_height": font["cell_h"],
                  "page_data_size": width * height // 2, "texture_format": A4,
                  "glyph_horizontal_count": font["columns"], "glyph_vertical_count": font["rows"],
                  "texture_width": width, "texture_height": height}],
        "MAP1": [map_entries([(char_code(chr(code)), glyph) for code, glyph, _left, _advance in entries])],
        "WID1": [{"first_code_included": 0, "last_code_included": count, "packets": packets}],
    }
    return metadata, sheets


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    font = _parse(original)
    per_sheet = font["columns"] * font["rows"]
    old = {code: (_glyph(font, sheet, cell >> 8, cell & 0xFF), left, advance)
           for code, advance, sheet, left, cell in font["records"]}
    records: List[bytes] = []
    for code, glyph, kerning, advance in edited_entries(metadata, old):
        sheet, cell = divmod(glyph, per_sheet)
        row, column = divmod(cell, font["columns"])
        if sheet >= len(font["sheets"]) or (row + 1) * font["cell_h"] > font["sheets"][sheet][2]:
            raise ValueError(f"U+{code:04X}: cell {column},{row} of sheet {sheet} is outside the texture")
        records.append(struct.pack("<IHHHH", code, max(0, min(0xFFFF, advance)), sheet,
                                   max(0, min(0xFFFF, kerning)), row << 8 | column))

    first_sheet = font["sheets"][0][0]
    table_end = font["table"] + RECORD * len(records)
    start = first_sheet if table_end <= first_sheet else -(-table_end // ALIGN) * ALIGN
    shift = start - first_sheet

    out = bytearray(original[:HEADER])
    struct.pack_into("<I", out, 0x14, len(records))
    for offset, sheet_w, sheet_h in font["sheets"]:
        out += struct.pack("<IHH", offset + shift, sheet_w, sheet_h)
    out += b"".join(records)
    out += bytes(start - len(out))
    for index, (offset, sheet_w, sheet_h) in enumerate(font["sheets"]):
        texture = decode(original[offset:], A4, sheet_w, sheet_h)
        texture.paste(sheets[index].convert("RGBA").crop((0, 0, min(sheet_w, sheets[index].width),
                                                           min(sheet_h, sheets[index].height))))
        out += bytes(offset + shift - len(out)) if offset + shift > len(out) else b""
        out += encode(texture, A4)
    end = font["sheets"][-1][0] + texture_size(A4, *font["sheets"][-1][1:])
    out += original[end:]
    return bytes(out)
