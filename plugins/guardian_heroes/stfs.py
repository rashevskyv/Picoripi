"""Read files out of an Xbox 360 STFS package (``LIVE`` / ``PIRS`` / ``CON``): enough to unpack the game's script.

Layout (Free60 "STFS"): the header holds the title id at 0x360, the volume descriptor sits at 0x379. Its bytes are:
size, reserved, block separation, the file table's block count (u16 LE) and its first block (u24 LE). Data blocks are
0x1000 bytes; an L0 hash table precedes every 0xAA blocks, and larger tables follow at 0x70E4 blocks. A file table
entry is 64 bytes: name, flags (name length in the low 6 bits, 0x40 = blocks are consecutive, 0x80 = folder), block
count, first block, parent index and size. A non-consecutive file follows the "next block" field of the hash entries.
The package is read-only here; nothing is written back.
"""
from __future__ import annotations

import struct
from typing import BinaryIO, Dict, Iterator, List, Optional, Tuple

MAGICS = (b"LIVE", b"PIRS", b"CON ")
BLOCK = 0x1000
TITLE_ID_OFFSET = 0x360
DESCRIPTOR_OFFSET = 0x379
HEADER_SIZE_OFFSET = 0x340
ENTRY_SIZE = 64
HASH_ENTRY = 0x18


class StfsError(ValueError):
    """The bytes are not an STFS package this reader understands."""


def title_id(path: str) -> Optional[int]:
    """The title id of an STFS package at ``path``, or ``None`` when the file is not one."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(TITLE_ID_OFFSET + 4)
    except OSError:
        return None
    if len(head) < TITLE_ID_OFFSET + 4 or head[:4] not in MAGICS:
        return None
    return struct.unpack_from(">I", head, TITLE_ID_OFFSET)[0]


class Package:
    """An open STFS package: ``files()`` lists it, ``read(path)`` returns one file's bytes."""

    def __init__(self, path: str):
        self._handle: BinaryIO = open(path, "rb")
        try:
            self._parse()
        except Exception:
            self._handle.close()
            raise

    def __enter__(self) -> "Package":
        return self

    def __exit__(self, *exc) -> None:
        self._handle.close()

    def _parse(self) -> None:
        self._handle.seek(0)
        if self._handle.read(4) not in MAGICS:
            raise StfsError("not an STFS package")
        self._handle.seek(HEADER_SIZE_OFFSET)
        header_size = struct.unpack(">I", self._handle.read(4))[0]
        self._handle.seek(DESCRIPTOR_OFFSET)
        descriptor = self._handle.read(0x24)
        if len(descriptor) < 8:
            raise StfsError("the volume descriptor is cut off")
        separation = descriptor[2]
        table_blocks = struct.unpack_from("<H", descriptor, 3)[0]
        table_start = int.from_bytes(descriptor[5:8], "little")
        self._base = (header_size + 0xFFF) & 0xF000
        # The hash tables are doubled unless the package says its blocks are not separated.
        self._shift = 0 if (self._base == 0xB000 or (separation & 1)) else 1
        self._entries = self._read_table(table_start, table_blocks)

    def _raw_block(self, n: int) -> int:
        raw = n + (((n + 0xAA) // 0xAA) << self._shift)
        if n >= 0xAA:
            raw += ((n + 0x70E4) // 0x70E4) << self._shift
        if n >= 0x70E4:
            raw += 1 << self._shift
        return raw

    def _block(self, n: int) -> bytes:
        self._handle.seek(self._base + (self._raw_block(n) << 12))
        data = self._handle.read(BLOCK)
        if len(data) != BLOCK:
            raise StfsError("a block lies past the end of the file")
        return data

    def _next_block(self, n: int) -> int:
        table = self._raw_block((n // 0xAA) * 0xAA) - (1 << self._shift)
        self._handle.seek(self._base + (table << 12) + (n % 0xAA) * HASH_ENTRY + 0x15)
        return int.from_bytes(self._handle.read(3), "big")

    def _read_table(self, start: int, count: int) -> List[Dict]:
        raw = b""
        block = start
        for _ in range(count):
            raw += self._block(block)
            block = self._next_block(block)
        entries: List[Dict] = []
        for i in range(len(raw) // ENTRY_SIZE):
            entry = raw[i * ENTRY_SIZE:(i + 1) * ENTRY_SIZE]
            flags = entry[0x28]
            length = flags & 0x3F
            if length == 0:
                break  # the table is zero-padded after its last entry
            entries.append({
                "name": entry[:length].decode("latin-1"),
                "folder": bool(flags & 0x80),
                "consecutive": bool(flags & 0x40),
                "blocks": int.from_bytes(entry[0x29:0x2C], "little"),
                "start": int.from_bytes(entry[0x2F:0x32], "little"),
                "parent": struct.unpack(">h", entry[0x32:0x34])[0],
                "size": struct.unpack(">I", entry[0x34:0x38])[0],
            })
        return entries

    def _path(self, index: int) -> str:
        parts: List[str] = []
        seen = set()
        while index >= 0 and index not in seen:
            seen.add(index)
            parts.append(self._entries[index]["name"])
            index = self._entries[index]["parent"]
        return "/".join(reversed(parts))

    def files(self) -> Iterator[Tuple[str, int]]:
        """(path, size) of every file, paths with ``/`` separators."""
        for index, entry in enumerate(self._entries):
            if not entry["folder"]:
                yield self._path(index), entry["size"]

    def read(self, path: str) -> bytes:
        """The bytes of the file at ``path`` (case-insensitive)."""
        wanted = path.lower()
        for index, entry in enumerate(self._entries):
            if entry["folder"] or self._path(index).lower() != wanted:
                continue
            data = bytearray()
            block = entry["start"]
            for _ in range(entry["blocks"]):
                data += self._block(block)
                block = block + 1 if entry["consecutive"] else self._next_block(block)
            return bytes(data[:entry["size"]])
        raise StfsError(f"{path} is not in the package")
