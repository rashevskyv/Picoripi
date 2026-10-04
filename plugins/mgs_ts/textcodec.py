"""The Twin Snakes text bytes <-> editor text.

Printable ASCII is itself. A character of the font's upper half (Mac Roman order: glyph
0x80 is "Ä") is written ``0x1F, code - 0x7F``. A line break is 0x0A in codec and script text
and 0x80 0x7C in subtitles; a subtitle string keeps the break it already used. Any other byte
is shown as ``{xNN}`` (the Japanese strings are full of them; English ones never are).

Ukrainian letters reach the game through the translation map: ``{"Б": "Á"}`` -- Б is drawn
by the glyph of Á, so it is written as Á's escape. Only upper-half slots are mapped, so ASCII
always reads back as itself.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, Optional, Set

ESCAPE = 0x1F
LF = b"\n"
SUB_LF = b"\x80|"
TAG_RE = re.compile(r"\{x([0-9A-Fa-f]{2})\}")


def _upper_char(code: int) -> str:
    """The character of font code 0x80..0xFF (the font follows Mac Roman)."""
    return bytes([code]).decode("mac_roman")


_UPPER: Dict[str, int] = {}
for _code in range(0x80, 0x100):
    _UPPER.setdefault(_upper_char(_code), _code)


def decode(raw: bytes, reverse_map: Optional[Dict[str, str]] = None) -> str:
    """Editor text of one string (without its NUL); ``reverse_map`` turns slot characters back
    into the letters they stand for (``{"Á": "Б"}``)."""
    out = []
    i, n = 0, len(raw)
    while i < n:
        b = raw[i]
        if b == ESCAPE and i + 1 < n and 0x01 <= raw[i + 1] <= 0x80:
            char = _upper_char(raw[i + 1] + 0x7F)
            out.append((reverse_map or {}).get(char, char))
            i += 2
        elif b == 0x80 and i + 1 < n and raw[i + 1] == 0x7C:
            out.append("\n")
            i += 2
        elif b == 0x0A:
            out.append("\n")
            i += 1
        elif 0x20 <= b < 0x7F:
            out.append(chr(b))
            i += 1
        else:
            out.append("{x%02X}" % b)
            i += 1
    return "".join(out)


def newline_of(raw: bytes, default: bytes = LF) -> bytes:
    """The line break a string uses: the first one in it, else ``default``."""
    lf, sub = raw.find(LF), raw.find(SUB_LF)
    if lf < 0 and sub < 0:
        return default
    if sub < 0 or (0 <= lf < sub):
        return LF
    return SUB_LF


def encode(text: str, newline: bytes = LF, translation_map: Optional[Dict[str, str]] = None,
           missing: Optional[Set[str]] = None) -> bytes:
    """Game bytes of editor text; characters with no glyph become ``?`` and go to ``missing``."""
    out = bytearray()
    mapping = translation_map or {}
    pos = 0
    for match in TAG_RE.finditer(text):
        out += _encode_plain(text[pos:match.start()], newline, mapping, missing)
        out.append(int(match.group(1), 16))
        pos = match.end()
    out += _encode_plain(text[pos:], newline, mapping, missing)
    return bytes(out)


def _encode_plain(text: str, newline: bytes, mapping: Dict[str, str], missing: Optional[Set[str]]) -> bytes:
    out = bytearray()
    for char in text:
        if char == "\n":
            out += newline
            continue
        char = mapping.get(char, char)
        code = ord(char)
        if 0x20 <= code < 0x7F:
            out.append(code)
        elif char in _UPPER:
            out += bytes((ESCAPE, _UPPER[char] - 0x7F))
        else:
            if missing is not None:
                missing.add(char)
            out.append(0x3F)
    return bytes(out)


def is_plain_english(raw: bytes) -> bool:
    """No escape and no byte outside ASCII text: what an English string looks like."""
    return all(b == 0x0A or 0x20 <= b < 0x7F for b in raw.replace(SUB_LF, b"\n"))


def tags_in(text: str) -> Iterable[str]:
    return (match.group(0) for match in TAG_RE.finditer(text))
