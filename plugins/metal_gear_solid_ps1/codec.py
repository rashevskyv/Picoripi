"""Metal Gear Solid (PlayStation) text bytes <-> editor text.

The game reads a byte below 0x80 as one character and anything else as a two-byte code. ``0x80 c``
is the same character ``c`` (the "hankaku" form); the other two-byte codes are control codes, button
icons and the extra glyphs a codec call, script or subtitle block carries with it.

- printable ASCII is itself;
- the line break is ``#N`` written as ``80 23 80 4E`` in codec calls and ``80 7C`` (``|``) in
  subtitles and item descriptions -- the caller says which (``RADIO_LF`` / ``SUB_LF``);
- ``"`` is ``80 22`` in codec calls and subtitles and a plain 0x22 in scripts and programs (the
  caller says which, ``quote``); the other form reads ``{8022}`` / ``{22}``;
- a "wide" string (save location names) writes every character as ``80 c`` and a space as ``90 01``;
- any other code is shown as a tag: ``{901B}`` (two bytes) or ``{0A}`` (one byte).

Ukrainian letters reach the game through the translation map (letter -> a character of the font).
"""
from __future__ import annotations

import re
from typing import Dict, Optional, Set

RADIO_LF = b"\x80#\x80N"
SUB_LF = b"\x80|"
QUOTE = b"\x80\""
PLAIN_QUOTE = b"\""
WIDE_SPACE = b"\x90\x01"
TAG_RE = re.compile(r"\{([0-9A-F]{2}|[0-9A-F]{4})\}")
_PRINTABLE = range(0x20, 0x7F)
_LITERAL = set(range(0x20, 0x7F)) - {0x22, 0x7B, 0x7D}


def is_wide(raw: bytes) -> bool:
    """Every character of the string is written ``80 c`` or ``90 xx`` (and one at least ``80 c``)."""
    if not raw or len(raw) % 2:
        return False
    pairs = [raw[i:i + 2] for i in range(0, len(raw), 2)]
    return all((p[0] == 0x80 and p[1] in _PRINTABLE) or p[0] == 0x90 for p in pairs) and any(p[0] == 0x80 for p in pairs)


def decode(raw: bytes, newline: bytes = RADIO_LF, quote: bytes = QUOTE,
           reverse_map: Optional[Dict[str, str]] = None) -> str:
    """Editor text of one string (without its NUL)."""
    back = reverse_map or {}
    if is_wide(raw):
        out = []
        for i in range(0, len(raw), 2):
            pair = raw[i:i + 2]
            if pair == WIDE_SPACE:
                out.append(" ")
            elif pair[0] == 0x80 and pair[1] in _LITERAL:
                out.append(back.get(chr(pair[1]), chr(pair[1])))
            else:
                out.append("{%02X%02X}" % (pair[0], pair[1]))
        return "".join(out)
    out = []
    i, n = 0, len(raw)
    while i < n:
        if newline and raw.startswith(newline, i):
            out.append("\n")
            i += len(newline)
        elif raw.startswith(quote, i):
            out.append('"')
            i += len(quote)
        elif raw[i] < 0x80:
            b = raw[i]
            out.append(back.get(chr(b), chr(b)) if b in _LITERAL else "{%02X}" % b)
            i += 1
        elif i + 1 < n:
            out.append("{%02X%02X}" % (raw[i], raw[i + 1]))
            i += 2
        else:
            out.append("{%02X}" % raw[i])
            i += 1
    return "".join(out)


def encode(text: str, newline: bytes = RADIO_LF, quote: bytes = QUOTE, wide: bool = False,
           translation_map: Optional[Dict[str, str]] = None, missing: Optional[Set[str]] = None) -> bytes:
    """Game bytes of editor text; a character with no glyph becomes ``?`` and goes to ``missing``."""
    mapping = translation_map or {}
    out = bytearray()
    pos = 0
    for match in TAG_RE.finditer(text):
        out += _plain(text[pos:match.start()], newline, quote, wide, mapping, missing)
        out += bytes.fromhex(match.group(1))
        pos = match.end()
    out += _plain(text[pos:], newline, quote, wide, mapping, missing)
    return bytes(out)


def _plain(text: str, newline: bytes, quote: bytes, wide: bool, mapping: Dict[str, str],
           missing: Optional[Set[str]]) -> bytes:
    out = bytearray()
    for char in text:
        if char == "\n":
            out += newline or b" "
            continue
        if wide and char == " ":
            out += WIDE_SPACE
            continue
        char = mapping.get(char, char)
        code = ord(char)
        if code not in _PRINTABLE:
            if missing is not None:
                missing.add(char)
            code = 0x3F
        if wide:
            out += bytes((0x80, code))
        elif code == 0x22:
            out += quote
        else:
            out.append(code)
    return bytes(out)


def has_letters(raw: bytes) -> bool:
    """The string reads as words: two letters in a row once tags are taken out."""
    return re.search(r"[A-Za-z]{2}", TAG_RE.sub("", decode(raw))) is not None
