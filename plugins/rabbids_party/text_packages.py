"""Text of Rayman Raving Rabbids TV Party (Jade engine, Montreal): ``TextPackages.bin`` of the bigfile.

Little endian: u32 language count (9), u32 row count, then per row an id and one string per language, each a
u16 byte length and UTF-16LE text with its NUL. The columns: 0 English (Europe), 1 French, 2 Spanish, 3 Italian,
4 German, 5 Dutch, 6 Japanese, 7 English (USA), 8 empty. The game shows column 0 to an English player; the
plugin edits it and keeps every other byte. Rich text: ``<font color='#FFCC00'>...</font>``.
"""
from __future__ import annotations

import struct
from typing import List, Tuple

ENGLISH = 0
TAG_PATTERN = r"</?font[^>]*>|</?[biu]>|<br\s*/?>|%[0-9]*[dsf]"


def _string(raw: bytes, at: int) -> Tuple[str, int]:
    size = struct.unpack_from("<H", raw, at)[0]
    return bytes(raw[at + 2:at + 2 + size]).decode("utf-16-le"), at + 2 + size


def is_text_packages(raw: bytes) -> bool:
    if len(raw) < 12:
        return False
    langs, rows = struct.unpack_from("<II", raw)
    if not (1 <= langs <= 32 and 0 < rows < 100000):
        return False
    try:
        ident, _at = _string(raw, 8)
    except (UnicodeDecodeError, struct.error):
        return False
    return ident.startswith("ID_")


def rows(raw: bytes) -> List[Tuple[str, List[str]]]:
    """``[(id, [string per language])]`` without the NULs."""
    langs, count = struct.unpack_from("<II", raw)
    at, out = 8, []
    for _ in range(count):
        ident, at = _string(raw, at)
        values = []
        for _ in range(langs):
            value, at = _string(raw, at)
            values.append(value.rstrip("\0"))
        out.append((ident.rstrip("\0"), values))
    if at != len(raw):
        raise ValueError("TextPackages.bin: unexpected bytes after the last row")
    return out


def build(raw: bytes, english: List[str]) -> bytes:
    """``raw`` with column 0 replaced; every other string keeps its bytes."""
    langs, count = struct.unpack_from("<II", raw)
    if len(english) != count:
        raise ValueError(f"TextPackages.bin has {count} rows, the project {len(english)}")
    out, at = bytearray(raw[:8]), 8
    for row in range(count):
        _ident, end = _string(raw, at)
        out += raw[at:end]
        at = end
        for lang in range(langs):
            value, end = _string(raw, at)
            if lang == ENGLISH and english[row] != value.rstrip("\0"):
                data = (english[row] + "\0").encode("utf-16-le")
                out += struct.pack("<H", len(data)) + data
            else:
                out += raw[at:end]
            at = end
    return bytes(out)
