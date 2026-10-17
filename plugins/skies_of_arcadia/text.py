"""The text of a Skies of Arcadia Legends script page as the editor shows it, and back.

Each byte is one character in the editor, so a byte count and a character count agree:

- printable ASCII (0x21 to 0x7e) is itself, except backslash and left brace;
- the space is byte 0x7f;
- the pair 0x5c 0x6e (backslash, n) is one line break, shown as ``\n``;
- every other byte is a token ``{xx}`` (two lowercase hex digits), so the editor's tag checks see it as a tag.

``decode`` and ``encode`` are exact inverses for every byte string: ``encode(decode(b)) == b``. A character the game
has no byte for (for example a Ukrainian letter) is written as ``?`` and reported in the set ``encode`` returns.
"""
from __future__ import annotations

import re
from typing import Set, Tuple

SPACE = 0x7F
NEWLINE = b"\x5c\x6e"
QUESTION = 0x3F
_HEX_TOKEN = re.compile(r"\{([0-9a-f]{2})\}")
TOKENS = frozenset(f"{{{b:02x}}}" for b in range(256))   # the tags the editor's tag checks accept


def _char_of(byte: int) -> str:
    if byte == SPACE:
        return " "
    if 0x21 <= byte <= 0x7E and byte not in (0x5C, 0x7B):
        return chr(byte)
    return f"{{{byte:02x}}}"


def decode(data: bytes) -> str:
    out = []
    i = 0
    while i < len(data):
        if data[i:i + 2] == NEWLINE:
            out.append("\\n")
            i += 2
            continue
        out.append(_char_of(data[i]))
        i += 1
    return "".join(out)


def encode(text: str) -> Tuple[bytes, Set[str]]:
    """The bytes of one editor text and the characters that have no byte (written as ``?``)."""
    out = bytearray()
    missing: Set[str] = set()
    i = 0
    while i < len(text):
        ch = text[i]
        if text.startswith("\\n", i):
            out += NEWLINE
            i += 2
            continue
        if ch == "\n":   # a real line feed from the editor is the same line break
            out += NEWLINE
            i += 1
            continue
        if ch == "{":
            match = _HEX_TOKEN.match(text, i)
            if match:
                out.append(int(match.group(1), 16))
                i = match.end()
                continue
        if ch == " ":
            out.append(SPACE)
        elif 0x21 <= ord(ch) <= 0x7E:
            out.append(ord(ch))   # backslash and left brace without a token: their own bytes
        else:
            missing.add(ch)
            out.append(QUESTION)
        i += 1
    return bytes(out), missing
