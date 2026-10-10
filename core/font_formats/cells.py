"""Fixed-size glyph cells stored one after another in a byte range of a file, as one sheet (DS-style fonts
that live in a data pack: The Tale of Two Towns 3DS ``font_data.bin``).

A cell is ``cell`` = ``[width, height]`` pixels of ``bpp`` bits (4: two pixels a byte, low nibble first; 8: one
byte a pixel), rows top to bottom, starting at ``offset``; ``count`` cells follow. The sheet shows them
``columns`` to a row, grey ``17 * value`` (4 bpp) with alpha where the value is not 0, so an unedited font packs
back to the same bytes. Cell ``i`` is character ``chars[i]`` (a string; a cell past the end has no character);
every glyph advances ``advance`` px (default: the cell width; widths are not stored in the file). ``tiles``
true: a 16x16 cell is four 8x8 tiles (top left, top right, bottom left, bottom right), the DS character layout.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, map_entries


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _geometry(params: Dict[str, Any]) -> Tuple[int, int, int, int, int, int]:
    width, height = (_int(v) for v in params["cell"])
    bpp = _int(params.get("bpp", 4))
    count, columns = _int(params["count"]), _int(params.get("columns", 16))
    return _int(params.get("offset", 0)), count, width, height, bpp, columns


def _xy(p: int, width: int, tiles: bool) -> Tuple[int, int]:
    """Pixel ``p`` of a cell: plain rows, or 8x8 tiles of a 16-wide cell."""
    if tiles and width == 16:
        tile, i = divmod(p, 64)
        return (tile % 2) * 8 + i % 8, (tile // 2) * 8 + i // 8
    return p % width, p // width


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    offset, count, width, height, bpp, columns = _geometry(params)
    tiles = bool(params.get("tiles"))
    rows = (count + columns - 1) // columns
    sheet = Image.new("RGBA", (columns * width, rows * height), (0, 0, 0, 0))
    pixels = sheet.load()
    size = width * height * bpp // 8
    for glyph in range(count):
        cell = data[offset + glyph * size:offset + (glyph + 1) * size]
        gx, gy = (glyph % columns) * width, (glyph // columns) * height
        for p in range(width * height):
            value = (cell[p // 2] >> ((p % 2) * 4)) & 15 if bpp == 4 else cell[p]
            if value:
                grey = value * 17 if bpp == 4 else value
                x, y = _xy(p, width, tiles)
                pixels[gx + x, gy + y] = (grey, grey, grey, 255)
    chars = str(params.get("chars", ""))[:count]
    pairs = [(char_code(char), glyph) for glyph, char in enumerate(chars) if char != "\0"]
    advance = _int(params.get("advance", width))
    metadata = {
        "header": {"signature": "Glyph cells", "num_chunks": 4},
        "INF1": [{"encoding": 0, "ascent": height, "descent": 0, "width": advance, "leading": height,
                  "fallback_code": pairs[0][0] if pairs else 0x20, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": width, "cell_height": height,
                  "page_data_size": 0, "texture_format": 0, "glyph_horizontal_count": columns,
                  "glyph_vertical_count": rows, "texture_width": sheet.width, "texture_height": sheet.height}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": count,
                  "packets": [{"kerning": 0, "width": advance} for _ in range(count)]}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    """``original`` with the sheet's cells written back into the byte range."""
    offset, count, width, height, bpp, columns = _geometry(params)
    sheet = sheets[0].convert("RGBA")
    rows = (count + columns - 1) // columns
    if sheet.size != (columns * width, rows * height):
        raise ValueError(f"The sheet is {sheet.width}x{sheet.height}, the font needs {columns * width}x{rows * height}")
    pixels = sheet.load()
    tiles = bool(params.get("tiles"))
    out = bytearray(original)
    size = width * height * bpp // 8
    for glyph in range(count):
        cell = bytearray(size)
        gx, gy = (glyph % columns) * width, (glyph // columns) * height
        for p in range(width * height):
            x, y = _xy(p, width, tiles)
            r, g, b, a = pixels[gx + x, gy + y]
            level = min(max(r, g, b), a)
            value = (min(15, (level + 8) // 17)) if bpp == 4 else level
            if bpp == 4:
                cell[p // 2] |= value << ((p % 2) * 4)
            else:
                cell[p] = value
        out[offset + glyph * size:offset + (glyph + 1) * size] = cell
    return bytes(out)
