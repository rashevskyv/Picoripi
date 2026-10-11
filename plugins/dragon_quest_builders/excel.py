"""Square Enix / Omega Force ``excel`` string tables of Dragon Quest Builders and Dragon Quest Builders 2.

A table file: u32 row count ``n`` (the rest of the 0x40-byte header is zero), the row ids as u32 at 0x40 (they
may skip numbers), then ``n * k`` u32 cells, row by row, then the string pool of NUL-terminated UTF-8 texts.
A text cell is an offset *relative to the cell's own position*; 0 means "no text". The column count ``k`` is not
stored, so every count is tried and the one that yields the most texts is kept. Some columns hold numbers, not
offsets: a column counts as text when nearly all of its non-zero cells point at the start of a string. A column of
Japanese text next to Western columns is the game's lookup key and is left out.

Writing keeps every unchanged cell and string where it was and appends each changed text at the end of the file,
then a footer (``FOOTER`` + u32 column count) so that the edited file is read with the same column count; the game
never reads past its pool. A table without changes is returned byte for byte.
"""
from __future__ import annotations

import struct
from typing import List, Optional, Tuple

HEADER = 0x40
MAX_COLUMNS = 64
NUL = b"\x00"
CONTROL_OK = chr(10) + chr(9) + chr(13)
FOOTER = b"PICORIPI-EXCEL-K"


class Table:
    """A parsed table: ``cells`` = [(file position of the cell, text)] of every text cell, in file order."""

    def __init__(self, data: bytes, rows: int, columns: int, pool: int, cells: List[Tuple[int, str]]):
        self.data, self.rows, self.columns, self.pool, self.cells = data, rows, columns, pool, cells

    def texts(self) -> List[str]:
        """The non-empty texts, the lines Picoripi shows."""
        return [text for _pos, text in self.cells if text]


def _decode(data: bytes, target: int, pool: int) -> Optional[str]:
    """The text that starts at ``target`` (right after a NUL), or None. Only an empty text may lie before the
    pool (a short offset that lands on a zero byte of the cells); a text with control characters is a number."""
    if target >= len(data) or (target and data[target - 1] != 0):
        return None
    end = data.find(NUL, target)
    if end < 0 or (end > target and target < pool):
        return None
    try:
        text = data[target:end].decode("utf-8")
    except UnicodeDecodeError:
        return None
    return None if any(ord(c) < 0x20 and c not in CONTROL_OK for c in text) else text


def _columns(data: bytes, rows: int, columns: int, base: int, pool: int) -> List[Tuple[int, str]]:
    """[(position, text)] of the text columns of the table read with ``columns`` cells per row."""
    values = struct.unpack_from(f"<{rows * columns}I", data, base)
    out: List[Tuple[int, str]] = []
    for column in range(columns):
        cells, good = [], 0
        for row in range(rows):
            value = values[row * columns + column]
            if not value:
                continue
            pos = base + 4 * (row * columns + column)
            text = _decode(data, pos + value, pool) if value < 0x80000000 else None
            cells.append((pos, text))
            good += text is not None
        if cells and good >= 0.98 * len(cells):
            out += [(pos, text) for pos, text in cells if text is not None]
    out.sort()
    return out


def _pool_start(data: bytes, cells: List[Tuple[int, str]], pool: int) -> int:
    """The lowest position a cell points at inside the pool (a real table refers to the first text of its pool)."""
    low = len(data)
    for pos, _text in cells:
        target = pos + struct.unpack_from("<I", data, pos)[0]
        if pool <= target < low:
            low = target
    return low


def _is_cjk(text: str) -> bool:
    return any(0x3040 <= ord(c) <= 0x30FF or 0x4E00 <= ord(c) <= 0x9FFF or 0xFF00 <= ord(c) <= 0xFFEF for c in text)


def _without_keys(cells: List[Tuple[int, str]], base: int, columns: int) -> List[Tuple[int, str]]:
    """The cells without the key columns: in a table of a Western language the Japanese source text stays as a
    column the game looks entries up by (``Def``, ``ActorName``); it is not shown and is never rewritten."""
    by_column = {}
    for pos, text in cells:
        if text:
            by_column.setdefault((pos - base) // 4 % columns, []).append(text)
    japanese = {c for c, texts in by_column.items() if sum(map(_is_cjk, texts)) >= 0.8 * len(texts)}
    if not japanese or len(japanese) == len(by_column):
        return cells
    return [(pos, text) for pos, text in cells if (pos - base) // 4 % columns not in japanese]


def parse(data: bytes) -> Optional[Table]:
    """The table of ``data``, or None when the bytes are not a string table with texts."""
    if len(data) < HEADER + 8:
        return None
    rows = struct.unpack_from("<I", data, 0)[0]
    if rows < 1 or rows > 200000 or HEADER + 8 * rows > len(data) or any(data[4:HEADER]):
        return None
    if struct.unpack_from("<I", data, HEADER)[0] != 0:
        return None
    base = HEADER + 4 * rows
    best = None
    known = None
    body = data
    if data[-len(FOOTER) - 4:-4] == FOOTER:
        known = struct.unpack_from("<I", data, len(data) - 4)[0]
        body = data[:-len(FOOTER) - 4]
    for columns in range(1, min(MAX_COLUMNS, (len(body) - base) // (4 * rows)) + 1):
        if known is not None and columns != known:
            continue
        pool = base + 4 * rows * columns
        cells = _columns(body, rows, columns, base, pool)
        score = sum(1 for _pos, text in cells if text)
        if score and (best is None or score > best[0]) and (known is not None or _pool_start(body, cells, pool) == pool):
            best = (score, columns, cells)
    if best is None:
        return None
    return Table(data, rows, best[1], base + 4 * rows * best[1], _without_keys(best[2], base, best[1]))


def write(table: Table, texts: List[str]) -> bytes:
    """``table.data`` with the non-empty texts replaced by ``texts`` (as ``Table.texts`` lists them)."""
    old = table.texts()
    if len(texts) != len(old):
        raise ValueError(f"the table has {len(old)} texts, {len(texts)} given")
    if texts == old:
        return table.data
    out = bytearray(table.data)
    if out[-len(FOOTER) - 4:-4] == FOOTER:
        del out[-len(FOOTER) - 4:]
    if out[-1:] != NUL:
        out += NUL
    added = {}
    new_texts = iter(texts)
    for pos, text in table.cells:
        if not text:
            continue
        new = next(new_texts)
        if new == text:
            continue
        if new not in added:
            added[new] = len(out)
            out += new.encode("utf-8") + NUL
        struct.pack_into("<I", out, pos, added[new] - pos)
    out += bytes(-len(out) % 4) + FOOTER + struct.pack("<I", table.columns)
    return bytes(out)


# -- packs: many tables as one project block ---------------------------------------------------------

PACK_MAGIC = b"DQBP"


def is_pack(data: bytes) -> bool:
    return bytes(data[:4]) == PACK_MAGIC


def pack_tables(items: List[Tuple[int, bytes]]) -> bytes:
    """Tables [(LINKDATA index, table bytes)] as one file: ``DQBP``, u32 count, then per table u32 index and u32
    size, then the tables one after another. The workspace script writes it; Picoripi shows one block of all the
    texts and saves the tables back into the same pack."""
    head = PACK_MAGIC + struct.pack("<I", len(items))
    head += b"".join(struct.pack("<II", index, len(data)) for index, data in items)
    return head + b"".join(data for _index, data in items)


def unpack_tables(data: bytes) -> List[Tuple[int, bytes]]:
    if not is_pack(data):
        raise ValueError("not a table pack")
    count = struct.unpack_from("<I", data, 4)[0]
    at = 8 + 8 * count
    out = []
    for i in range(count):
        index, size = struct.unpack_from("<II", data, 8 + 8 * i)
        out.append((index, bytes(data[at:at + size])))
        at += size
    if at != len(data):
        raise ValueError("the table pack is cut short or has trailing bytes")
    return out


def pack_texts(data: bytes) -> Optional[List[str]]:
    """The texts of every table of a pack, in order, or None when a table of it cannot be read."""
    out: List[str] = []
    for _index, raw in unpack_tables(data):
        table = parse(raw)
        if table is None:
            return None
        out += table.texts()
    return out


def pack_write(data: bytes, texts: List[str]) -> bytes:
    """The pack with the texts (as ``pack_texts`` lists them) written back table by table; unchanged tables and
    an unchanged pack are returned byte for byte."""
    items, at = [], 0
    for index, raw in unpack_tables(data):
        table = parse(raw)
        if table is None:
            raise ValueError(f"table {index} of the pack cannot be read")
        count = len(table.texts())
        items.append((index, write(table, texts[at:at + count])))
        at += count
    if at != len(texts):
        raise ValueError(f"the pack has {at} texts, {len(texts)} given")
    return pack_tables(items)
