"""A minimal ISO 9660 reader for the PlayStation 2 disc: find a file in the root folder and read a range of it.

Only the primary volume descriptor and the directory records are read; the disc is read in place, never copied.
"""
from __future__ import annotations

import struct
from typing import BinaryIO, List, NamedTuple, Optional

SECTOR = 2048


class DiscEntry(NamedTuple):
    name: str
    lba: int
    size: int
    is_dir: bool


def _root(image: BinaryIO) -> Optional[DiscEntry]:
    image.seek(16 * SECTOR)
    pvd = image.read(SECTOR)
    if len(pvd) < SECTOR or pvd[1:6] != b"CD001":
        return None
    record = pvd[156:156 + 34]
    return DiscEntry("", struct.unpack_from("<I", record, 2)[0], struct.unpack_from("<I", record, 10)[0], True)


def directory(image: BinaryIO, folder: DiscEntry) -> List[DiscEntry]:
    """The entries of a directory (the names without the ';1' version)."""
    image.seek(folder.lba * SECTOR)
    data = image.read(folder.size)
    out: List[DiscEntry] = []
    pos = 0
    while pos < len(data):
        length = data[pos]
        if length == 0:                       # records do not cross a sector: skip to the next one
            pos = (pos // SECTOR + 1) * SECTOR
            continue
        lba = struct.unpack_from("<I", data, pos + 2)[0]
        size = struct.unpack_from("<I", data, pos + 10)[0]
        flags = data[pos + 25]
        name_len = data[pos + 32]
        raw = data[pos + 33:pos + 33 + name_len]
        pos += length
        if raw in (b"\x00", b"\x01"):         # the '.' and '..' entries
            continue
        name = raw.decode("ascii", "replace").split(";")[0]
        out.append(DiscEntry(name, lba, size, bool(flags & 2)))
    return out


def find(image: BinaryIO, name: str) -> Optional[DiscEntry]:
    """A file of the root folder, by its name (case as on the disc, e.g. 'SYSTEM.CNF')."""
    root = _root(image)
    if root is None:
        return None
    for entry in directory(image, root):
        if entry.name.upper() == name.upper() and not entry.is_dir:
            return entry
    return None


def read(image: BinaryIO, entry: DiscEntry, offset: int, count: int) -> bytes:
    """``count`` bytes of the file from ``offset`` (clipped to the file)."""
    count = max(0, min(count, entry.size - offset))
    image.seek(entry.lba * SECTOR + offset)
    return image.read(count)
