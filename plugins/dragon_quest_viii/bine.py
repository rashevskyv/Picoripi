"""Dragon Quest VIII (3DS) ``.binE`` message tables (``data/Message/eng``, ``data/Script/field/message/eng``).

Layout: u32 group count, u32 string count, u32 ids[count], u32 group sizes[groups] (they add up to the count),
u32 offsets[count] (absolute, ascending), then the UTF-8 strings, each ending with the literal ``[end]``.
The other language slots (``fre``, ``ger``, ``ita``, ``spa``) have the same layout.
"""
from __future__ import annotations

import struct
from typing import List, Sequence

END = b"[end]"


class FormatError(ValueError):
    pass


class Table:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.ids: List[int] = []
        self.head = raw
        self.entries: List[bytes] = []
        if not raw:
            return                                   # msg_facility.binE is empty
        if len(raw) < 8:
            raise FormatError("too short for a binE table")
        groups, count = struct.unpack_from("<II", raw, 0)
        head = 8 + count * 4 + groups * 4 + count * 4
        if groups > 4096 or head > len(raw):
            raise FormatError("not a binE table")
        self.raw = raw
        self.ids = list(struct.unpack_from(f"<{count}I", raw, 8))
        sizes = struct.unpack_from(f"<{groups}I", raw, 8 + count * 4)
        if sum(sizes) != count:
            raise FormatError("group sizes do not add up to the string count")
        self.head = raw[:head - count * 4]           # groups, count, ids, group sizes
        offsets = struct.unpack_from(f"<{count}I", raw, 8 + count * 4 + groups * 4)
        self.entries: List[bytes] = []
        for i, at in enumerate(offsets):
            end = offsets[i + 1] if i + 1 < count else len(raw)
            blob = raw[at:end]
            if not blob.endswith(END):
                raise FormatError(f"string {i} does not end with [end]")
            self.entries.append(blob[:-len(END)])

    def texts(self) -> List[str]:
        return [e.decode("utf-8") for e in self.entries]

    def build(self, texts: Sequence[str]) -> bytes:
        if len(texts) != len(self.entries):
            raise FormatError(f"{len(texts)} strings for {len(self.entries)} entries")
        blobs = [str(t).encode("utf-8") + END for t in texts]
        at = len(self.head) + len(blobs) * 4
        offsets = []
        for blob in blobs:
            offsets.append(at)
            at += len(blob)
        return self.head + struct.pack(f"<{len(blobs)}I", *offsets) + b"".join(blobs)
