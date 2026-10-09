"""GPC2: the Level-5 archive of Dragon Quest IX (DS) (``*.gp2``), read and rebuilt.

A DS cousin of the 3DS XPCK (``core.containers.level5``). Header, little endian:

- ``0x00`` ``GPC2``; ``0x04`` u16 flags (low 12 bits: the file count); ``0x06`` u16 version (5);
- ``0x08`` / ``0x0A`` u16: offset of the name table / of the data, divided by 4;
- ``0x0C`` / ``0x0E`` u16: unpacked size of the entry table / of the name table, divided by 4;
- ``0x10`` u32: low 28 bits the data size / 4; bit 28 set = members are stored as they are (else each member is
  Level-5 compressed);
- ``0x14`` the entry table, Level-5 compressed; then the compressed name table (NUL-separated names).

An entry is 12 bytes: u32 hash, u32 ``data offset / 4`` (24 bits) | name offset low byte << 24, u32 size (24 bits) |
name offset high byte << 24. Members are 4-aligned in the data area.

``build()`` gives the original bytes when nothing changed; otherwise it lays the members out again in their old
order, recompresses only the changed ones (LZ10) and writes the entry table again (LZ10).
"""
from __future__ import annotations

import struct
from typing import Dict, List, Optional

from core.containers import level5
from core.containers.base_container import BaseArchiveContainer

MAGIC = b"GPC2"
RAW_MEMBERS = 0x10000000


class Gpc2:
    """A parsed GPC2: ``names`` in entry order, ``stored`` (name -> bytes as stored) and ``read``/``write``."""

    def __init__(self, raw: bytes):
        raw = bytes(raw)
        if raw[:4] != MAGIC:
            raise ValueError("Not a GPC2 archive")
        self.raw = raw
        _flags, _version, names_at, data_at, _table, _names_size = struct.unpack_from("<6H", raw, 4)
        self.names_at, self.data_at = names_at * 4, data_at * 4
        self.size_word = struct.unpack_from("<I", raw, 0x10)[0]
        self.raw_members = bool(self.size_word & RAW_MEMBERS)
        table = level5.decompress(raw[0x14:self.names_at])
        names = level5.decompress(raw[self.names_at:self.data_at])
        self.entries: List[List[int]] = []          # [hash, offset, size, name offset]
        self.names: List[str] = []
        self.stored: Dict[str, bytes] = {}
        for index in range(len(table) // 12):
            crc, word_a, word_b = struct.unpack_from("<3I", table, index * 12)
            name_at = word_a >> 24 | (word_b >> 24) << 8
            offset, size = (word_a & 0xFFFFFF) * 4, word_b & 0xFFFFFF
            name = names[name_at:names.index(b"\0", name_at)].decode("ascii")
            self.entries.append([crc, offset, size, name_at])
            self.names.append(name)
            self.stored[name] = raw[self.data_at + offset:self.data_at + offset + size]
        self._original = dict(self.stored)

    def read(self, name: str) -> bytes:
        """A member's bytes, unpacked."""
        blob = self.stored[name]
        return blob if self.raw_members else level5.decompress(blob)

    def write(self, name: str, data: bytes) -> None:
        if name not in self.stored:
            raise KeyError(name)
        if self.read(name) == bytes(data):
            return
        self.stored[name] = bytes(data) if self.raw_members else level5.compress(data)

    def build(self) -> bytes:
        if self.stored == self._original:
            return self.raw
        order = sorted(range(len(self.names)), key=lambda i: self.entries[i][1])
        body = bytearray()
        spans = {}
        for index in order:
            blob = self.stored[self.names[index]]
            spans[index] = (len(body), len(blob))
            body += blob + bytes(-len(blob) % 4)
        table = bytearray()
        for index, (crc, _off, _size, name_at) in enumerate(self.entries):
            start, size = spans[index]
            if size >= 1 << 24 or start // 4 >= 1 << 24:
                raise ValueError("GPC2: a member is too large")
            table += struct.pack("<3I", crc, start // 4 | (name_at & 0xFF) << 24, size | (name_at >> 8) << 24)
        packed = level5.compress(bytes(table))
        packed += bytes(-len(packed) % 4)
        names_block = self.raw[self.names_at:self.data_at]
        head = bytearray(self.raw[:0x14])
        names_at = 0x14 + len(packed)
        data_at = names_at + len(names_block)
        struct.pack_into("<HH", head, 8, names_at // 4, data_at // 4)
        struct.pack_into("<I", head, 0x10, (self.size_word & ~0x0FFFFFFF) | len(body) // 4)
        return bytes(head) + bytes(packed) + names_block + bytes(body)


class Gpc2Container(BaseArchiveContainer):
    """A GPC2 as an archive (Font Editor and Textures members): members are read unpacked, written packed."""

    MAGIC = MAGIC

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return bytes(data[:4]) == MAGIC

    def __init__(self, data: bytes) -> None:
        self._pack = Gpc2(data)

    def list_files(self) -> List[str]:
        return list(self._pack.names)

    def read_file(self, path: str) -> bytes:
        return self._pack.read(path)

    def write_file(self, path: str, data: bytes) -> None:
        self._pack.write(path, data)

    def pack(self) -> bytes:
        return self._pack.build()


def open_gpc2(data: bytes) -> Optional[Gpc2]:
    try:
        return Gpc2(data)
    except (ValueError, struct.error, IndexError):
        return None
