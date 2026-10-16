"""Nintendo DS Gen 4 bitmap font bins (``FontData``: Pokemon Diamond / Pearl / Platinum / HeartGold / SoulSilver).

A member of ``graphic/font.narc`` (raw, not compressed):
  u32 headerSize (16), u32 widthDataStart, u32 numGlyphs, u8 fixedWidth, u8 fixedHeight, u8 glyphWidth, u8 glyphHeight
  numGlyphs x glyph (16 * glyphWidth * glyphHeight bytes): 8x8 tiles at 2 bits per pixel, row-major
  numGlyphs bytes at widthDataStart: the width of each glyph
A tile is 8 rows of 2 bytes. A row is a u16 whose high byte holds the left four pixels and whose low byte the
right four; each byte is four 2-bit pixels, the leftmost in the top bits. The text code of a character is its
glyph index + 1 (the engine's ``TryLoadGlyph``). Glyphs are 16 x 16 in the game (glyphWidth = glyphHeight = 2).

The model is one sheet of grey cells, 16 glyphs to a row, one level per 2-bit value (0, 85, 170, 255). An
unedited font packs back to the same bytes; an edited pixel is quantised to the nearest level. Widths come
from the metadata's WID1 packets when they are given, else the file keeps its own widths. No new glyphs
(``ADDS_GLYPHS`` is False): the glyph table has a fixed size.

Params: ``chars`` (``{character: glyph index}``: the Font Editor labels those cells; the plugin builds it from the
game's charmap, text code - 1; a glyph index past the font's end is left out), optional ``columns`` (default 16).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries

ADDS_GLYPHS = False
HEADER = 16
TILE_BYTES = 16


def _header(data: bytes) -> Tuple[int, int, int, int, int, int]:
    """``(glyph bytes, widths start, glyphs, glyph width in tiles, glyph height in tiles, fixed width)``."""
    if len(data) < HEADER:
        raise ValueError("The font bin is shorter than its header")
    head_size, widths, count, fixed_w, _fixed_h, gw, gh = struct.unpack_from("<IIIBBBB", data, 0)
    if head_size != HEADER or gw not in (1, 2) or gh not in (1, 2):
        raise ValueError("Not a Gen 4 font bin")
    glyph = TILE_BYTES * gw * gh
    if widths != HEADER + count * glyph or widths + count != len(data):
        raise ValueError("Not a Gen 4 font bin (sizes do not add up)")
    return glyph, widths, count, gw, gh, fixed_w


def is_font_bin(data: bytes) -> bool:
    try:
        _header(data)
    except (ValueError, struct.error):
        return False
    return True


def glyph_levels(data: bytes, index: int) -> List[List[int]]:
    """The 2-bit pixel levels (0-3) of glyph index, row by row, as the Font Editor draws it."""
    glyph, _widths_at, count, gw, gh, _fixed = _header(data)
    if not 0 <= index < count:
        raise ValueError(f"glyph {index} is not in the font ({count} glyphs)")
    base = HEADER + index * glyph
    rows: List[List[int]] = []
    for r in range(8 * gh):
        ty, row = divmod(r, 8)
        line: List[int] = []
        for tx in range(gw):
            at = base + (ty * gw + tx) * TILE_BYTES + row * 2
            for x in range(8):
                byte = data[at + 1] if x < 4 else data[at]
                line.append((byte >> (6 - 2 * (x % 4))) & 3)
        rows.append(line)
    return rows


def glyph_widths(data: bytes) -> List[int]:
    """The advance width of every glyph (the WID table at widthDataStart)."""
    _glyph, widths_at, count, _gw, _gh, _fixed = _header(data)
    return list(data[widths_at:widths_at + count])


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    glyph, widths_at, count, gw, gh, _fixed = _header(data)
    cell_w, cell_h = 8 * gw, 8 * gh
    columns = int(params.get("columns", 16))
    lines = -(-count // columns)
    stride = columns * cell_w
    ink = bytearray(stride * lines * cell_h)
    for g in range(count):
        base = HEADER + g * glyph
        x0, y0 = (g % columns) * cell_w, (g // columns) * cell_h
        for tile in range(gw * gh):
            tx, ty = tile % gw, tile // gw
            for row in range(8):
                at = base + tile * TILE_BYTES + row * 2
                for x in range(8):
                    byte = data[at + 1] if x < 4 else data[at]
                    value = (byte >> (6 - 2 * (x % 4))) & 3
                    ink[(y0 + ty * 8 + row) * stride + x0 + tx * 8 + x] = value * 85
    sheet = grey_sheet(Image.frombytes("L", (stride, lines * cell_h), bytes(ink)))
    widths = list(data[widths_at:widths_at + count])
    # params "chars": {character: glyph index} (the plugin builds it from the game's charmap, text code - 1)
    chars = params.get("chars") or {}
    pairs = sorted({(char_code(char), int(index)) for char, index in chars.items()
                    if len(char) == 1 and 0 <= int(index) < count})
    metadata = {
        "header": {"signature": "Gen 4 font bin", "num_chunks": 4},
        "INF1": [{"encoding": 0, "ascent": cell_h - 2, "descent": 2, "width": cell_w, "leading": cell_h,
                  "fallback_code": 0, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": cell_w, "cell_height": cell_h,
                  "page_data_size": count * glyph, "texture_format": 0, "glyph_horizontal_count": columns,
                  "glyph_vertical_count": lines, "texture_width": stride, "texture_height": lines * cell_h}],
        "MAP1": [map_entries(pairs)] if pairs else [],
        "WID1": [{"first_code_included": 0, "last_code_included": count - 1,
                  "packets": [{"kerning": 0, "width": w} for w in widths]}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    glyph, widths_at, count, gw, gh, _fixed = _header(original)
    cell_w, cell_h = 8 * gw, 8 * gh
    columns = int(params.get("columns", 16))
    ink = coverage(sheets[0]).tobytes()
    stride = sheets[0].width
    out = bytearray(original)
    for g in range(count):
        base = HEADER + g * glyph
        x0, y0 = (g % columns) * cell_w, (g // columns) * cell_h
        for tile in range(gw * gh):
            tx, ty = tile % gw, tile // gw
            for row in range(8):
                at = base + tile * TILE_BYTES + row * 2
                hi = lo = 0
                for x in range(8):
                    value = min(3, (ink[(y0 + ty * 8 + row) * stride + x0 + tx * 8 + x] + 42) // 85)
                    if x < 4:
                        hi |= value << (6 - 2 * x)
                    else:
                        lo |= value << (6 - 2 * (x - 4))
                out[at + 1] = hi
                out[at] = lo
    packets = (metadata.get("WID1") or [{}])[0].get("packets") or []
    if len(packets) == count:
        out[widths_at:widths_at + count] = bytes(int(p["width"]) & 0xFF for p in packets)
    return bytes(out)
