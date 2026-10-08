"""1-bit glyph records of Konami's GBA Castlevania games (Harmony of Dissonance, Aria of Sorrow).

The file is a run of ``glyphs`` records of ``record`` bytes: a 2-byte key (big endian: the glyph's index or its
Shift-JIS code) and then one byte per pixel row (``rows`` rows, 8 pixels, the high bit left). Bits in
``keep_mask`` are not pixels (AoS keeps other data in bit 0) and are written back as they were.

Widths: with ``widths`` (``{"stride": 4, "byte": 1}``) the font comes with its width table as the companion file
(``sources.join_pair``): one ``stride``-byte entry per glyph, the advance in byte ``byte``. Without it every glyph
advances ``advance`` pixels (or its ``glyph_widths`` entry, ``{"glyph index": width}``, for a game that keeps
widths elsewhere) and widths are not written.

Pixels: a set bit is white ink, a clear one transparent; a drawn pixel is ink when its coverage is at least half.
Params: ``glyphs``, ``record``, ``rows``, optional ``keep_mask``, ``widths``, ``advance`` (default 8),
``columns`` (default 16) and ``chars`` (``{"character": glyph index}``; several characters may share a glyph).
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries
from core.font_formats.sources import join_pair, split_pair

KEY = 2
CELL_W = 8


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _layout(params: Dict[str, Any]) -> Tuple[int, int, int, int, int]:
    """``(glyphs, record bytes, rows, kept bits, columns)``."""
    return (_int(params["glyphs"]), _int(params["record"]), _int(params["rows"]),
            _int(params.get("keep_mask", 0)), _int(params.get("columns", 16)))


def _split(data: bytes, params: Dict[str, Any]) -> Tuple[bytes, bytes]:
    return split_pair(data) if params.get("widths") else (bytes(data), b"")


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    glyphs_data, table = _split(data, params)
    count, record, rows, keep, columns = _layout(params)
    if len(glyphs_data) < count * record:
        raise ValueError(f"The font has {len(glyphs_data)} bytes, {count} glyphs need {count * record}")
    lines = -(-count // columns)
    ink = bytearray(columns * CELL_W * lines * rows)
    stride = columns * CELL_W
    for glyph in range(count):
        x0, y0 = (glyph % columns) * CELL_W, (glyph // columns) * rows
        for y in range(rows):
            byte = glyphs_data[glyph * record + KEY + y] & ~keep
            for x in range(CELL_W):
                if byte >> (7 - x) & 1:
                    ink[(y0 + y) * stride + x0 + x] = 255
    sheet = grey_sheet(Image.frombytes("L", (stride, lines * rows), bytes(ink)))
    advance = _int(params.get("advance", CELL_W))
    widths = params.get("widths")
    if widths:
        step, at = _int(widths.get("stride", 4)), _int(widths.get("byte", 1))
        packets = [{"kerning": 0, "width": table[glyph * step + at]} for glyph in range(count)]
    else:
        shown = {_int(k): _int(v) for k, v in (params.get("glyph_widths") or {}).items()}
        packets = [{"kerning": 0, "width": shown.get(glyph, advance)} for glyph in range(count)]
    chars = params.get("chars") or {}
    pairs = sorted({(char_code(char), _int(index)) for char, index in chars.items() if len(char) == 1 and _int(index) < count})
    metadata = {
        "header": {"signature": "Castlevania GBA font", "num_chunks": 4},
        "INF1": [{"encoding": 0, "ascent": rows - 2, "descent": 2, "width": advance, "leading": rows + 2,
                  "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": CELL_W, "cell_height": rows,
                  "page_data_size": count * rows, "texture_format": 0, "glyph_horizontal_count": columns,
                  "glyph_vertical_count": lines, "texture_width": stride, "texture_height": lines * rows}],
        "MAP1": [map_entries(pairs)] if pairs else [],
        "WID1": [{"first_code_included": 0, "last_code_included": count, "packets": packets}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    glyphs_data, table = _split(original, params)
    count, record, rows, keep, columns = _layout(params)
    ink = coverage(sheets[0]).tobytes()
    stride = sheets[0].width
    out = bytearray(glyphs_data)
    for glyph in range(count):
        x0, y0 = (glyph % columns) * CELL_W, (glyph // columns) * rows
        for y in range(rows):
            bits = 0
            row = (y0 + y) * stride + x0
            for x in range(CELL_W):
                if ink[row + x] >= 128:
                    bits |= 0x80 >> x
            at = glyph * record + KEY + y
            out[at] = out[at] & keep | bits & ~keep & 0xFF
    widths = params.get("widths")
    if not widths:
        return bytes(out)
    new_table = bytearray(table)
    step, at = _int(widths.get("stride", 4)), _int(widths.get("byte", 1))
    packets = ((metadata.get("WID1") or [{}])[0].get("packets") or [])
    for glyph, packet in enumerate(packets[:count]):
        new_table[glyph * step + at] = max(0, min(255, int(packet.get("width", 0))))
    return join_pair(bytes(out), bytes(new_table))
