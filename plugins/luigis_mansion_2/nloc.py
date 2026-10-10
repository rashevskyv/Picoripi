"""The ``NLOC`` text table of Luigi's Mansion: Dark Moon (3DS): the data member of ``art/fe/<language>.data``.

``NLOC``, u32 version 1, u32 hash, u32 count, count x (u32 character offset, u32 key hash) sorted by hash, u32
statistic (about the text's size), then the strings: UTF-16LE, each ended by a NUL, in the order the game's
sources have them. The offset counts characters from the first string. Texts show in file order (not hash
order); ``ids`` are the key hashes. Page and style markup is plain text in the strings: ``{p}`` (next line or
page), ``{tp:0.01}...{/tp}`` (typewriter), ``{clr:RRGGBB}...{clr:pop}`` (colour), ``{ts:1.5}...{/ts}`` (size),
``{0}`` (a value the game fills in).
"""
from __future__ import annotations

import struct
from typing import List, Sequence

MAGIC = b"NLOC"


class Table:
    """An NLOC table. ``build`` returns the original bytes while no string changed."""

    def __init__(self, raw: bytes):
        if raw[:4] != MAGIC or len(raw) < 0x14:
            raise ValueError("not an NLOC table")
        self.raw = bytes(raw)
        self.count = struct.unpack_from("<I", raw, 12)[0]
        self.entries = [struct.unpack_from("<II", raw, 0x10 + 8 * i) for i in range(self.count)]
        self.stat_at = 0x10 + 8 * self.count
        self.pool_at = self.stat_at + 4
        if self.pool_at > len(raw):
            raise ValueError("NLOC table is cut short")
        pool = raw[self.pool_at:].decode("utf-16-le")
        self.order = sorted(range(self.count), key=lambda i: self.entries[i][0])   # entries in pool order
        self._texts = []
        for i in self.order:
            start = self.entries[i][0]
            self._texts.append(pool[start:pool.index("\0", start)])

    def texts(self) -> List[str]:
        return list(self._texts)

    def ids(self) -> List[str]:
        return [f"{self.entries[i][1]:08X}" for i in self.order]

    def build(self, texts: Sequence[str]) -> bytes:
        if list(texts) == self._texts:
            return self.raw
        if len(texts) != self.count:
            raise ValueError(f"the table holds {self.count} strings, {len(texts)} were given")
        offsets, pool, at = {}, [], 0
        for entry_index, text in zip(self.order, texts):
            offsets[entry_index] = at
            pool.append(text + "\0")
            at += len(text) + 1
        old_chars = (len(self.raw) - self.pool_at) // 2
        stat = struct.unpack_from("<I", self.raw, self.stat_at)[0]
        if at > old_chars:   # a statistic that grows with the text size (about one unit per six characters)
            stat = -(-stat * at // old_chars)
        head = bytearray(self.raw[:0x10])
        for i, (_old, key) in enumerate(self.entries):
            head += struct.pack("<II", offsets[i], key)
        head += struct.pack("<I", stat)
        return bytes(head) + "".join(pool).encode("utf-16-le")


class Credits:
    """``art/fe/credits.txt``: the staff roll script, Windows-1252 text lines. ``@...`` lines are layout commands and
    empty lines are spacing; every other line (headings ``/h1:Design``, roles, names) is a string."""

    def __init__(self, raw: bytes):
        self.raw = bytes(raw)
        self.lines = self.raw.decode("cp1252").split("\r\n")
        self.cells = [i for i, line in enumerate(self.lines) if line.strip() and not line.startswith("@")]

    def texts(self) -> List[str]:
        return [self.lines[i] for i in self.cells]

    def ids(self) -> List[str]:
        return [str(i + 1) for i in self.cells]

    def build(self, texts: Sequence[str]) -> bytes:
        if list(texts) == self.texts():
            return self.raw
        if len(texts) != len(self.cells):
            raise ValueError(f"the script holds {len(self.cells)} strings, {len(texts)} were given")
        lines = list(self.lines)
        for i, text in zip(self.cells, texts):
            lines[i] = text
        return "\r\n".join(lines).encode("cp1252", "replace")
