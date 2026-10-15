"""BCSV (JMapInfo) tables of Super Mario Galaxy: read the rows, write them back with changed values.

Layout (Petari, CC0, ``JMapInfo.hpp``): a 0x10-byte header (s32 rows, s32 fields, u32 data offset, u32 row size),
then one 12-byte item per field (u32 name hash, u32 mask, u16 offset in the row, u8 shift, u8 type), the rows from the
data offset, and the string pool after the rows. Types: 0 int, 2 float, 3 long, 4 short, 5 char, 6 string (an offset
into the pool). The Wii file is big-endian; the Switch port's is little-endian (told apart by the field count).
"""
from __future__ import annotations

import struct
from typing import Dict, List, Union

INT, STRING_INLINE, FLOAT, LONG, SHORT, CHAR, STRING = range(7)
SIZES = {INT: 4, FLOAT: 4, LONG: 4, SHORT: 2, CHAR: 1, STRING: 4}
CODES = {INT: "i", FLOAT: "f", LONG: "I", SHORT: "h", CHAR: "b", STRING: "I"}
MAX_ROWS = 1 << 20

Value = Union[int, float, str]


def name_hash(name: str) -> int:
    """The JMap field name hash: h = h * 31 + byte, 32 bits."""
    value = 0
    for byte in name.encode("ascii"):
        value = (value * 31 + byte) & 0xFFFFFFFF
    return value


def endian(data: bytes) -> str:
    """'>' or '<': the field count of a real table is small in its own byte order."""
    if len(data) < 0x10:
        raise ValueError("a BCSV table is shorter than its header")
    return ">" if struct.unpack_from(">i", data, 4)[0] in range(1, 0x1000) else "<"


def read_rows(data: bytes, names: List[str]) -> List[Dict[str, Value]]:
    """Each row as ``{name: value}`` for the fields in ``names`` that the table has (strings decoded as Shift-JIS)."""
    e = endian(data)
    rows, fields, data_at, row_size = struct.unpack_from(e + "iiII", data, 0)
    if not (0 <= rows <= MAX_ROWS and 0 < fields < 0x1000) or data_at + rows * row_size > len(data):
        raise ValueError("the BCSV table does not fit its file")
    by_hash = {name_hash(name): name for name in names}
    columns = []
    for index in range(fields):
        hashed, mask, offset, shift, kind = struct.unpack_from(e + "IIHBB", data, 0x10 + index * 12)
        if hashed in by_hash and kind in CODES:
            columns.append((by_hash[hashed], mask, offset, shift, kind))
    pool = data_at + rows * row_size
    out = []
    for row in range(rows):
        base = data_at + row * row_size
        values: Dict[str, Value] = {}
        for name, mask, offset, shift, kind in columns:
            value = struct.unpack_from(e + CODES[kind], data, base + offset)[0]
            if kind == STRING:
                end = data.index(b"\0", pool + value)
                value = data[pool + value:end].decode("shift_jis", "replace")
            elif kind in (INT, LONG, SHORT, CHAR):
                value = ((value & mask) >> shift) if kind != INT or mask != 0xFFFFFFFF else value
            values[name] = value
        out.append(values)
    return out
