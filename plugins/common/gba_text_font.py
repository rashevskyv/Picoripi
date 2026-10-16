"""The Generation III text font: read the glyphs from a ROM and decode them to pixel classes.

A glyph is 16 x 14 pixels in four 8 x 8 tiles (top-left, top-right, bottom-left, bottom-right). Each tile takes
16 bytes. Byte ``e ^ 1`` of a tile is the half-row code of row ``e // 2``, half ``e % 2`` (4 pixels). A code is an
index into a 256-byte table in the ROM; that index selects one of 81 combinations of three colour classes:
0 paper (no ink), 1 ink, 2 shadow. The address of the glyph table, the width table and the half-row table come
from the game's facts file (``font`` key), written by tools/pokemon_fr_font_facts.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

GLYPH_BYTES = 64          # 4 tiles x 16 bytes
GLYPH_ROWS = 14           # rows that carry ink; the other two of the 16 are blank
PAPER, INK, SHADOW = 0, 1, 2


def half_row_pixels(index: int) -> List[int]:
    """The four pixel classes of combination ``index`` (0..80), leftmost first."""
    i, rest = divmod(index, 27)
    j, rest = divmod(rest, 9)
    k, l = divmod(rest, 3)
    return [i, j, k, l]


def decode_glyph(data: bytes, half_rows: bytes) -> List[List[int]]:
    """The 16 x 16 pixel classes of one glyph; rows from GLYPH_ROWS on stay PAPER."""
    rows = [[PAPER] * 16 for _ in range(16)]
    for tile in range(4):
        block = data[16 * tile:16 * tile + 16]
        left, top = 8 * (tile % 2), 8 * (tile // 2)
        for e in range(16):
            pixels = half_row_pixels(half_rows[block[e ^ 1]])
            y, x = top + e // 2, left + 4 * (e % 2)
            rows[y][x:x + 4] = pixels
    return rows


class GlyphSet:
    """Widths and decoded glyphs of one font. ``code`` is the glyph index, which is the text byte."""

    def __init__(self, widths: bytes, glyphs: bytes, half_rows: bytes) -> None:
        self._widths = widths
        self._glyphs = glyphs
        self._half_rows = half_rows
        self._cache: Dict[int, List[List[int]]] = {}

    @property
    def count(self) -> int:
        return len(self._widths)

    def width(self, code: int) -> int:
        return self._widths[code] if 0 <= code < len(self._widths) else 0

    def drawn_width(self, code: int) -> int:
        return self.width(code)

    def pixels(self, code: int) -> List[List[int]]:
        if code not in self._cache:
            block = self._glyphs[code * GLYPH_BYTES:(code + 1) * GLYPH_BYTES]
            self._cache[code] = decode_glyph(block, self._half_rows)
        return self._cache[code]


def read_glyph_set(rom_path: Path, facts: Dict[str, Any]) -> GlyphSet:
    """Read the three tables from the ROM (a few tens of kilobytes; call it from a worker thread)."""
    count = int(facts["glyph_count"])
    with open(rom_path, "rb") as handle:
        handle.seek(int(facts["width_table"]))
        widths = handle.read(count)
        handle.seek(int(facts["glyph_table"]))
        glyphs = handle.read(count * GLYPH_BYTES)
        handle.seek(int(facts["half_row_table"]))
        half_rows = handle.read(256)
    if len(widths) != count or len(glyphs) != count * GLYPH_BYTES or len(half_rows) != 256:
        raise ValueError("the ROM ends before the font tables")
    return GlyphSet(widths, glyphs, half_rows)


def font_facts(facts_file: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The ``font`` entry of a facts file, or None when the file has none."""
    return facts_file.get("font") if isinstance(facts_file, dict) else None


# -- Ruby and Sapphire: 4bpp glyphs (font 3) --------------------------------------------------------------------
# A glyph is 8 pixels wide and 16 tall: the upper 8x8 tile (32 bytes, 4 bytes per row, low nibble first) and the
# lower 8x8 tile (32 bytes). The nibble is the palette index: 0 paper, 1 ink, 2 shadow. Advance widths come from
# the game's width table, one byte per glyph. The shared renderer draws ``drawn_width`` columns and advances by
# ``width``. The FireRed set below keeps the old behaviour (its drawn width is its advance width).
GLYPH4_BYTES = 64
GLYPH4_ROWS = 16
GLYPH4_COLUMNS = 8


# The GBA nibbles of the Ruby font: 0 paper, 15 ink, 14 shadow (the palette of the text window: ink 1, shadow 8).
NIBBLE_CLASS = {0: PAPER, 0xF: INK, 0xE: SHADOW}


def decode_glyph_4bpp(data: bytes) -> List[List[int]]:
    """The 16 x 8 pixel classes of one glyph (upper tile first, then the lower tile)."""
    rows = []
    for y in range(GLYPH4_ROWS):
        tile, row = divmod(y, 8)
        base = 32 * tile + 4 * row
        cells = []
        for x in range(GLYPH4_COLUMNS):
            byte = data[base + x // 2]
            cells.append(NIBBLE_CLASS.get((byte >> (4 * (x % 2))) & 0xF, PAPER))
        rows.append(cells)
    return rows


class Glyph4bppSet:
    """Widths and decoded 4bpp glyphs of one Ruby or Sapphire font. ``code`` is the glyph index (the text byte)."""

    def __init__(self, widths: bytes, glyphs: bytes) -> None:
        self._widths = widths
        self._glyphs = glyphs
        self._cache: Dict[int, List[List[int]]] = {}

    @property
    def count(self) -> int:
        return len(self._widths)

    def width(self, code: int) -> int:
        return self._widths[code] if 0 <= code < len(self._widths) else 0

    def drawn_width(self, code: int) -> int:
        return GLYPH4_COLUMNS if 0 <= code < len(self._widths) else 0

    def pixels(self, code: int) -> List[List[int]]:
        if code not in self._cache:
            block = self._glyphs[code * GLYPH4_BYTES:(code + 1) * GLYPH4_BYTES]
            self._cache[code] = decode_glyph_4bpp(block)
        return self._cache[code]


def read_glyph_set_4bpp(rom_path: Path, facts: Dict[str, Any]) -> Glyph4bppSet:
    """Read the width table and the 4bpp glyph table of a Ruby or Sapphire font from the ROM."""
    count = int(facts["glyph_count"])
    width_count = int(facts.get("width_count", count))
    with open(rom_path, "rb") as handle:
        handle.seek(int(facts["width_table"]))
        widths = handle.read(width_count)
        handle.seek(int(facts["glyph_table"]))
        glyphs = handle.read(count * GLYPH4_BYTES)
    if len(widths) != width_count or len(glyphs) != count * GLYPH4_BYTES:
        raise ValueError("the ROM ends before the font tables")
    return Glyph4bppSet(widths, glyphs)
