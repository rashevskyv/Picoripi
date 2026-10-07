"""Replace byte ranges inside nested size-prefixed structures and fix every size on the way.

A parser records each size field it reads (``Field``: where it is, how wide, big endian, and the
byte range whose length it counts, minus ``bias``); ``rewrite`` splices the new bytes in and adds
to each field the change in length of the edits inside its range.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple


class SizeError(ValueError):
    """A size no longer fits its field (an option or string grew past 255 bytes)."""


@dataclass(frozen=True)
class Field:
    pos: int
    width: int          # 1, 2 or 4 bytes, big endian
    start: int          # the counted range
    end: int
    wrap: bool = False  # the game keeps only the low bits (a GCL option longer than 255 bytes)


Edit = Tuple[int, int, bytes]           # (start, end, new bytes)


def rewrite(data: bytes, fields: Iterable[Field], edits: Iterable[Edit]) -> bytes:
    """``data`` with ``edits`` applied (non-overlapping, never touching a field) and fields fixed."""
    edits = sorted((s, e, bytes(b)) for s, e, b in edits if data[s:e] != b)
    if not edits:
        return bytes(data)
    out = bytearray()
    shifts: List[Tuple[int, int]] = []      # (old end of edit, running delta after it)
    pos = delta = 0
    for start, end, new in edits:
        out += data[pos:start]
        out += new
        delta += len(new) - (end - start)
        shifts.append((end, delta))
        pos = end
    out += data[pos:]

    def moved(at: int) -> int:
        shift = 0
        for end, running in shifts:
            if end <= at:
                shift = running
            else:
                break
        return at + shift

    for field in fields:
        grow = sum(len(new) - (e - s) for s, e, new in edits if field.start <= s and e <= field.end)
        if not grow:
            continue
        at = moved(field.pos)
        old = int.from_bytes(out[at:at + field.width], "big")
        value = old + grow
        if field.wrap:
            value %= 1 << (8 * field.width)
        if not 0 <= value < 1 << (8 * field.width):
            raise SizeError(f"a {field.width}-byte size at {field.pos:#x} would be {value}")
        out[at:at + field.width] = value.to_bytes(field.width, "big")
    return bytes(out)
