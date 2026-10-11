"""Metal Gear 1/2 Master Collection english.raw: lossless split into strings and raw bytes.

Only the split is decoded. A NUL-terminated run of 4 or more printable bytes is a string; every other
byte stays raw. Record headers (00 00 LEN, and 00 00 hi lo 00 01 f8) are not decoded yet, so some
runs are noise (for example "yyyy" tables). join() restores the input byte for byte.

ponytail: split only, skipped: record grammar and pointers, add when the header fields are decoded.
"""
from __future__ import annotations

import re
from typing import List, Tuple

_STRING = re.compile(rb"[\x20-\x7e\n]{4,}\x00")


def split(data: bytes) -> List[Tuple[bool, bytes]]:
    """(is_string, bytes) chunks. A string chunk holds its text and its NUL terminator."""
    chunks: List[Tuple[bool, bytes]] = []
    pos = 0
    for m in _STRING.finditer(data):
        if m.start() > pos:
            chunks.append((False, data[pos:m.start()]))
        chunks.append((True, m.group()))
        pos = m.end()
    if pos < len(data):
        chunks.append((False, data[pos:]))
    return chunks


def join(chunks: List[Tuple[bool, bytes]]) -> bytes:
    return b"".join(chunk for _, chunk in chunks)
