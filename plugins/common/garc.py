"""GARC archives of the Pokémon 3DS games: v4 (generation 6) and v6 (generation 7).

A GARC keeps per file a list of sub-files (``bit``, start, end, length). A sub-file is stored as bytes that may be
LZ11 compressed. ``member`` returns the plain bytes and whether they were compressed, so ``rebuild`` can store a
changed member the same way. The layout follows the workspace tool ``zt/pkgen6.py`` and ``zt/pkgen7.py``.
ponytail: ``rebuild`` keeps the FAT shape and writes the changed members; the header fields it sets are the ones
the games read (largest member, data size).
"""
from __future__ import annotations

import struct
from typing import Dict, List, Tuple

from core.containers.nitro import lz11_compress, lz11_decompress

Replace = Dict[Tuple[int, int], bytes]
VERSIONS = (0x0400, 0x0600)


class GarcError(ValueError):
    """The bytes are not a GARC this module reads."""


def unwrap(raw: bytes) -> Tuple[bytes, bool]:
    """``(plain bytes, was LZ11 compressed)``. Bytes that do not decode as LZ11 are returned as they are."""
    if len(raw) > 4 and raw[0] == 0x11:
        try:
            return lz11_decompress(raw)[0], True
        except (ValueError, IndexError):
            pass
    return raw, False


def wrap(plain: bytes, compressed: bool) -> bytes:
    """The stored bytes of a member: LZ11 again when the original was compressed."""
    return lz11_compress(plain) if compressed else plain


class Garc:
    """One GARC archive. ``files[index]`` is the list of its sub-files, in table order."""

    def __init__(self, data: bytes) -> None:
        if data[:4] != b"CRAG":
            raise GarcError("not a GARC archive")
        self.data = data
        hsize, _bom, self.version, _chunks, self.data_off, _fsize = struct.unpack_from("<IHHIII", data, 4)
        if self.version not in VERSIONS:
            raise GarcError(f"GARC version {self.version:#x} is not read (v4 or v6)")
        self.hsize = hsize
        fato_size, count = struct.unpack_from("<IH", data, hsize + 4)
        self.fatb = hsize + fato_size
        self.fatb_size = struct.unpack_from("<I", data, self.fatb + 4)[0]
        self.files: List[List[Tuple[int, int, int, int]]] = []
        p = self.fatb + 12
        for _ in range(count):
            vector = struct.unpack_from("<I", data, p)[0]
            p += 4
            subs = []
            for bit in range(32):
                if vector & (1 << bit):
                    subs.append((bit,) + struct.unpack_from("<III", data, p))
                    p += 12
            self.files.append(subs)

    def bits(self, index: int) -> List[int]:
        return [bit for bit, *_ in self.files[index]]

    def stored(self, index: int, bit: int) -> bytes:
        """The stored (possibly compressed) bytes of one sub-file."""
        for b, start, _end, length in self.files[index]:
            if b == bit:
                return self.data[self.data_off + start:self.data_off + start + length]
        raise GarcError(f"file {index} has no sub-file {bit}")

    def member(self, index: int, bit: int) -> Tuple[bytes, bool]:
        """``(plain bytes, was compressed)`` of one sub-file."""
        return unwrap(self.stored(index, bit))

    def rebuild(self, replace: Replace) -> bytes:
        """The archive with ``replace`` ({(index, bit): stored bytes}) put in. Other sub-files keep their bytes."""
        fatb = bytearray(self.data[self.fatb:self.fatb + self.fatb_size])
        body, p, largest = bytearray(), 12, 0
        for index, subs in enumerate(self.files):
            p += 4
            for bit, _start, _end, _length in subs:
                blob = replace.get((index, bit))
                if blob is None:
                    blob = self.stored(index, bit)
                start = len(body)
                body += blob
                body += b"\xff" * (-len(body) % 4)           # the games pad members with 0xFF
                struct.pack_into("<III", fatb, p, start, len(body), len(blob))
                largest = max(largest, len(blob))
                p += 12
        head = bytearray(self.data[:self.fatb])
        fimb = struct.pack("<4sII", b"BMIF", 12, len(body))
        struct.pack_into("<I", head, 0x14, len(head) + len(fatb) + len(fimb) + len(body))
        struct.pack_into("<I", head, 0x18, (largest + 3) & ~3)   # the largest member, padded to 4 bytes
        if self.version == 0x0600:
            struct.pack_into("<I", head, 0x1C, largest)
        return bytes(head) + bytes(fatb) + fimb + bytes(body)
