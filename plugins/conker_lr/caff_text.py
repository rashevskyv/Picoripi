"""Conker: Live & Reloaded text files (CAFF ``default.bin``): read the dialogue strings and write them back, grown if needed.

A file starts with ``CAFF`` and holds an ``LSBL`` block. The u32 at ``LSBL + 32`` counts its dialogue strings.
Each string is UTF-16LE, NUL-terminated, and lies after ``LSBL + 48``. Key names (``cutscene_...``) and the
empty string are stored in the same blob and are not text, so they are skipped.

The LSBL table after the header holds 6-byte records ``(u16 id, u32 value)``: ``value`` is a UTF-16 unit offset
from the first string; the record ending in id 0xFFFF marks the end of the blob. Writing a text of another
length rebuilds the blob, then moves every position that points into or after it (the table, the LSBL offsets
at +0x10..+0x1C and +0x2C, header 0x34) and the section sizes (0x50, 0x64).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence
import struct

MAGIC = b"CAFF"
LSBL = b"LSBL"
COUNT_OFFSET = 32
TEXT_START_OFFSET = 48
TABLE_OFFSET = 0x30
TABLE_RECORD = 6
END_ID = 0xFFFF
SECTION_SIZE_FIELDS = (0x50, 0x64)
SECTION_BASE = 0x180
HEADER_POINTER = 0x34
LSBL_RELATIVE_FIELDS = (0x10, 0x14, 0x18, 0x1C)
LSBL_UNIT_FIELD = 0x2C
SKIPPED_PREFIXES = ("cutscene_",)
SKIPPED_NAMES = ("EmptyString",)


class CaffError(ValueError):
    """The bytes are not a CAFF text file this plugin reads, or a rebuild cannot be checked."""


@dataclass(frozen=True)
class Slot:
    """One string of the block: its byte offset, its text length in bytes (without the NUL) and its text."""

    offset: int
    capacity: int
    text: str


def _unit(data: bytes, pos: int) -> int:
    return data[pos] | (data[pos + 1] << 8)


def _is_text_unit(data: bytes, pos: int) -> bool:
    """A Latin-1 unit: low byte set, high byte zero (the game's table records are not text)."""
    return data[pos] != 0 and data[pos + 1] == 0


def _scan_runs(data: bytes, start: int):
    """Yield (offset, capacity, text) for every NUL-ended run of at least two Latin-1 UTF-16 units."""
    end = len(data) - 1
    pos = start
    while pos < end:
        stop = pos
        while stop < end and _is_text_unit(data, stop):
            stop += 2
        units = (stop - pos) // 2
        if units >= 2 and stop < len(data) - 1 and _unit(data, stop) == 0:
            text = data[pos:stop].decode("utf-16le", errors="replace")
            yield pos, stop - pos, text
            pos = stop + 2
        else:
            pos += 2


def _text_start(data: bytes, lsbl: int) -> int:
    """Where the strings begin: just after the table's end record (or after the fixed header if none is found)."""
    pos = lsbl + TABLE_OFFSET
    for _ in range(4096):
        if pos + TABLE_RECORD > len(data):
            break
        if struct.unpack_from("<H", data, pos)[0] == END_ID:
            return pos + TABLE_RECORD
        pos += TABLE_RECORD
    return lsbl + TEXT_START_OFFSET


def read_slots(data: bytes) -> List[Slot]:
    """Return the dialogue strings of one CAFF text file, in file order."""
    if not data.startswith(MAGIC):
        raise CaffError("missing CAFF header")
    lsbl = data.find(LSBL)
    if lsbl < 0:
        raise CaffError("missing LSBL block")
    count = struct.unpack_from("<I", data, lsbl + COUNT_OFFSET)[0]
    slots: List[Slot] = []
    for offset, capacity, text in _scan_runs(data, _text_start(data, lsbl)):
        if text.startswith(SKIPPED_PREFIXES) or text in SKIPPED_NAMES:
            continue
        slots.append(Slot(offset, capacity, text))
        if len(slots) == count:
            break
    if len(slots) != count:
        raise CaffError(f"found {len(slots)} strings, the block counts {count}")
    return slots


def has_letter(text: str) -> bool:
    """True for a string a translator reads: three or more characters, one of them an ASCII letter.

    Other runs are codes or table bytes of the block and keep their bytes.
    """
    return len(text) >= 3 and any("A" <= ch <= "Z" or "a" <= ch <= "z" for ch in text)


def translatable(slots: Sequence[Slot]) -> List[int]:
    """Indexes (into ``slots``) of the strings a translator edits, in file order."""
    return [index for index, slot in enumerate(slots) if has_letter(slot.text)]


def _table_fields(data: bytes, lsbl: int, limit: int) -> List[int]:
    """Positions of the u32 unit values of the LSBL table (one per record, up to the end record).

    The table lies before ``limit`` (the first string); a record that starts at or after it is not read.
    """
    positions = []
    pos = lsbl + TABLE_OFFSET
    while pos + TABLE_RECORD <= limit:
        rid = struct.unpack_from("<H", data, pos)[0]
        positions.append(pos + 2)
        if rid == END_ID:
            break
        pos += TABLE_RECORD
    return positions


def write_slots(data: bytes, texts: Sequence[str]) -> bytes:
    """Return the file with the translatable strings replaced by ``texts`` (in ``translatable`` order).

    A text may be longer or shorter than the original: the blob is rebuilt and every position that points into or
    after it is moved. Other runs keep their bytes. Same texts give the same bytes.
    """
    slots = read_slots(data)
    indexes = translatable(slots)
    if len(texts) != len(indexes):
        raise CaffError(f"{len(texts)} texts for {len(indexes)} strings")
    if not slots:
        return bytes(data)
    new_text = dict(zip(indexes, texts))
    lsbl = data.find(LSBL)
    first = slots[0].offset
    old_end = slots[-1].offset + slots[-1].capacity + 2

    # 1. rebuild the blob: gap bytes stay, each string gets its new bytes (or its old bytes)
    blob = bytearray()
    new_starts: List[int] = []
    deltas: List[int] = []
    pos = first
    for index, slot in enumerate(slots):
        blob += data[pos:slot.offset]
        new_starts.append(first + len(blob))
        old_len = slot.capacity + 2
        if index in new_text:
            raw = new_text[index].encode("utf-16le") + b"\x00\x00"
        else:
            raw = data[slot.offset:slot.offset + old_len]
        blob += raw
        deltas.append(len(raw) - old_len)
        pos = slot.offset + old_len
    total = len(blob) - (old_end - first)

    def relocate(t: int) -> int:
        if t < first:
            return t
        if t >= old_end:
            return t + total
        shift = 0
        for index, slot in enumerate(slots):
            start, end = slot.offset, slot.offset + slot.capacity + 2
            if start <= t < end:
                return new_starts[index] + (t - start)
            if end <= t:
                shift += deltas[index]
        return t + shift

    out = bytearray(data[:first]) + blob + bytearray(data[old_end:])

    # 2. header section sizes: the section runs to the end of the file
    old_size = len(data)
    for field in SECTION_SIZE_FIELDS:
        if struct.unpack_from("<I", data, field)[0] == old_size - SECTION_BASE:
            struct.pack_into("<I", out, field, len(out) - SECTION_BASE)
    # 3. header pointer into the file
    value = struct.unpack_from("<I", data, HEADER_POINTER)[0]
    if value < old_size:
        struct.pack_into("<I", out, HEADER_POINTER, relocate(value))
    # 4. LSBL fields: relative to the LSBL block, or unit offsets from the first string
    for field in LSBL_RELATIVE_FIELDS:
        if lsbl + field + 4 > first:
            continue
        value = struct.unpack_from("<I", data, lsbl + field)[0]
        struct.pack_into("<I", out, lsbl + field, relocate(lsbl + value) - lsbl)
    unit_fields = [lsbl + LSBL_UNIT_FIELD] + _table_fields(data, lsbl, first)
    for field in unit_fields:
        if field + 4 > first:
            continue
        value = struct.unpack_from("<I", data, field)[0]
        struct.pack_into("<I", out, field, (relocate(first + 2 * value) - first) // 2)

    _check_rebuild(bytes(out), new_starts, slots, new_text, indexes)
    return bytes(out)


def _check_rebuild(out: bytes, new_starts: List[int], slots: Sequence[Slot], new_text: dict, indexes: List[int]):
    """Every edited string reads back at its new start, and the table points at the starts."""
    for index in indexes:
        if index not in new_text:
            continue
        start = new_starts[index]
        raw = new_text[index].encode("utf-16le") + b"\x00\x00"
        if out[start:start + len(raw)] != raw:
            raise CaffError(f"rebuild: string {index} is not at its new position")
