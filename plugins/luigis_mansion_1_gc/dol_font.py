"""The dialogue font and the resource archive of Luigi's Mansion (GameCube) as members of ``sys/main.dol``.

The executable holds one ResFONT (``FONTbfn1``, 32x32 cells) at file offset ``FONT_AT``; the game draws its dialogue
with it. It also holds a RARC at ``ARCHIVE_AT`` with the Yay0 archives the game mounts from memory: the title screen
(``res_titl.szp``: PRESS START, the logo), the pause menu (``res_paus.szp``), the item and ghost list (``res_list.szp``)
and a few more. The members are ``dialogue_font.bfn`` and ``resources.arc``, each with the room it has in the
executable: a member never grows, so the executable keeps its size and layout, and the disc writer writes
``sys/main.dol`` in place. A smaller member is padded with zeros.
"""
from __future__ import annotations

import struct
from typing import Dict, Tuple

from core.containers.base_container import BaseArchiveContainer

DOL_SIZE = 3799584                  # main.dol of GLME01 rev 0
FONT_AT = 0x303560                  # file offset of FONTbfn1 in that executable
FONT_MAGIC = b"FONTbfn1"
MEMBER = "dialogue_font.bfn"
ARCHIVE_AT = 0x21B000               # file offset of the resource RARC in that executable
ARCHIVE_MEMBER = "resources.arc"


class DolFont(BaseArchiveContainer):
    """``main.dol`` of GLME01 rev 0, seen as its font member and its resource archive member."""

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return (len(data) == DOL_SIZE and data[:4] == b"\x00\x00\x01\x00"
                and bytes(data[FONT_AT:FONT_AT + 8]) == FONT_MAGIC)

    def __init__(self, data: bytes) -> None:
        self._data = bytes(data)
        # member -> (file offset, room); the room is the size field of the member's own header.
        self._members: Dict[str, Tuple[int, int]] = {
            MEMBER: (FONT_AT, struct.unpack_from(">I", self._data, FONT_AT + 8)[0])}
        if self._data[ARCHIVE_AT:ARCHIVE_AT + 4] == b"RARC":
            self._members[ARCHIVE_MEMBER] = (ARCHIVE_AT, struct.unpack_from(">I", self._data, ARCHIVE_AT + 4)[0])
        self._changes: Dict[str, bytes] = {}

    def list_files(self) -> list[str]:
        return list(self._members)

    def read_file(self, path: str) -> bytes:
        if path in self._changes:
            return self._changes[path]
        at, room = self._member(path)
        return self._data[at:at + room]

    def write_file(self, path: str, data: bytes) -> None:
        _at, room = self._member(path)
        if len(data) > room:
            raise ValueError(f"main.dol/{path}: {len(data)} bytes, the executable has room for {room}")
        self._changes[path] = bytes(data)

    def has_pending_changes(self) -> bool:
        return bool(self._changes)

    def pack(self) -> bytes:
        out = bytearray(self._data)
        for path, data in self._changes.items():
            at, room = self._members[path]
            out[at:at + room] = data + bytes(room - len(data))
        return bytes(out)

    def _member(self, path: str) -> Tuple[int, int]:
        if path not in self._members:
            raise ValueError(f"main.dol: no member {path}")
        return self._members[path]
