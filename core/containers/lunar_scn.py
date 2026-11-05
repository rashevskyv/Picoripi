"""Lunar 2 Eternal Blue Remastered event scripts (``DATA_us/SCN``, ``DATA_jp/SCN``): the dialogue messages.

Each script is a stream of little-endian u16 words. A word is one of three things:

- Japanese (``DATA_jp``): a Shift-JIS character stored as its code (``0x82A0`` for hiragana A is the word).
- English (``DATA_us``): a glyph ``0x70XX``; ``XX`` indexes the English font (``EN_GLYPHS``). The table was
  derived from the decoded text itself: letters follow the frequency order of English, and the decoded
  words read as dialogue (for example ``0x48`` to ``0x61`` are ``a`` to ``z``, ``0x28`` to ``0x41`` are
  ``A`` to ``Z``, ``0x07`` is the space). Glyphs without a proven value stay as ``[XX]``.
- Control words, for example ``0x1000`` (line break), ``0x2000`` (message end) and voice cues such as ``0xB2C1``.

A message is the text between two ``0x2000`` words. Its lines are split at ``0x1000``. The English and Japanese
scripts of one file use the same control words, so the message count of both files is the same in most files.
Other words (tables, offsets) are not text; a run of more than ``MAX_GAP`` control words ends a message without
a ``0x2000`` mark, and such a message is dropped.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

LINE_BREAK = 0x1000
MESSAGE_END = 0x2000
MAX_GAP = 3
EN_PAGE = 0x70

EN_GLYPHS: Dict[int, str] = {0x07: " ", 0x08: "!", 0x0E: "'", 0x13: ",", 0x15: ".", 0x26: "?"}
EN_GLYPHS.update({0x28 + i: chr(ord("A") + i) for i in range(26)})
EN_GLYPHS.update({0x48 + i: chr(ord("a") + i) for i in range(26)})


@dataclass
class ScnMessage:
    """One dialogue message: where it starts in the script, its voice cues, and its lines."""

    offset: int
    cues: Tuple[int, ...] = ()
    lines: List[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def _char(word: int, english: bool) -> Optional[str]:
    if english:
        if word >> 8 != EN_PAGE:
            return None
        low = word & 0xFF
        return EN_GLYPHS.get(low, "[%02X]" % low)
    hi = word >> 8
    if not (0x81 <= hi <= 0x9F or 0xE0 <= hi <= 0xFC):
        return None
    try:
        return bytes([hi, word & 0xFF]).decode("cp932")
    except UnicodeDecodeError:
        return None


def read_messages(data: bytes, english: bool) -> List[ScnMessage]:
    """Every message that ends with a ``0x2000`` mark, in file order. ``english`` selects the glyph page."""
    words = struct.unpack_from("<%dH" % (len(data) // 2), data, 0)
    out: List[ScnMessage] = []
    msg: Optional[ScnMessage] = None
    line: List[str] = []
    cues: List[int] = []
    gap = 0
    for i, word in enumerate(words):
        char = _char(word, english)
        if char is not None:
            if msg is None:
                msg = ScnMessage(offset=2 * i)
            line.append(char)
            gap = 0
            continue
        if word == LINE_BREAK:
            if line and msg is not None:
                msg.lines.append("".join(line))
            line = []
            gap = 0
            continue
        if word == MESSAGE_END:
            if line and msg is not None:
                msg.lines.append("".join(line))
            if msg is not None and msg.lines:
                msg.cues = tuple(cues)
                out.append(msg)
            msg, line, cues, gap = None, [], [], 0
            continue
        gap += 1
        if gap > MAX_GAP:
            msg, line, cues, gap = None, [], [], 0
            continue
        if msg is None:
            cues.append(word)
        else:
            line.append("{%04X}" % word)
    return out
