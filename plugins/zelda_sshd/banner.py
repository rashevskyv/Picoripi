"""Wii disc channel banner ``opening.bnr`` as an archive, for the Textures window.

Layout: 0x40 zero bytes, the IMET header (names, decompressed sizes, MD5 of the first 0x600 bytes), then a U8
archive with ``meta/banner.bin``, ``meta/icon.bin``, ``meta/sound.bin``. Banner and icon are ``IMD5`` (u32
payload size, 8 zero bytes, MD5 of the payload) around ``LZ77`` + an LZ77 type 0x10 stream of a U8 archive with
``arc/timg/*.tpl``. This container shows those two members decompressed; a written member is compressed again
with a new IMD5 hash. The IMET header stays as it is: a texture keeps its size, so the decompressed sizes it
records do not change.
"""
from __future__ import annotations

import hashlib
import struct

from core.containers import lz10
from core.containers.base_container import BaseArchiveContainer
from core.containers.u8_container import U8Container

_IMET_AT, _U8_AT = 0x40, 0x600


def _unwrap(stored: bytes) -> bytes:
    if stored[:4] == b"IMD5" and stored[32:36] == b"LZ77":
        return lz10.decompress(stored, 36)[0]
    return stored


class WiiBannerContainer(BaseArchiveContainer):
    """``opening.bnr``: its U8 members, banner and icon decompressed."""

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return data[_IMET_AT:_IMET_AT + 4] == b"IMET" and data[_U8_AT:_U8_AT + 4] == b"\x55\xaa\x38\x2d"

    def __init__(self, data: bytes) -> None:
        self._head = bytes(data[:_U8_AT])
        self._u8 = U8Container(bytes(data[_U8_AT:]))

    def list_files(self) -> list[str]:
        return self._u8.list_files()

    def read_file(self, path: str) -> bytes:
        return _unwrap(self._u8.read_file(path))

    def write_file(self, path: str, data: bytes) -> None:
        stored = self._u8.read_file(path)
        if _unwrap(stored) == data:
            return
        if stored[:4] == b"IMD5":
            payload = b"LZ77" + lz10.compress(data)
            data = b"IMD5" + struct.pack(">I", len(payload)) + bytes(8) + hashlib.md5(payload).digest() + payload
        self._u8.write_file(path, data)

    def pack(self) -> bytes:
        return self._head + self._u8.pack()
