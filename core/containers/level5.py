"""Level-5 compression (3DS games: Yo-kai Watch, Inazuma Eleven, Layton) and the XPCK pack.

Compressed data starts with a little-endian u32: ``decompressed size << 3 | method``. Methods: 0 stored,
1 LZ10 (Nintendo LZ77 without its own header), 2 / 3 Huffman with 4-bit (low nibble first) / 8-bit
symbols, 4 RLE, 5 zlib. Decoding follows Kuriimu2 (Kompression, Level5 decoders); encoding writes LZ10 or
stored, which every Level-5 decoder reads.

XPCK packs a few files (an ``.xf`` font: the ``.xi`` texture and ``fnt.bin``): a 0x14-byte header whose
offsets and sizes are stored divided by 4, 12-byte entries (CRC32 of the name, name offset, data
offset / 4 and size in 24 bits each), a compressed table of names, then the data, each file padded to 4
(Kuriimu2 ``Xpck.cs``).
"""
from __future__ import annotations

import struct
import zlib
from typing import Dict, List, Tuple

from core.containers.base_container import BaseArchiveContainer

STORED, LZ10, HUFFMAN4, HUFFMAN8, RLE, ZLIB = range(6)


def method_of(data: bytes) -> int:
    return data[0] & 7


def size_of(data: bytes) -> int:
    return struct.unpack_from("<I", data, 0)[0] >> 3


def _lz10(src: bytes, pos: int, size: int) -> bytes:
    out = bytearray()
    n = len(src)
    while len(out) < size:
        flags = src[pos]
        pos += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                if pos + 1 >= n:
                    raise ValueError("Level-5 LZ10: data cut short")
                b1, b2 = src[pos], src[pos + 1]
                pos += 2
                length = (b1 >> 4) + 3
                disp = ((b1 & 0x0F) << 8 | b2) + 1
                if disp > len(out):
                    raise ValueError("Level-5 LZ10: back-reference before the start")
                start = len(out) - disp
                if disp >= length:
                    out += out[start:start + length]
                else:
                    for k in range(length):
                        out.append(out[start + k])
            else:
                out.append(src[pos])
                pos += 1
    return bytes(out[:size])


def _huffman(src: bytes, pos: int, size: int, depth: int) -> bytes:
    count = size * 8 // depth
    tree_size = src[pos]
    root = src[pos + 1]
    tree = src[pos + 2:pos + 2 + tree_size * 2]
    pos += 2 + tree_size * 2
    result = bytearray(count)
    i = code = nxt = 0
    node = root
    done = 0
    while done < count:
        if i % 32 == 0:
            code = struct.unpack_from("<I", src, pos)[0]
            pos += 4
        nxt += ((node & 0x3F) << 1) + 2
        direction = 2 if (code >> (31 - i % 32)) & 1 == 0 else 1
        leaf = (node >> 5 >> direction) & 1
        node = tree[nxt - direction]
        if leaf:
            result[done] = node
            done += 1
            node = root
            nxt = 0
        i += 1
    if depth == 8:
        return bytes(result)
    return bytes(result[2 * j] | result[2 * j + 1] << 4 for j in range(size))


def _rle(src: bytes, pos: int, size: int) -> bytes:
    out = bytearray()
    while len(out) < size:
        flag = src[pos]
        pos += 1
        if flag & 0x80:
            out += bytes([src[pos]]) * ((flag & 0x7F) + 3)
            pos += 1
        else:
            out += src[pos:pos + flag + 1]
            pos += flag + 1
    return bytes(out[:size])


def decompress(data: bytes) -> bytes:
    """The data behind a Level-5 compression header."""
    data = bytes(data)
    method, size = method_of(data), size_of(data)
    if method == STORED:
        return data[4:4 + size]
    if method == LZ10:
        return _lz10(data, 4, size)
    if method in (HUFFMAN4, HUFFMAN8):
        return _huffman(data, 4, size, 4 if method == HUFFMAN4 else 8)
    if method == RLE:
        return _rle(data, 4, size)
    if method == ZLIB:
        return zlib.decompress(data[4:])
    raise ValueError(f"Unknown Level-5 compression method {method}")


def _header(size: int, method: int) -> bytes:
    if size >= 1 << 29:
        raise ValueError("Too large for a Level-5 compression header")
    return struct.pack("<I", size << 3 | method)


def lz10_encode(data: bytes) -> bytes:
    """LZ10 body (no header): greedy matches, window 4096, lengths 3..18."""
    n = len(data)
    out = bytearray()
    heads: Dict[bytes, List[int]] = {}
    pos = 0
    while pos < n:
        flag_at = len(out)
        out.append(0)
        flags = 0
        for bit in range(8):
            if pos >= n:
                break
            best_len = best_disp = 0
            if pos + 3 <= n:
                key = data[pos:pos + 3]
                chain = heads.get(key)
                if chain:
                    limit = min(18, n - pos)
                    for cand in reversed(chain[-64:]):     # ponytail: 64 candidates per key; widen if ratio matters
                        disp = pos - cand
                        if disp > 0x1000:
                            break
                        length = 3
                        while length < limit and data[cand + length] == data[pos + length]:
                            length += 1
                        if length > best_len:
                            best_len, best_disp = length, disp
                            if length == limit:
                                break
            step = best_len if best_len >= 3 else 1
            if best_len >= 3:
                flags |= 0x80 >> bit
                value = (best_len - 3) << 12 | (best_disp - 1)
                out += bytes((value >> 8, value & 0xFF))
            else:
                out.append(data[pos])
            for p in range(pos, min(pos + step, n - 2)):
                heads.setdefault(data[p:p + 3], []).append(p)
            pos += step
        out[flag_at] = flags
    return bytes(out)


def compress(data: bytes, method: int = LZ10) -> bytes:
    """``data`` behind a Level-5 header: LZ10, stored or zlib (Huffman and RLE are written as LZ10)."""
    data = bytes(data)
    if method == STORED:
        return _header(len(data), STORED) + data
    if method == ZLIB:
        return _header(len(data), ZLIB) + zlib.compress(data, 9)
    return _header(len(data), LZ10) + lz10_encode(data)


def recompress(original: bytes, data: bytes) -> bytes:
    """``data`` compressed like ``original``: the original bytes when they already hold ``data``."""
    if decompress(original) == data:
        return bytes(original)
    return compress(data, method_of(original) if method_of(original) in (STORED, ZLIB) else LZ10)


# -- XPCK --------------------------------------------------------------------------------


class Xpck:
    """A parsed XPCK: ``files`` (name -> stored bytes, in table order). ``build()`` lays them out again."""

    HEADER = 0x14

    def __init__(self, raw: bytes):
        raw = bytes(raw)
        if raw[:4] != b"XPCK":
            raise ValueError("Not an XPCK pack")
        self.raw = raw
        fc1, fc2 = raw[4], raw[5]
        count = (fc2 & 0x0F) << 8 | fc1
        info, names_off, data_off, _info_size, names_size = (v << 2 for v in struct.unpack_from("<5H", raw, 6))
        self.name_method = method_of(raw[names_off:])
        names = decompress(raw[names_off:names_off + names_size])
        self.entries: List[Tuple[int, int, int, int, int]] = []      # hash, name offset, offset, size, raw tail
        self.files: Dict[str, bytes] = {}
        for index in range(count):
            crc, name_at, lo_off, lo_size, hi_off, hi_size = struct.unpack_from("<IHHHBB", raw, info + index * 12)
            offset = (hi_off << 16 | lo_off) << 2
            size = hi_size << 16 | lo_size
            name = names[name_at:names.index(b"\0", name_at)].decode("ascii")
            self.entries.append((crc, name_at, offset, size, index))
            self.files[name] = raw[data_off + offset:data_off + offset + size]
        self.data_offset = data_off

    def build(self) -> bytes:
        """The pack with the current ``files``; the original bytes when nothing changed."""
        names = list(self.files)
        if all(self.files[name] == self.raw[self.data_offset + off:self.data_offset + off + size]
               for name, (_c, _n, off, size, _i) in zip(names, self.entries)):
            return self.raw
        info = self.HEADER
        names_off = info + 12 * len(names)
        head = bytearray(self.raw[:struct.unpack_from("<H", self.raw, 10)[0] << 2])   # header .. data start
        if len(head) < names_off:
            raise ValueError("XPCK header area is smaller than its table")
        order = sorted(range(len(names)), key=lambda i: self.entries[i][2])
        body = bytearray()
        spans = {}
        for index in order:
            blob = self.files[names[index]]
            start = len(body)
            body += blob
            body += b"\0" * (-len(body) % 4 or 4)
            spans[index] = (start, len(blob))
        for index, (crc, name_at, _off, _size, _i) in enumerate(self.entries):
            start, size = spans[index]
            struct.pack_into("<IHHHBB", head, info + index * 12, crc, name_at, (start >> 2) & 0xFFFF, size & 0xFFFF,
                             start >> 18, size >> 16)
        struct.pack_into("<I", head, 0x10, len(body) >> 2)
        return bytes(head) + bytes(body)


class XpckContainer(BaseArchiveContainer):
    """An XPCK pack (``.xa``, ``.xc``, ``.xf``...) as an archive: members keep their bytes, order and names."""

    MAGIC = b"XPCK"

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return bytes(data[:4]) == cls.MAGIC

    def __init__(self, data: bytes) -> None:
        self._pack = Xpck(data)
        self._overlay: Dict[str, bytes] = {}

    def list_files(self) -> List[str]:
        return list(self._pack.files)

    def read_file(self, path: str) -> bytes:
        if path in self._overlay:
            return self._overlay[path]
        return self._pack.files[path]

    def write_file(self, path: str, data: bytes) -> None:
        if path not in self._pack.files:
            raise KeyError(path)
        self._overlay[path] = bytes(data)

    def pack(self) -> bytes:
        self._pack.files.update(self._overlay)
        self._overlay.clear()
        return self._pack.build()
