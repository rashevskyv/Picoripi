"""Grezzo's 3DS archives and compression (Ocarina of Time 3D, Majora's Mask 3D).

``ZarContainer``: ZAR v1 / GAR v2 -- u32 size, u16 type count, u16 file count, offsets of the type
table, the file info table (ZAR: u32 size + u32 name offset per file; GAR: u32 size, u32 short name
offset, u32 full name offset) and the data offset table. Writing lays the data out again in the same
order and alignment and rewrites sizes and offsets.

``lzs_decompress`` / ``lzs_compress``: ``LzS\\x01`` + 4 bytes + u32 size + u32 packed size, then LZSS
with a 4096-byte ring (start 0xFEE), flag bits LSB first (1 = literal), a match = 12-bit ring
position + 4-bit length - 3.
"""
from __future__ import annotations

import struct
from typing import Dict, List, Tuple

from core.containers.base_container import BaseArchiveContainer

LZS_MAGIC = b"LzS\x01"


def lzs_decompress(data: bytes) -> bytes:
    size = int.from_bytes(data[8:12], "little")
    ring, r, src, out = bytearray(4096), 0xFEE, 16, bytearray()
    while len(out) < size:
        flags = data[src]
        src += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags >> bit & 1:
                c = data[src]
                src += 1
                out.append(c)
                ring[r] = c
                r = (r + 1) & 0xFFF
            else:
                b1, b2 = data[src], data[src + 1]
                src += 2
                at = b1 | (b2 & 0xF0) << 4
                for k in range((b2 & 0x0F) + 3):
                    c = ring[(at + k) & 0xFFF]
                    out.append(c)
                    ring[r] = c
                    r = (r + 1) & 0xFFF
    return bytes(out)


def lzs_compress(data: bytes, header: bytes = LZS_MAGIC + bytes(4)) -> bytes:
    """LZSS with back references to the last 4078 bytes (greedy, hash chains of 3-byte prefixes)."""
    n = len(data)
    chains: Dict[bytes, List[int]] = {}
    body = bytearray()
    pos = 0
    while pos < n:
        flag_at = len(body)
        body.append(0)
        for bit in range(8):
            if pos >= n:
                break
            best_len = best_from = 0
            limit = min(18, n - pos)
            if limit >= 3:
                for start in reversed(chains.get(data[pos:pos + 3], ())):
                    if pos - start > 4078:
                        break
                    length = 3
                    while length < limit and data[start + length] == data[pos + length]:
                        length += 1
                    if length > best_len:
                        best_len, best_from = length, start
                        if length == limit:
                            break
            step = best_len if best_len >= 3 else 1
            if step == 1:
                body[flag_at] |= 1 << bit
                body.append(data[pos])
            else:
                ring = (0xFEE + best_from) & 0xFFF
                body += bytes((ring & 0xFF, (ring >> 4) & 0xF0 | (best_len - 3)))
            for k in range(step):
                if pos + k + 3 <= n:
                    chains.setdefault(data[pos + k:pos + k + 3], []).append(pos + k)
            pos += step
    return bytes(header[:8]) + struct.pack("<II", n, len(body)) + bytes(body)


class ZarContainer(BaseArchiveContainer):
    """A Grezzo ZAR (v1) or GAR (v2) archive."""

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return data[:4] in (b"ZAR\x01", b"GAR\x02")

    def __init__(self, data: bytes) -> None:
        self._data = bytes(data)
        self._gar = data[:3] == b"GAR"
        _size, _types, count, _types_at, self._info, self._offsets = struct.unpack_from("<IHHIII", data, 4)
        self._entries: List[Tuple[str, int, int]] = []
        for index in range(count):
            if self._gar:
                size, _short, name_at = struct.unpack_from("<III", data, self._info + index * 12)
            else:
                size, name_at = struct.unpack_from("<II", data, self._info + index * 8)
            name = data[name_at:data.index(b"\0", name_at)].decode("ascii", "replace").replace("\\", "/")
            start = struct.unpack_from("<I", data, self._offsets + index * 4)[0]
            self._entries.append((name, start, size))
        self._overlay: Dict[str, bytes] = {}

    def list_files(self) -> List[str]:
        return [name for name, _start, _size in self._entries]

    def read_file(self, path: str) -> bytes:
        if path in self._overlay:
            return self._overlay[path]
        for name, start, size in self._entries:
            if name == path:
                return self._data[start:start + size]
        raise KeyError(path)

    def write_file(self, path: str, data: bytes) -> None:
        self.read_file(path)
        self._overlay[path] = bytes(data)

    def pack(self) -> bytes:
        if all(self._overlay.get(name, None) in (None, self._data[start:start + size])
               for name, start, size in self._entries):
            return self._data
        order = sorted(range(len(self._entries)), key=lambda i: self._entries[i][1])
        first = self._entries[order[0]][1]
        head = bytearray(self._data[:first])
        body = bytearray()
        for index in order:
            name, start, size = self._entries[index]
            align = min(start & -start or 0x80, 0x80)
            body += bytes(-(first + len(body)) % align)
            at = first + len(body)
            blob = self._overlay.get(name, self._data[start:start + size])
            body += blob
            struct.pack_into("<I", head, self._offsets + index * 4, at)
            struct.pack_into("<I", head, self._info + index * (12 if self._gar else 8), len(blob))
        last = max(start + size for _n, start, size in self._entries)
        out = head + body + self._data[last:]
        struct.pack_into("<I", out, 4, len(out))
        return bytes(out)
