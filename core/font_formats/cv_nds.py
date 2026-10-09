"""1-bit glyph records of Konami's DS Castlevania games (Dawn of Sorrow, Portrait of Ruin, Order of Ecclesia).

``font/LD_font_u8.DAT`` (8 x 8) and ``font/LD_font_u12.DAT`` (16 x 12) are runs of records: a 2-byte key (big
endian; it counts up from 0 and starts again for the button pictures after glyph 0xBF) and then the pixels,
``w * h`` bits row by row, the high bit left. Glyph ``i`` is record ``i``; bytes after the last whole record
are kept as they are. The text code of a letter is its glyph index (``plugins.castlevania_ds.codec``).

Pixels: a set bit is ink, a clear one transparent; a drawn pixel is ink when its coverage is at least half.
The game spaces the letters by a fixed step, so every glyph advances ``advance`` pixels and no width is written.
Params: ``cell`` ([w, h]), optional ``advance`` (default w), ``columns`` (default 16) and ``chars``
(``{"character": glyph index}``).
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries

KEY = 2


def _layout(data: bytes, params: Dict[str, Any]) -> Tuple[int, int, int, int, int]:
    """``(glyphs, record bytes, cell width, cell height, columns)``."""
    width, height = (int(v) for v in params["cell"])
    record = KEY + width * height // 8
    return len(data) // record, record, width, height, int(params.get("columns", 16))


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    count, record, width, height, columns = _layout(data, params)
    if not count:
        raise ValueError(f"The font has {len(data)} bytes, less than one {record}-byte glyph")
    lines = -(-count // columns)
    stride = columns * width
    ink = bytearray(stride * lines * height)
    for glyph in range(count):
        bits = data[glyph * record + KEY:(glyph + 1) * record]
        x0, y0 = (glyph % columns) * width, (glyph // columns) * height
        for pixel in range(width * height):
            if bits[pixel >> 3] & (0x80 >> (pixel & 7)):
                ink[(y0 + pixel // width) * stride + x0 + pixel % width] = 255
    sheet = grey_sheet(Image.frombytes("L", (stride, lines * height), bytes(ink)))
    advance = int(params.get("advance", width))
    chars = params.get("chars") or {}
    pairs = sorted({(char_code(char), int(index)) for char, index in chars.items() if len(char) == 1 and int(index) < count})
    metadata = {
        "header": {"signature": "Castlevania DS font", "num_chunks": 4},
        "INF1": [{"encoding": 0, "ascent": height - 2, "descent": 2, "width": advance, "leading": height + 2,
                  "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": width, "cell_height": height,
                  "page_data_size": count * (record - KEY), "texture_format": 0, "glyph_horizontal_count": columns,
                  "glyph_vertical_count": lines, "texture_width": stride, "texture_height": lines * height}],
        "MAP1": [map_entries(pairs)] if pairs else [],
        "WID1": [{"first_code_included": 0, "last_code_included": count,
                  "packets": [{"kerning": 0, "width": advance} for _ in range(count)]}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    count, record, width, height, columns = _layout(original, params)
    ink = coverage(sheets[0]).tobytes()
    stride = sheets[0].width
    out = bytearray(original)
    for glyph in range(count):
        x0, y0 = (glyph % columns) * width, (glyph // columns) * height
        bits = bytearray(record - KEY)
        for pixel in range(width * height):
            if ink[(y0 + pixel // width) * stride + x0 + pixel % width] >= 128:
                bits[pixel >> 3] |= 0x80 >> (pixel & 7)
        out[glyph * record + KEY:(glyph + 1) * record] = bits
    return bytes(out)
