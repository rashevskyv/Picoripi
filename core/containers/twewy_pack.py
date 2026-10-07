"""The World Ends with You (DS): the ``pack`` archive of its graphics and font files (``Grp_*.bin``).

Layout (little endian): ``"pack"``, u32 slot count N, u32 data size (file size - header), 20 zero bytes,
then N slots ``(u32 offset from byte 0x20, u32 size)``; an unused slot is ``(0, 0)``. Member ``#0`` is a
32-byte descriptor: u32 count of the other used slots, u32 the data size again. The last used slot is 32
zero bytes. Members follow the header in slot order, 32-byte aligned, zero filled. A member is stored plain
or as a GBA LZ77 (``0x10``) stream; packs nest (a member is often a packed ``pack``).

Members are named ``#<slot>`` and read decompressed; a member written back is compressed again when it was
stored compressed (Vram-safe LZ77, so the game may unpack it straight into video memory). An unchanged pack
is returned byte for byte; every pack of the game re-laid out from its own members gives its own bytes.
"""
from __future__ import annotations

import struct
from typing import Dict, List, Optional, Tuple

from core.containers import lz10
from core.containers.base_container import BaseArchiveContainer

MAGIC = b"pack"
ALIGN = 0x20


def slots(data: bytes) -> List[Tuple[int, int]]:
    """``(offset in the file, size)`` per slot; ValueError when ``data`` is not a pack."""
    if data[:4] != MAGIC or len(data) < 0x20:
        raise ValueError("not a pack archive")
    count = struct.unpack_from("<I", data, 4)[0]
    if not 1 <= count <= 0x1000 or 0x20 + 8 * count > len(data):
        raise ValueError("pack archive with a bad slot count")
    out = []
    for i in range(count):
        offset, size = struct.unpack_from("<II", data, 0x20 + 8 * i)
        if size and 0x20 + offset + size > len(data):
            raise ValueError(f"pack slot {i} runs past the end of the file")
        out.append((0x20 + offset if size else 0, size))
    return out


def unpack_member(stored: bytes) -> Tuple[bytes, bool]:
    """``(plain bytes, was compressed)`` of a stored member."""
    if stored[:1] == b"\x10" and len(stored) >= 4:
        try:
            plain, end = lz10.decompress(stored)
        except ValueError:
            return stored, False
        if len(stored) - end < 4:          # the stream fills the member (padding at most 3 bytes)
            return plain, True
    return stored, False


def build(original: bytes, members: List[Optional[bytes]]) -> bytes:
    """``original`` (a pack) laid out again with ``members`` (stored bytes per slot, None = unused)."""
    count = len(members)
    head = 0x20 + 8 * count
    out = bytearray(original[:head])
    body = bytearray()
    for i, member in enumerate(members):
        if not member:
            struct.pack_into("<II", out, 0x20 + 8 * i, 0, 0)
            continue
        struct.pack_into("<II", out, 0x20 + 8 * i, head + len(body) - 0x20, len(member))
        body += member + bytes(-len(member) % ALIGN)
    out += body
    struct.pack_into("<I", out, 8, len(body))
    if members and members[0] and len(members[0]) >= 8:                # the descriptor repeats the data size
        descriptor = bytearray(members[0])
        struct.pack_into("<I", descriptor, 4, len(body))
        out[head:head + len(descriptor)] = descriptor
    return bytes(out)


class TwewyPack(BaseArchiveContainer):
    """A ``pack`` archive: members ``#<slot>``, read decompressed, written back as they were stored."""

    MAGIC = MAGIC

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        try:
            slots(bytes(data))
        except (ValueError, struct.error):
            return False
        return True

    def __init__(self, data: bytes) -> None:
        self._data = bytes(data)
        self._slots = slots(self._data)
        self._changed: Dict[int, bytes] = {}

    def _stored(self, index: int) -> bytes:
        offset, size = self._slots[index]
        return self._data[offset:offset + size]

    def list_files(self) -> list[str]:
        return [f"#{i}" for i, (_offset, size) in enumerate(self._slots) if size]

    def _index(self, path: str) -> int:
        index = int(str(path).lstrip("#"))
        if not 0 <= index < len(self._slots) or not self._slots[index][1]:
            raise KeyError(path)
        return index

    def read_original(self, path: str) -> bytes:
        return unpack_member(self._stored(self._index(path)))[0]

    def read_file(self, path: str) -> bytes:
        index = self._index(path)
        return self._changed.get(index) or unpack_member(self._stored(index))[0]

    def write_file(self, path: str, data: bytes) -> None:
        self._changed[self._index(path)] = bytes(data)

    def pack(self) -> bytes:
        members: List[Optional[bytes]] = []
        changed = False
        for index in range(len(self._slots)):
            stored = self._stored(index) if self._slots[index][1] else None
            new = self._changed.get(index)
            if stored is not None and new is not None:
                plain, compressed = unpack_member(stored)
                if new != plain:
                    stored = lz10.compress(new, vram=True) if compressed else new
                    changed = True
            members.append(stored)
        return build(self._data, members) if changed else self._data
