"""CRI AFS archives (Grandia II and other Sega, CRI and Sega-era games): read the entries, replace some, write the archive.

Layout (verified on the owner's Grandia II disc: 281 AFS files, every entry offset a multiple of 0x800, no overlap,
zero bytes in every gap):

* magic ``AFS\\0``, then the entry count (u32, little-endian);
* entry table: ``count`` pairs of (offset, size) as u32, followed by one more pair (the trailer: offset and size of
  a block after the last entry, or 0 0). Entries with size 0 keep whatever offset the table holds;
* the first entry starts at the offset the archive header reserves (0x800 in most archives, 0x80000 in some); the
  bytes before it are kept verbatim;
* entries follow in offset order, each one padded with zeros to the next 0x800 boundary;
* the trailer block (GR2.AFS, MGRP_SEB.AFS) and any tail bytes start right after the last entry; the file is padded
  with zeros to a multiple of 0x800.

Entries have no names in these archives: an entry is named by its index. ``parse`` returns the entries,
``write`` rebuilds the archive with some entries replaced. An unchanged archive comes back byte for byte.
"""
from __future__ import annotations

import struct
from typing import Mapping, NamedTuple

from core.i18n import tr

MAGIC = b"AFS\x00"
ALIGN = 0x800
HEADER = 8
PAIR = struct.Struct("<II")


class AfsEntry(NamedTuple):
    index: int
    offset: int
    size: int

    @property
    def name(self) -> str:
        return f"{self.index:04d}"


class AfsError(ValueError):
    """The bytes are not an AFS archive in the layout described above, or a replacement does not fit it."""


def _align(value: int) -> int:
    return (value + ALIGN - 1) // ALIGN * ALIGN


def parse(data: bytes) -> list[AfsEntry]:
    """The entries of an AFS archive in table order; AfsError when the table does not fit the bytes."""
    if len(data) < HEADER or data[:4] != MAGIC:
        raise AfsError(tr("not an AFS archive"))
    count = struct.unpack_from("<I", data, 4)[0]
    if HEADER + PAIR.size * (count + 1) > len(data):
        raise AfsError(tr("the AFS table of {0} entries runs past the end of the file", count))
    entries = []
    for index in range(count):
        offset, size = PAIR.unpack_from(data, HEADER + PAIR.size * index)
        if offset + size > len(data):
            raise AfsError(tr("AFS entry {0} runs past the end of the file", index))
        entries.append(AfsEntry(index, offset, size))
    return entries


def write(data: bytes, replacements: Mapping[int, bytes]) -> bytes:
    """``data`` with the entries in ``replacements`` replaced; every other byte is kept.

    Entries are laid out again in their original order from the original first offset, each on a 0x800 boundary,
    so a longer entry moves the ones behind it. The table and the trailer pair are rewritten to match.
    """
    entries = parse(data)
    count = len(entries)
    for index in replacements:
        if not 0 <= index < count:
            raise AfsError(tr("AFS entry {0} is not in the archive", index))
        if entries[index].size == 0:
            raise AfsError(tr("AFS entry {0} is empty and cannot be filled", index))
    placed = sorted((entry for entry in entries if entry.size), key=lambda entry: (entry.offset, entry.index))
    if not placed:
        return bytes(data)
    for before, after in zip(placed, placed[1:]):
        if after.offset < before.offset + before.size:
            raise AfsError(tr("AFS entries {0} and {1} overlap", before.index, after.index))
    first = placed[0].offset
    last = placed[-1]
    last_end = last.offset + last.size
    out = bytearray(data[:first])
    table = {}
    cursor = first
    new_end = first
    for entry in placed:
        payload = replacements.get(entry.index)
        if payload is None:
            payload = data[entry.offset:entry.offset + entry.size]
        out.extend(b"\x00" * (cursor - len(out)))
        table[entry.index] = (cursor, len(payload))
        out.extend(payload)
        new_end = cursor + len(payload)
        cursor = _align(new_end)
    tail = data[last_end:]
    out.extend(tail)
    trailer_offset, trailer_size = PAIR.unpack_from(data, HEADER + PAIR.size * count)
    if trailer_offset >= last_end and (trailer_offset or trailer_size):
        trailer_offset += new_end - last_end
    out.extend(b"\x00" * (_align(len(out)) - len(out)))
    for index, (offset, size) in table.items():
        PAIR.pack_into(out, HEADER + PAIR.size * index, offset, size)
    for entry in entries:   # an empty entry keeps its offset unless the file got shorter than that offset
        if entry.size == 0 and entry.offset > len(out):
            PAIR.pack_into(out, HEADER + PAIR.size * entry.index, len(out), 0)
    PAIR.pack_into(out, HEADER + PAIR.size * count, trailer_offset, trailer_size)
    return bytes(out)
