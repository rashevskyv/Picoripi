"""Little- and big-endian cursors over bytes, used by the Unity serialized-file and type-tree readers.

``Reader`` moves through a buffer; ``Writer`` appends to one. Both take the byte order as ``"<"`` or ``">"``. A short
read raises ``EOFError``. Strings are C strings (UTF-8, ended by a zero byte) or Unity's aligned strings (an int32
length, the bytes, then zero bytes up to a multiple of four).
"""
from __future__ import annotations

import struct


class Reader:
    def __init__(self, data: bytes, pos: int = 0, endian: str = "<"):
        self.data = data
        self.pos = pos
        self.endian = endian

    def _take(self, count: int) -> bytes:
        end = self.pos + count
        if count < 0 or end > len(self.data):
            raise EOFError(f"read of {count} bytes at {self.pos} runs past {len(self.data)}")
        chunk = self.data[self.pos:end]
        self.pos = end
        return chunk

    def unpack(self, fmt: str):
        return struct.unpack(self.endian + fmt, self._take(struct.calcsize(self.endian + fmt)))[0]

    def bytes(self, count: int) -> bytes:
        return self._take(count)

    def align(self, alignment: int = 4) -> None:
        self.pos += (alignment - self.pos % alignment) % alignment

    def cstr(self) -> str:
        end = self.data.index(b"\x00", self.pos)
        text = self.data[self.pos:end].decode("utf-8", "replace")
        self.pos = end + 1
        return text

    def aligned_str(self) -> str:
        length = self.unpack("i")
        if 0 < length <= len(self.data) - self.pos:
            text = self._take(length).decode("utf-8", "surrogateescape")
            self.align()
            return text
        return ""


class Writer:
    def __init__(self, endian: str = "<"):
        self.buf = bytearray()
        self.endian = endian

    def pack(self, fmt: str, value) -> None:
        self.buf += struct.pack(self.endian + fmt, value)

    def bytes(self, value: bytes) -> None:
        self.buf += value

    def align(self, alignment: int = 4) -> None:
        self.buf += b"\x00" * ((alignment - len(self.buf) % alignment) % alignment)

    def cstr(self, text: str) -> None:
        self.buf += text.encode("utf-8") + b"\x00"

    def aligned_str(self, text: str) -> None:
        raw = text.encode("utf-8", "surrogateescape")
        self.pack("i", len(raw))
        self.buf += raw
        self.align()
