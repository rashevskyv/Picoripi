"""Monolith Soft BDAT data tables, the legacy layout of Xenoblade Chronicles 2 / Torna (and Xenoblade X): the text
cells of every table as one list of strings, and the file written back with new strings (a changed table's
string region is laid out again and its checksum and scrambling redone; every other table is copied byte for
byte).

File: u32 table count, u32 file size, u32 table offsets. A table (offsets from the table start): ``BDAT``,
u8 flags (bit 1 = the names and the strings are scrambled), u8 0, u16 names offset, u16 row length, u16 hash
table offset, u16 hash slots, u16 rows offset, u16 row count, u16 base id, u16 unknown, u16 checksum, u32
strings offset, u32 strings length, u16 member table offset, u16 member count. A member is (u16 info offset,
u16 next in hash chain, u16 name offset); the info is u8 kind (1 scalar, 2 array, 3 flag) + for a scalar u8
value type, u16 offset in the row; for an array also u16 count; a flag is u8 index, u32 mask, u16 parent offset.
Value types: 1 u8, 2 u16, 3 u32, 4 s8, 5 s16, 6 s32, 7 string (u32 offset from the table start), 8 float.
Scrambling (XbTool): two running keys ``~checksum >> 8`` and ``~checksum & 0xFF`` XOR the even and odd bytes,
each key advanced by the stored (scrambled) byte. Checksum: the sum over the plain table bytes from 0x20 to
its end of ``(byte << (offset & 3)) & 0xFF``, mod 65536. Every string starts on an even offset; a table is padded to 16 bytes (the file header is 12, so tables start at 12 mod 16).

A text cell is a scalar or array string cell of any column except ``label`` (the row's name); an offset of 0
reads as an empty string.
"""
from __future__ import annotations

import struct
from typing import List, Tuple

MAGIC = b"BDAT"
SCRAMBLED = 2
STRING = 7
SKIP_COLUMNS = ("label",)
_TABLE = struct.Struct("<4sBBHHHHHHHHHIIHH")


def is_bdat(data: bytes) -> bool:
    if len(data) < 12 or data[:4] == MAGIC:
        return False
    count, size = struct.unpack_from("<II", data, 0)
    if size != len(data) or count == 0 or 8 + 4 * count > len(data):
        return False
    first = struct.unpack_from("<I", data, 8)[0]
    return first + _TABLE.size <= len(data) and data[first:first + 4] == MAGIC


def unscramble(buf: bytes, checksum: int) -> bytes:
    out = bytearray(buf)
    a, b = (~checksum >> 8) & 0xFF, ~checksum & 0xFF
    for i in range(0, len(out) - 1, 2):
        stored_even, stored_odd = out[i], out[i + 1]
        out[i] ^= a
        out[i + 1] ^= b
        a = (a + stored_even) & 0xFF
        b = (b + stored_odd) & 0xFF
    return bytes(out)


def checksum_of(plain: bytes) -> int:
    return sum((b << (i & 3)) & 0xFF for i, b in enumerate(plain[0x20:], 0x20)) & 0xFFFF


def _tables(data: bytes) -> List[Tuple[int, int]]:
    count = struct.unpack_from("<I", data, 0)[0]
    offsets = list(struct.unpack_from(f"<{count}I", data, 8))
    return list(zip(offsets, offsets[1:] + [len(data)]))


def _cstr(buf: bytes, at: int) -> str:
    return buf[at:buf.index(b"\0", at)].decode("utf-8")


class _Table:
    """One table, unscrambled: ``cells`` = (row offset, count) of every string column that is text."""

    def __init__(self, raw: bytes):
        (magic, self.flags, _v, names_off, self.row_len, hash_off, _slots, self.rows_off, self.rows, _base, _u,
         self.checksum, self.str_off, self.str_len, mem_off, mem_count) = _TABLE.unpack_from(raw, 0)
        if magic != MAGIC:
            raise ValueError("BDAT table: bad magic")
        plain = bytearray(raw)
        if self.flags & SCRAMBLED:
            plain[names_off:hash_off] = unscramble(raw[names_off:hash_off], self.checksum)
            plain[self.str_off:self.str_off + self.str_len] = unscramble(raw[self.str_off:self.str_off + self.str_len], self.checksum)
        self.plain = bytes(plain)
        self.cells: List[Tuple[int, int]] = []          # (offset in the row, element count) of the text columns
        self.strings: List[Tuple[int, int]] = []        # the same for every string column (labels included)
        for i in range(mem_count):
            info_off, _next, name_off = struct.unpack_from("<HHH", self.plain, mem_off + 6 * i)
            kind = self.plain[info_off]
            if kind not in (1, 2):
                continue
            value_type, offset = struct.unpack_from("<BH", self.plain, info_off + 1)
            if value_type != STRING:
                continue
            count = struct.unpack_from("<H", self.plain, info_off + 4)[0] if kind == 2 else 1
            self.strings.append((offset, count))
            if _cstr(self.plain, name_off) not in SKIP_COLUMNS:
                self.cells.append((offset, count))

    def offset_at(self, row: int, offset: int, k: int) -> int:
        return struct.unpack_from("<I", self.plain, self.rows_off + row * self.row_len + offset + 4 * k)[0]

    def text(self, at: int) -> str:
        return _cstr(self.plain, at) if at else ""

    def texts(self) -> List[str]:
        return [self.text(self.offset_at(row, offset, k)) for row in range(self.rows) for offset, count in self.cells
                for k in range(count)]


def read(data: bytes) -> List[str]:
    """Every text cell, table by table, row by row, column by column."""
    out: List[str] = []
    for start, end in _tables(data):
        out += _Table(data[start:end]).texts()
    return out


def _rebuild(table: _Table, texts: List[str]) -> bytes:
    """The table with its text cells set to ``texts``: new string region, checksum and scrambling."""
    body = bytearray(table.plain[:table.str_off])
    blob, where = bytearray(), {}
    new = iter(texts)

    def put(text: str) -> int:                  # in row order, one copy per distinct string, as the game's files are laid out
        if text not in where:
            where[text] = table.str_off + len(blob)
            blob.extend(text.encode("utf-8") + b"\0")
            blob.extend(bytes(len(blob) % 2))  # every string starts on an even offset
        return where[text]

    for row in range(table.rows):
        for offset, count in table.strings:
            is_text = (offset, count) in table.cells
            for k in range(count):
                old = table.offset_at(row, offset, k)
                text = next(new) if is_text else table.text(old)
                at = put(text) if (old or is_text) else 0
                struct.pack_into("<I", body, table.rows_off + row * table.row_len + offset + 4 * k, at)
    blob.extend(bytes(-(table.str_off + len(blob)) % 16))        # the table ends on a 16-byte boundary
    struct.pack_into("<I", body, 0x1C, len(blob))
    plain = bytes(body) + bytes(blob)
    checksum = checksum_of(plain)
    out = bytearray(plain)
    struct.pack_into("<H", out, 0x16, checksum)
    if table.flags & SCRAMBLED:
        names_off, hash_off = struct.unpack_from("<H", plain, 6)[0], struct.unpack_from("<H", plain, 10)[0]
        out[names_off:hash_off] = _scramble(plain[names_off:hash_off], checksum)
        out[table.str_off:] = _scramble(plain[table.str_off:], checksum)
    return bytes(out)


def _scramble(buf: bytes, checksum: int) -> bytes:
    """Plain -> scrambled: the key advances by the stored byte, which here is the output."""
    out = bytearray(buf)
    a, b = (~checksum >> 8) & 0xFF, ~checksum & 0xFF
    for i in range(0, len(out) - 1, 2):
        out[i] ^= a
        out[i + 1] ^= b
        a = (a + out[i]) & 0xFF
        b = (b + out[i + 1]) & 0xFF
    return bytes(out)


def write(data: bytes, texts: List[str]) -> bytes:
    """``data`` with its text cells replaced by ``texts`` (as ``read`` lists them); a table whose texts did not
    change is copied byte for byte."""
    parts, index = [], 0
    for start, end in _tables(data):
        table = _Table(data[start:end])
        old = table.texts()
        new = texts[index:index + len(old)]
        index += len(old)
        parts.append(data[start:end] if new == old else _rebuild(table, new))
    if index != len(texts):
        raise ValueError(f"the table file has {index} text cells, the list {len(texts)}")
    head_size = 8 + 4 * len(parts)
    offsets, at = [], head_size
    for part in parts:
        offsets.append(at)
        at += len(part)
    return struct.pack("<II", len(parts), at) + struct.pack(f"<{len(parts)}I", *offsets) + b"".join(parts)
