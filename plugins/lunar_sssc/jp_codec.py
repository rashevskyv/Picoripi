"""Japanese text of Lunar SSS Remastered (PS1 JP): raw glyph bytes to characters.

The JP program maps each raw glyph byte 0x10-0xD5 to a 2-byte code (``raw_codes`` in ``jp_glyph_table.json``).
Codes 0x9908-0x99F8 are symbol glyphs (kana, Latin capitals, punctuation, a few kanji and symbols); their
index is ``code - 0x9908`` in ``symbols``. Every other code is a Shift-JIS character (cp932), drawn by the
console's BIOS kanji font. Controls (0x01-0x07, 0xD6 and up) and the compressed run (0x0E) work as in ``codec``.

A lead byte 0xDD-0xEE starts a two-byte glyph: its code is ``(lead - 0x55) << 8 | trail`` (0x88xx-0x99xx), read
the same way (so 0xEE xx is a symbol glyph). Leads 0xF6 and up stay the controls of ``codec``. The rule was
checked against the PSP remake's Unicode text: 975 codes aligned with its lines, none disagree.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from plugins.lunar_sssc import codec

_TABLE = json.loads((Path(__file__).resolve().parent / "jp_glyph_table.json").read_text(encoding="utf-8"))
SYMBOL_BASE = 0x9908
SYMBOL_LAST = 0x99F8
GLYPH_FIRST, GLYPH_LAST = 0x10, 0xD5
PAIR_FIRST, PAIR_LAST, PAIR_SHIFT = 0xDD, 0xEE, 0x55


def _char(code: int) -> Optional[str]:
    if SYMBOL_BASE <= code <= SYMBOL_LAST:
        return _TABLE["symbols"][code - SYMBOL_BASE]
    try:
        return bytes([code >> 8, code & 0xFF]).decode("cp932") if code else None
    except UnicodeDecodeError:
        return None


def _glyph_table() -> Dict[int, str]:
    out: Dict[int, str] = {}
    for raw in range(GLYPH_FIRST, GLYPH_LAST + 1):
        char = _char(_TABLE["raw_codes"][raw])
        if char:
            out[raw] = char
    for lead in range(PAIR_FIRST, PAIR_LAST + 1):
        for trail in range(0x100):
            char = _char((lead - PAIR_SHIFT) << 8 | trail)
            if char:
                out[lead << 8 | trail] = char
    return out


GLYPHS: Dict[int, str] = _glyph_table()


def decode_message(data: bytes, start: int, end: int) -> str:
    """The JP text of ``data[start:end]``, with the same tags as ``codec.decode_message``."""
    return codec.decode_message(data, start, end, glyphs=GLYPHS)
