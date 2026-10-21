"""Wii archives of MadWorld's HOME Menu and disc banner: U8 archives, LZ77 (type 0x10) streams, the IMET channel banner
header and IMD5 wrappers. ``explode`` lists the picture, font and CSV members; ``replace`` writes one member back and
keeps every other byte of the archive's layout.
"""
from __future__ import annotations

import hashlib
import struct
from typing import Callable, Dict, Tuple

U8_MAGIC = b"\x55\xaa\x38\x2d"
MEMBERS = (".tpl", ".brfnt", ".csv")


class U8:
    """A U8 archive: ``files`` {path: bytes} in node order; ``build()`` keeps names, order and 0x20 alignment."""

    def __init__(self, raw: bytes) -> None:
        if raw[:4] != U8_MAGIC:
            raise ValueError("not a U8 archive")
        self.raw = raw
        root, _size, self.data_off = struct.unpack_from(">III", raw, 4)
        total = struct.unpack_from(">I", raw, root + 8)[0]
        names = root + total * 12
        self.nodes = [(word >> 24, word & 0xFFFFFF, off, size) for word, off, size in
                      (struct.unpack_from(">III", raw, root + i * 12) for i in range(total))]
        self.node_at = [root + i * 12 for i in range(total)]
        self.files: Dict[str, bytes] = {}
        self.index: Dict[str, int] = {}

        def walk(first: int, end: int, prefix: str) -> None:
            i = first
            while i < end:
                kind, name_off, off, size = self.nodes[i]
                name = raw[names + name_off:raw.index(b"\0", names + name_off)].decode("ascii")
                if kind == 1:
                    walk(i + 1, size, prefix + name + "/")
                    i = size
                else:
                    self.files[prefix + name] = raw[off:off + size]
                    self.index[prefix + name] = i
                    i += 1

        walk(1, total, "")

    def build(self) -> bytes:
        head = bytearray(self.raw[:self.data_off])
        order = sorted(self.files, key=lambda p: self.nodes[self.index[p]][2])
        data = bytearray()
        for path in order:
            data += bytes(-len(data) % 0x20)
            struct.pack_into(">II", head, self.node_at[self.index[path]] + 4, self.data_off + len(data),
                             len(self.files[path]))
            data += self.files[path]
        last = max(off + size for kind, _n, off, size in self.nodes if kind == 0) if self.files else self.data_off
        return bytes(head) + bytes(data) + self.raw[last:]


def lz_decompress(data: bytes, at: int = 0) -> bytes:
    size, pos, out = int.from_bytes(data[at + 1:at + 4], "little"), at + 4, bytearray()
    while len(out) < size:
        flags = data[pos]
        pos += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                token = data[pos] << 8 | data[pos + 1]
                pos += 2
                back = (token & 0xFFF) + 1
                for _ in range((token >> 12) + 3):
                    out.append(out[-back])
            else:
                out.append(data[pos])
                pos += 1
    return bytes(out)


def lz_compress(data: bytes) -> bytes:
    """Greedy LZ77 type 0x10 (window 4096, lengths 3..18), padded to 4 bytes."""
    n, out, heads, pos = len(data), bytearray(b"\x10" + len(data).to_bytes(3, "little")), {}, 0
    while pos < n:
        flag_at = len(out)
        out.append(0)
        for bit in range(8):
            if pos >= n:
                break
            best = dist = 0
            for cand in reversed(heads.get(data[pos:pos + 3], [])[-64:]):
                back = pos - cand
                if back > 0x1000:
                    break
                limit, length = min(18, n - pos), 0
                while length < limit and data[cand + length] == data[pos + length]:
                    length += 1
                if length > best:
                    best, dist = length, back
                    if length == limit:
                        break
            if best >= 3:
                out[flag_at] |= 0x80 >> bit
                out += ((best - 3) << 12 | (dist - 1)).to_bytes(2, "big")
            else:
                best = 1
                out.append(data[pos])
            for p in range(pos, min(pos + best, n - 2)):
                heads.setdefault(data[p:p + 3], []).append(p)
            pos += best
    return bytes(out + bytes(-len(out) % 4))


def unwrap(raw: bytes) -> Tuple[bytes, Callable[[bytes], bytes]]:
    """``(inner U8 bytes, inner -> stored bytes)`` for a U8, an IMET channel banner, an IMD5 member or an LZ77 stream.

    Raises ValueError when ``raw`` is none of them.
    """
    if raw[:4] == U8_MAGIC:
        return raw, lambda new: new
    if raw[0x40:0x44] == b"IMET" and raw[0x600:0x604] == U8_MAGIC:
        head = raw[:0x600]
        return raw[0x600:], lambda new: head + new
    if raw[:4] == b"IMD5" and raw[32:36] == b"LZ77":
        def imd5(new: bytes) -> bytes:
            payload = b"LZ77" + lz_compress(new)
            return b"IMD5" + struct.pack(">I", len(payload)) + bytes(8) + hashlib.md5(payload).digest() + payload
        return lz_decompress(raw, 36), imd5
    if raw[:1] == b"\x10" and len(raw) > 8:
        try:
            inner = lz_decompress(raw)
        except IndexError:
            inner = None
        if inner is not None and inner[:4] == U8_MAGIC:
            return inner, lz_compress
    raise ValueError("not a U8 archive, an LZ77 stream or a channel banner")


def _is_archive(data: bytes) -> bool:
    try:
        unwrap(data)
    except (ValueError, struct.error):
        return False
    return True


def explode(raw: bytes, prefix: str, put: Callable[[str, bytes], None]) -> None:
    """Call ``put(path, bytes)`` for each picture, font or CSV member of the archive ``raw``, nested archives included."""
    if not _is_archive(raw):
        raise ValueError(f"{prefix}: not an archive")
    inner, _wrap = unwrap(raw)
    for member, data in U8(inner).files.items():
        if _is_archive(data):
            found, _w = unwrap(data)
            if found[:4] == U8_MAGIC:       # an IMD5 member may hold sound, not an archive
                explode(data, f"{prefix}/{member}", put)
                continue
        if member.lower().endswith(MEMBERS):
            put(f"{prefix}/{member}", data)


def replace(raw: bytes, path: str, new: bytes) -> bytes:
    """``raw`` (an archive, maybe wrapped) with member ``path`` (maybe inside nested archives) set to ``new``."""
    inner, wrap = unwrap(raw)
    u8 = U8(inner)
    parts = path.split("/")
    for cut in range(len(parts), 0, -1):
        member = "/".join(parts[:cut])
        if member in u8.files:
            rest = "/".join(parts[cut:])
            u8.files[member] = replace(u8.files[member], rest, new) if rest else new
            return wrap(u8.build())
    raise ValueError(f"{path}: no such file in the archive")
