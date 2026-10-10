"""Text codec of Silent Hill 3 (PC, English messages): the game's glyph bytes as editor text.

Each glyph byte is the ASCII code minus 0x20: 0x00 is a space, 0x0E a full stop, 0x21-0x3A are the
capitals, 0x41-0x5A the small letters, 0x10-0x19 the digits. The bytes 0x3C, 0x5B and 0x5D (a backslash,
a brace) and every byte from 0x5F up are shown as a tag ``{XX}`` (two hex digits), so a tag never
looks like text and every byte has one visible form.

A message keeps the position of its marker bytes: a space before 0x80 (message start), 0x90 (message
end) or 0x10 (page break) must sit at an even offset of the message; ``align`` adds a zero byte where
needed.
"""
from __future__ import annotations

import re

TAG_BYTES = frozenset({0x3C, 0x5B, 0x5D})
MARKER_BYTES = frozenset({0x80, 0x90, 0x10})
SPACE = 0x00
TAG_RE = re.compile(r"\{([0-9A-F]{2})\}")
_TOKEN_RE = re.compile(r"\{[0-9A-F]{2}\}|.", re.DOTALL)


def _is_text(byte: int) -> bool:
    return byte < 0x5F and byte not in TAG_BYTES


def decode(raw: bytes) -> str:
    return "".join(chr(byte + 0x20) if _is_text(byte) else "{%02X}" % byte for byte in raw)


def encode(text: str) -> bytes:
    """Editor text back to glyph bytes; raises ValueError for a character the game's font has no glyph for."""
    out = bytearray()
    for token in _TOKEN_RE.findall(text):
        tag = TAG_RE.fullmatch(token)
        if tag is not None:
            out.append(int(tag.group(1), 16))
            continue
        code = ord(token)
        if not 0x20 <= code <= 0x7E or (code - 0x20) in TAG_BYTES:
            raise ValueError(f"character {token!r} has no glyph in the English font")
        out.append(code - 0x20)
    return align(bytes(out))


def align(body: bytes) -> bytes:
    """Insert a zero byte before a marker's space when that space would sit at an odd offset."""
    out = bytearray()
    for byte in body:
        if byte in MARKER_BYTES and out and out[-1] == SPACE and (len(out) - 1) % 2:
            out.insert(len(out) - 1, SPACE)
        out.append(byte)
    return bytes(out)
