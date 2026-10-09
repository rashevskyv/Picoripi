"""Final Fantasy XII: Revenant Wings ``.dpk`` packs as archives the Font Editor and the Textures window open.

A pack (``rwtext.dpk_members``): u32 count, (u32 id, u32 offset, u32 size) per member, members 16-byte aligned
with ``EE`` filler. Members are named ``#<index>``. A member stored LZ10 packed (the mission title pictures)
is read unpacked and packed again when it changes; a font or NARC member is read up to its own size (the
pack's filler behind it stays). An unchanged pack gives its original bytes back.
"""
from __future__ import annotations

import struct
from typing import List, Optional, Tuple

from core.containers import lz10
from core.containers.base_container import BaseArchiveContainer

from .rwtext import EE, dpk_members, dpk_pack


def _looks_like_dpk(data: bytes) -> bool:
    if len(data) < 16:
        return False
    count = struct.unpack_from("<I", data, 0)[0]
    head = 4 + 12 * count
    if not 0 < count < 4096 or head > len(data):
        return False
    first = head + (-head % 16)
    at = first
    for i in range(count):
        _ident, offset, size = struct.unpack_from("<III", data, 4 + 12 * i)
        if offset != at or offset + size > len(data):
            return False
        at = offset + size + (-size % 16)
    return at == len(data)


def _unpack(member: bytes) -> Optional[bytes]:
    """The LZ10 payload of ``member``, or None when it is stored plain."""
    if member[:1] != b"\x10" or len(member) < 8:
        return None
    try:
        plain, end = lz10.decompress(member)
    except (ValueError, IndexError):
        return None
    return plain if len(member) - end < 16 and plain[:4] in (b"NARC", b"RTFN", b"RGCN", b"RLCN") else None


class DpkContainer(BaseArchiveContainer):
    """A ``.dpk`` pack: members ``#0``, ``#1``... (LZ10 members shown unpacked)."""

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return _looks_like_dpk(bytes(data))

    def __init__(self, data: bytes) -> None:
        self._original = bytes(data)
        self._members: List[Tuple[int, bytes]] = dpk_members(self._original)
        self._plain: List[Optional[bytes]] = [_unpack(member) for _ident, member in self._members]
        self._changed = False

    def list_files(self) -> list[str]:
        return [f"#{i}" for i in range(len(self._members))]

    def _index(self, path: str) -> int:
        try:
            return int(str(path).lstrip("#"))
        except ValueError:
            raise KeyError(f"No {path} in the pack") from None

    def _split(self, index: int) -> Tuple[bytes, bytes]:
        """``(file, filler)``: a NITRO file stops at its own size; the pack's filler after it is kept apart."""
        plain = self._plain[index]
        data = plain if plain is not None else self._members[index][1]
        if plain is None and data[:4] in (b"RTFN", b"NARC") and len(data) >= 12:
            size = struct.unpack_from("<I", data, 8)[0]
            if size <= len(data):
                return data[:size], data[size:]
        return data, b""

    def read_file(self, path: str) -> bytes:
        return self._split(self._index(path))[0]

    def write_file(self, path: str, data: bytes) -> None:
        index = self._index(path)
        old, filler = self._split(index)
        if bytes(data) == old:
            return
        ident, _old = self._members[index]
        if self._plain[index] is not None:
            self._plain[index] = bytes(data)
            data = lz10.compress(bytes(data))
        self._members[index] = (ident, bytes(data) + filler)
        self._changed = True

    def has_pending_changes(self) -> bool:
        return self._changed

    def pack(self) -> bytes:
        if not self._changed:
            return self._original
        count = len(self._members)
        head = 4 + 12 * count
        fill = self._original[head:head + (-head % 16)][-1:] or EE
        return dpk_pack(self._members, fill)
