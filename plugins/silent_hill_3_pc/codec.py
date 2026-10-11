"""Text codec of Silent Hill 3 (PC, English messages): the game's glyph bytes as editor text.

Each glyph byte is the ASCII code minus 0x20: 0x00 is a space, 0x0E a full stop, 0x21-0x3A are the
capitals, 0x41-0x5A the small letters, 0x10-0x19 the digits. The bytes 0x3C, 0x5B and 0x5D (a backslash,
a brace) and every byte from 0x5F up are shown as a tag ``{XX}`` (two hex digits), so a tag never
looks like text and every byte has one visible form.

Three control bytes are also a text byte, so they need a context: a page break is ``00 10 00 80``
(a space, 0x10, a space, the message-start marker). Its 0x10 is shown as the tag ``{10}``. Every other
0x10 is the digit zero. The message-start marker 0x80, the message-end marker 0x90 and the page break
0x10 each follow a space (0x00), and that space must sit at an even offset of the message. ``encode``
adds a zero byte before such a space when it would sit at an odd offset. A typed digit zero never adds one.
"""
from __future__ import annotations

import re
from typing import List, Tuple

TAG_BYTES = frozenset({0x3C, 0x5B, 0x5D})
MARKER_BYTES = frozenset({0x80, 0x90, 0x10})
PAGE_BREAK = 0x10
MESSAGE_START = b"\x00\x80"
SPACE = 0x00
TAG_RE = re.compile(r"\{([0-9A-F]{2})\}")
_TOKEN_RE = re.compile(r"\{[0-9A-F]{2}\}|.", re.DOTALL)


def _is_text(byte: int) -> bool:
    return byte < 0x5F and byte not in TAG_BYTES


def _is_page_break(raw: bytes, index: int) -> bool:
    """A 0x10 is a page break when a space at an even offset comes before it and the message start after it."""
    return (raw[index] == PAGE_BREAK and index >= 1 and raw[index - 1] == SPACE and (index - 1) % 2 == 0
            and raw[index + 1:index + 3] == MESSAGE_START)


def decode(raw: bytes) -> str:
    out: List[str] = []
    for index, byte in enumerate(raw):
        if byte == PAGE_BREAK and _is_page_break(raw, index):
            out.append("{10}")
        elif _is_text(byte):
            out.append(chr(byte + 0x20))
        else:
            out.append("{%02X}" % byte)
    return "".join(out)


def encode(text: str) -> bytes:
    """Editor text back to glyph bytes; raises ValueError for a character the game's font has no glyph for."""
    pieces: List[Tuple[int, bool]] = []          # (byte, is a marker tag)
    for token in _TOKEN_RE.findall(text):
        tag = TAG_RE.fullmatch(token)
        if tag is not None:
            value = int(tag.group(1), 16)
            pieces.append((value, value in MARKER_BYTES))
            continue
        code = ord(token)
        if not 0x20 <= code <= 0x7E or (code - 0x20) in TAG_BYTES:
            raise ValueError(f"character {token!r} has no glyph in the English font")
        pieces.append((code - 0x20, False))
    return align(pieces)


def align(pieces: List[Tuple[int, bool]]) -> bytes:
    """The bytes of the pieces; a zero byte goes before a marker's space when that space is at an odd offset."""
    out = bytearray()
    for byte, marker in pieces:
        if marker and out and out[-1] == SPACE and (len(out) - 1) % 2:
            out.insert(len(out) - 1, SPACE)
        out.append(byte)
    return bytes(out)
