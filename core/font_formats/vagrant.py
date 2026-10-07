"""Vagrant Story (PlayStation) fonts: the text font ``FONT/VSFONT.FNT`` and the staff-roll font.

The text font lives in two files: the 4-bit glyph texture in ``BATTLE/SYSTEM.DAT`` (256 x 216
pixels at 0x1AA70, low nibble first; 12 x 12 cells, 21 a row: cell ``n`` is character code ``n``
of the regular font, cell ``189 + n`` the same code in the italic font that dialog balloons use)
and the advance of every cell in ``BATTLE/BATTLE.PRG`` (378 bytes). The workspace's unpack step
puts both in one file and its build step puts them back::

    "VSFN", u32 texture bytes (27648), u32 width count (378), u32 0, texture, widths

Parameter ``set``: 0 opens the regular font (menus, help), 1 the italic one (dialog balloons).
Each is 189 glyphs mapped to the characters of ``plugins.vagrant_story.codec`` -- the same
characters in both, so one translation map serves both fonts.

``layout: "credits"`` opens the staff-roll font inside ``ENDING/ENDING.PRG`` instead: a 4-bit TIM
of 256 x 224 pixels (pixels at ``texture``, a grey CLUT: the index is the ink), 16 x 16 cells, 16 a
row, two fonts of 112 cells (``set`` 0 italic, 1 bold capitals), cell ``n`` is the ASCII code
``0x20 + n`` the staff roll writes (``>`` is drawn as ç, ``!`` as Ä...); the advances are 224 bytes
at ``widths``. Packing writes only that set's cells and widths; unedited, it gives the file back
byte for byte.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries

# Character of each cell (both sets): the game's own table of codes. It is the text codec's table too
# (plugins.vagrant_story.codec); 0xAB/0xAC ('{' '}') are shown full width so they never read as a tag.
_LATIN_EXTRA = "ŒÀÁÂÄÇÈÉÊËÌÍÎÏÒÓÔÖÙÚÛÜßœàáâäçèéêëìíîïòóôöùúûü"
_SYMBOLS = "„‼≠≦≧÷·—⋯ !\"#$%&'()=@[];:,./\\<>?_-+*`｛｝♪△□○×←→↑↓"

CHARACTERS: Dict[int, str] = {}
for _i in range(10):
    CHARACTERS[_i] = chr(48 + _i)
for _i in range(26):
    CHARACTERS[0x0A + _i] = chr(65 + _i)
    CHARACTERS[0x24 + _i] = chr(97 + _i)
for _i, _c in enumerate(_LATIN_EXTRA):
    CHARACTERS[0x3E + _i] = _c
for _i, _c in enumerate(_SYMBOLS):
    CHARACTERS[0x86 + _i] = _c
CHARACTERS[0xB7], CHARACTERS[0xB8], CHARACTERS[0xB9] = "★", "◼", "~"
# The 27 cells after ü are empty in the game's font. They are named with Latin-1 letters the game
# does not have, so the translation map and the font editor can put Ukrainian letters on them.
EMPTY_CELLS = range(0x6B, 0x86)
for _i, _c in enumerate("ÅåØøÃãÕõÝýÞþÐð¿¡ªº°±²³µ¶¹¼½"):
    CHARACTERS[EMPTY_CELLS[0] + _i] = _c

MAGIC = b"VSFN"
HEADER = 16
CELL, COLUMNS, ROWS = 12, 21, 9          # one set: 189 cells
ROW_BYTES = 128                          # the textures are 256 pixels wide
SET_GLYPHS = COLUMNS * ROWS
TEXTURE = ROW_BYTES * CELL * ROWS * 2
WIDTHS = SET_GLYPHS * 2
CREDITS_CELL, CREDITS_COLUMNS, CREDITS_ROWS, CREDITS_FIRST = 16, 16, 7, 0x20


def _parse(data: bytes) -> None:
    if data[:4] != MAGIC or len(data) < HEADER:
        raise ValueError("Not a Vagrant Story font file (VSFN)")
    texture, count = struct.unpack_from("<II", data, 4)
    if texture != TEXTURE or count != WIDTHS or len(data) < HEADER + texture + count:
        raise ValueError("Vagrant Story font of an unexpected size")


def _set(params: Dict[str, Any]) -> int:
    value = int(params.get("set", 0))
    if value not in (0, 1):
        raise ValueError(f"Font set {value}: 0 is the first font of the file, 1 the second")
    return value


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def characters() -> Dict[int, str]:
    """Character of each cell of a text-font set."""
    return dict(CHARACTERS)


def _layout(data: bytes, params: Dict[str, Any]) -> Dict[str, Any]:
    """Where one set's cells and widths are, and the code of each cell."""
    which = _set(params)
    if params.get("layout") == "credits":
        glyphs = CREDITS_COLUMNS * CREDITS_ROWS
        out = {"texture": _int(params["texture"]), "cell": CREDITS_CELL, "columns": CREDITS_COLUMNS,
               "rows": CREDITS_ROWS, "widths": _int(params["widths"]) + which * glyphs,
               "codes": [(CREDITS_FIRST + i, i) for i in range(glyphs)], "ascent": 12, "leading": 16,
               "page": ROW_BYTES * CREDITS_CELL * CREDITS_ROWS}
    else:
        _parse(data)
        out = {"texture": HEADER, "cell": CELL, "columns": COLUMNS, "rows": ROWS,
               "widths": HEADER + TEXTURE + which * SET_GLYPHS, "ascent": 10, "leading": 13, "page": TEXTURE // 2,
               "codes": [(char_code(char), code) for code, char in characters().items()
                         if len(char) == 1 and code < SET_GLYPHS]}
    out["first_row"] = which * out["rows"] * out["cell"]
    out["glyphs"] = out["columns"] * out["rows"]
    if out["texture"] + (out["first_row"] + out["rows"] * out["cell"]) * ROW_BYTES > len(data) or \
            out["widths"] + out["glyphs"] > len(data):
        raise ValueError("Vagrant Story font of an unexpected size")
    return out


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    lay = _layout(data, params)
    cell, glyphs = lay["cell"], lay["glyphs"]
    width, height = lay["columns"] * cell, lay["rows"] * cell
    ink = bytearray(width * height)
    for y in range(height):
        start = lay["texture"] + (lay["first_row"] + y) * ROW_BYTES
        row = data[start:start + ROW_BYTES]
        for x in range(width):
            byte = row[x >> 1]
            ink[y * width + x] = ((byte >> 4) if x & 1 else (byte & 0xF)) * 17
    sheet = grey_sheet(Image.frombytes("L", (width, height), bytes(ink)))
    widths = data[lay["widths"]:lay["widths"] + glyphs]
    metadata = {
        "header": {"signature": "VSFN", "num_chunks": 4},
        "INF1": [{"encoding": 0, "ascent": lay["ascent"], "descent": 2, "width": 6, "leading": lay["leading"],
                  "fallback_code": char_code("?"), "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": glyphs - 1, "cell_width": cell, "cell_height": cell,
                  "page_data_size": lay["page"], "texture_format": 0,
                  "glyph_horizontal_count": lay["columns"], "glyph_vertical_count": lay["rows"],
                  "texture_width": width, "texture_height": height}],
        "MAP1": [map_entries(lay["codes"])],
        "WID1": [{"first_code_included": 0, "last_code_included": glyphs,
                  "packets": [{"kerning": 0, "width": int(value)} for value in widths]}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    lay = _layout(original, params)
    cell, glyphs = lay["cell"], lay["glyphs"]
    out = bytearray(original)
    ink = coverage(sheets[0]).tobytes()
    width = sheets[0].width
    for y in range(min(lay["rows"] * cell, sheets[0].height)):
        base = lay["texture"] + (lay["first_row"] + y) * ROW_BYTES
        for x in range(0, lay["columns"] * cell, 2):
            low = min(15, (ink[y * width + x] + 8) // 17)
            high = min(15, (ink[y * width + x + 1] + 8) // 17)
            out[base + (x >> 1)] = high << 4 | low
    packets = (metadata.get("WID1") or [{}])[0].get("packets", [])
    for glyph in range(min(glyphs, len(packets))):
        value = int(packets[glyph].get("width", 0))
        if not 0 <= value <= 255:
            raise ValueError(f"Glyph {glyph}: width {value} does not fit a byte")
        out[lay["widths"] + glyph] = value
    return bytes(out)


def build(texture: bytes, widths: bytes) -> bytes:
    """A font file from the game's texture rows and width table (what the unpack step writes)."""
    if len(texture) != TEXTURE or len(widths) != WIDTHS:
        raise ValueError("texture or width table of an unexpected size")
    return MAGIC + struct.pack("<III", TEXTURE, WIDTHS, 0) + bytes(texture) + bytes(widths)
