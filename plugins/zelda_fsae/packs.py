"""The game's own graphics packs, as archives the Textures window walks (members ``#<index>``).

- ``*.cmp`` (``subtask*.cmp``): an LZ11 stream of a pack: ``u32`` offsets of the files and of the end, the
  first offset being the size of that table; the files are NCGR / NCLR / NSCR / NCER / NANR, back to back.
- ``zeldat*.bin`` (the Game Boy Advance engine's graphics): ``(u32 offset, u32 size)`` per entry, the first
  offset being the size of the table; bit 31 of the size marks an entry stored LZ11 packed; entries start
  4-byte aligned. Members are read unpacked; an edited entry is packed again and the entries laid out anew.
  ``zelmap.bin`` has the same layout (maps, no text).
"""
from __future__ import annotations

import struct
from typing import Dict, List, Tuple

from core.containers import nitro
from core.containers.base_container import BaseArchiveContainer

PACKED = 0x80000000


def _offsets_table(data: bytes) -> List[int]:
    """The offset table at the start of ``data``, or [] when it is not one."""
    if len(data) < 8:
        return []
    first = struct.unpack_from("<I", data, 0)[0]
    if first < 8 or first % 4 or first > len(data) or first > 0x10000:
        return []
    offsets = list(struct.unpack_from(f"<{first // 4}I", data, 0))
    if offsets[-1] != len(data) or any(b < a for a, b in zip(offsets, offsets[1:])):
        return []
    return offsets


class CmpPack(BaseArchiveContainer):
    """``subtask*.cmp``: an LZ11-packed table of NITRO graphics files."""

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        if data[:1] != b"\x11" or len(data) < 8 or int.from_bytes(data[1:4], "little") > 0x400000:
            return False
        try:
            plain = nitro.lz11_decompress(data)[0]
        except ValueError:
            return False
        return bool(_offsets_table(plain)) and plain[_offsets_table(plain)[0]:][:4] in (
            b"RGCN", b"RLCN", b"RCSN", b"RECN", b"RNAN")

    def __init__(self, data: bytes) -> None:
        self._data = bytes(data)
        plain = nitro.lz11_decompress(self._data)[0]
        offsets = _offsets_table(plain)
        self._files = [plain[a:b] for a, b in zip(offsets, offsets[1:])]
        self._changed: Dict[int, bytes] = {}

    def list_files(self) -> list[str]:
        return [f"#{i}" for i in range(len(self._files))]

    def read_file(self, path: str) -> bytes:
        index = int(path.lstrip("#"))
        return self._changed.get(index, self._files[index])

    def write_file(self, path: str, data: bytes) -> None:
        self._changed[int(path.lstrip("#"))] = bytes(data)

    def pack(self) -> bytes:
        files = [self._changed.get(i, data) for i, data in enumerate(self._files)]
        if files == self._files:
            return self._data
        at = 4 * (len(files) + 1)
        offsets = []
        for data in files:
            offsets.append(at)
            at += len(data)
        offsets.append(at)
        return nitro.lz11_compress(struct.pack(f"<{len(offsets)}I", *offsets) + b"".join(files))


class ZeldatPack(BaseArchiveContainer):
    """``zeldat*.bin``: the Game Boy Advance engine's graphics entries (LZ11 packed or plain)."""

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return bool(cls._entries(data))

    @staticmethod
    def _entries(data: bytes) -> List[Tuple[int, int, bool]]:
        if len(data) < 16:
            return []
        first = struct.unpack_from("<I", data, 0)[0]
        if first < 16 or first % 8 or first > len(data) or first > 0x10000:
            return []
        entries, end = [], first
        for i in range(first // 8):
            offset, size = struct.unpack_from("<II", data, 8 * i)
            length = size & ~PACKED
            if offset < end or offset + length > len(data):
                return []
            if offset % 4 or size & PACKED and data[offset:offset + 1] != b"\x11":
                return []
            entries.append((offset, length, bool(size & PACKED)))
            end = offset + length
        return entries if len(data) - end <= 3 else []

    def __init__(self, data: bytes) -> None:
        self._data = bytes(data)
        self._entries_ = self._entries(self._data)
        self._changed: Dict[int, bytes] = {}

    def list_files(self) -> list[str]:
        return [f"#{i}" for i in range(len(self._entries_))]

    def read_file(self, path: str) -> bytes:
        index = int(path.lstrip("#"))
        if index in self._changed:
            return self._changed[index]
        offset, length, packed = self._entries_[index]
        raw = self._data[offset:offset + length]
        return nitro.lz11_decompress(raw)[0] if packed else raw

    def write_file(self, path: str, data: bytes) -> None:
        self._changed[int(path.lstrip("#"))] = bytes(data)

    def pack(self) -> bytes:
        changed = {i: d for i, d in self._changed.items() if d != self.read_file_original(i)}
        if not changed:
            return self._data
        table = bytearray(8 * len(self._entries_))
        body = bytearray()
        for i, (offset, length, packed) in enumerate(self._entries_):
            if i in changed:
                stored = nitro.lz11_compress(changed[i]) if packed else changed[i]
            else:
                stored = self._data[offset:offset + length]
            body += bytes(-(len(table) + len(body)) % 4)
            struct.pack_into("<II", table, 8 * i, len(table) + len(body), len(stored) | (PACKED if packed else 0))
            body += stored
        out = bytes(table) + bytes(body)
        return out + bytes(-len(out) % 4)

    def read_file_original(self, index: int) -> bytes:
        offset, length, packed = self._entries_[index]
        raw = self._data[offset:offset + length]
        return nitro.lz11_decompress(raw)[0] if packed else raw
