"""AFS archives of the PlayStation 2 disc: the entry table, and the message containers among the entries.

Layout (as read on the Okami disc): 'AFS\\0', u32 count, count x (u32 offset in bytes from the start of the archive,
u32 size). An entry is named by its index. A message entry is an HD-style container (see ``plugins.okami_hd.msd``):
``count`` is small and its tag table names an MSD section. Only those entries are read in full.
"""
from __future__ import annotations

import struct
from typing import BinaryIO, List, NamedTuple

from . import iso

MESSAGE_LIMIT = 8 * 1024 * 1024        # a message container is far smaller; larger entries are skipped unread


class AfsEntry(NamedTuple):
    index: int
    offset: int
    size: int


def table(image: BinaryIO, archive: iso.DiscEntry) -> List[AfsEntry]:
    head = iso.read(image, archive, 0, 8)
    if head[:4] != b"AFS\x00":
        raise ValueError("not an AFS archive")
    count = struct.unpack_from("<I", head, 4)[0]
    raw = iso.read(image, archive, 8, 8 * count)
    return [AfsEntry(i, *struct.unpack_from("<II", raw, 8 * i)) for i in range(count)]


def _tags_name_msd(head: bytes) -> bool:
    """True when the bytes are a container header with an MSD tag (a cheap test on the header only)."""
    if len(head) < 4:
        return False
    count = struct.unpack_from("<I", head, 0)[0]
    return 1 <= count <= 64 and len(head) >= 4 + 8 * count and b"MSD\x00" in head[4 + 4 * count:4 + 8 * count]


def message_entries(image: BinaryIO, archive: iso.DiscEntry) -> List[AfsEntry]:
    """The entries of the archive that are message containers (each read only from its header first)."""
    found: List[AfsEntry] = []
    for entry in table(image, archive):
        if not entry.size or entry.size > MESSAGE_LIMIT:
            continue
        head = iso.read(image, archive, entry.offset, 4 + 8 * 64)
        count = struct.unpack_from("<I", head, 0)[0] if len(head) >= 4 else 0
        if not 1 <= count <= 64:
            continue
        window = head[:4 + 8 * count]
        if len(window) == 4 + 8 * count and _tags_name_msd(window):
            found.append(entry)
    return found


def read_entry(image: BinaryIO, archive: iso.DiscEntry, entry: AfsEntry) -> bytes:
    return iso.read(image, archive, entry.offset, entry.size)
