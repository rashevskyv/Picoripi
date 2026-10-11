"""Senran Kagura Burst's ``.bin`` packs (``romfs/ui/lyt_*.bin``, ``arc``, model files): a list of files, optionally
compressed as a whole.

Plain pack (little endian): ``0x0E, 0, 4, 4, 4, 0x80, 0, 0`` (eight u32), the file count at 0x20, the offsets of the
files, their sizes, zero padding up to 0x80 where the first file starts; every file starts on a 0x80 boundary and the
pack ends on one. The files of the UI packs are ``darc`` archives (layouts, animations and ``timg/*.bclim`` pictures).

Compressed pack: u32 plain size, u32 0, then groups of eight items led by a flag byte (the most significant bit
first): a clear bit is one literal byte, a set bit is a copy of two bytes ``(b0, b1)``: ``b0`` is the distance back
(256 - b0, 256 when 0) and ``b1 + 1`` the length; ``b1 == 0`` is followed by a u16 that is the length minus one
(the longer runs, ``b1 == 1`` never occurs). The history before the start is zeros.

A changed pack is written the way it was read (compressed again by ``lz_compress``, a greedy matcher that is
about 4 % larger than the game's own).
"""
from __future__ import annotations

import struct
from typing import Dict, List, Optional, Tuple

from core.containers.base_container import BaseArchiveContainer

_ALIGN = 0x80
_HEAD = b"\x0e\0\0\0\0\0\0\0\x04\0\0\0\x04\0\0\0\x04\0\0\0\x80\0\0\0\0\0\0\0\0\0\0\0"


def lz_decompress(data: bytes, limit: Optional[int] = None) -> bytes:
    """The plain bytes of a compressed pack (``limit``: stop after that many)."""
    size = struct.unpack_from("<I", data, 0)[0]
    if limit is not None:
        size = min(size, limit)
    out = bytearray(256)
    ip, end = 8, len(data)
    while len(out) - 256 < size and ip < end:
        flags = data[ip]
        ip += 1
        for bit in range(7, -1, -1):
            if len(out) - 256 >= size or ip >= end:
                break
            if flags >> bit & 1:
                b0, b1 = data[ip], data[ip + 1]
                ip += 2
                length = b1 + 1
                if b1 == 0:
                    length = (data[ip] | data[ip + 1] << 8) + 1
                    ip += 2
                dist = 256 - b0 if b0 else 256
                if length <= dist:
                    start = len(out) - dist
                    out += out[start:start + length]
                else:
                    for _ in range(length):
                        out.append(out[-dist])
            else:
                out.append(data[ip])
                ip += 1
    return bytes(out[256:256 + size])


def lz_compress(plain: bytes) -> bytes:
    """A compressed pack of ``plain`` (greedy matching in a 256-byte window, no copy reaches before the start).

    The result is decoded again and compared; a mismatch raises ``ValueError``.
    """
    n = len(plain)
    out = bytearray(struct.pack("<II", n, 0))
    chains: Dict[bytes, List[int]] = {}
    items: List[bytes] = []
    flags = 0
    i = 0

    def flush() -> None:
        nonlocal items, flags
        out.append(flags << (8 - len(items)) & 0xFF)
        for item in items:
            out.extend(item)
        items, flags = [], 0

    while i < n:
        best_len, best_dist = 0, 0
        if i + 3 <= n:
            key = plain[i:i + 3]
            for p in reversed(chains.get(key, ())):
                dist = i - p
                if dist > 256:
                    break
                limit = min(n - i, 65536)
                length = 3
                while length + 32 <= limit and plain[p + length:p + length + 32] == plain[i + length:i + length + 32]:
                    length += 32
                while length < limit and plain[p + length] == plain[i + length]:
                    length += 1
                if length > best_len:
                    best_len, best_dist = length, dist
                    if length >= 256:
                        break
        if best_len >= 3:
            b0 = (256 - best_dist) & 0xFF
            if best_len <= 256:
                items.append(bytes((b0, best_len - 1)))
            else:
                items.append(bytes((b0, 0)) + struct.pack("<H", best_len - 1))
            flags = flags << 1 | 1
            step = best_len
        else:
            items.append(plain[i:i + 1])
            flags <<= 1
            step = 1
        for p in range(i, min(i + step, i + 48)):      # long copies are indexed only at their start
            if p + 3 <= n:
                lst = chains.setdefault(plain[p:p + 3], [])
                lst.append(p)
                if len(lst) > 12:
                    del lst[0]
        i += step
        if len(items) == 8:
            flush()
    if items:
        flush()
    result = bytes(out)
    if lz_decompress(result) != plain:
        raise ValueError("the compressed pack does not decode to the original")
    return result


def _table(plain: bytes) -> List[Tuple[int, int]]:
    count = struct.unpack_from("<I", plain, 0x20)[0]
    if count > 4096 or 0x24 + 8 * count > len(plain):
        raise ValueError("not a Senran Kagura Burst pack")
    offsets = struct.unpack_from(f"<{count}I", plain, 0x24)
    sizes = struct.unpack_from(f"<{count}I", plain, 0x24 + 4 * count)
    return list(zip(offsets, sizes))


def is_plain(data: bytes) -> bool:
    return len(data) > 0x24 and bytes(data[:32]) == _HEAD


def is_compressed(data: bytes) -> bool:
    if len(data) < 0x20 or struct.unpack_from("<II", data, 0)[1] != 0 or data[:4] == b"\x0e\0\0\0":
        return False
    size = struct.unpack_from("<I", data, 0)[0]
    if size < 0x80 or size > 0x10000000:
        return False
    try:
        return lz_decompress(data, 32) == _HEAD
    except IndexError:
        return False


def _kind(blob: bytes) -> str:
    if blob[:4] == b"darc":
        return "darc"
    if blob[:4] == b"CGFX":
        return "bcres"
    return "bin"


def build_plain(files: List[bytes]) -> bytes:
    """A plain pack of ``files``."""
    count = len(files)
    at = (0x24 + 8 * count + _ALIGN - 1) // _ALIGN * _ALIGN
    offsets, body = [], bytearray()
    for blob in files:
        offsets.append(at + len(body))
        body += blob + bytes(-len(blob) % _ALIGN)
    head = bytearray(_HEAD) + struct.pack("<I", count) + struct.pack(f"<{count}I", *offsets) \
        + struct.pack(f"<{count}I", *(len(f) for f in files))
    head += bytes(at - len(head))
    return bytes(head) + bytes(body)


class PackContainer(BaseArchiveContainer):
    MAGIC = b""

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return is_plain(data) or is_compressed(data)

    def __init__(self, data: bytes) -> None:
        data = bytes(data)
        self._original = data
        self._compressed = not is_plain(data)
        if self._compressed and not is_compressed(data):
            raise ValueError("Not a Senran Kagura Burst pack")
        self._plain = lz_decompress(data) if self._compressed else data
        self._entries: List[Tuple[int, int]] = _table(self._plain)
        self._names = [f"{i}.{_kind(self._plain[off:off + 4])}" for i, (off, _size) in enumerate(self._entries)]
        self._changes: Dict[str, bytes] = {}

    def list_files(self) -> List[str]:
        return list(self._names)

    def read_file(self, path: str) -> bytes:
        if path in self._changes:
            return self._changes[path]
        off, size = self._entries[self._names.index(path)]
        return self._plain[off:off + size]

    def write_file(self, path: str, data: bytes) -> None:
        if path not in self._names:
            raise KeyError(f"No {path} in the pack")
        self._changes[path] = bytes(data)

    def pack(self) -> bytes:
        changed = {p: d for p, d in self._changes.items()
                   if d != self._plain[self._entries[self._names.index(p)][0]:][:self._entries[self._names.index(p)][1]]}
        if not changed:
            return self._original
        plain = build_plain([self.read_file(name) for name in self._names])
        return lz_compress(plain) if self._compressed else plain

    def has_pending_changes(self) -> bool:
        return bool(self._changes)
