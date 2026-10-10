"""``ContentInfoArchive_EUR_*.bin`` of Strange Journey Redux's DLC: the titles and descriptions of the add-on content.

Little endian: u32 1, u32 count, then ``count + 1`` entries of 0xC8 bytes from offset 8: a title (0x40 bytes) and a
description (0x88 bytes), both NUL-padded ASCII; entry 0 is a ``Dummy`` pair. The header and the entry order stay;
a text must fit its field (63 / 135 bytes).
"""
from __future__ import annotations

import struct
from typing import List, Sequence

from .mbm import FormatError

ENTRY, TITLE, HEAD = 0xC8, 0x40, 8


def is_info(raw: bytes) -> bool:
    if len(raw) < HEAD + ENTRY or struct.unpack_from("<I", raw, 0)[0] != 1:
        return False
    return len(raw) == HEAD + ENTRY * (struct.unpack_from("<I", raw, 4)[0] + 1)


def _field(raw: bytes, at: int, size: int) -> str:
    return raw[at:at + size].split(b"\0", 1)[0].decode("ascii", "replace")


def texts(raw: bytes) -> List[str]:
    """Title and description of every entry, one after another."""
    if not is_info(raw):
        raise FormatError("not a ContentInfoArchive")
    out: List[str] = []
    for at in range(HEAD, len(raw), ENTRY):
        out += [_field(raw, at, TITLE), _field(raw, at + TITLE, ENTRY - TITLE)]
    return out


def build(raw: bytes, new_texts: Sequence[str]) -> bytes:
    old = texts(raw)
    if len(new_texts) != len(old):
        raise FormatError(f"{len(new_texts)} strings for {len(old)} fields")
    out = bytearray(raw)
    for i, (text, was) in enumerate(zip(new_texts, old)):
        if str(text) == was:
            continue
        at = HEAD + i // 2 * ENTRY + (i % 2) * TITLE
        size = TITLE if i % 2 == 0 else ENTRY - TITLE
        try:
            blob = str(text).encode("ascii")
        except UnicodeEncodeError:
            raise FormatError(f"{text!r}: the field takes ASCII only") from None
        if len(blob) >= size:
            raise FormatError(f"{text!r} needs {len(blob)} bytes, the field has {size - 1}")
        out[at:at + size] = blob.ljust(size, b"\0")
    return bytes(out)
