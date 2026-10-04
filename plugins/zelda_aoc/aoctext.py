"""One Age of Calamity text resource: an "AOCT" bundle of 12 or 13 language tables, English exposed.

The game keeps its text in ``data/LinkData2.bin``; the workspace script (``_tools/zt/aoc.py``) splits it
into bundles and packs edited bundles back. A bundle::

    "AOCT"  u16 version 1  u16 slot count
    slot count x (u32 type, u32 hash, u32 offset, u32 size)     -- the LinkData entry of each table
    the tables, 16-aligned

A table: ``u32 rows, u32 pool size, u64 0``, rows of a fixed size whose string cells are u32 offsets
relative to the cell (0 = no string), then the NUL-terminated UTF-8 strings in pool order. Which columns
are strings is not stored: a column is a string column when every value is 0 or points at the start of
a pool string. Parsing checks that the table rebuilds byte-exact.

Slots: 12 = EN FR ES FR-CA DE IT JA KO NL ZH-CN ES-LA ZH-TW; 13 (battle dialogue) = EN EN2 and the same
eleven. EN (slot 0) is edited; a 13-slot bundle also gets the change in EN2 where that cell held the
same English. A cell is a string to translate when its English is not empty and not ``0`` (the game's
placeholder), and a translation never writes such a value, so the list is the same after a reload.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import tags

LANGUAGES_12 = ("EN", "FR", "ES", "FR-CA", "DE", "IT", "JA", "KO", "NL", "ZH-CN", "ES-LA", "ZH-TW")
LANGUAGES_13 = ("EN", "EN2") + LANGUAGES_12[1:]
_HIDDEN = ("", "0")


class FormatError(ValueError):
    """The bytes are not an AOCT bundle of text tables."""


@dataclass
class Table:
    """A parsed text table: its bytes and where its strings are."""

    data: bytes
    rows: int
    row_size: int
    pool: int
    columns: List[int]

    @classmethod
    def parse(cls, data: bytes) -> "Table":
        if len(data) < 16:
            raise FormatError("table too short")
        rows, pool_size, zero = struct.unpack_from("<IIQ", data, 0)
        pool = len(data) - pool_size
        if zero or not rows or not pool_size or pool < 16 or (pool - 16) % rows:
            raise FormatError("not a text table")
        row_size = (pool - 16) // rows
        columns = []
        for column in range(0, row_size - 3, 4):  # string offsets are 4-aligned in every table of the game
            positions = range(16 + column, pool, row_size)
            values = [(p, struct.unpack_from("<I", data, p)[0]) for p in positions]
            if any(v for _p, v in values) and all(
                    not v or (pool <= p + v < len(data) and (p + v == pool or data[p + v - 1] == 0))
                    for p, v in values):
                columns.append(column)
        table = cls(data, rows, row_size, pool, columns)
        if table.build({}) != data:
            raise FormatError("table does not rebuild byte-exact")
        return table

    def _offset(self, row: int, column: int) -> int:
        position = 16 + row * self.row_size + column
        value = struct.unpack_from("<I", self.data, position)[0]
        return position + value if value else 0

    def raw(self, row: int, column: int) -> bytes:
        at = self._offset(row, column)
        return self.data[at:self.data.index(b"\0", at)] if at else b""

    def text(self, row: int, column: int) -> str:
        return self.raw(row, column).decode("utf-8", errors="replace")

    def value(self, row: int, at: int, fmt: str):
        """A number stored in the row at byte ``at`` (``struct`` format ``fmt``)."""
        return struct.unpack_from("<" + fmt, self.data, 16 + row * self.row_size + at)[0]

    def build(self, changes: Dict[Tuple[int, int], bytes]) -> bytes:
        """The table with ``{(row, column): new bytes}``; the pool keeps its order."""
        cells = sorted((self._offset(r, c), r, c) for r in range(self.rows) for c in self.columns
                       if self._offset(r, c))
        out = bytearray(self.data[:self.pool])
        pool = bytearray()
        for _at, row, column in cells:
            position = 16 + row * self.row_size + column
            struct.pack_into("<I", out, position, self.pool + len(pool) - position)
            pool += changes.get((row, column), self.raw(row, column)) + b"\0"
        struct.pack_into("<I", out, 4, len(pool))
        return bytes(out + pool)


def read_bundle(data: bytes) -> List[Tuple[int, int, bytes]]:
    if len(data) < 8:
        raise FormatError("not an AOCT bundle")
    magic, version, count = struct.unpack_from("<4sHH", data, 0)
    if magic != b"AOCT" or version != 1 or count not in (12, 13):
        raise FormatError("not an AOCT bundle")
    slots = []
    for index in range(count):
        kind, key, offset, size = struct.unpack_from("<IIII", data, 8 + 16 * index)
        if offset + size > len(data):
            raise FormatError("AOCT slot runs past the end")
        slots.append((kind, key, data[offset:offset + size]))
    return slots


def build_bundle(slots: List[Tuple[int, int, bytes]]) -> bytes:
    out = bytearray(8 + 16 * len(slots))
    struct.pack_into("<4sHH", out, 0, b"AOCT", 1, len(slots))
    for index, (kind, key, payload) in enumerate(slots):
        out += b"\0" * (-len(out) % 16)
        struct.pack_into("<IIII", out, 8 + 16 * index, kind, key, len(out), len(payload))
        out += payload
    return bytes(out)


class TextBundle:
    """The English table of a bundle as one block of strings; ``build`` writes a translation back."""

    def __init__(self, data: bytes):
        self.slots = read_bundle(data)
        if build_bundle(self.slots) != data:
            raise FormatError("AOCT bundle does not rebuild byte-exact")
        self.table = Table.parse(self.slots[0][2])
        self.cells: List[Tuple[int, int]] = [
            (r, c) for r in range(self.table.rows) for c in self.table.columns
            if self.table.text(r, c) not in _HIDDEN]

    @property
    def languages(self) -> Tuple[str, ...]:
        return LANGUAGES_13 if len(self.slots) == 13 else LANGUAGES_12

    @property
    def is_battle_dialogue(self) -> bool:
        return len(self.slots) == 13

    def texts(self) -> List[str]:
        return [tags.to_editor(self.table.text(r, c)) for r, c in self.cells]

    def build(self, texts: List[Optional[str]]) -> bytes:
        changes: Dict[Tuple[int, int], bytes] = {}
        for index, (row, column) in enumerate(self.cells):
            text = texts[index] if index < len(texts) else None
            if text is None or text == tags.to_editor(self.table.text(row, column)):
                continue
            raw = tags.from_editor(text)
            if raw in _HIDDEN:  # would stop being a string to translate
                continue
            changes[(row, column)] = raw.encode("utf-8")
        if not changes:
            return build_bundle(self.slots)
        slots = list(self.slots)
        slots[0] = (slots[0][0], slots[0][1], self.table.build(changes))
        if len(slots) == 13:
            slots[1] = (slots[1][0], slots[1][1], self._mirror(slots[1][2], changes))
        return build_bundle(slots)

    def _mirror(self, payload: bytes, changes: Dict[Tuple[int, int], bytes]) -> bytes:
        try:
            mirror = Table.parse(payload)
        except FormatError:
            return payload
        if (mirror.rows, mirror.row_size) != (self.table.rows, self.table.row_size):
            return payload
        same = {key: new for key, new in changes.items()
                if key[1] in mirror.columns and mirror.raw(*key) == self.table.raw(*key)}
        return mirror.build(same) if same else payload
