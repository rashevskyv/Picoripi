"""Dragon Quest IX (DS) text tables: the two string-pool formats of the English GPC2 members.

``cfg`` (``*.bin``: NPC talk, events, menus): u32 entry count, u32 pool offset, u32 pool size, u32 string count,
then the entries -- u16 id, u8 argument count, one type byte per four arguments (two bits each, low first:
0 string, 1 integer, 2 float), padding to 4, u32 arguments -- then 0xFF up to the pool of NUL-terminated strings
(0xFF after it up to 16). A string argument is an offset in the pool (0xFFFFFFFF = none).

``nat`` (``*.nat``: item, monster, spell names and descriptions): u32 ``pool size << 12 | record count``, fixed-size
records, then the pool. ``nat`` with bit 31 set (the item data tables): u32 flags, u32 0, u32 pool size, then the
records and further tables. The pointer fields are not marked: a 4-aligned u32 field of the table area is a
pointer when it and every field of the same column (stride ``record size``) is the start of a pool string or
0xFFFFFFFF, and the column has at least one non-zero start (checked against all five languages of the game).

Building writes the strings in their old order (shared strings stay shared) and moves the pointers; an unchanged
table gives its old bytes. Text: the pool bytes are ASCII with ``<tags>``; the editor shows the game's two-char
``\\n`` as a line break.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

NONE = 0xFFFFFFFF
NATX_RECORD = 32          # the record size of the first table of an item data table (``natx``)


class FormatError(ValueError):
    pass


def _starts(pool: bytes) -> List[int]:
    out, at = [], 0
    for piece in pool.split(b"\0")[:-1]:
        out.append(at)
        at += len(piece) + 1
    return out


@dataclass
class Table:
    """A parsed table: ``strings`` (pool order) and where the pool and the pointers are."""

    kind: str
    raw: bytes
    pool_at: int
    pool_end: int
    strings: List[bytes]
    pointers: List[int] = field(default_factory=list)       # byte offsets of the u32 pointer fields

    def _pool(self, strings: List[bytes]) -> Tuple[bytes, Dict[int, int]]:
        old = _starts(self.raw[self.pool_at:self.pool_end])
        pool, moved = bytearray(), {}
        for start, text in zip(old, strings):
            moved[start] = len(pool)
            pool += bytes(text) + b"\0"
        return bytes(pool), moved

    def build(self, strings: Optional[List[bytes]] = None) -> bytes:
        strings = self.strings if strings is None else strings
        if list(strings) == self.strings:
            return self.raw
        if any(b"\0" in s for s in strings):
            raise FormatError("A string cannot hold a NUL byte")
        pool, moved = self._pool(strings)
        head = bytearray(self.raw[:self.pool_at])
        for at in self.pointers:
            value = struct.unpack_from("<I", head, at)[0]
            if value != NONE:
                struct.pack_into("<I", head, at, moved[value])
        if self.kind == "cfg":
            struct.pack_into("<I", head, 8, len(pool))
            out = bytes(head) + pool
            return out + b"\xff" * (-len(out) % 16)
        if self.kind == "nat":
            if len(pool) >= 1 << 20:
                raise FormatError("The table's text is too long")
            count = struct.unpack_from("<I", head, 0)[0] & 0xFFF
            struct.pack_into("<I", head, 0, len(pool) << 12 | count)
        elif self.kind == "natl":
            if len(pool) > 0xFFFF:
                raise FormatError("The table's text is too long")
            struct.pack_into("<H", head, 8, len(pool))
        else:                                            # natx
            struct.pack_into("<I", head, 8, len(pool))
        return bytes(head) + pool


def parse_cfg(data: bytes) -> Table:
    data = bytes(data)
    if len(data) < 16:
        raise FormatError("too short")
    count, pool_at, pool_size, _strings = struct.unpack_from("<4I", data, 0)
    if pool_at + pool_size > len(data) or pool_at < 16 or count > 0x10000 or data[pool_at + pool_size:].strip(b"\xff"):
        raise FormatError("not a cfg table")
    at, pointers = 16, []
    for _ in range(count):
        if at + 3 > pool_at:
            raise FormatError("entries run into the pool")
        args = data[at + 2]
        type_bytes = data[at + 3:at + 3 + (args + 3) // 4]
        first = at + 3 + (args + 3) // 4
        first += -first % 4
        for k in range(args):
            if (type_bytes[k // 4] >> (2 * (k % 4))) & 3 == 0:
                pointers.append(first + 4 * k)
        at = first + 4 * args
    if at > pool_at or data[at:pool_at].strip(b"\xff"):
        raise FormatError("entries do not end at the pool")
    pool = data[pool_at:pool_at + pool_size]
    if pool and not pool.endswith(b"\0"):
        raise FormatError("the pool does not end with NUL")
    starts = set(_starts(pool))
    for p in pointers:
        value = struct.unpack_from("<I", data, p)[0]
        if value != NONE and value not in starts:
            raise FormatError(f"string argument {value:#x} is not a string start")
    return Table("cfg", data, pool_at, pool_at + pool_size, pool.split(b"\0")[:-1], pointers)


def _columns(data: bytes, first: int, end: int, stride: int, starts) -> List[int]:
    """Pointer fields of records ``[first, end)`` of ``stride`` bytes (see the module docstring)."""
    out = []
    count = (end - first) // stride
    for column in range(0, stride - stride % 4, 4):
        values = [struct.unpack_from("<I", data, first + i * stride + column)[0] for i in range(count)]
        used = {v for v in values if v != NONE}
        # A parameter that happens to equal one string start (one repeated non-zero value next to zeros) is not one.
        repeated_flag = len(used - {0}) == 1 and 0 in used and sum(v not in (0, NONE) for v in values) > 1
        if values and used <= starts and used - {0} and not repeated_flag:
            out += [first + i * stride + column for i in range(count)]
    return out


def parse_nat(data: bytes) -> Table:
    data = bytes(data)
    if len(data) < 8:
        raise FormatError("too short")
    head = struct.unpack_from("<I", data, 0)[0]
    if head & 0x80000000:
        if len(data) < 12:
            raise FormatError("too short")
        pool_size = struct.unpack_from("<I", data, 8)[0]
        pool_at = len(data) - pool_size
        pool = data[pool_at:]
        if pool_size > len(data) - 12 or (pool and not pool.endswith(b"\0")):
            raise FormatError("not a nat table")
        count = head & 0xFFFF
        end = 12 + count * NATX_RECORD
        if end > pool_at:
            raise FormatError("not a nat table")
        pointers = _columns(data, 12, end, NATX_RECORD, set(_starts(pool)))
        return Table("natx", data, pool_at, len(data), pool.split(b"\0")[:-1], pointers)
    count, pool_size = head & 0xFFF, head >> 12
    if count == 0 or pool_size > len(data) - 4 or (len(data) - 4 - pool_size) % count:
        return _parse_nat_list(data)
    stride = (len(data) - 4 - pool_size) // count
    pool_at = 4 + stride * count
    pool = data[pool_at:]
    if pool and not pool.endswith(b"\0"):
        raise FormatError("the pool does not end with NUL")
    pointers = _columns(data, 4, pool_at, stride, set(_starts(pool)))
    return Table("nat", data, pool_at, len(data), pool.split(b"\0")[:-1], pointers)


def _parse_nat_list(data: bytes) -> Table:
    """The encounter table kind (``enchab``): u16 table counts at 0..6, u16 pool size at 8; the last table, right
    before the pool, is ``count at 6`` string offsets."""
    names, pool_size = struct.unpack_from("<HH", data, 6)
    pool_at = len(data) - pool_size
    first = pool_at - 4 * names
    pool = data[pool_at:]
    if first < 12 or not pool.endswith(b"\0"):
        raise FormatError("not a nat table")
    starts = set(_starts(pool))
    pointers = [first + 4 * i for i in range(names)]
    if any(struct.unpack_from("<I", data, p)[0] not in starts | {NONE} for p in pointers):
        raise FormatError("not a nat table")
    return Table("natl", data, pool_at, len(data), pool.split(b"\0")[:-1], pointers)


def parse(name: str, data: bytes) -> Table:
    if name.lower().endswith(".nat"):
        return parse_nat(data)
    return parse_cfg(data)


# -- editor text ----------------------------------------------------------------------------------
# The game's ``<tag>`` is shown as ``{tag}`` (no English line has a brace of its own); ``[LF]`` is a line feed
# byte, ``[xNN]`` a byte that is not UTF-8 (Japanese leftovers).
TAG_RE = re.compile(r"\{[^{}\n]+\}|\[(?:LF|x[0-9A-Fa-f]{2})\]")
_BYTE_TAG = re.compile(r"\[x([0-9A-Fa-f]{2})\]")


def to_editor(raw: bytes) -> str:
    """Pool bytes as editor text: ``\\n`` (two characters in the game) becomes a line break."""
    raw = bytes(raw)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = "".join(chr(b) if b < 0x80 else f"[x{b:02X}]" for b in raw)
    text = text.replace("{", "[x7B]").replace("}", "[x7D]")
    text = re.sub(r"<([^<>\n]+)>", r"{\1}", text)
    return text.replace("\n", "[LF]").replace("\\n", "\n")


def from_editor(text: str) -> bytes:
    text = str(text).replace("\r\n", "\n").replace("\n", "\\n").replace("[LF]", "\n")
    text = re.sub(r"\{([^{}\n]+)\}", r"<\1>", text)
    out = bytearray()
    at = 0
    for match in _BYTE_TAG.finditer(text):
        out += text[at:match.start()].encode("utf-8") + bytes([int(match.group(1), 16)])
        at = match.end()
    return bytes(out + text[at:].encode("utf-8"))
