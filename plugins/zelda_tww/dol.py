"""The resources Wind Waker keeps inside ``sys/main.dol``, as a container Picoripi can open like an archive.

The executable carries its own disc-error messages (a BMG: "The Disc Cover is open..." and four more, drawn
by ``m_Do_dvd_error`` when the disc cannot be read) and the font they are drawn with (a BFN, a copy of the
message font), one after the other in the data section. Members: ``disc_errors.bmg`` (its room runs up to
the font) and ``disc_error_font.bfn`` (its room is its own size). A member may shrink (the rest of its
room is zero-filled) but never grow, so the executable keeps its size and layout.
"""
from __future__ import annotations

import struct
from typing import Dict, List, Tuple

from core.containers.base_container import BaseArchiveContainer

BMG, BFN = b"MESGbmg1", b"FONTbfn1"
NAMES = {BMG: "disc_errors.bmg", BFN: "disc_error_font.bfn"}


def _is_dol(data: bytes) -> bool:
    # A DOL header: the first text section starts right after the 0x100-byte header.
    return len(data) > 0x100 and data[:4] == b"\x00\x00\x01\x00" and data[0xE0:0xE4] != b"\x00\x00\x00\x00"


class DolResources(BaseArchiveContainer):
    """``main.dol`` with an embedded BMG and BFN."""

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return _is_dol(data) and BMG in data and BFN in data

    def __init__(self, data: bytes) -> None:
        self._data = bytes(data)
        self._slots: Dict[str, Tuple[int, int, int]] = {}      # name -> (offset, size, room)
        font = self._data.find(BFN)
        font_size = struct.unpack_from(">I", self._data, font + 8)[0]
        text = self._data.find(BMG)
        if not 0 <= text < font:
            raise ValueError("main.dol: the message file does not come before the font")
        text_size = 32 * struct.unpack_from(">I", self._data, text + 8)[0]
        self._slots[NAMES[BMG]] = (text, text_size, font - text)
        self._slots[NAMES[BFN]] = (font, font_size, font_size)
        self._changes: Dict[str, bytes] = {}

    def list_files(self) -> List[str]:
        return list(self._slots)

    def read_file(self, path: str) -> bytes:
        if path in self._changes:
            return self._changes[path]
        offset, size, _room = self._slots[path]
        return self._data[offset:offset + size]

    def write_file(self, path: str, data: bytes) -> None:
        _offset, _size, room = self._slots[path]
        if len(data) > room:
            raise ValueError(f"main.dol/{path}: {len(data)} bytes, the executable has room for {room}")
        self._changes[path] = bytes(data)

    def has_pending_changes(self) -> bool:
        return bool(self._changes)

    def pack(self) -> bytes:
        out = bytearray(self._data)
        for path, data in self._changes.items():
            offset, _size, room = self._slots[path]
            out[offset:offset + room] = data + bytes(room - len(data))
        return bytes(out)
