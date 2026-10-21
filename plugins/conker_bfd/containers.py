"""Nested containers of Conker's Bad Fur Day: an eight-byte record table, then blobs, each padded to eight bytes.

The container starts with a big-endian u32 table size, which is also the offset of the first blob. Each
eight-byte record holds (relative offset, length with flags in the top byte). Flag bit 0x10 marks an RZIP blob
(see ``n64_archive``); other flag bits are kept as they are when a blob is rebuilt. A zero length marks an empty
slot. An empty slot still holds its flags, and its offset is the position where the next blob would start.

The same layout holds the bank index, the bank 0x1A entries and the bank 0x1C holder. Serialising parsed slots
reproduces the original bytes when no slot changes.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import List

from .n64_archive import RomError, decode_rzip, encode_rzip

RZIP_FLAG = 0x10
LENGTH_MASK = 0x0FFFFFFF


@dataclass(frozen=True)
class Slot:
    flags: int     # the top byte of the length word (0x10 = RZIP)
    stored: bytes  # the blob as stored: RZIP stream or raw bytes; empty for an empty slot

    @property
    def empty(self) -> bool:
        return not self.stored

    @property
    def rzip(self) -> bool:
        return bool(self.flags & RZIP_FLAG)

    def payload(self) -> bytes:
        return decode_rzip(self.stored)[0] if self.rzip else bytes(self.stored)


def align8(value: int) -> int:
    return (value + 7) & ~7


def parse_container(data: bytes) -> List[Slot]:
    """Slots of one container. ``data`` is exactly the container's bytes (table first)."""
    if len(data) < 8:
        raise RomError("container is shorter than its table")
    table = struct.unpack_from(">I", data, 0)[0]
    if table == 0 or table % 8 or table > len(data):
        raise RomError("container table has no valid eight-byte span")
    slots: List[Slot] = []
    previous_end = table
    for index in range(table // 8):
        rel, length_flags = struct.unpack_from(">II", data, index * 8)
        length = length_flags & LENGTH_MASK
        flags = length_flags >> 24
        if length == 0:
            slots.append(Slot(flags=flags, stored=b""))
            continue
        end = rel + length
        if rel < previous_end or end > len(data):
            raise RomError(f"container slot {index} has an invalid range")
        slots.append(Slot(flags=flags, stored=bytes(data[rel:end])))
        previous_end = align8(end)
    return slots


def build_container(slots: List[Slot]) -> bytes:
    """Serialise slots in order. Blobs follow the table in slot order and are padded to eight bytes.

    An empty slot stores the current write position as its offset, as the original tables do, so a rebuilt
    container matches the original bytes when nothing changed.
    """
    table = 8 * len(slots)
    records = bytearray(table)
    blobs = bytearray()
    for index, slot in enumerate(slots):
        if len(slot.stored) > LENGTH_MASK:
            raise ValueError(f"slot {index} is too long")
        cursor = table + len(blobs)
        struct.pack_into(">II", records, index * 8, cursor, len(slot.stored) | (slot.flags << 24))
        blobs += slot.stored
        blobs += b"\x00" * (align8(len(slot.stored)) - len(slot.stored))
    return bytes(records + blobs)


def empty_slot(flags: int = 0) -> Slot:
    return Slot(flags=flags, stored=b"")


def raw_slot(payload: bytes, flags: int) -> Slot:
    """A slot that stores ``payload`` uncompressed: the RZIP bit is cleared and the other flag bits are kept."""
    return Slot(flags=flags & ~RZIP_FLAG & 0xFF, stored=bytes(payload))


def rzip_slot(payload: bytes, flags: int) -> Slot:
    return Slot(flags=(flags | RZIP_FLAG) & 0xFF, stored=encode_rzip(payload))
