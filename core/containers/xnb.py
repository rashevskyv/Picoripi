"""MonoGame / XNA ``.xnb`` container, uncompressed (header flag 0x00): the reader and writer of the object
graph, and the ``Texture2D`` block a SpriteFont or a picture carries.

The file is ``XNB`` + platform + version + flags + size, then the type-reader table, the shared-resource
count and the primary object. Objects are written as a 7-bit type index (0 for null) and their fields.
Compressed files (flag 0x80, LZX) raise ``ValueError``.

Writing keeps the bytes before the object the reader stopped at, and the type indices it read, so a file
that is read and written again without edits comes back byte for byte.
"""
from __future__ import annotations

from core.i18n import tr
import struct
from dataclasses import dataclass
from typing import List, Optional


class Reader:
    def __init__(self, data: bytes, pos: int = 0):
        self.data = data
        self.pos = pos

    def u8(self) -> int:
        value = self.data[self.pos]
        self.pos += 1
        return value

    def unpack(self, fmt: str):
        value = struct.unpack_from("<" + fmt, self.data, self.pos)
        self.pos += struct.calcsize("<" + fmt)
        return value

    def i32(self) -> int:
        return self.unpack("i")[0]

    def f32(self) -> float:
        return self.unpack("f")[0]

    def v7(self) -> int:
        """7-bit encoded integer (BinaryReader.Read7BitEncodedInt)."""
        result = shift = 0
        while True:
            byte = self.u8()
            result |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return result
            shift += 7

    def string(self) -> str:
        length = self.v7()
        raw = self.data[self.pos:self.pos + length]
        self.pos += length
        return raw.decode("utf-8")

    def char(self) -> str:
        """One character as BinaryReader.ReadChar reads it: UTF-8, 1 to 3 bytes."""
        lead = self.u8()
        if lead < 0x80:
            return chr(lead)
        if lead & 0xE0 == 0xC0:
            return chr(((lead & 0x1F) << 6) | (self.u8() & 0x3F))
        if lead & 0xF0 == 0xE0:
            second, third = self.u8(), self.u8()
            return chr(((lead & 0x0F) << 12) | ((second & 0x3F) << 6) | (third & 0x3F))
        raise ValueError(tr("unsupported UTF-8 lead byte {0:#x} in an XNB character", lead))


def write7(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def write_char(char: str) -> bytes:
    return char.encode("utf-8")


@dataclass
class Xnb:
    """A parsed file: the type names, the bytes before the primary object, and the reader after the header."""

    type_names: List[str]
    head: bytes          # file bytes up to (not including) the primary object's type index
    reader: Reader       # positioned at the primary object's type index

    def type_of(self, index: int) -> str:
        return self.type_names[index - 1]


def open_xnb(data: bytes) -> Xnb:
    """Parse the header and the type-reader table. Raises ``ValueError`` for a compressed or foreign file."""
    if bytes(data[:3]) != b"XNB":
        raise ValueError(tr("not an XNB file"))
    if data[5] & 0x80:
        raise ValueError(tr("compressed XNB (LZX) is not read here"))
    reader = Reader(data, 10)
    names = []
    for _ in range(reader.v7()):
        names.append(reader.string())
        reader.i32()  # reader version
    reader.v7()  # shared resources
    head_end = reader.pos
    return Xnb(type_names=[name.split(",")[0] for name in names], head=bytes(data[:head_end]), reader=reader)


@dataclass
class Texture2D:
    """The fields of a Texture2D: the surface format number, size, and the mip bytes (one mip)."""

    surface_format: int
    width: int
    height: int
    mip: bytes


def read_texture2d(reader: Reader) -> Texture2D:
    fmt, width, height, mips = reader.unpack("iiii")
    if mips != 1:
        raise ValueError(tr("{0} mip levels: only one is supported", mips))
    size = reader.i32()
    mip = reader.data[reader.pos:reader.pos + size]
    reader.pos += size
    return Texture2D(fmt, width, height, bytes(mip))


def write_texture2d(texture: Texture2D) -> bytes:
    return struct.pack("<iiiii", texture.surface_format, texture.width, texture.height, 1, len(texture.mip)) \
        + texture.mip


def finish(out: bytearray) -> bytes:
    """Write the total size into the header (bytes 6 to 10)."""
    out[6:10] = struct.pack("<I", len(out))
    return bytes(out)


def is_xnb(data: bytes) -> Optional[str]:
    """``'w'`` for a Windows XNB (the platform byte), else None."""
    return chr(data[3]) if bytes(data[:3]) == b"XNB" and len(data) > 10 else None
