"""The World Ends with You (DS) text: ``Apl_Fuk/mestxt.bin`` and its index ``mestable.bin``.

``mestxt.bin`` is every message of the game back to back, u16 little endian codes, each message ending with
``FFFF``; one zero code ends the file. ``mestable.bin`` is ``(u32 offset, u32 byte length)`` per
message, in file order, so it is made again from ``mestxt.bin`` (``table``); the build script does that.

Codes: below ``0xFF00`` a code is a glyph of the text font (``core.font_formats.twewy.CHARACTERS``: 0x00-0x5E
are ASCII, then Japanese, symbols, accented Latin, button pictures); ``FFFE`` breaks the line. Editor form:
a line break is ``\\n``; a glyph without a character is ``[g:XXX]``; the other codes are tags:

  ``[color:1]`` ``FFB6`` character names, headings     ``[color:2]`` ``FFB8`` shop notices
  ``[color:3]`` ``FFBA`` pin names, credits headings    ``[color:4]`` ``FFBC`` key words (the usual highlight)
  ``[/color]``  ``FFBE`` back to the normal colour      ``[num]``     ``FFD0`` a number the game fills in
  ``[value]``   ``FFD1`` a signed value (pin stats)     ``[name]``    ``FFD2`` an item or pin name the game fills in
  ``[c:FFxx]``  any other control code
"""
from __future__ import annotations

import re
import struct
from typing import Dict, List

from core.font_formats.twewy import CHARACTERS

END, NEWLINE = 0xFFFF, 0xFFFE
TAIL = bytes(2)                  # the zero code after the last message
TAGS: Dict[int, str] = {0xFFB6: "[color:1]", 0xFFB8: "[color:2]", 0xFFBA: "[color:3]", 0xFFBC: "[color:4]",
                        0xFFBE: "[/color]", 0xFFD0: "[num]", 0xFFD1: "[value]", 0xFFD2: "[name]"}
CODES = {tag: code for code, tag in TAGS.items()}
CHAR_CODES = {char: code for code, char in CHARACTERS.items()}
TAG_RE = re.compile(r"\[(?:color:[1-4]|/color|num|value|name|g:[0-9A-Fa-f]{1,3}|c:FF[0-9A-Fa-f]{2})\]")
DESCRIPTIONS = {"[color:1]": "Colour 1 (character names, headings)", "[color:2]": "Colour 2 (shop notices)",
                "[color:3]": "Colour 3 (pin names, credits headings)", "[color:4]": "Colour 4 (key words)",
                "[/color]": "Back to the normal colour", "[num]": "A number the game fills in",
                "[value]": "A signed value the game fills in (pin stats)",
                "[name]": "An item or pin name the game fills in"}


class FormatError(ValueError):
    """The bytes are not a TWEWY message file, or a text cannot be encoded."""


def split(data: bytes) -> List[bytes]:
    """The messages of ``mestxt.bin`` (each with its ``FFFF``)."""
    if len(data) < 2 or len(data) % 2:
        raise FormatError("mestxt.bin must be a whole number of u16 codes")
    codes = struct.unpack_from(f"<{len(data) // 2}H", data)
    out, start = [], 0
    for index, code in enumerate(codes):
        if code == END:
            out.append(bytes(data[2 * start:2 * index + 2]))
            start = index + 1
    if not out or len(codes) - start != len(TAIL) // 2 or any(codes[start:]):
        raise FormatError("not a TWEWY message file (it must end with FFFF and one zero code)")
    if any(0x1000 <= code < 0xFF00 for code in codes):
        raise FormatError("not a TWEWY message file (codes beyond the font)")
    return out


def join(messages: List[bytes]) -> bytes:
    return b"".join(messages) + TAIL


def table(data: bytes) -> bytes:
    """``mestable.bin`` for ``mestxt.bin``."""
    out, at = bytearray(), 0
    for message in split(data):
        out += struct.pack("<II", at, len(message))
        at += len(message)
    return bytes(out)


def to_editor(message: bytes) -> str:
    parts: List[str] = []
    for (code,) in struct.iter_unpack("<H", message):
        if code == END:
            break
        if code == NEWLINE:
            parts.append("\n")
        elif code in TAGS:
            parts.append(TAGS[code])
        elif code >= 0xFF00:
            parts.append(f"[c:{code:04X}]")
        else:
            parts.append(CHARACTERS.get(code) or f"[g:{code:X}]")
    return "".join(parts)


def from_editor(text: str) -> bytes:
    codes: List[int] = []
    text = str(text).replace("\r\n", "\n")
    at = 0
    for match in list(TAG_RE.finditer(text)) + [None]:
        chunk = text[at:match.start() if match else len(text)]
        for char in chunk:
            if char == "\n":
                codes.append(NEWLINE)
            elif char in CHAR_CODES:
                codes.append(CHAR_CODES[char])
            else:
                raise FormatError(f"The game's font has no character {char!r} (U+{ord(char):04X})")
        if match is None:
            break
        tag = match.group()
        codes.append(CODES[tag] if tag in CODES else int(tag[3:-1], 16))
        at = match.end()
    codes.append(END)
    return struct.pack(f"<{len(codes)}H", *codes)


def describe(tag: str) -> str:
    """A tooltip for a tag, or "" for text that is not one."""
    if not TAG_RE.fullmatch(tag):
        return ""
    if tag.startswith("[g:"):
        return f"Glyph {tag[3:-1].upper()} of the text font (a picture or a character with no name here)"
    if tag.startswith("[c:"):
        return f"Control code {tag[3:-1].upper()} (meaning unknown)"
    return DESCRIPTIONS[tag]
