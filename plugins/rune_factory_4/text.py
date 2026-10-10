"""The ``TEXT`` tables of Rune Factory 4 (3DS): ``TEXT``, u32 count, count x (u32 byte length, u32 offset),
then the UTF-8 strings, each ended by one NUL, in table order.

One file is one table: ``script/rf3mc.eng`` (the story and event dialogue), ``text/*.eng`` (names, map names)
and ``textAndData/text/*.eng`` (items, NPCs, quests, skills, menus). A line break inside a string is a
plain ``\n``; ``＠...＠`` is a variable the game fills in (the hero's name, an item, a number).
"""
from __future__ import annotations

import struct
from typing import List, Sequence

MAGIC = b"TEXT"


class Table:
    """A ``TEXT`` table. ``build`` returns the original bytes while no string changed."""

    def __init__(self, raw: bytes):
        if raw[:4] != MAGIC or len(raw) < 8:
            raise ValueError("not a TEXT table")
        self.raw = bytes(raw)
        count = struct.unpack_from("<I", raw, 4)[0]
        if 8 + 8 * count > len(raw):
            raise ValueError("TEXT table is cut short")
        self.cells = [struct.unpack_from("<II", raw, 8 + 8 * i) for i in range(count)]
        self._texts = [raw[at:at + size].decode("utf-8") for size, at in self.cells]

    def texts(self) -> List[str]:
        return list(self._texts)

    def ids(self) -> List[str]:
        return [str(i) for i in range(len(self._texts))]

    def build(self, texts: Sequence[str]) -> bytes:
        if list(texts) == self._texts:
            return self.raw
        if len(texts) != len(self._texts):
            raise ValueError(f"the table holds {len(self._texts)} strings, {len(texts)} were given")
        blobs = [t.encode("utf-8") for t in texts]
        at = 8 + 8 * len(blobs)
        head = bytearray(MAGIC + struct.pack("<I", len(blobs)))
        body = bytearray()
        for blob in blobs:
            head += struct.pack("<II", len(blob), at + len(body))
            body += blob + b"\0"
        return bytes(head) + bytes(body)
