"""Text codec of Silent Hill (PlayStation): the game's bytes as editor text.

The game's strings are plain ASCII with its own control codes (``~N`` line break, ``~E`` end, ``~J0(2.5)``
timing, ``~C2`` colour, ``~S4`` choice). A byte 0x0A is shown as ``\\n`` and a byte 0x09 as ``\\t``; the
underscore is a space in the game and stays as it is. Any other byte is its Latin-1 character.
"""
from __future__ import annotations

import re

NEWLINE = 0x0A
TAB = 0x09
TAG_RE = re.compile(r"~[A-Z](?:\d+(?:\.\d+)?|\(\d+(?:\.\d+)?\))?")


def decode(raw: bytes) -> str:
    out = []
    for byte in raw:
        if byte == NEWLINE:
            out.append("\\n")
        elif byte == TAB:
            out.append("\\t")
        elif byte == 0x5C:               # a backslash is shown as \\ so that \n and \t stay unambiguous
            out.append("\\\\")
        else:
            out.append(chr(byte))
    return "".join(out)


def encode(text: str) -> bytes:
    """Editor text back to bytes; raises ValueError for a character the game's font cannot print."""
    out = bytearray()
    i = 0
    while i < len(text):
        char = text[i]
        if char == "\\" and i + 1 < len(text) and text[i + 1] in "nt\\":
            out.append({"n": NEWLINE, "t": TAB, "\\": 0x5C}[text[i + 1]])
            i += 2
            continue
        code = ord(char)
        if code > 0xFF or code == 0 or char == "\n":
            raise ValueError(f"character {char!r} is not in the game's text")
        out.append(code)
        i += 1
    return bytes(out)
