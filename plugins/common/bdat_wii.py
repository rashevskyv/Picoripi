"""Monolith Soft BDAT tables of Xenoblade Chronicles (Wii, big-endian; the New 3DS port little-endian): the
text cells of every table as lists of strings, and the file written back with new strings (a changed table's
string region is laid out again and its checksum and scrambling redone; every other table is copied byte for
byte).

File: u32 table count, u32 file size, u32 table offsets. A table (offsets from the table start): ``BDAT``,
u8 flags (bit 1 = the names and the strings are scrambled), u8 0, u16 names offset, u16 row length, u16 hash
table offset, u16 hash slots, u16 rows offset, u16 row count, u16 base id, u16 2, u16 checksum, u32 strings
offset, u32 strings length; then (Wii layout, no member table header) the column infos packed from 0x20 to the
names offset: u8 kind (1 scalar, 2 array, 3 flag), u8 value type, u16 offset in the row (+ u16 count for an
array). The names region holds the table name, then one node per column: u16 info offset, u16 next in the
hash chain, the name (even-aligned). Value type 7 is a string: a u32 offset from the table start, 0 = empty.
Scrambling and checksum are the XbTool rules (``plugins/common/bdat_legacy`` on the Switch branch, which this
module follows for the big-endian Wii layout): two running keys ``~checksum >> 8`` and ``~checksum & 0xFF``
XOR the even and odd bytes, each advanced by the stored byte; the checksum is the sum over the plain table
bytes from 0x20 of ``(byte << (offset & 3)) & 0xFF`` mod 65536.

A text cell is a string cell of any column not in ``SKIP_COLUMNS`` (resource names, file names, debug names).
"""
from __future__ import annotations

import struct
from typing import List, Tuple

MAGIC = b"BDAT"
SCRAMBLED = 2
STRING = 7
SKIP_COLUMNS = frozenset({"resource", "filename", "filename_1", "filename_2", "file", "file_name", "ID_NAME",
                          "name_dbg", "floorname", "str", "pain1", "pain2", "icon_pain", "label"})


def endian_of(data: bytes) -> str:
    """``">"`` (Wii) or ``"<"`` (3DS) when ``data`` is a BDAT file, else ``""``."""
    for e in (">", "<"):
        if len(data) >= 16:
            count, size = struct.unpack_from(e + "II", data, 0)
            if 0 < count < 4096 and size == len(data) and 8 + 4 * count <= len(data):
                first = struct.unpack_from(e + "I", data, 8)[0]
                if first + 0x20 <= len(data) and data[first:first + 4] == MAGIC:
                    return e
    return ""


def is_bdat(data: bytes) -> bool:
    return bool(endian_of(data))


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


def _scramble(buf: bytes, checksum: int) -> bytes:
    out = bytearray(buf)
    a, b = (~checksum >> 8) & 0xFF, ~checksum & 0xFF
    for i in range(0, len(out) - 1, 2):
        out[i] ^= a
        out[i + 1] ^= b
        a = (a + out[i]) & 0xFF
        b = (b + out[i + 1]) & 0xFF
    return bytes(out)


def checksum_of(plain: bytes) -> int:
    return sum((b << (i & 3)) & 0xFF for i, b in enumerate(plain[0x20:], 0x20)) & 0xFFFF


def _tables(data: bytes, e: str) -> List[Tuple[int, int]]:
    count = struct.unpack_from(e + "I", data, 0)[0]
    offsets = list(struct.unpack_from(f"{e}{count}I", data, 8))
    return list(zip(offsets, offsets[1:] + [len(data)]))


def _cstr(buf: bytes, at: int) -> str:
    end = buf.find(b"\0", at)
    return buf[at:end if end >= 0 else len(buf)].decode("utf-8", "replace")


class Table:
    """One table, unscrambled: ``name``, ``columns`` (name, row offset, count) of every string column."""

    def __init__(self, raw: bytes, e: str):
        self.e = e
        (magic, self.flags, _z, names_off, self.row_len, hash_off, _slots, self.rows_off, self.rows, _base, _u,
         self.checksum, self.str_off, self.str_len) = struct.unpack_from(e + "4sBBHHHHHHHHHII", raw, 0)
        if magic != MAGIC:
            raise ValueError("BDAT table: bad magic")
        plain = bytearray(raw)
        if self.flags & SCRAMBLED:
            plain[names_off:hash_off] = unscramble(raw[names_off:hash_off], self.checksum)
            plain[self.str_off:self.str_off + self.str_len] = unscramble(
                raw[self.str_off:self.str_off + self.str_len], self.checksum)
        self.plain = bytes(plain)
        self.names_off, self.hash_off = names_off, hash_off
        self.name = _cstr(self.plain, names_off)
        self.columns: List[Tuple[str, int, int]] = []   # every string column: (name, offset in the row, count)
        at = (names_off + len(self.name.encode("utf-8")) + 2) & ~1
        while at + 4 < hash_off:
            info_off, _next = struct.unpack_from(e + "HH", self.plain, at)
            if not 0x20 <= info_off < names_off:
                break
            cname = _cstr(self.plain, at + 4)
            kind, value_type, offset = struct.unpack_from(e + "BBH", self.plain, info_off)
            if kind in (1, 2) and value_type == STRING:
                count = struct.unpack_from(e + "H", self.plain, info_off + 4)[0] if kind == 2 else 1
                self.columns.append((cname, offset, count))
            at = (at + 4 + len(cname.encode("utf-8")) + 2) & ~1

    def _cells(self):
        for row in range(self.rows):
            for cname, offset, count in self.columns:
                for k in range(count):
                    yield cname, self.rows_off + row * self.row_len + offset + 4 * k

    def text_at(self, where: int) -> str:
        at = struct.unpack_from(self.e + "I", self.plain, where)[0]
        return _cstr(self.plain, at) if at else ""

    def texts(self) -> List[str]:
        """The text cells, row by row, column by column (skipped columns left out)."""
        return [self.text_at(where) for cname, where in self._cells() if cname not in SKIP_COLUMNS]

    def rebuild(self, texts: List[str]) -> bytes:
        """The table with its text cells set to ``texts``: new string region, checksum and scrambling."""
        e = self.e
        body = bytearray(self.plain[:self.str_off])
        blob, where = bytearray(), {}
        new = iter(texts)
        for cname, cell in self._cells():
            old = struct.unpack_from(e + "I", self.plain, cell)[0]
            text = next(new) if cname not in SKIP_COLUMNS else (_cstr(self.plain, old) if old else "")
            if not old and not text:
                continue
            if text not in where:
                where[text] = self.str_off + len(blob)
                blob.extend(text.encode("utf-8") + b"\0")
                blob.extend(bytes(len(blob) % 2))        # every string starts on an even offset
            struct.pack_into(e + "I", body, cell, where[text])
        blob.extend(bytes(-(self.str_off + len(blob)) % 16))
        struct.pack_into(e + "I", body, 0x1C, len(blob))
        plain = bytes(body) + bytes(blob)
        checksum = checksum_of(plain)
        out = bytearray(plain)
        struct.pack_into(e + "H", out, 0x16, checksum)
        if self.flags & SCRAMBLED:
            out[self.names_off:self.hash_off] = _scramble(plain[self.names_off:self.hash_off], checksum)
            out[self.str_off:] = _scramble(plain[self.str_off:], checksum)
        return bytes(out)


def read(data: bytes) -> List[Tuple[str, List[str]]]:
    """``[(table name, text cells)]`` of every table of a BDAT file."""
    e = endian_of(data)
    if not e:
        raise ValueError("not a BDAT file")
    out = []
    for start, end in _tables(data, e):
        table = Table(data[start:end], e)
        out.append((table.name, table.texts()))
    return out


def write(data: bytes, tables: List[List[str]]) -> bytes:
    """``data`` with the text cells of table ``i`` replaced by ``tables[i]``; an unchanged table is copied byte
    for byte."""
    e = endian_of(data)
    if not e:
        raise ValueError("not a BDAT file")
    spans = _tables(data, e)
    if len(tables) != len(spans):
        raise ValueError(f"the file has {len(spans)} tables, the project {len(tables)}")
    parts = []
    for (start, end), texts in zip(spans, tables):
        table = Table(data[start:end], e)
        old = table.texts()
        if len(texts) != len(old):
            raise ValueError(f"table {table.name} has {len(old)} text cells, the project {len(texts)}")
        parts.append(data[start:end] if list(texts) == old else table.rebuild(list(texts)))
    offsets, at = [], 8 + 4 * len(parts)
    at += -at % 4
    head_pad = at - (8 + 4 * len(parts))
    for part in parts:
        offsets.append(at)
        at += len(part)
    return (struct.pack(e + "II", len(parts), at) + struct.pack(f"{e}{len(parts)}I", *offsets) + bytes(head_pad)
            + b"".join(parts))
