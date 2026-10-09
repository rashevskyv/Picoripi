"""Monolith Soft BDAT data tables, the modern layout of Xenoblade Chronicles 3 (file version 0x1004, tables
0x3004; hashed labels): the text cells of every table as one list of strings, and the file written back with
new strings (the string tables grow or shrink; rows, hashes and every other column stay).

File: ``BDAT``, u16 version 0x1004, u16 0x0100, u32 table count, u32 file size, then the table offsets. A table:
``BDAT``, u16 0x3004, u16 0, u32 column count, row count, base id, 0, column table offset, hash table offset,
rows offset, row length, string table offset, string table length (offsets from the table start). A column is
u8 type + u16 offset of its 4-byte label hash in the string table; a row is the column values packed by type
(``SIZES``); a string cell (type 7, or 11 for a debug string) is a u32 offset into the string table, whose first
byte is an empty string and whose next bytes hold the table-name and column hashes before the texts. Tables
are padded to 4 bytes.

The older BDAT of Xenoblade 2 / X is a different layout (plain-text labels, flag columns) and is not read here.
"""
from __future__ import annotations

import struct
from typing import List, Tuple

MAGIC = b"BDAT"
SIZES = {1: 1, 2: 2, 3: 4, 4: 1, 5: 2, 6: 4, 7: 4, 8: 4, 9: 4, 10: 1, 11: 4, 12: 1, 13: 2}
STRING_TYPES = (7, 11)
TEXT_TYPE = 7
_FILE = struct.Struct("<4sHHII")
_TABLE = struct.Struct("<4sHH10I")


def is_bdat(data: bytes) -> bool:
    if len(data) < _FILE.size:
        return False
    magic, version, _flags, count, size = _FILE.unpack_from(data, 0)
    return magic == MAGIC and version == 0x1004 and size == len(data) and _FILE.size + 4 * count <= len(data)


def _tables(data: bytes) -> List[int]:
    count = _FILE.unpack_from(data, 0)[3]
    return list(struct.unpack_from(f"<{count}I", data, _FILE.size))


def _table(data: bytes, at: int):
    """(columns [(type, label offset)], row count, rows offset, row length, string table offset, length)."""
    (magic, _ver, _pad, ncol, nrow, _base, _unk, o_col, _o_hash, o_row, row_len, o_str, str_len) = _TABLE.unpack_from(data, at)
    if magic != MAGIC:
        raise ValueError(f"BDAT table at {at}: bad magic")
    cols = [struct.unpack_from("<BH", data, at + o_col + 3 * i) for i in range(ncol)]
    return cols, nrow, o_row, row_len, o_str, str_len


def _cells(cols) -> List[Tuple[int, int]]:
    """(row offset, column type) of every string column."""
    out, pos = [], 0
    for kind, _label in cols:
        if kind in STRING_TYPES:
            out.append((pos, kind))
        pos += SIZES[kind]
    return out


def _cstr(table: bytes, offset: int) -> str:
    end = table.index(b"\0", offset)
    return table[offset:end].decode("utf-8")


def read(data: bytes) -> List[str]:
    """Every text cell (type 7), table by table, row by row."""
    out = []
    for at in _tables(data):
        cols, nrow, o_row, row_len, o_str, str_len = _table(data, at)
        strings = data[at + o_str:at + o_str + str_len]
        cells = [(pos, kind) for pos, kind in _cells(cols) if kind == TEXT_TYPE]
        for row in range(nrow):
            base = at + o_row + row * row_len
            for pos, _kind in cells:
                out.append(_cstr(strings, struct.unpack_from("<I", data, base + pos)[0]))
    return out


def write(data: bytes, texts: List[str]) -> bytes:
    """``data`` with its text cells replaced by ``texts`` (as ``read`` lists them); a table whose texts did not
    change is copied byte for byte."""
    tables = _tables(data)
    starts = tables + [len(data)]
    out_tables, index = [], 0
    for n, at in enumerate(tables):
        cols, nrow, o_row, row_len, o_str, str_len = _table(data, at)
        strings = data[at + o_str:at + o_str + str_len]
        cells = _cells(cols)
        old = [[struct.unpack_from("<I", data, at + o_row + row * row_len + pos)[0] for pos, _k in cells]
               for row in range(nrow)]
        new_texts = []
        changed = False
        for row in range(nrow):
            for (pos, kind), offset in zip(cells, old[row]):
                if kind == TEXT_TYPE:
                    text = texts[index]
                    index += 1
                    changed |= text != _cstr(strings, offset)
                    new_texts.append(text)
                else:
                    new_texts.append(_cstr(strings, offset))
        if not changed:
            out_tables.append(data[at:starts[n + 1]])
            continue
        used = [o for row in old for o in row if o]
        prefix = strings[:min(used)] if used else strings[:9 + 4 * len(cols)]
        table = bytearray(data[at:at + o_str])
        blob = bytearray(prefix)
        where = {"": 0}
        k = 0
        for row in range(nrow):
            for pos, _kind in cells:
                text = new_texts[k]
                k += 1
                if text not in where:
                    where[text] = len(blob)
                    blob += text.encode("utf-8") + b"\0"
                struct.pack_into("<I", table, o_row + row * row_len + pos, where[text])
        struct.pack_into("<I", table, 0x2C, len(blob))
        table += blob
        table += bytes(-len(table) % 4)
        out_tables.append(bytes(table))
    header_size = _FILE.size + 4 * len(tables)
    offsets, pos = [], header_size
    for table in out_tables:
        offsets.append(pos)
        pos += len(table)
    head = bytearray(data[:header_size])
    struct.pack_into("<I", head, 12, pos)
    struct.pack_into(f"<{len(offsets)}I", head, _FILE.size, *offsets)
    return bytes(head) + b"".join(out_tables)
