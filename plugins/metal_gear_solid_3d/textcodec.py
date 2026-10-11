"""Snake Eater 3D subtitle bytes <-> editor text.

Printable ASCII is itself. A character of the font's upper half is written ``0x1F, latin1 - 0x7F`` (the font follows
ISO 8859-1: ``ä`` = ``1F 65``, ``ß`` = ``1F 60``, ``¡`` = ``1F 22``). A line break is ``0x80 0x7C`` (or 0x0A). Any
other byte is shown as ``{xNN}``. The same scheme as the Twin Snakes (``plugins.mgs_ts.textcodec``) with the Latin-1
upper half instead of Mac Roman.

Ukrainian letters reach the game through the translation map: ``{"Б": "Á"}`` -- Б is drawn by the glyph of Á, so it
is written as Á's escape.
"""
from __future__ import annotations

import re
from typing import Dict, Optional, Set

ESCAPE = 0x1F
LF = b"\n"
SUB_LF = b"\x80|"
TAG_RE = re.compile(r"\{x([0-9A-Fa-f]{2})\}")


def _upper_char(code: int) -> str:
    return bytes([code]).decode("latin-1")


def decode(raw: bytes, reverse_map: Optional[Dict[str, str]] = None) -> str:
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


def newline_of(raw: bytes, default: bytes = SUB_LF) -> bytes:
    """The line break a string uses: the first one in it, else ``default``."""
    lf, sub = raw.find(LF), raw.find(SUB_LF)
    if lf < 0 and sub < 0:
        return default
    if sub < 0 or (0 <= lf < sub):
        return LF
    return SUB_LF


def encode(text: str, newline: bytes = SUB_LF, translation_map: Optional[Dict[str, str]] = None,
           missing: Optional[Set[str]] = None) -> bytes:
    """Game bytes of editor text; characters with no glyph become ``?`` and go to ``missing``."""
    out = bytearray()
    mapping = translation_map or {}
    pos = 0
    for match in TAG_RE.finditer(text):
        out += _plain(text[pos:match.start()], newline, mapping, missing)
        out.append(int(match.group(1), 16))
        pos = match.end()
    out += _plain(text[pos:], newline, mapping, missing)
    return bytes(out)


def _plain(text: str, newline: bytes, mapping: Dict[str, str], missing: Optional[Set[str]]) -> bytes:
    out = bytearray()
    for char in text:
        if char == "\n":
            out += newline
            continue
        char = mapping.get(char, char)
        code = ord(char)
        if 0x20 <= code < 0x7F:
            out.append(code)
        elif 0xA0 <= code <= 0xFF:
            out += bytes((ESCAPE, code - 0x7F))
        else:
            if missing is not None:
                missing.add(char)
            out.append(0x3F)
    return bytes(out)
