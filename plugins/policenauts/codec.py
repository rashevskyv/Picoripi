"""Policenauts subtitle bytes as editable text with readable tags, and back.

The English patch writes ASCII (0x20-0x7E) with 0x0A for a new line. Two more codes occur:
``D0 06`` (a long dash, a glyph of the kanji font) shown as ``{dash}``, and 0x80 before ``#2`` in "CO₂"
shown as ``{x80}``. Any other byte from 0x80 up reads as ``{xHH}`` and is written back as it is. The
fonts' half-width katakana cells (codes 0xA1-0xDF) are typed as the Unicode half-width katakana
U+FF61-U+FF9F, so letters drawn on them later can be reached from the editor.
"""
from __future__ import annotations

import re
from typing import Set

DASH = b"\xd0\x06"
TAG_RE = re.compile(r"\{(?:dash|x[0-9A-F]{2})\}")
_TOKEN = re.compile(r"\{(?:dash|x[0-9A-F]{2})\}|.", re.S)


def decode(data: bytes) -> str:
    out = []
    i = 0
    while i < len(data):
        b = data[i]
        if data[i:i + 2] == DASH:
            out.append("{dash}")
            i += 2
            continue
        if b == 0x0A or 0x20 <= b < 0x7F:
            out.append(chr(b))
        elif 0xA1 <= b <= 0xDF:
            out.append(chr(0xFF61 + b - 0xA1))
        else:
            out.append(f"{{x{b:02X}}}")
        i += 1
    return "".join(out)


def encode(text: str, missing: Set[str]) -> bytes:
    """The bytes of ``text``; a character the game cannot write becomes '?' and goes into ``missing``."""
    out = bytearray()
    for token in _TOKEN.findall(text):
        if token == "{dash}":
            out += DASH
        elif len(token) == 5 and token.startswith("{x"):
            out.append(int(token[2:4], 16))
        else:
            code = ord(token)
            if code == 0x0A or 0x20 <= code < 0x7F:
                out.append(code)
            elif 0xFF61 <= code <= 0xFF9F:
                out.append(0xA1 + code - 0xFF61)
            else:
                missing.add(token)
                out.append(0x3F)
    return bytes(out)
