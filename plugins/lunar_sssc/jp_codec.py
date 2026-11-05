"""Japanese text of Lunar SSS Remastered (PS1 JP): raw glyph bytes to characters.

The JP program maps each raw glyph byte 0x10-0xD5 to a 2-byte code (``raw_codes`` in ``jp_glyph_table.json``).
Codes 0x9908-0x99F8 are symbol glyphs (kana, Latin capitals, punctuation, a few kanji and symbols); their
index is ``code - 0x9908`` in ``symbols``. Every other code is a Shift-JIS character (cp932), drawn by the
console's BIOS kanji font. Controls (0x01-0x07, 0xD6 and up) and the compressed run (0x0E) work as in ``codec``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from plugins.lunar_sssc import codec

_TABLE = json.loads((Path(__file__).resolve().parent / "jp_glyph_table.json").read_text(encoding="utf-8"))
SYMBOL_BASE = 0x9908
SYMBOL_LAST = 0x99F8
GLYPH_FIRST, GLYPH_LAST = 0x10, 0xD5


def _glyph_table() -> Dict[int, str]:
    symbols = _TABLE["symbols"]
    out: Dict[int, str] = {}
    for raw in range(GLYPH_FIRST, GLYPH_LAST + 1):
        code = _TABLE["raw_codes"][raw]
        if SYMBOL_BASE <= code <= SYMBOL_LAST:
            out[raw] = symbols[code - SYMBOL_BASE]
        elif code:
            out[raw] = bytes([code >> 8, code & 0xFF]).decode("cp932")
    return out


GLYPHS: Dict[int, str] = _glyph_table()


def decode_message(data: bytes, start: int, end: int) -> str:
    """The JP text of ``data[start:end]``, with the same tags as ``codec.decode_message``."""
    return codec.decode_message(data, start, end, glyphs=GLYPHS)
