"""Shift-JIS strings inside the game's executable (``exefs/code.bin``): skill, place and menu names.

A string is a NUL-terminated run of full-width Shift-JIS characters and ``F8xx`` codes (the same form as the
``.mbm`` strings, without the ``FFFF`` end). The strings are found by scanning; an edit is written in place and
must fit the room the string has (its own bytes), the rest is NUL-padded.
"""
from __future__ import annotations

import re
from typing import List, Sequence, Tuple

from . import mbm

_RUN = re.compile(rb"(?:\x81[\x40-\x9f]|\x82[\x4f-\x9a]|\x83[\x40-\x96]|\x84[\x40-\x99]|\xf8[\x00-\xff](?:[\x00-\x7f]\x00)?){2,}(?=\x00)")


class FormatError(ValueError):
    pass


def strings(data: bytes) -> List[Tuple[int, int]]:
    """``(offset, size)`` of every string."""
    return [(m.start(), len(m.group())) for m in _RUN.finditer(data)]


def texts(data: bytes) -> List[str]:
    return [mbm.decode(data[at:at + size]) for at, size in strings(data)]


def build(data: bytes, new_texts: Sequence[str]) -> bytes:
    found = strings(data)
    if len(new_texts) != len(found):
        raise FormatError(f"{len(new_texts)} strings for {len(found)} in the executable")
    out = bytearray(data)
    for (at, size), text in zip(found, new_texts):
        old = mbm.decode(data[at:at + size])
        if str(text) == old:
            continue
        blob = mbm.encode(str(text))[:-2]   # no FFFF in the executable
        if len(blob) > size:
            raise FormatError(f"'{text}' needs {len(blob)} bytes, the executable has {size} at {at:#x}")
        out[at:at + size] = blob + bytes(size - len(blob))
    return bytes(out)
