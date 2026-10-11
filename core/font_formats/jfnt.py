"""Ganbarion ``.jfnt`` fonts (One Piece: Unlimited World Red, 3DS).

Layout: ``JFNT``, u32 file size, 4 bytes, byte ascent-ish, byte ``cell height - gap``, byte number of cells per row,
byte ``gap``; u16 range count and per range u16 first code, u16 last code, u16 first glyph; u16 width count and one
byte advance per glyph; padding to a multiple of 0x80; a ``jIMG`` picture (``core.texture_formats.jimg``, A8) that
holds the glyphs in a grid, glyph ``i`` in cell ``i`` (row by row), cell width = picture width // cells per row,
cell height = ``cell height - gap`` + ``gap``.

The model is the picture's used rows (one cell per glyph). Packing writes the cells that changed and the advance
bytes; mapping and cell grid stay. New glyphs cannot be added by a file edit: the translator chooses cells.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, Tuple


from core.font_formats import Metadata, Sheets, char_code, map_entries
from core.texture_formats import jimg

MAGIC = b"JFNT"


def _layout(data: bytes) -> Dict[str, Any]:
    if bytes(data[:4]) != MAGIC:
        raise ValueError("not a JFNT font")
    ranges_n = struct.unpack_from("<H", data, 0x10)[0]
    ranges = [struct.unpack_from("<HHH", data, 0x12 + 6 * i) for i in range(ranges_n)]
    at = 0x12 + 6 * ranges_n
    count = struct.unpack_from("<H", data, at)[0]
    image_at = data.find(jimg.MAGIC, at + 2 + count)
    if image_at < 0:
        raise ValueError("JFNT font has no picture")
    width, height, _codec = jimg.header(data, image_at)
    columns = data[14] or 1
    cell_h = data[13] + data[15]
    cell_w = width // columns
    glyphs = sum(b - a + 1 for a, b, _g in ranges)
    rows = -(-glyphs // columns)
    return {"ranges": ranges, "widths_at": at + 2, "width_count": count, "image_at": image_at, "width": width,
            "height": height, "columns": columns, "cell_w": cell_w, "cell_h": cell_h, "glyphs": glyphs, "rows": rows,
            "ascent": data[12]}


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    lay = _layout(data)
    atlas = jimg.read_at(data, lay["image_at"])
    sheet = atlas.crop((0, 0, lay["columns"] * lay["cell_w"], min(lay["height"], lay["rows"] * lay["cell_h"])))
    widths = list(data[lay["widths_at"]:lay["widths_at"] + lay["width_count"]])
    default = widths[0] if widths else lay["cell_w"]
    packets = [{"kerning": 0, "width": widths[i] if i < len(widths) else default} for i in range(lay["glyphs"])]
    pairs = [(char_code(chr(code)), glyph + code - first) for first, last, glyph in lay["ranges"]
             for code in range(first, last + 1)]
    cap = lay["columns"] * lay["rows"]
    metadata = {
        "header": {"signature": "JFNT", "num_chunks": 4},
        "INF1": [{"encoding": 1, "ascent": lay["ascent"], "descent": max(0, lay["cell_h"] - lay["ascent"]),
                  "width": default, "leading": lay["cell_h"], "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": cap - 1, "cell_width": lay["cell_w"], "cell_height": lay["cell_h"],
                  "glyph_horizontal_count": lay["columns"], "glyph_vertical_count": lay["rows"],
                  "texture_width": sheet.width, "texture_height": sheet.height}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": lay["glyphs"], "packets": packets}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    lay = _layout(original)
    out = bytearray(original)
    if sheets:
        sheet = sheets[0].convert("RGBA")
        atlas = jimg.read_at(original, lay["image_at"])
        edited = atlas.copy()
        edited.paste(sheet.crop((0, 0, min(sheet.width, atlas.width), min(sheet.height, atlas.height))), (0, 0))
        jimg.write_at(out, lay["image_at"], edited)
    packets = (metadata.get("WID1") or [{}])[0].get("packets") or []
    for i in range(min(len(packets), lay["width_count"], lay["glyphs"])):
        out[lay["widths_at"] + i] = max(0, min(255, int(packets[i]["width"])))
    return bytes(out)
