"""Metal Gear 1/2 Master Collection english.raw: lossless split into strings and raw bytes.

Only the split is decoded. A NUL-terminated run of 4 or more printable bytes is a string; every other
byte stays raw. Record headers (00 00 LEN, and 00 00 hi lo 00 01 f8) are not decoded yet, so some
runs are noise (for example "yyyy" tables). join() restores the input byte for byte.

ponytail: split only, skipped: record grammar and pointers, add when the header fields are decoded.

MG1 dialogue (dialogue_split): records of [flag u8][length u16 BE][text of length bytes], no terminator. The
walk starts at DIALOGUE_START. A candidate counts when its text has 3 letters and no NUL, and the next two
records follow it within 4 raw bytes. This finds 269 records (14,240 text bytes) in the install file. Other
records sit in gaps the walk does not decode (about 4 KB of binary table and a few short records). Bytes
between records stay raw. No pointer table is found, so an edit that changes a length is not proven to boot.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

_STRING = re.compile(rb"[\x20-\x7e\n]{4,}\x00")

DIALOGUE_START = 0x1594A5   # MG1 english.raw: first dialogue record (flag 00, length 0x01F8)
_LETTERS = re.compile(rb"[A-Za-z]{3,}")
_LENGTH_MAX = 4096
_GAP_WINDOW = 4096
_TAIL_MAX = 4      # raw bytes allowed between two records
_LOOKAHEAD = 2     # records that must follow a candidate for it to count


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


def _record_length(data: bytes, pos: int) -> Optional[int]:
    """Text length of a dialogue record at pos, or None when no record starts there."""
    if pos + 3 > len(data):
        return None
    length = (data[pos + 1] << 8) | data[pos + 2]
    if not 1 <= length <= _LENGTH_MAX or pos + 3 + length > len(data):
        return None
    text = data[pos + 3:pos + 3 + length]
    if b"\x00" in text or not _LETTERS.search(text):
        return None
    return length


def _chain_ok(data: bytes, pos: int, depth: int) -> bool:
    """True when a record starts at pos and the next depth records follow it (small gaps allowed)."""
    length = _record_length(data, pos)
    if length is None:
        return False
    nxt = pos + 3 + length
    if depth == 0 or nxt + 3 > len(data):
        return True
    return any(_chain_ok(data, nxt + gap, depth - 1) for gap in range(_TAIL_MAX + 1))


def _next_record(data: bytes, pos: int) -> Optional[int]:
    for candidate in range(pos, min(len(data), pos + _GAP_WINDOW)):
        if _chain_ok(data, candidate, _LOOKAHEAD):
            return candidate
    return None


def dialogue_split(data: bytes, start: int = DIALOGUE_START) -> List[Tuple[bool, bytes]]:
    """(is_record, bytes) chunks: a record chunk holds its header and its text, every other byte is raw.

    join() restores the input byte for byte. Bytes before start are raw.
    """
    chunks: List[Tuple[bool, bytes]] = []
    end = 0
    pos = start
    while pos < len(data):
        length = _record_length(data, pos) if _chain_ok(data, pos, _LOOKAHEAD) else None
        if length is None:
            pos = _next_record(data, pos + 1)
            if pos is None:
                break
            continue
        if end < pos:
            chunks.append((False, data[end:pos]))
        chunks.append((True, data[pos:pos + 3 + length]))
        pos = end = pos + 3 + length
    if end < len(data):
        chunks.append((False, data[end:]))
    return chunks


def dialogue_text(chunk: bytes) -> bytes:
    """The text of a record chunk from dialogue_split()."""
    return chunk[3:]
