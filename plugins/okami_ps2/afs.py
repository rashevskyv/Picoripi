"""AFS archives of the PlayStation 2 disc: the entry table, and the message containers among the entries.

The archive is read through a reader ``read(offset, count)`` (``ps2_reader`` for a disc file, a file view of a Wii disc
for the Wii build), so one code path reads both. The entry table is ``core.containers.afs``. A message entry is an
HD-style container (see ``plugins.okami_hd.msd``): ``count`` is small and its tag table names an MSD section. Only those
entries are read in full.
"""
from __future__ import annotations

import struct
from typing import List

from core.containers import afs as core_afs
from core.containers.afs import AfsEntry, Reader
from . import iso

MESSAGE_LIMIT = 8 * 1024 * 1024        # a message container is far smaller; larger entries are skipped unread


def ps2_reader(image, archive: iso.DiscEntry) -> Reader:
    """The reader of an archive that is a file of the disc (``iso.read``)."""
    return lambda offset, count: iso.read(image, archive, offset, count)


def stream_reader(stream, offset: int, size: int) -> Reader:
    """The reader of an archive that is ``size`` bytes at ``offset`` of ``stream`` (a Wii file view, read on demand)."""
    def read(at: int, count: int) -> bytes:
        count = max(0, min(count, size - at))
        stream.seek(offset + at)
        return stream.read(count)
    return read


def table(read: Reader, size: int) -> List[AfsEntry]:
    return core_afs.parse_from(read, size)


def _tags_name_msd(head: bytes, endian: str) -> bool:
    """True when the bytes are a container header with an MSD tag (a cheap test on the header only)."""
    if len(head) < 4:
        return False
    count = struct.unpack_from(endian + "I", head, 0)[0]
    return 1 <= count <= 64 and len(head) >= 4 + 8 * count and b"MSD\x00" in head[4 + 4 * count:4 + 8 * count]


def message_entries(read: Reader, size: int, endian: str = "<") -> List[AfsEntry]:
    """The entries of the archive that are message containers (each read only from its header first).

    ``endian`` is the byte order of the container headers: little on the PS2 disc, big on the Wii disc (the AFS table
    itself is little-endian on both)."""
    found: List[AfsEntry] = []
    for entry in table(read, size):
        if not entry.size or entry.size > MESSAGE_LIMIT:
            continue
        head = read(entry.offset, 4 + 8 * 64)
        count = struct.unpack_from(endian + "I", head, 0)[0] if len(head) >= 4 else 0
        if not 1 <= count <= 64:
            continue
        window = head[:4 + 8 * count]
        if len(window) == 4 + 8 * count and _tags_name_msd(window, endian):
            found.append(entry)
    return found


def read_entry(read: Reader, entry: AfsEntry) -> bytes:
    return read(entry.offset, entry.size)


TIM2_MAGIC = b"TIM2"
TEXTURE_LIMIT = 4 * 1024 * 1024       # a picture with words is far smaller; larger entries are skipped unread


def texture_entries(read: Reader, size: int) -> List[AfsEntry]:
    """The entries of the archive that are PS2 TIM2 pictures (each read only from its first four bytes)."""
    return [entry for entry in table(read, size)
            if 0 < entry.size <= TEXTURE_LIMIT and bytes(read(entry.offset, 4)) == TIM2_MAGIC]
