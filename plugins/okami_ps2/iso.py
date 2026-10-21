"""A minimal ISO 9660 reader and the two writes the Okami build needs, for the PlayStation 2 disc.

The reader finds a file in the root folder and reads a range of it; the disc is read in place. The writes change a
root file's extent and size in its directory record, and the volume's sector count. Nothing else of the disc is changed.
"""
from __future__ import annotations

import struct
from typing import BinaryIO, Iterator, List, NamedTuple, Optional, Set, Tuple

SECTOR = 2048
PVD_SECTOR = 16
PVD_VOLUME_AT = 80          # volume space size: u32 little-endian, then u32 big-endian
PVD_PATH_TABLES = ((140, "<I"), (144, "<I"), (148, ">I"), (152, ">I"))   # (lba at, its endian) of the four path tables
PVD_PATH_SIZE_AT = 132      # path table size: u32 little-endian, then u32 big-endian


class DiscEntry(NamedTuple):
    name: str
    lba: int
    size: int
    is_dir: bool


def _root(image: BinaryIO) -> Optional[DiscEntry]:
    image.seek(PVD_SECTOR * SECTOR)
    pvd = image.read(SECTOR)
    if len(pvd) < SECTOR or pvd[1:6] != b"CD001":
        return None
    record = pvd[156:156 + 34]
    return DiscEntry("", struct.unpack_from("<I", record, 2)[0], struct.unpack_from("<I", record, 10)[0], True)


def _records(data: bytes) -> Iterator[Tuple[int, DiscEntry, bytes]]:
    """(byte position in the folder, entry, raw name) of each record, the '.' and '..' records included."""
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
        name = raw.decode("ascii", "replace").split(";")[0]
        yield pos, DiscEntry(name, lba, size, bool(flags & 2)), raw
        pos += length


def directory(image: BinaryIO, folder: DiscEntry) -> List[DiscEntry]:
    """The entries of a directory (the names without the ';1' version)."""
    image.seek(folder.lba * SECTOR)
    data = image.read(folder.size)
    return [entry for _pos, entry, raw in _records(data) if raw not in (b"\x00", b"\x01")]


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


def root_record(image: BinaryIO, name: str) -> Optional[Tuple[int, DiscEntry]]:
    """(byte position on the disc of the root record of the file ``name``, its entry), or None."""
    root = _root(image)
    if root is None:
        return None
    image.seek(root.lba * SECTOR)
    data = image.read(root.size)
    for pos, entry, raw in _records(data):
        if raw not in (b"\x00", b"\x01") and not entry.is_dir and entry.name.upper() == name.upper():
            return root.lba * SECTOR + pos, entry
    return None


def volume_sectors(image: BinaryIO) -> int:
    """The volume space size in sectors (the primary volume descriptor)."""
    image.seek(PVD_SECTOR * SECTOR + PVD_VOLUME_AT)
    return struct.unpack("<I", image.read(4))[0]


def used_extents(image: BinaryIO) -> List[Tuple[int, int]]:
    """(first sector, sector count) of every file, folder and path table of the disc, found from the directory tree."""
    image.seek(PVD_SECTOR * SECTOR)
    pvd = image.read(SECTOR)
    out: List[Tuple[int, int]] = []
    size = struct.unpack_from("<I", pvd, PVD_PATH_SIZE_AT)[0]
    for lba_at, endian in PVD_PATH_TABLES:
        lba = struct.unpack_from(endian, pvd, lba_at)[0]
        if lba and size:
            out.append((lba, (size + SECTOR - 1) // SECTOR))
    root = _root(image)
    if root is None:
        return out
    seen: Set[int] = set()
    stack = [root]
    while stack:
        folder = stack.pop()
        if folder.lba in seen:
            continue
        seen.add(folder.lba)
        out.append((folder.lba, (folder.size + SECTOR - 1) // SECTOR))
        for entry in directory(image, folder):
            if entry.is_dir:
                stack.append(entry)
            else:
                out.append((entry.lba, (entry.size + SECTOR - 1) // SECTOR))
    return out


def write_extent(out: BinaryIO, record_at: int, lba: int, size: int) -> None:
    """Set the extent (first sector) and size of the file whose root record is at ``record_at``, both endians."""
    out.seek(record_at + 2)
    out.write(struct.pack("<I", lba) + struct.pack(">I", lba))
    out.seek(record_at + 10)
    out.write(struct.pack("<I", size) + struct.pack(">I", size))


def write_volume_sectors(out: BinaryIO, sectors: int) -> None:
    out.seek(PVD_SECTOR * SECTOR + PVD_VOLUME_AT)
    out.write(struct.pack("<I", sectors) + struct.pack(">I", sectors))
