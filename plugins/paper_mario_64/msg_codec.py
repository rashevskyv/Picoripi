"""Paper Mario (N64) message bytes <-> editor text, byte-exact for unchanged messages.

Source: pmret/papermario ``include/enums.h`` (``MsgChars``, US block), ``src/msg.c`` (``dma_load_msg``).
A message is ``body + 0xFD (end) + zero padding`` to a multiple of four bytes. The editor sees the body
as text. Every byte the table does not name is a tag ``[@hh]``: control codes 0xF0-0xFF with their
arguments, the symbols 0x90-0xA1 and the bracket 0x3B (so a raw ``[`` never appears in the text).
The reader stops at the first 0xFD, as the game does. Argument bytes are kept as plain bytes, so the
round trip is exact without knowing each code's argument count.
"""
from __future__ import annotations

import re
from typing import Dict

END = 0xFD
TAG_RE = re.compile(r"\[@([0-9A-Fa-f]{2})\]")

# Character code -> character, US charset (the glyph of code i is glyph i of gCharsetStandard).
_ASCII = r"!\#$%&'()*+,-./0123456789:;<=>?@"
_ACCENTED_UPPER = "ÀÁÂÄÇÈÉÊËÌÍÎÏÑÒÓÔÖÙÚÛÜ"
_ACCENTED_LOWER = "àáâäçèéêëìíîïñòóôöùúûü"
_LATIN_LOWER = "abcdefghijklmnopqrstuvwxyz"
CHARMAP: Dict[int, str] = {}
for _offset, _char in enumerate(_ASCII, start=0x01):
    CHARMAP[_offset] = _char                  # 0x01-0x20 punctuation, digits, '@'
for _offset, _char in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", start=0x21):
    CHARMAP[_offset] = _char                  # 0x21-0x3A
CHARMAP[0x3C] = "¥"
CHARMAP[0x3D] = "]"
CHARMAP[0x3E] = "^"
CHARMAP[0x3F] = "_"
CHARMAP[0x40] = "`"
for _offset, _char in enumerate(_LATIN_LOWER, start=0x41):
    CHARMAP[_offset] = _char                  # 0x41-0x5A
CHARMAP[0x5B] = "{"
CHARMAP[0x5C] = "|"
CHARMAP[0x5D] = "}"
CHARMAP[0x5E] = "~"
CHARMAP[0x5F] = "°"
for _offset, _char in enumerate(_ACCENTED_UPPER + "ß", start=0x60):
    CHARMAP[_offset] = _char                  # 0x60-0x76
for _offset, _char in enumerate(_ACCENTED_LOWER, start=0x77):
    CHARMAP[_offset] = _char                  # 0x77-0x8C
CHARMAP[0x8D] = "¡"
CHARMAP[0x8E] = "¿"
CHARMAP[0x8F] = "ª"
CHARMAP[0xF7] = " "                           # READ_SPACE: the game's space, so text keeps plain spaces
CHARMAP[0xA2] = "“"
CHARMAP[0xA3] = "”"
CHARMAP[0xA4] = "‘"
CHARMAP[0xA5] = "’"
# Not in the map, so tags: the note 0x00, the bracket 0x3B, the symbols 0x90-0xA1 and the codes 0xF0-0xFF except 0xF7.
_TO_CODE = {char: code for code, char in CHARMAP.items()}


# Argument bytes after a function code (0xFF): the codes the decomp's reader is known to consume. The
# others read as plain bytes; the round trip does not depend on this table, only the text does.
FUNCTION_ARGS = {0x00: 1, 0x01: 1, 0x05: 1, 0x06: 1, 0x09: 1, 0x0A: 1, 0x0B: 1, 0x0C: 1,
                 0x0D: 2, 0x0F: 2, 0x10: 2, 0x11: 1, 0x12: 1, 0x13: 1, 0x14: 1, 0x15: 1, 0x16: 3,
                 0x17: 2, 0x18: 7, 0x19: 1, 0x1A: 3, 0x1B: 2, 0x1C: 1, 0x1D: 2, 0x29: 1}
FUNCTION = 0xFF
ONE_ARG = (0xF2, 0xFC)                        # READ_PAUSE and READ_STYLE: one argument byte


def decode_message(raw: bytes) -> str:
    """Editor text of one message, read as the game reads it up to the end code; tags for every other byte."""
    parts = []
    i = 0
    while i < len(raw) and raw[i] != END:
        byte = raw[i]
        if byte == FUNCTION and i + 1 < len(raw) and raw[i + 1] != END:
            width = 2 + FUNCTION_ARGS.get(raw[i + 1], 0)
        elif byte in ONE_ARG and i + 1 < len(raw) and raw[i + 1] != END:
            width = 2
        else:
            width = 1
        for part in raw[i:i + width]:
            if part == END:                   # an argument never swallows the end code
                return "".join(parts)
            char = CHARMAP.get(part)
            parts.append(char if char is not None and width == 1 else f"[@{part:02X}]")
        i += width
    return "".join(parts)


def encode_message(text: str) -> bytes:
    """Message bytes for editor text: characters and tags, then the end code, padded to four bytes."""
    out = bytearray()
    position = 0
    for match in TAG_RE.finditer(text):
        out += _plain(text[position:match.start()])
        out.append(int(match.group(1), 16))
        position = match.end()
    out += _plain(text[position:])
    out.append(END)
    while len(out) % 4:
        out.append(0)
    return bytes(out)


def _plain(text: str) -> bytes:
    out = bytearray()
    for char in text:
        code = _TO_CODE.get(char)
        if code is None:
            raise ValueError(f"the game's font has no {char!r}")
        out.append(code)
    return bytes(out)
