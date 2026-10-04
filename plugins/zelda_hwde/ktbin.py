"""Koei Tecmo data containers used by Hyrule Warriors DE: offset tables and XL typed tables.

Offset table ("container"): ``u32 count`` then ``count`` pairs of ``(u32 offset, u32 size)`` and the
payloads. Text files nest them (language -> table) and the leaves are XL tables.

XL table (all little endian)::

    0x00  "XL" u16 version (0x13)
    0x04  u16 size & 0xFFFF   u16 column count
    0x08  u16 row count       u16 row size
    0x0C  u32 rows offset     (0x10 + column types padded to 4 with 0xFF)
    0x10  u8 column type[n]
    rows  packed rows, then the string pool for type-0 columns

Column type sizes: 0 string offset (u32, relative to the rows offset), 1 s32, 2 s16, 3 u8, 4 f32,
5 u16, 6 s8, 7 u32. Strings are NUL-terminated bytes stored in row order.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

TYPE_SIZES = {0: 4, 1: 4, 2: 2, 3: 1, 4: 4, 5: 2, 6: 1, 7: 4}
# f32 (type 4) is kept as its raw bits so every value, NaNs included, writes back unchanged.
TYPE_FMT = {0: "I", 1: "i", 2: "h", 3: "B", 4: "I", 5: "H", 6: "b", 7: "I"}
STRING = 0


class FormatError(ValueError):
    """The bytes are not the structure the parser expected."""


# --------------------------------------------------------------------------- containers


def looks_like_container(data: bytes) -> bool:
    if len(data) < 12 or data[:2] == b"XL":
        return False
    n = struct.unpack_from("<I", data)[0]
    if not 1 <= n <= 4096 or 4 + 8 * n > len(data):
        return False
    end = 4 + 8 * n
    for i in range(n):
        off, size = struct.unpack_from("<II", data, 4 + 8 * i)
        if off < end or off + size > len(data):
            return False
        end = off + size
    return True


def split_container(data: bytes) -> tuple[list[bytes], list[bytes]]:
    """Return (payloads, gaps); gaps[i] is the raw bytes that follow payload i (alignment, tail)."""
    n = struct.unpack_from("<I", data)[0]
    pairs = [struct.unpack_from("<II", data, 4 + 8 * i) for i in range(n)]
    head_end = 4 + 8 * n
    if pairs and pairs[0][0] != head_end:
        raise FormatError("container payloads do not start right after the header")
    payloads, gaps = [], []
    for i, (off, size) in enumerate(pairs):
        payloads.append(data[off : off + size])
        nxt = pairs[i + 1][0] if i + 1 < n else len(data)
        gaps.append(data[off + size : nxt])
    return payloads, gaps


def build_container(payloads: list[bytes], gaps: list[bytes] | None = None) -> bytes:
    """Inverse of ``split_container``. Without ``gaps`` each payload is zero-padded to 4 bytes,
    which is what the game files do (the last one included)."""
    if gaps is None:
        gaps = [b"\0" * (-len(p) % 4) for p in payloads]
    out = bytearray(struct.pack("<I", len(payloads)))
    pos = 4 + 8 * len(payloads)
    for p, g in zip(payloads, gaps):
        out += struct.pack("<II", pos, len(p))
        pos += len(p) + len(g)
    for p, g in zip(payloads, gaps):
        out += p + g
    return bytes(out)


# --------------------------------------------------------------------------- XL tables


@dataclass
class XlTable:
    version: int
    types: list[int]
    rows: list[list]  # a string cell holds its raw bytes with the terminator; other cells numbers
    tail: bytes = b""  # bytes after the rows of a table without strings, kept verbatim

    @property
    def string_columns(self) -> list[int]:
        return [i for i, t in enumerate(self.types) if t == STRING]

    @property
    def row_size(self) -> int:
        return sum(TYPE_SIZES[t] for t in self.types)


def parse_xl(data: bytes) -> XlTable:
    if data[:2] != b"XL":
        raise FormatError("not an XL table")
    version, _size, ncols, nrows, rowsize, rows_off = struct.unpack_from("<HHHHHI", data, 2)
    types = list(data[0x10 : 0x10 + ncols])
    if any(t not in TYPE_SIZES for t in types):
        raise FormatError(f"unknown XL column type in {types}")
    if sum(TYPE_SIZES[t] for t in types) != rowsize:
        raise FormatError("XL row size does not match column types")
    fmt = "<" + "".join(TYPE_FMT[t] for t in types)
    pool_start = rows_off + nrows * rowsize
    rows = [list(struct.unpack_from(fmt, data, rows_off + r * rowsize)) for r in range(nrows)]
    cells = [(r, c) for r in range(nrows) for c, t in enumerate(types) if t == STRING]
    starts = [rows_off + rows[r][c] for r, c in cells]
    if starts and starts[0] != pool_start:
        raise FormatError("XL string pool does not start right after the rows")
    if any(b <= a for a, b in zip(starts, starts[1:])):
        raise FormatError("XL strings are shared or out of row order")
    # A cell owns the bytes up to the next cell: text plus its terminator (1 NUL, or 4 for wide/CJK).
    # The last cell runs to the end of the table.
    ends = starts[1:] + [len(data)]
    for (r, c), a, b in zip(cells, starts, ends):
        rows[r][c] = data[a:b]
    # Not rebuilt here to check it (that doubled the read time): TextFile(verify=True) checks the whole file.
    return XlTable(version, types, rows, b"" if starts else data[pool_start:])


def build_xl(t: XlTable) -> bytes:
    ncols = len(t.types)
    rows_off = 0x10 + ((ncols + 3) & ~3)
    rowsize = t.row_size
    fmt = "<" + "".join(TYPE_FMT[x] for x in t.types)
    pool = bytearray()
    pool_base = len(t.rows) * rowsize
    packed = bytearray()
    for row in t.rows:
        vals = list(row)
        for c, ty in enumerate(t.types):
            if ty == STRING:
                vals[c] = pool_base + len(pool)
                pool += row[c]
        packed += struct.pack(fmt, *vals)
    body = bytes(packed) + bytes(pool) + t.tail
    total = rows_off + len(body)
    head = struct.pack("<2sHHHHHI", b"XL", t.version, total & 0xFFFF, ncols, len(t.rows), rowsize, rows_off)
    types = bytes(t.types) + b"\xff" * (rows_off - 0x10 - ncols)
    return head + types + body
