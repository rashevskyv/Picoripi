"""Black & White text table (Scripts/InfoScript2.txt): read the ADD_TEXT strings and write translated ones back.

The file is UTF-16 LE with a byte order mark and CRLF lines. Each line is one call::

    ADD_TEXT( <flag>, <NARRATOR_ENUM>, "<KEY>", "<text>")

The text number of a line is its place in the file (RUN_TEXT numbers count the same order). A text may hold a bare
line feed, and the game's own line breaks are the two characters backslash and n. Saving splices only the text
literals into the source bytes, so every other byte of the file stays as it was.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Sequence

BOM = "﻿"
_RECORD = re.compile(r'ADD_TEXT\(\s*(\d+),\s*(\w+),\s*"([^"]*)",\s*"([^"]*)"\)', re.S)


@dataclass(frozen=True)
class TextRecord:
    """One ADD_TEXT call: the fields the game reads, and the text a translator edits."""

    flag: str
    narrator: str
    key: str
    text: str


class InfoScriptError(ValueError):
    """The bytes are not a text table this module can read or write."""


def _decode(raw: bytes) -> tuple[str, bool]:
    """(text without the byte order mark, whether the file had one)."""
    if raw[:2] == b"\xff\xfe":
        return raw[2:].decode("utf-16-le"), True
    if raw[:2] == b"\xfe\xff":
        return raw[2:].decode("utf-16-be"), True
    return raw.decode("utf-16-le"), False


def _encode(text: str, bom: bool) -> bytes:
    return ((BOM if bom else "") + text).encode("utf-16-le")


def records(raw: bytes) -> List[TextRecord]:
    """Every ADD_TEXT call of the file, in file order."""
    text, _ = _decode(raw)
    return [TextRecord(m.group(1), m.group(2), m.group(3), m.group(4)) for m in _RECORD.finditer(text)]


def texts(raw: bytes) -> List[str]:
    """The text of each ADD_TEXT call, in file order (the strings a translator sees)."""
    return [record.text for record in records(raw)]


def replace_texts(template: bytes, new_texts: Sequence[str]) -> bytes:
    """``template`` with the text of each ADD_TEXT call replaced by ``new_texts`` (same count, same order).

    Only the text literal changes. A text may not hold a double quote: the game reads the quote as the end of the
    literal.
    """
    decoded, bom = _decode(template)
    spans = [m.span(4) for m in _RECORD.finditer(decoded)]
    if len(spans) != len(new_texts):
        raise InfoScriptError(f"{len(new_texts)} texts for {len(spans)} ADD_TEXT calls")
    for index, value in enumerate(new_texts):
        if '"' in value:
            raise InfoScriptError(f"text {index} holds a double quote, which ends the literal in the game")
    pieces: List[str] = []
    cursor = 0
    for (start, end), value in zip(spans, new_texts):
        pieces.append(decoded[cursor:start])
        pieces.append(value)
        cursor = end
    pieces.append(decoded[cursor:])
    return _encode("".join(pieces), bom)


def keys(raw: bytes) -> List[str]:
    """The key of each ADD_TEXT call, in file order."""
    return [record.key for record in records(raw)]


def looks_like_table(raw: bytes) -> bool:
    """Whether the start of ``raw`` holds an ADD_TEXT call (a cheap content check for file recognition)."""
    try:
        head, _ = _decode(raw[:8192])
    except UnicodeDecodeError:
        return False
    return "ADD_TEXT(" in head
