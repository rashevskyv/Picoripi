"""Dragon Quest IX (DS) ``.pac`` picture packs: Level-5 ``CHAR`` / ``PALT`` / ``SCRN`` blocks (or NITRO files).

A pack is a run of entries ended by an empty one: a 0x50-byte head -- the name (NUL padded, at most 0x14 bytes, so
long names lose their end and may repeat) and the leftovers of the tool that wrote it, then at ``0x40`` u32 data
offset (0x50), u32 data size, u32 entry size -- and the data, padded to the entry size.

Blocks (data offset 0x10): ``CHAR`` (u16, u16 width / u16 height in tiles, u8 1 = 8 bits a pixel else 4, u8,
u32 tile bytes), ``PALT`` (BGR555 colours), ``SCRN`` (u16 width / height in tiles, u16 tile entries). A pack can
hold NITRO ``NCGR`` / ``NCLR`` / ``NCER`` files instead.

Members are named by their name; a repeated name gets ``#2``, ``#3``... A member written with the same size keeps
its place; another size lays the pack out again.
"""
from __future__ import annotations

import struct
from typing import Dict, List, Tuple

from core.containers.base_container import BaseArchiveContainer

HEAD = 0x50


def entries(data: bytes) -> List[Tuple[str, int, int, int]]:
    """``[(member name, entry offset, data size, entry size)]``."""
    out, at, seen = [], 0, {}
    while at + HEAD <= len(data):
        data_at, size, entry = struct.unpack_from("<3I", data, at + 0x40)
        if not entry:
            break
        if data_at != HEAD or at + entry > len(data) or size > entry - HEAD:
            raise ValueError("Broken pac entry")
        name = data[at:at + 0x14].split(b"\0")[0].decode("latin-1")
        seen[name] = seen.get(name, 0) + 1
        out.append((name if seen[name] == 1 else f"{name}#{seen[name]}", at, size, entry))
        at += entry
    return out


class PacContainer(BaseArchiveContainer):
    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        data = bytes(data)
        if len(data) < HEAD + 16 or data[:4] in (b"GPC2", b"NARC") or struct.unpack_from("<I", data, 0x40)[0] != HEAD:
            return False
        try:
            found = entries(data)
        except (ValueError, struct.error):
            return False
        return bool(found)

    def __init__(self, data: bytes) -> None:
        self._raw = bytes(data)
        self._entries = entries(self._raw)
        self._new: Dict[str, bytes] = {}

    def list_files(self) -> List[str]:
        return [name for name, *_ in self._entries]

    def read_file(self, path: str) -> bytes:
        if path in self._new:
            return self._new[path]
        for name, at, size, _entry in self._entries:
            if name == path:
                return self._raw[at + HEAD:at + HEAD + size]
        raise KeyError(path)

    def write_file(self, path: str, data: bytes) -> None:
        if path not in self.list_files():
            raise KeyError(path)
        self._new[path] = bytes(data)

    def pack(self) -> bytes:
        if not self._new:
            return self._raw
        out = bytearray()
        for name, at, size, entry in self._entries:
            head = bytearray(self._raw[at:at + HEAD])
            data = self._new.get(name, self._raw[at + HEAD:at + HEAD + size])
            padded = entry if len(data) == size else HEAD + len(data) + -(HEAD + len(data)) % 0x10
            struct.pack_into("<II", head, 0x44, len(data), padded)
            out += head + data + bytes(padded - HEAD - len(data))
        end = self._entries[-1][1] + self._entries[-1][3] if self._entries else 0
        return bytes(out) + self._raw[end:]
