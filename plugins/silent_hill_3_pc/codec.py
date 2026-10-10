"""Text codec of Silent Hill 3 (PC, English messages): the game's glyph bytes as editor text.

The English messages hold one byte per glyph. The bytes 0x00, 0x07, 0x0C, 0x0E and 0x1F are a space,
an apostrophe, a comma, a full stop and a question mark. The letters A to Z are read from two glyph sets,
0x21-0x3A and 0x41-0x5A; a letter written back always uses 0x41-0x5A. Every other byte (control codes,
the start and end markers of a message) is shown as a tag ``{XX}`` (two hex digits), so every byte has
one visible form and a message without edits gives back its own bytes.
"""
from __future__ import annotations

import re

SPACE = 0x00
PUNCTUATION = {0x00: " ", 0x07: "'", 0x0C: ",", 0x0E: ".", 0x1F: "?"}
TAG_RE = re.compile(r"\{([0-9A-F]{2})\}")
_TOKEN_RE = re.compile(r"\{[0-9A-F]{2}\}|.", re.DOTALL)


def _letter(byte: int) -> str | None:
    if 0x21 <= byte <= 0x3A or 0x41 <= byte <= 0x5A:
        return chr(ord("A") + (byte - 0x21) % 0x20)
    return None


def _glyph_byte(char: str) -> int | None:
    for byte, shown in PUNCTUATION.items():
        if shown == char:
            return byte
    if "A" <= char <= "Z":
        return 0x41 + ord(char) - ord("A")
    return None


def decode(raw: bytes) -> str:
    out = []
    for byte in raw:
        shown = PUNCTUATION.get(byte) or _letter(byte)
        out.append(shown if shown is not None else "{%02X}" % byte)
    return "".join(out)


def encode(text: str) -> bytes:
    """Editor text back to glyph bytes; raises ValueError for a character the game's font has no glyph for."""
    out = bytearray()
    for token in _TOKEN_RE.findall(text):
        tag = TAG_RE.fullmatch(token)
        if tag is not None:
            out.append(int(tag.group(1), 16))
            continue
        byte = _glyph_byte(token)
        if byte is None:
            raise ValueError(f"character {token!r} has no glyph in the English font")
        out.append(byte)
    return bytes(out)
