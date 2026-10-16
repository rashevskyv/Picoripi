"""Metal Gear 1/2 Master Collection english.raw: lossless split into strings and raw bytes.

Only the split is decoded. A NUL-terminated run of 4 or more printable bytes is a string; every other
byte stays raw. Record headers (00 00 LEN, and 00 00 hi lo 00 01 f8) are not decoded yet, so some
runs are noise (for example "yyyy" tables). join() restores the input byte for byte.

ponytail: split only, skipped: record grammar and pointers, add when the header fields are decoded.

MG1 dialogue (dialogue_split): records of [flag u8][length u16 BE][text of length bytes], no terminator. The
walk starts at DIALOGUE_START and finds the next record by its header and its text (printable bytes plus
high bytes, one word of 3 letters). Bytes between records (binary tables, 4-byte tails, one 3.4 KB table)
stay raw. The pointers into this file are not found yet, so an edit that changes a length is not proven
to boot.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

_STRING = re.compile(rb"[\x20-\x7e\n]{4,}\x00")

DIALOGUE_START = 0x1594A5   # MG1 english.raw: first dialogue record (flag 00, length 0x01F8)
_TEXT_OK = bytes(range(0x20, 0x100)) + b"\n"
_WORD = re.compile(rb"[A-Za-z]{3,}")
_FLAG_MAX = 9
_LENGTH_MAX = 1000
_GAP_WINDOW = 4096


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
    if pos + 3 > len(data) or data[pos] > _FLAG_MAX:
        return None
    length = (data[pos + 1] << 8) | data[pos + 2]
    if not 1 <= length <= _LENGTH_MAX or pos + 3 + length > len(data):
        return None
    text = data[pos + 3:pos + 3 + length]
    if text.translate(None, _TEXT_OK) or not _WORD.search(text):
        return None
    return length


def _next_record(data: bytes, pos: int) -> Optional[int]:
    for candidate in range(pos, min(len(data), pos + _GAP_WINDOW)):
        if _record_length(data, candidate) is not None:
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
        length = _record_length(data, pos)
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
