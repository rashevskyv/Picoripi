"""The dialogue font of Luigi's Mansion (GameCube) as a member of ``sys/main.dol``.

The executable holds one ResFONT (``FONTbfn1``, 32x32 cells) at file offset ``FONT_AT``; the game draws its dialogue
with it. The member is ``dialogue_font.bfn`` and has the room of the font itself: a member never grows, so the
executable keeps its size and layout, and the disc writer writes ``sys/main.dol`` in place.
"""
from __future__ import annotations

import struct
from typing import Dict

from core.containers.base_container import BaseArchiveContainer

DOL_SIZE = 3799584                  # main.dol of GLME01 rev 0
FONT_AT = 0x303560                  # file offset of FONTbfn1 in that executable
FONT_MAGIC = b"FONTbfn1"
MEMBER = "dialogue_font.bfn"


class DolFont(BaseArchiveContainer):
    """``main.dol`` of GLME01 rev 0, seen as the one font member."""

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return (len(data) == DOL_SIZE and data[:4] == b"\x00\x00\x01\x00"
                and bytes(data[FONT_AT:FONT_AT + 8]) == FONT_MAGIC)

    def __init__(self, data: bytes) -> None:
        self._data = bytes(data)
        self._room = struct.unpack_from(">I", self._data, FONT_AT + 8)[0]
        self._changes: Dict[str, bytes] = {}

    def list_files(self) -> list[str]:
        return [MEMBER]

    def read_file(self, path: str) -> bytes:
        if path in self._changes:
            return self._changes[path]
        return self._data[FONT_AT:FONT_AT + self._room]

    def write_file(self, path: str, data: bytes) -> None:
        if path != MEMBER:
            raise ValueError(f"main.dol: no member {path}")
        if len(data) > self._room:
            raise ValueError(f"main.dol/{path}: {len(data)} bytes, the executable has room for {self._room}")
        self._changes[path] = bytes(data)

    def has_pending_changes(self) -> bool:
        return bool(self._changes)

    def pack(self) -> bytes:
        out = bytearray(self._data)
        for data in self._changes.values():
            out[FONT_AT:FONT_AT + self._room] = data + bytes(self._room - len(data))
        return bytes(out)
