"""Arc System Works ``jMSG`` message files (``message/msg_en.jmsg`` of Dragon Ball Fusions, 3DS), little endian.

``jMSG``, u32 file size, u32 string count ``n``, u32 0x10; then ``n + 1`` pairs of u32 ``(key, offset)`` from 0x10:
the first pair is a header (``0x202``, 0), pair ``i`` (1..n) is a hash key and the offset of its string from 0x18,
keys and offsets both ascending. The strings follow the table: UTF-16LE, NUL-terminated, one after another in
table order; a few bytes of padding end the file. A text may change its length; the keys stay.
"""
from __future__ import annotations

import struct
from typing import List, Sequence

MAGIC = b"jMSG"


class FormatError(ValueError):
    pass


class Jmsg:
    def __init__(self, raw: bytes):
        raw = bytes(raw)
        if raw[:4] != MAGIC or len(raw) < 0x20:
            raise FormatError("not a jMSG file")
        size, count, start = struct.unpack_from("<III", raw, 4)
        if size != len(raw) or start != 0x10 or 0x10 + (count + 1) * 8 > len(raw):
            raise FormatError("bad jMSG header")
        self.raw, self.count = raw, count
        self.header = raw[0x10:0x18]
        self.keys: List[int] = []
        self.offsets: List[int] = []
        for i in range(1, count + 1):
            key, offset = struct.unpack_from("<II", raw, 0x10 + i * 8)
            self.keys.append(key)
            self.offsets.append(offset)
        self.text_at = 0x10 + (count + 1) * 8
        if count and self.offsets[0] + 0x18 != self.text_at:
            raise FormatError("the first string does not follow the table")
        self.texts: List[str] = []
        ends = 0
        for offset in self.offsets:
            at = 0x18 + offset
            end = at
            while end + 1 < len(raw) and raw[end:end + 2] != b"\0\0":
                end += 2
            self.texts.append(raw[at:end].decode("utf-16-le", "surrogatepass"))
            ends = max(ends, end + 2)
        self.tail = raw[ends:]

    def build(self, texts: Sequence[str]) -> bytes:
        if len(texts) != self.count:
            raise FormatError(f"{len(texts)} strings for {self.count} entries")
        if list(texts) == self.texts:
            return self.raw
        body, offsets = bytearray(), []
        for text in texts:
            offsets.append(self.text_at - 0x18 + len(body))
            body += str(text).encode("utf-16-le", "surrogatepass") + b"\0\0"
        out = bytearray(self.raw[:0x10 + 8])
        for key, offset in zip(self.keys, offsets):
            out += struct.pack("<II", key, offset)
        out += body + self.tail
        struct.pack_into("<I", out, 4, len(out))
        return bytes(out)
