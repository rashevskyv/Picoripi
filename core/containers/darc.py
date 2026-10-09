"""Nintendo 3DS ``darc`` archives (Dragon Quest VII's ``LAYOUT/*.arc``: layouts, pictures and the game fonts).

Header: ``darc``, BOM, header size, version, file size, table offset, table length, data offset. The table
holds 12-byte entries (name offset with a directory flag in the top byte, data offset or parent index, size or
the index after the directory's last child) followed by UTF-16LE names. Packing writes the changed members
after the table, each on a 0x80 boundary like the game's own files, and rewrites the offsets and sizes.
"""
from __future__ import annotations

import struct
from typing import Dict, List, Tuple

from core.containers.base_container import BaseArchiveContainer

_ALIGN = 0x80


class DarcContainer(BaseArchiveContainer):
    MAGIC = b"darc"

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return len(data) >= 0x1C and data[:4] == cls.MAGIC

    def __init__(self, data: bytes) -> None:
        if not self.can_handle(data):
            raise ValueError("Not a darc archive")
        self._original = bytes(data)
        self._table_off, self._table_len, self._data_off = struct.unpack_from("<III", data, 0x10)
        count = struct.unpack_from("<I", data, self._table_off + 8)[0]
        names = data[self._table_off + count * 12:self._table_off + self._table_len]
        self._entries: List[Tuple[str, bool, int, int]] = []   # (path, is_dir, offset, size)
        stack: List[Tuple[int, str]] = []    # (index after the directory's last child, path prefix)
        for i in range(count):
            raw_name, a, b = struct.unpack_from("<III", data, self._table_off + i * 12)
            while stack and i >= stack[-1][0]:
                stack.pop()
            name = names[raw_name & 0xFFFFFF:].decode("utf-16-le").split("\0", 1)[0]
            prefix = stack[-1][1] if stack else ""
            is_dir = bool(raw_name >> 24)
            path = prefix + name if name not in ("", ".") else prefix
            self._entries.append((path, is_dir, a, b))
            if is_dir:
                stack.append((b, path + "/" if path else ""))
        self._files: Dict[str, int] = {path: i for i, (path, is_dir, _a, _b) in enumerate(self._entries) if not is_dir}
        self._changes: Dict[str, bytes] = {}

    def list_files(self) -> List[str]:
        return list(self._files)

    def read_file(self, path: str) -> bytes:
        if path in self._changes:
            return self._changes[path]
        _p, _d, off, size = self._entries[self._files[path]]
        return self._original[off:off + size]

    def write_file(self, path: str, data: bytes) -> None:
        if path not in self._files:
            raise KeyError(f"No {path} in the archive")
        self._changes[path] = bytes(data)

    def pack(self) -> bytes:
        if all(self.read_file(p) == self._original[e[2]:e[2] + e[3]] for p, i in self._files.items() for e in [self._entries[i]]):
            return self._original
        out = bytearray(self._original[:self._data_off])
        table = bytearray(self._original[self._table_off:self._table_off + self._table_len])
        for index, (path, is_dir, _off, _size) in enumerate(self._entries):
            if is_dir:
                continue
            data = self.read_file(path)
            out += bytes(-len(out) % _ALIGN)
            struct.pack_into("<II", table, index * 12 + 4, len(out), len(data))
            out += data
        out[self._table_off:self._table_off + self._table_len] = table
        struct.pack_into("<I", out, 0x0C, len(out))
        return bytes(out)
