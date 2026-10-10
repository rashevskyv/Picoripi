"""Silent Hill 3 (PC) ``.arc`` archives: read the entries, replace some, write the archive back.

Layout (all little-endian u32, verified on every archive of ``data\\``):

* header, 16 bytes: magic ``0x20030507``, entry count, size of the info block, 0;
* entry table, 16 bytes per entry: data offset, offset of the entry's slot in the info block, size, size;
* info block, ``info size`` bytes: kept verbatim (the game's runtime slots; not decoded here);
* data: the entries, back to back, with no padding, ending at the file size.

``arc.arc`` (gzip) is the name catalog of all archives: groups of records per archive extension
(``msg`` = ``msg.arc``, ``tex`` = ``tex.arc`` ...), each record holding the entry index and the path.
"""
from __future__ import annotations

import gzip
import struct
from dataclasses import dataclass
from typing import Dict, List, Mapping, Tuple

MAGIC = 0x20030507
CATALOG_MAGIC = 0x20030417
HEADER = struct.Struct("<4I")
ENTRY = struct.Struct("<4I")


@dataclass(frozen=True)
class ArcEntry:
    offset: int
    slot: int
    size: int


class ArcError(ValueError):
    """The bytes are not a Silent Hill 3 archive in the layout described above."""


def parse(data: bytes) -> Tuple[int, List[ArcEntry]]:
    """Return (info_size, entries) of an archive; raises ArcError when the layout does not hold."""
    if len(data) < HEADER.size:
        raise ArcError("archive shorter than its header")
    magic, count, info_size, _ = HEADER.unpack_from(data, 0)
    if magic != MAGIC:
        raise ArcError(f"bad magic {magic:08x}")
    start = HEADER.size + ENTRY.size * count
    entries = []
    for i in range(count):
        offset, slot, size, size_again = ENTRY.unpack_from(data, HEADER.size + ENTRY.size * i)
        if size != size_again:
            raise ArcError(f"entry {i}: the two size fields differ")
        entries.append(ArcEntry(offset, slot, size))
    expected = start + info_size
    cursor = expected
    for i, entry in enumerate(entries):
        if entry.offset != cursor:
            raise ArcError(f"entry {i} is not contiguous")
        cursor += entry.size
    if cursor != len(data):
        raise ArcError("the entries do not end at the file size")
    return info_size, entries


def entry_bytes(data: bytes, entry: ArcEntry) -> bytes:
    return data[entry.offset:entry.offset + entry.size]


def rebuild(data: bytes, replacements: Mapping[int, bytes]) -> bytes:
    """The archive with the entries in ``replacements`` (index -> new bytes) swapped in.

    The header, the slot numbers and the info block stay as they are; offsets and sizes are rewritten.
    With no replacements the result is the input byte for byte.
    """
    info_size, entries = parse(data)
    count = len(entries)
    start = HEADER.size + ENTRY.size * count
    info = data[start:start + info_size]
    table = bytearray()
    body = bytearray()
    cursor = start + info_size
    for i, entry in enumerate(entries):
        raw = replacements[i] if i in replacements else entry_bytes(data, entry)
        table += ENTRY.pack(cursor, entry.slot, len(raw), len(raw))
        body += raw
        cursor += len(raw)
    head = HEADER.pack(MAGIC, count, info_size, 0)
    return bytes(head) + bytes(table) + info + bytes(body)


def parse_catalog(gz_bytes: bytes) -> Dict[str, List[Tuple[int, str]]]:
    """``arc.arc`` (gzip) -> {archive extension: [(entry index, path), ...]} in index order.

    Each record holds the archive id in its high 16 bits and the entry index in the low 16 bits.
    """
    data = gzip.decompress(gz_bytes)
    if struct.unpack_from("<I", data, 0)[0] != CATALOG_MAGIC:
        raise ArcError("arc.arc: unknown catalog magic")
    groups: Dict[str, List[Tuple[int, str]]] = {}
    pos = 0x10
    current = None
    while pos < len(data):
        tag, size = struct.unpack_from("<HH", data, pos)
        if size == 0:
            raise ArcError(f"arc.arc: zero record size at {pos:#x}")
        if tag == 2:
            end = data.index(b"\0", pos + 8)
            current = data[pos + 8:end].decode("latin1")
            groups[current] = []
        elif tag == 3:
            if current is None:
                raise ArcError("arc.arc: entry before any group")
            index = struct.unpack_from("<I", data, pos + 4)[0] & 0xFFFF  # high bits: the archive id
            end = data.index(b"\0", pos + 8)
            groups[current].append((index, data[pos + 8:end].decode("latin1")))
        elif tag != 1:
            raise ArcError(f"arc.arc: unknown record tag {tag} at {pos:#x}")
        pos += size
    return groups
