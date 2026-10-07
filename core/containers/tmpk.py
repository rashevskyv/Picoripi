"""TMPK packs (Twilight Princess HD ``*.pack.gz`` once gunzipped): named files at fixed, aligned offsets.

Header: ``TMPK``, u32 file count, u32 alignment, u32 0; then per file 0x10 bytes: u32 name offset, u32 data
offset, u32 size, u32 0 (big endian, offsets from the start). The HD game keeps the GX2 textures (``.gtx``) of
an archive's BTI and BMD files here. A member is written in place, so it must keep its size.
"""
from __future__ import annotations

import struct
from typing import Dict, List, Tuple

from core.containers.base_container import BaseArchiveContainer


class TmpkContainer(BaseArchiveContainer):
    MAGIC = b"TMPK"

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return data[:4] == cls.MAGIC

    def __init__(self, data: bytes) -> None:
        self._data = bytearray(data)
        self._files: Dict[str, Tuple[int, int]] = {}
        for index in range(struct.unpack_from(">I", data, 4)[0]):
            name_at, at, size = struct.unpack_from(">III", data, 0x10 + 0x10 * index)
            name = bytes(data[name_at:data.index(b"\0", name_at)]).decode("utf-8")
            self._files[name] = (at, size)

    def list_files(self) -> List[str]:
        return list(self._files)

    def read_file(self, path: str) -> bytes:
        at, size = self._files[path]
        return bytes(self._data[at:at + size])

    def write_file(self, path: str, data: bytes) -> None:
        at, size = self._files[path]
        if len(data) != size:
            raise ValueError(f"{path}: a TMPK member keeps its size ({size} bytes, not {len(data)})")
        self._data[at:at + size] = data

    def pack(self) -> bytes:
        return bytes(self._data)
