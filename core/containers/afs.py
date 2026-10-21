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

``parse_from`` and ``write_to`` take a reader ``read(offset, count)`` instead of the bytes, and ``write_to`` streams its
output: an archive of gigabytes (a PlayStation 2 disc's AFS) is never held in memory.
"""
from __future__ import annotations

import io
import struct
from typing import BinaryIO, Callable, Mapping, NamedTuple

from core.i18n import tr

MAGIC = b"AFS\x00"
ALIGN = 0x800
HEADER = 8
PAIR = struct.Struct("<II")
CHUNK = 8 * 1024 * 1024        # copy size of a payload that is not held in memory

Reader = Callable[[int, int], bytes]


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


def parse_from(read: Reader, size: int) -> list[AfsEntry]:
    """The entries of an AFS archive of ``size`` bytes that ``read(offset, count)`` gives; AfsError when it does not fit."""
    if size < HEADER or read(0, 4) != MAGIC:
        raise AfsError(tr("not an AFS archive"))
    count = struct.unpack("<I", read(4, 4))[0]
    if HEADER + PAIR.size * (count + 1) > size:
        raise AfsError(tr("the AFS table of {0} entries runs past the end of the file", count))
    table = read(HEADER, PAIR.size * count)
    entries = []
    for index in range(count):
        offset, length = PAIR.unpack_from(table, PAIR.size * index)
        if offset + length > size:
            raise AfsError(tr("AFS entry {0} runs past the end of the file", index))
        entries.append(AfsEntry(index, offset, length))
    return entries


def parse(data: bytes) -> list[AfsEntry]:
    """The entries of an AFS archive in table order; AfsError when the table does not fit the bytes."""
    return parse_from(lambda offset, count: data[offset:offset + count], len(data))


def _copy(read: Reader, offset: int, count: int, out: BinaryIO) -> None:
    """``count`` bytes from ``offset`` of the source, copied to ``out`` in chunks."""
    for done in range(0, count, CHUNK):
        out.write(read(offset + done, min(CHUNK, count - done)))


def _zeros(out: BinaryIO, count: int) -> None:
    for done in range(0, count, CHUNK):
        out.write(b"\x00" * min(CHUNK, count - done))


class Layout(NamedTuple):
    """Where each entry of the rebuilt archive goes; ``total`` is the new size in bytes."""
    count: int
    first: int
    last_end: int
    new_end: int
    total: int
    entries: list
    placed: list
    moved: dict
    trailer: tuple


def layout(read: Reader, size: int, replacements: Mapping[int, bytes]) -> Layout:
    """The layout ``write_to`` would write, without writing: the new offsets, the new size, the trailer pair."""
    entries = parse_from(read, size)
    count = len(entries)
    for index in replacements:
        if not 0 <= index < count:
            raise AfsError(tr("AFS entry {0} is not in the archive", index))
        if entries[index].size == 0:
            raise AfsError(tr("AFS entry {0} is empty and cannot be filled", index))
    placed = sorted((entry for entry in entries if entry.size), key=lambda entry: (entry.offset, entry.index))
    if not placed:
        return Layout(count, 0, 0, 0, size, entries, placed, {}, (0, 0))
    for before, after in zip(placed, placed[1:]):
        if after.offset < before.offset + before.size:
            raise AfsError(tr("AFS entries {0} and {1} overlap", before.index, after.index))
    first = placed[0].offset
    last_end = placed[-1].offset + placed[-1].size
    moved: dict[int, tuple[int, int]] = {}
    cursor = first
    new_end = first
    for entry in placed:
        payload = replacements.get(entry.index)
        length = entry.size if payload is None else len(payload)
        moved[entry.index] = (cursor, length)
        new_end = cursor + length
        cursor = _align(new_end)
    total = _align(new_end + size - last_end)
    trailer_offset, trailer_size = PAIR.unpack(read(HEADER + PAIR.size * count, PAIR.size))
    if trailer_offset >= last_end and (trailer_offset or trailer_size):
        trailer_offset += new_end - last_end
    return Layout(count, first, last_end, new_end, total, entries, placed, moved, (trailer_offset, trailer_size))


def new_size(read: Reader, size: int, replacements: Mapping[int, bytes]) -> int:
    """The size in bytes of the archive ``write_to`` would write."""
    return layout(read, size, replacements).total


def write_to(read: Reader, size: int, out: BinaryIO, replacements: Mapping[int, bytes]) -> int:
    """Write the archive with the entries in ``replacements`` replaced to ``out``; returns the new size in bytes.

    Entries are laid out again in their original order from the original first offset, each on a 0x800 boundary,
    so a longer entry moves the ones behind it. The table and the trailer pair are rewritten to match. Every other
    byte is kept, so an archive without replacements is copied byte for byte.
    """
    plan = layout(read, size, replacements)
    if not plan.placed:
        _copy(read, 0, size, out)
        return size
    total, moved, count = plan.total, plan.moved, plan.count
    head = bytearray(read(0, plan.first))
    for index, (offset, length) in moved.items():
        PAIR.pack_into(head, HEADER + PAIR.size * index, offset, length)
    for entry in plan.entries:   # an empty entry keeps its offset unless the file got shorter than that offset
        if entry.size == 0 and entry.offset > total:
            PAIR.pack_into(head, HEADER + PAIR.size * entry.index, total, 0)
    PAIR.pack_into(head, HEADER + PAIR.size * count, *plan.trailer)
    out.write(head)
    written = plan.first
    for entry in plan.placed:
        offset, length = moved[entry.index]
        _zeros(out, offset - written)
        payload = replacements.get(entry.index)
        if payload is None:
            _copy(read, entry.offset, entry.size, out)
        else:
            out.write(payload)
        written = offset + length
    _copy(read, plan.last_end, size - plan.last_end, out)
    _zeros(out, total - (plan.new_end + size - plan.last_end))
    return total


def write(data: bytes, replacements: Mapping[int, bytes]) -> bytes:
    """``data`` with the entries in ``replacements`` replaced; every other byte is kept (see ``write_to``)."""
    out = io.BytesIO()
    write_to(lambda offset, count: data[offset:offset + count], len(data), out, replacements)
    return out.getvalue()
