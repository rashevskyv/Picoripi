"""Text of Lunar 2: Eternal Blue Complete (PlayStation) as editable strings with readable tags.

Text is a stream of 16-bit units (little-endian in the file). The game's printer (SLUS_010.71
0x80012BB4) reads them two ways:

- outside a line, ``0x06cc`` starts a line with character ``cc`` (``0x06FF``: an empty line, nothing
  drawn); ``0x1000`` is a new line; any other unit is a control the window code acts on (portrait
  ``0xBxxx``, name ``0xCxxx``, page ``0x2000``, choice ``0x4xxx``, icon ``0x3xxx``, pause ``0xDxxx``...);
- inside a line a unit holds two characters, high byte first. A character with bit 7 set ends the line
  after it is drawn; a 0xFF byte ends it without drawing.

A character ``c`` (0x01-0x5F) is the font's ASCII ``c + 0x1F``: 0x40 (``_``) moves the pen to the next
16-pixel stop, 0x5C and 0x5E are the curly quotes. Here a line is plain text, ``\n`` is the unit 0x1000,
``{XXXX}`` any other unit, ``{XX}`` a character byte without a glyph and ``{/}`` the boundary of two
lines that follow each other without a unit between them.
"""
from __future__ import annotations

import re
import struct
from typing import List, Set

LINE, NEWLINE, END = 0x06, 0x1000, 0xFF
EMPTY_LINE = 0x06FF
SPECIAL = {0x5C: "“", 0x5E: "”"}
CODES = {char: code for code, char in SPECIAL.items()}
TAG_RE = re.compile(r"\{(?:[0-9A-F]{4}|[0-9A-F]{2}|/)\}")
_TOKEN = re.compile(r"\{(?:[0-9A-F]{4}|[0-9A-F]{2}|/)\}|\n|.", re.S)


def char(code: int) -> str:
    if code in SPECIAL:
        return SPECIAL[code]
    if 0x01 <= code <= 0x5F:
        return chr(code + 0x1F)
    return f"{{{code:02X}}}"


def code_of(text: str) -> int:
    """The character byte of one character, or -1."""
    if text in CODES:
        return CODES[text]
    value = ord(text) - 0x1F if len(text) == 1 else -1
    return value if 0x01 <= value <= 0x5F and value not in CODES else -1


def units(data: bytes, start: int = 0, end: int = -1) -> List[int]:
    end = len(data) if end < 0 else end
    return list(struct.unpack_from(f"<{(end - start) // 2}H", data, start))


def pack(values: List[int]) -> bytes:
    return struct.pack(f"<{len(values)}H", *values)


def decode(values: List[int]) -> str:
    """The text of a unit stream."""
    out: List[str] = []
    inline = ended = False
    for unit in values:
        hi, lo = unit >> 8, unit & 0xFF
        if not inline:
            if hi == LINE and lo != END:
                if ended:
                    out.append("{/}")
                out.append(char(lo & 0x7F))
                inline = not lo & 0x80
                ended = not inline
                continue
            out.append("\n" if unit == NEWLINE else f"{{{unit:04X}}}")
            ended = False
            continue
        if unit == 0x0600 or hi == END:
            out.append(f"{{{unit:04X}}}")           # ends the line; kept as a raw unit
            inline, ended = False, False
            continue
        out.append(char(hi & 0x7F))
        if hi & 0x80:
            inline, ended = False, True
            if lo:
                out.append(f"{{{lo:02X}}}")         # an ignored byte after the end
            continue
        if lo == END:
            inline, ended = False, True
            continue
        out.append(char(lo & 0x7F))
        if lo & 0x80:
            inline, ended = False, True
    return "".join(out)


class Encoder:
    """Text to units; characters the game cannot write become '?' and go to ``missing``."""

    def __init__(self):
        self.missing: Set[str] = set()

    def _line(self, codes: List[int], open_end: bool = False) -> List[int]:
        raw = [LINE] + codes
        if len(raw) % 2:
            raw.append(END)
        elif not open_end:                          # a raw unit that follows ends the line itself
            raw[-1] |= 0x80
        return [raw[i] << 8 | raw[i + 1] for i in range(0, len(raw), 2)]

    def encode(self, text: str) -> List[int]:
        out: List[int] = []
        line: List[int] = []

        def flush(open_end: bool = False):
            if line:
                out.extend(self._line(line, open_end))
                line.clear()

        for token in _TOKEN.findall(text):
            if token == "\n":
                flush()
                out.append(NEWLINE)
            elif token == "{/}":
                flush()
            elif TAG_RE.fullmatch(token) and len(token) == 6:
                unit = int(token[1:5], 16)
                flush(unit == 0x0600 or unit >> 8 == END)
                out.append(unit)
            elif TAG_RE.fullmatch(token):
                line.append(int(token[1:3], 16))
            else:
                code = code_of(token)
                if code < 0:
                    self.missing.add(token)
                    code = code_of("?")
                line.append(code)
        flush()
        return out
