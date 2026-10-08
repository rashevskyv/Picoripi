"""EA FntG bitmap fonts of the Wii (Spore Hero ``.gfn``): a glyph table and one SHPG texture page.

Header (big endian, the size at 4 little endian): ``FntG``, u32 file size, u16, u16 glyph count, ..., u32 glyph
table offset at 0x14, u32 offset of the page's record chain at 0x1C, u32 line height at 0x24. A glyph is 16
bytes: u16 character (Unicode), u8 width, u8 height, u16 x, u16 y (its box on the page), u8, s8 left offset,
s8 top offset (from the top of the line), u8, u32 advance; the table is sorted by character. The page is an
SHPG record chain without the SHPG header (``core.texture_formats.shpg``): C4 with an IA8 palette of white at
sixteen alpha levels.

The model copies every glyph box into a cell of a grid (16 columns, 256 cells per sheet), at its top offset so
the glyphs share a baseline. Packing writes the cells back into their boxes (each pixel takes the palette
entry of the nearest ink level), the left offsets and advances (WID1 kerning and width) and the characters of
MAP1 (a glyph given another character keeps its box: the way to turn an unused letter into a new one); an
unedited model packs to the original bytes. New glyphs cannot be added (the page has no free table room).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, char_map, code_char, coverage, map_entries
from core.texture_formats import shpg

GLYPH = struct.Struct(">HBBHHBbbBI")
CODE, WIDTH, HEIGHT, X, Y, LEFT, TOP, ADVANCE = 0, 1, 2, 3, 4, 6, 7, 9
COLUMNS, PER_SHEET = 16, 256


def _font(data: bytes) -> Dict[str, Any]:
    if data[:4] != b"FntG":
        raise ValueError("Not an EA FntG font")
    count = struct.unpack_from(">H", data, 10)[0]
    table = struct.unpack_from(">I", data, 0x14)[0]
    glyphs = [list(GLYPH.unpack_from(data, table + GLYPH.size * i)) for i in range(count)]
    page = shpg.image_at(data, struct.unpack_from(">I", data, 0x1C)[0])
    return {"table": table, "glyphs": glyphs, "page": page, "line": struct.unpack_from(">I", data, 0x24)[0]}


def _grid(glyphs: List[list]) -> Tuple[int, int, int]:
    """``(cell width, cell height, top of the highest glyph)``."""
    top = min([g[TOP] for g in glyphs] + [0])
    return (max([g[WIDTH] for g in glyphs] + [1]), max([g[TOP] - top + g[HEIGHT] for g in glyphs] + [1]), top)


def _cell_at(cell: int, cell_w: int, cell_h: int) -> Tuple[int, int]:
    slot = cell % PER_SHEET
    return (slot % COLUMNS) * cell_w, (slot // COLUMNS) * cell_h


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    info = _font(data)
    glyphs, page = info["glyphs"], shpg.read_image(data, info["page"])
    cell_w, cell_h, top = _grid(glyphs)
    rows = PER_SHEET // COLUMNS
    sheets = [Image.new("RGBA", (COLUMNS * cell_w, rows * cell_h)) for _ in range(max(1, -(-len(glyphs) // PER_SHEET)))]
    for cell, g in enumerate(glyphs):
        if g[WIDTH] and g[HEIGHT]:
            x, y = _cell_at(cell, cell_w, cell_h)
            box = page.crop((g[X], g[Y], g[X] + g[WIDTH], g[Y] + g[HEIGHT]))
            sheets[cell // PER_SHEET].paste(box, (x, y + g[TOP] - top))
    space = next((g[ADVANCE] for g in glyphs if g[CODE] == 0x20), cell_w // 2)
    metadata = {
        "header": {"signature": "FntG", "num_chunks": 4},
        "INF1": [{"encoding": 1, "ascent": info["line"] - top, "descent": max(1, cell_h - info["line"] + top),
                  "width": space, "leading": info["line"], "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": len(sheets) * PER_SHEET - 1, "cell_width": cell_w,
                  "cell_height": cell_h, "glyph_horizontal_count": COLUMNS, "glyph_vertical_count": rows,
                  "texture_width": COLUMNS * cell_w, "texture_height": rows * cell_h}],
        "MAP1": [map_entries([(char_code(chr(g[CODE])), i) for i, g in enumerate(glyphs)])],
        "WID1": [{"first_code_included": 0, "last_code_included": len(sheets) * PER_SHEET,
                  "packets": [{"kerning": -g[LEFT], "width": g[ADVANCE]} for g in glyphs]}],
    }
    return metadata, sheets


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    info = _font(original)
    glyphs, head = info["glyphs"], info["page"]
    out = bytearray(original)
    cell_w, cell_h, top = _grid(glyphs)
    colours = shpg.palette(original, head)
    levels = sorted({c[3] for c in colours})
    by_level = {c[3]: c for c in reversed(colours)}
    page = shpg.read_image(original, head)
    for cell, g in enumerate(glyphs):
        if not (g[WIDTH] and g[HEIGHT]) or cell // PER_SHEET >= len(sheets):
            continue
        x, y = _cell_at(cell, cell_w, cell_h)
        y += g[TOP] - top
        ink = coverage(sheets[cell // PER_SHEET].crop((x, y, x + g[WIDTH], y + g[HEIGHT])))
        box = Image.new("RGBA", ink.size)
        box.putdata([by_level[min(levels, key=lambda level: abs(level - v))] for v in ink.get_flattened_data()])
        old = page.crop((g[X], g[Y], g[X] + g[WIDTH], g[Y] + g[HEIGHT]))
        if coverage(old).tobytes() != ink.tobytes():
            page.paste(box, (g[X], g[Y]))
    shpg.write_image(out, head, page)
    packets = (metadata.get("WID1") or [{}])[0].get("packets", [])
    codes = {glyph: char for char, glyph in char_map(metadata).items()}
    for i, g in enumerate(glyphs):
        if i < len(packets):
            g[LEFT] = max(-128, min(127, -int(packets[i]["kerning"])))
            g[ADVANCE] = max(0, int(packets[i]["width"]))
        if i in codes and code_char(char_code(codes[i])) != chr(g[CODE]):
            g[CODE] = ord(codes[i])
    for i, g in enumerate(sorted(glyphs, key=lambda g: g[CODE])):
        GLYPH.pack_into(out, info["table"] + GLYPH.size * i, *g)
    return bytes(out)
