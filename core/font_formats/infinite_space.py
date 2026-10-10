"""Infinite Space (DS) dialogue font: 8x16 glyphs as pairs of OBJ tiles in an ``.obd`` sprite file (``is_obd``).

``.obd`` (``OBD\\0``): u16 0, u16 32 (bytes a tile), u16 tile bytes / 1024, u16 tile bytes, u16 0, u16 palettes,
u16 palette bytes, then u32 offsets at ``0x18``: tiles, palettes and three more tables (sprite cells and
animations), each table right after the one before. Glyph ``i`` is tile ``first + 2 i`` (top half) and the tile
after it (bottom half), 4 bits a pixel, rows of 4 bytes, low nibble first. The text codes of the game are
``0x80, 2 i + 1`` (``plugins/infinite_space/scx.py``). The file has no room for more glyphs: tiles added at the
end of ``T000OBJ.obd`` make the game lose the dialogue window (checked in NO$GBA), so the editor shows only the
game's ``count`` glyphs.

Pixels: nibble 1 is the ink, 2 the outline, 0 transparent; the sheet shows ``LEVELS`` greys (ink white,
outline dark grey, others ``17 * n``) and a pixel takes the nibble of the nearest grey, so an unedited font packs
back to the same bytes. Every glyph advances 8 pixels.

Params: ``first`` (tile of glyph 0), ``count``, ``chars`` (the characters of the glyphs, in order).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries

MAGIC = b"OBD\0"
TILE = 32
CELL_W, CELL_H = 8, 16
COLUMNS = 16
LEVELS = {0: 0, 1: 255, 2: 96}
ADVANCE = 8


def _grey(nibble: int) -> int:
    return LEVELS.get(nibble, 17 * nibble)


def _nibble(grey: int) -> int:
    choices = {**{n: 17 * n for n in range(16)}, **LEVELS}
    return min(choices, key=lambda n: (abs(choices[n] - grey), n not in LEVELS))


def _layout(data: bytes):
    if data[:4] != MAGIC:
        raise ValueError("Not an Infinite Space OBD file")
    tile_bytes = struct.unpack_from("<H", data, 0x0A)[0]
    offsets = list(struct.unpack_from("<5I", data, 0x18))
    return tile_bytes, offsets


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _decode_tile(raw: bytes) -> List[int]:
    return [(raw[r // 2] >> (4 * (r & 1))) & 15 for r in range(64)]


def extract(data: bytes, params: Dict[str, Any]):
    tile_bytes, offsets = _layout(data)
    first = _int(params["first"])
    total = _int(params["count"])
    stored = min(total, (tile_bytes // TILE - first) // 2)
    rows = -(-total // COLUMNS)
    ink = Image.new("L", (COLUMNS * CELL_W, rows * CELL_H))
    px = ink.load()
    for glyph in range(stored):
        for half in range(2):
            at = offsets[0] + (first + 2 * glyph + half) * TILE
            for r, nibble in enumerate(_decode_tile(data[at:at + TILE])):
                px[(glyph % COLUMNS) * CELL_W + r % 8, (glyph // COLUMNS) * CELL_H + half * 8 + r // 8] = _grey(nibble)
    chars = str(params.get("chars", ""))
    pairs = [(char_code(char), n) for n, char in enumerate(chars[:total])]
    metadata: Metadata = {
        "header": {"signature": "OBD", "num_chunks": 4},
        "INF1": [{"encoding": 1, "ascent": 12, "descent": 4, "width": ADVANCE, "leading": CELL_H,
                  "fallback_code": char_code("?"), "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": total - 1, "cell_width": CELL_W, "cell_height": CELL_H,
                  "page_data_size": 0, "texture_format": 0, "glyph_horizontal_count": COLUMNS,
                  "glyph_vertical_count": rows, "texture_width": COLUMNS * CELL_W, "texture_height": rows * CELL_H}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": total,
                  "packets": [{"kerning": 0, "width": ADVANCE} for _ in range(total)]}],
    }
    return metadata, [grey_sheet(ink)]


def _encode_cell(ink: Image.Image, glyph: int) -> bytes:
    px = ink.load()
    out = bytearray(2 * TILE)
    for half in range(2):
        for r in range(64):
            x, y = (glyph % COLUMNS) * CELL_W + r % 8, (glyph // COLUMNS) * CELL_H + half * 8 + r // 8
            out[half * TILE + r // 2] |= _nibble(px[x, y]) << (4 * (r & 1))
    return bytes(out)


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    tile_bytes, offsets = _layout(original)
    first = _int(params["first"])
    stored = min(_int(params["count"]), (tile_bytes // TILE - first) // 2)
    ink = coverage(sheets[0])
    old = coverage(extract(original, params)[1][0])
    data = bytearray(original)
    for glyph in range(stored):
        new = _encode_cell(ink, glyph)
        if new != _encode_cell(old, glyph):
            at = offsets[0] + (first + 2 * glyph) * TILE
            data[at:at + 2 * TILE] = new
    return bytes(data)
