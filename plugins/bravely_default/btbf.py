"""Bravely Default ``BTBF`` tables (``.btb``, ``.txb``, ``.spb``, ``.trb``, ``.mtb``, ``.tbl``, ``.subtitles``).

A table is a 0x30-byte header, fixed-size rows of u32 fields, an optional ASCII table (resource paths, never
text) and a UTF-16LE string table of NUL-terminated strings. Header: magic, file size, header size, rows size,
ASCII table offset and size, string table offset and size, row stride, row count, two zero words.

A row field that holds text is an offset into the string table. Which fields those are is not written down,
so it is read off the data: the game's writer stores the strings row by row, column by column, so the string
columns are the fields whose values follow the string table in that order (``_columns``). A table whose
layout does not follow the rule falls back to the fields that always point at a string start.

Saving writes the string table again from the edited strings (the ASCII table and the rows keep their bytes
apart from the offsets), so text may grow; an unchanged table is written back byte for byte.
"""
from __future__ import annotations

import struct
from typing import Dict, List, Optional, Tuple

MAGIC = b"BTBF"
_HEADER = "<4s11I"
HEADER_SIZE = 0x30


class Btbf:
    """One table. ``texts[i]`` is string ``i`` of the string table (in file order); ``cells`` maps every
    text-holding row field ``(row, column byte offset)`` to its string index."""

    def __init__(self, raw: bytes):
        raw = bytes(raw)
        if raw[:4] != MAGIC:
            raise ValueError("Not a BTBF table")
        (_magic, self.size, self.header_size, self.rows_size, self.ascii_off, self.ascii_size, self.strings_off,
         self.strings_size, self.stride, self.count, _a, _b) = struct.unpack_from(_HEADER, raw, 0)
        if self.header_size != HEADER_SIZE or self.strings_off + self.strings_size > len(raw):
            raise ValueError("BTBF header does not fit the file")
        self.raw = raw
        self.offsets, self.texts = self._strings()
        self.columns = self._columns()
        index = {offset: i for i, offset in enumerate(self.offsets)}
        self.cells: Dict[Tuple[int, int], int] = {}
        for row in range(self.count):
            for column in self.columns:
                self.cells[(row, column)] = index[self._field(row, column)]

    # -- reading ------------------------------------------------------------------

    def _field(self, row: int, column: int) -> int:
        return struct.unpack_from("<I", self.raw, self.header_size + row * self.stride + column)[0]

    def _strings(self) -> Tuple[List[int], List[str]]:
        table = self.raw[self.strings_off:self.strings_off + self.strings_size]
        offsets, texts, at = [], [], 0
        while at + 1 < len(table):
            end = at
            while end + 1 < len(table) and table[end:end + 2] != b"\0\0":
                end += 2
            offsets.append(at)
            texts.append(table[at:end].decode("utf-16-le", "surrogatepass"))
            at = end + 2
        return offsets, texts

    def _columns(self) -> List[int]:
        fields = range(0, self.stride - 3, 4)
        if self.count and not len(self.offsets) % self.count:
            per_row = len(self.offsets) // self.count
            found = []
            for column in fields:
                for j in range(per_row):
                    if all(self._field(row, column) == self.offsets[row * per_row + j] for row in range(self.count)):
                        found.append(column)
                        break
            if len(found) == per_row:
                return found
        starts = set(self.offsets)
        return [column for column in fields if all(self._field(row, column) in starts for row in range(self.count))]

    # -- writing ------------------------------------------------------------------

    def build(self, texts: List[str]) -> bytes:
        """The table with ``texts`` (one per string, file order) as its string table."""
        if len(texts) != len(self.texts):
            raise ValueError(f"The table has {len(self.texts)} strings, got {len(texts)}")
        if texts == self.texts:
            return self.raw
        table, offsets = bytearray(), []
        for text in texts:
            offsets.append(len(table))
            table += text.encode("utf-16-le", "surrogatepass") + b"\0\0"
        out = bytearray(self.raw[:self.strings_off]) + table
        for (row, column), index in self.cells.items():
            struct.pack_into("<I", out, self.header_size + row * self.stride + column, offsets[index])
        struct.pack_into("<I", out, 4, len(out))
        struct.pack_into("<I", out, 0x1C, len(table))
        return bytes(out)


def cell_label(row: int, column: int) -> str:
    return f"row {row} field {column // 4}"


def label_of(table: Btbf, index: int) -> Optional[str]:
    """``row R field F`` of the first cell that shows string ``index``."""
    for (row, column), i in table.cells.items():
        if i == index:
            return cell_label(row, column)
    return None
