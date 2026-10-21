"""Okami HD message codes: the u16 units of the English MSD strings and the characters they show.

The font atlas (``etc/core_30.bin``, texture at 0x93C0, 1200 x 1200, BC7) is a glyph sheet. Its cells, row-major
with 16 columns, hold the characters in this order: digits 0-9 at cells 14-23, capitals A-V at 26-47, W-Z at 48-51,
lowercase a-z at 52-77. A letter's message code is its cell index minus 3. Verified on the English dialogue of
``st1/r101.bin``: "the" (0x44 0x38 0x35), "ing", "and", "Somebody", "Celestial Brush", "I wasn't looking" decode as
English. The capitals are fixed by B, C, H, I, S, T, W, Y, which all decode correctly with this run. Digits sit at
the same grid but are not checked against text yet.

0x0001 is the space (the most common code after a letter). 0x000A is the apostrophe ("wasn't", "tryin'"). Every
other unit is kept as a tag ``{xxxx}`` (hex, 4 digits), so no unit is lost. The periods and commas (0x0002-0x0004
after words) and the control codes (0x80xx, 0xA0xx, 0xD0xx, ...) stay tags until they are checked on the screen.

``decode`` and ``encode`` are exact inverses on any unit sequence: ``encode(decode(raw)) == raw``.
"""
from __future__ import annotations

import re
import struct
from typing import Dict

SPACE = 0x0001
APOSTROPHE = 0x000A
ATLAS_COLUMNS = 16
ATLAS_CODE_OFFSET = 3          # code = atlas cell index - 3 (letters)


# Ukrainian letters: 66 atlas cells that the English strings never use (codes 0x5E-0xFC, checked on every English MSD
# string; see tests). The font atlas gives each its cell (code + 3); the owner draws the glyphs in the Font Editor.
UKRAINIAN_LETTERS = (
    "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"
    "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
)
UK_SLOT_CODES = (
    0x5E, 0x5F, 0x60, 0x65, 0x66, 0x67, 0x68, 0x6A, 0x6B, 0x6C, 0x71, 0x76, 0x7E, 0x7F, 0x88, 0x89,
    0x8C, 0x8E, 0x8F, 0x90, 0x92, 0x93, 0x94, 0x95, 0x9A, 0x9E, 0x9F, 0xA1, 0xA2, 0xA3, 0xA4, 0xA6,
    0xA7, 0xA9, 0xAC, 0xB1, 0xB3, 0xB5, 0xB6, 0xBA, 0xBB, 0xBD, 0xC0, 0xC2, 0xC4, 0xC9, 0xCD, 0xCE,
    0xCF, 0xD0, 0xD1, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xDB, 0xDD, 0xDE, 0xDF, 0xE0,
    0xE1, 0xE2,
)


def _cell_chars() -> Dict[int, str]:
    """Message code -> character for the letters and digits that the atlas grid fixes."""
    # atlas cell index -> character. Cells 13, 24 and 25 are blank. The capitals A-V fill cells 26-47 in one run:
    # this fits every capital checked on the text (B, C, H, I, S, T, W, Y), and the blank cells are where the
    # atlas grid shows a gap (see module docstring).
    runs = (
        (14, "0123456789"),
        (26, "ABCDEFGHIJKLMNOPQRSTUV"),
        (48, "WXYZ"),
        (52, "abcdefghijklmnopqrstuvwxyz"),
    )
    table: Dict[int, str] = {}
    for start, chars in runs:
        for offset, char in enumerate(chars):
            table[start + offset - ATLAS_CODE_OFFSET] = char
    table[SPACE] = " "
    table[APOSTROPHE] = "'"    # "wasn't", "tryin'" in the dialogue
    for code, letter in zip(UK_SLOT_CODES, UKRAINIAN_LETTERS):
        table[code] = letter
    return table


CODE_TO_CHAR: Dict[int, str] = _cell_chars()
CHAR_TO_CODE: Dict[str, int] = {char: code for code, char in CODE_TO_CHAR.items()}
_TAG = re.compile(r"\{([0-9a-fA-F]{4})\}")


def atlas_cell(code: int) -> tuple:
    """(row, column) of the atlas cell that holds the glyph of a letter code."""
    index = code + ATLAS_CODE_OFFSET
    return divmod(index, ATLAS_COLUMNS)


def decode(raw: bytes, endian: str = "<") -> str:
    """The text of a raw string: letters and the space as characters, every other unit as ``{xxxx}``.

    ``endian`` is the byte order of the 16-bit units: little for the Switch and PS2 files, big for the Wii files."""
    out = []
    for pos in range(0, len(raw) - 1, 2):
        unit = struct.unpack_from(endian + "H", raw, pos)[0]
        char = CODE_TO_CHAR.get(unit)
        out.append(char if char is not None else "{%04x}" % unit)
    if len(raw) % 2:
        out.append("{%02x}" % raw[-1])   # an odd byte at the end is kept as a two-digit tag
    return "".join(out)


def encode(text: str, endian: str = "<") -> bytes:
    """The raw bytes of a text made by ``decode``. Raises ValueError for a character the atlas does not show."""
    out = bytearray()
    pos = 0
    while pos < len(text):
        match = _TAG.match(text, pos)
        if match:
            out += struct.pack(endian + "H", int(match.group(1), 16))
            pos = match.end()
            continue
        if text[pos] == "{" and text[pos:pos + 4] and re.match(r"\{[0-9a-fA-F]{2}\}", text[pos:pos + 4]):
            out.append(int(text[pos + 1:pos + 3], 16))
            pos += 4
            continue
        char = text[pos]
        code = CHAR_TO_CODE.get(char)
        if code is None:
            raise ValueError(f"no atlas glyph for {char!r}")
        out += struct.pack(endian + "H", code)
        pos += 1
    return bytes(out)
