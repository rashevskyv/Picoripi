"""Vagrant Story (PlayStation) text font: ``FONT/VSFONT.FNT`` of the translation workspace.

The game keeps the font in two files: the 4-bit glyph texture in ``BATTLE/SYSTEM.DAT`` (256 x 216
pixels at 0x1AA70, low nibble first; 12 x 12 cells, 21 a row: cell ``n`` is character code ``n``
of the regular font, cell ``189 + n`` the same code in the italic font that dialog balloons use)
and the advance of every cell in ``BATTLE/BATTLE.PRG`` (378 bytes). The workspace's unpack step
puts both in one file and its build step puts them back::

    "VSFN", u32 texture bytes (27648), u32 width count (378), u32 0, texture, widths

Parameter ``set``: 0 opens the regular font (menus, help), 1 the italic one (dialog balloons).
Each is 189 glyphs mapped to the characters of ``plugins.vagrant_story.codec`` -- the same
characters in both, so one translation map serves both fonts. Packing writes only that set's
cells and widths; unedited, it gives the file back byte for byte.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries

MAGIC = b"VSFN"
HEADER = 16
CELL, COLUMNS, ROWS = 12, 21, 9          # one set: 189 cells
ROW_BYTES = 128                          # the texture is 256 pixels wide
SET_GLYPHS = COLUMNS * ROWS
TEXTURE = ROW_BYTES * CELL * ROWS * 2
WIDTHS = SET_GLYPHS * 2


def _parse(data: bytes) -> None:
    if data[:4] != MAGIC or len(data) < HEADER:
        raise ValueError("Not a Vagrant Story font file (VSFN)")
    texture, count = struct.unpack_from("<II", data, 4)
    if texture != TEXTURE or count != WIDTHS or len(data) < HEADER + texture + count:
        raise ValueError("Vagrant Story font of an unexpected size")


def _set(params: Dict[str, Any]) -> int:
    value = int(params.get("set", 0))
    if value not in (0, 1):
        raise ValueError(f"Font set {value}: 0 is the regular font, 1 the italic one")
    return value


def characters() -> Dict[int, str]:
    """Character of each cell of a set (the plugin's codec)."""
    from plugins.vagrant_story.codec import CHARS
    return dict(CHARS)


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    _parse(data)
    which = _set(params)
    width, height = COLUMNS * CELL, ROWS * CELL
    first_row = which * height
    ink = bytearray(width * height)
    for y in range(height):
        start = HEADER + (first_row + y) * ROW_BYTES
        row = data[start:start + ROW_BYTES]
        for x in range(width):
            byte = row[x >> 1]
            ink[y * width + x] = ((byte >> 4) if x & 1 else (byte & 0xF)) * 17
    sheet = grey_sheet(Image.frombytes("L", (width, height), bytes(ink)))
    start = HEADER + TEXTURE + which * SET_GLYPHS
    widths = data[start:start + SET_GLYPHS]
    pairs = [(char_code(char), code) for code, char in characters().items() if len(char) == 1 and code < SET_GLYPHS]
    metadata = {
        "header": {"signature": "VSFN", "num_chunks": 4},
        "INF1": [{"encoding": 0, "ascent": 10, "descent": 2, "width": 6, "leading": 13,
                  "fallback_code": char_code("?"), "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": SET_GLYPHS - 1, "cell_width": CELL, "cell_height": CELL,
                  "page_data_size": TEXTURE // 2, "texture_format": 0,
                  "glyph_horizontal_count": COLUMNS, "glyph_vertical_count": ROWS,
                  "texture_width": width, "texture_height": height}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": SET_GLYPHS,
                  "packets": [{"kerning": 0, "width": int(value)} for value in widths]}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    _parse(original)
    which = _set(params)
    out = bytearray(original)
    ink = coverage(sheets[0]).tobytes()
    width = sheets[0].width
    first_row = which * ROWS * CELL
    for y in range(min(ROWS * CELL, sheets[0].height)):
        base = HEADER + (first_row + y) * ROW_BYTES
        for x in range(0, COLUMNS * CELL, 2):
            low = min(15, (ink[y * width + x] + 8) // 17)
            high = min(15, (ink[y * width + x + 1] + 8) // 17)
            out[base + (x >> 1)] = high << 4 | low
    packets = (metadata.get("WID1") or [{}])[0].get("packets", [])
    start = HEADER + TEXTURE + which * SET_GLYPHS
    for glyph in range(min(SET_GLYPHS, len(packets))):
        value = int(packets[glyph].get("width", 0))
        if not 0 <= value <= 255:
            raise ValueError(f"Glyph {glyph}: width {value} does not fit a byte")
        out[start + glyph] = value
    return bytes(out)


def build(texture: bytes, widths: bytes) -> bytes:
    """A font file from the game's texture rows and width table (what the unpack step writes)."""
    if len(texture) != TEXTURE or len(widths) != WIDTHS:
        raise ValueError("texture or width table of an unexpected size")
    return MAGIC + struct.pack("<III", TEXTURE, WIDTHS, 0) + bytes(texture) + bytes(widths)
