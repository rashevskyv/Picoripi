"""Conker: Live & Reloaded text files (CAFF ``default.bin``): read the dialogue strings and write them back, grown if needed.

A file starts with ``CAFF`` and holds an ``LSBL`` block. The u32 at ``LSBL + 32`` counts the block's entries.
The LSBL table starts at ``LSBL + 0x24``: 6-byte records ``(u16 id, u32 value)``, one per entry, then an end record
with id 0xFFFF. ``value`` is a UTF-16 unit offset from the first string, and the first string starts right after the
end record. Each string is UTF-16LE and NUL-terminated. The table is the authority for where each string starts:
a scan for text runs would merge neighbours and read the index as text. Key names (``cutscene_...``) and the empty
string are entries too, but they are not text and are skipped.

The block index at the pointer LSBL+0x10 holds one 8-byte entry ``(u16, u16, u32 unit)`` per entry, after an 8-byte
header; its units are offsets from the first string as well, and they may point inside a string.

Writing a text of another length rebuilds the blob, then moves every position that points into or after it (the
table, the index, the LSBL offsets at +0x10..+0x1C), grows the data size (header 0x34) and the section sizes (0x50,
0x64) by the same amount, and recomputes the header checksum (0x14) last. The game refuses a header whose
checksum is wrong, and sizes its buffers from these fields.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple
import struct

MAGIC = b"CAFF"
LSBL = b"LSBL"
COUNT_OFFSET = 32
TABLE_OFFSET = 0x24
TABLE_RECORD = 6
END_ID = 0xFFFF
SECTION_SIZE_FIELDS = (0x50, 0x64)
SECTION_BASE = 0x180
CHECKSUM_FIELD = 0x14
DATA_SIZE_FIELD = 0x34
LSBL_RELATIVE_FIELDS = (0x10, 0x14, 0x18, 0x1C)
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


def _table(data: bytes, lsbl: int) -> Tuple[List[int], int]:
    """The table values before the end record, and the offset of the first string (just after the end record)."""
    values: List[int] = []
    pos = lsbl + TABLE_OFFSET
    while pos + TABLE_RECORD <= len(data):
        rid, value = struct.unpack_from("<HI", data, pos)
        pos += TABLE_RECORD
        if rid == END_ID:
            return values, pos
        values.append(value)
    raise CaffError("the LSBL table has no end record")


def _run(data: bytes, pos: int) -> Tuple[int, str]:
    """(byte length without the NUL, text) of the UTF-16 string at ``pos``."""
    end = pos
    while True:
        if end + 2 > len(data):
            raise CaffError("a string runs past the end of the file")
        if data[end] == 0 and data[end + 1] == 0:
            break
        end += 2
    return end - pos, data[pos:end].decode("utf-16le", errors="replace")


def read_slots(data: bytes) -> List[Slot]:
    """Return the dialogue strings of one CAFF text file, in file order (keys and the empty string left out)."""
    if not data.startswith(MAGIC):
        raise CaffError("missing CAFF header")
    lsbl = data.find(LSBL)
    if lsbl < 0:
        raise CaffError("missing LSBL block")
    count = struct.unpack_from("<I", data, lsbl + COUNT_OFFSET)[0]
    values, first = _table(data, lsbl)
    if len(values) != count:
        raise CaffError(f"the table has {len(values)} entries, the block counts {count}")
    slots: List[Slot] = []
    for value in values:
        offset = first + 2 * value
        capacity, text = _run(data, offset)
        if text.startswith(SKIPPED_PREFIXES) or text in SKIPPED_NAMES:
            continue
        slots.append(Slot(offset, capacity, text))
    for before, after in zip(slots, slots[1:]):
        if after.offset < before.offset + before.capacity + 2:
            raise CaffError("the strings overlap or are out of file order")
    return slots


def has_letter(text: str) -> bool:
    """True for a string a translator reads: three or more characters, one of them an ASCII letter.

    Other strings are codes, punctuation or a single symbol and keep their bytes.
    """
    return len(text) >= 3 and any("A" <= ch <= "Z" or "a" <= ch <= "z" for ch in text)


def translatable(slots: Sequence[Slot]) -> List[int]:
    """Indexes (into ``slots``) of the strings a translator edits, in file order."""
    return [index for index, slot in enumerate(slots) if has_letter(slot.text)]


def _table_fields(data: bytes, lsbl: int) -> List[int]:
    """Positions of the u32 values of the LSBL table records, end record included."""
    positions = []
    pos = lsbl + TABLE_OFFSET
    while pos + TABLE_RECORD <= len(data):
        positions.append(pos + 2)
        if struct.unpack_from("<H", data, pos)[0] == END_ID:
            break
        pos += TABLE_RECORD
    return positions


def _index_fields(data: bytes, lsbl: int, count: int) -> List[int]:
    """Positions of the u32 unit values of the block index (the pointer at LSBL+0x10).

    The index is an 8-byte header ``(u32, u32 count)`` and ``count`` entries ``(u16, u16, u32 unit)``. Each unit is a
    UTF-16 unit offset from the first string, like the table, and it may point inside a string (line starts).
    The index lies inside the blob or after it, so its units move with the blob. Empty when the pointer is not an index.
    """
    start = lsbl + struct.unpack_from("<I", data, lsbl + LSBL_RELATIVE_FIELDS[0])[0]
    if start + 8 + 8 * count > len(data) or struct.unpack_from("<I", data, start + 4)[0] != count:
        return []
    if count and struct.unpack_from("<H", data, start + 8)[0] != 0:
        return []
    return [start + 8 + 8 * k + 4 for k in range(count)]


def write_slots(data: bytes, texts: Sequence[str]) -> bytes:
    """Return the file with the translatable strings replaced by ``texts`` (in ``translatable`` order).

    A text may be longer or shorter than the original: the blob is rebuilt and every position that points into or
    after it is moved. Other strings keep their bytes. Same texts give the same bytes.
    """
    slots = read_slots(data)
    indexes = translatable(slots)
    if len(texts) != len(indexes):
        raise CaffError(f"{len(texts)} texts for {len(indexes)} strings")
    if not slots:
        return bytes(data)
    new_text = dict(zip(indexes, texts))
    lsbl = data.find(LSBL)
    count = struct.unpack_from("<I", data, lsbl + COUNT_OFFSET)[0]
    _, first = _table(data, lsbl)
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

    # 2. header sizes: the section (data + tail) runs to the end of the file; the data size (+0x34) is counted from
    # 0x180 and grows by the same amount as the blob
    old_size = len(data)
    for field in SECTION_SIZE_FIELDS:
        if struct.unpack_from("<I", data, field)[0] == old_size - SECTION_BASE:
            struct.pack_into("<I", out, field, len(out) - SECTION_BASE)
    data_size = struct.unpack_from("<I", data, DATA_SIZE_FIELD)[0]
    if SECTION_BASE + data_size < old_end:
        raise CaffError("the data size does not cover the text block")
    struct.pack_into("<I", out, DATA_SIZE_FIELD, data_size + total)
    # 4. LSBL pointers: relative to the LSBL block
    for field in LSBL_RELATIVE_FIELDS:
        if lsbl + field + 4 > first:
            continue
        value = struct.unpack_from("<I", data, lsbl + field)[0]
        struct.pack_into("<I", out, lsbl + field, relocate(lsbl + value) - lsbl)
    # 4b. in every file LSBL+0x1C is LSBL+0x10 minus 0x1C: keep that relation after the move
    if struct.unpack_from("<I", data, lsbl + 0x10)[0] - struct.unpack_from("<I", data, lsbl + 0x1C)[0] == 0x1C:
        new_index = struct.unpack_from("<I", out, lsbl + 0x10)[0]
        struct.pack_into("<I", out, lsbl + 0x1C, (new_index - 0x1C) & 0xFFFFFFFF)
    # 5. table values: unit offsets from the first string (the table lies before it, so its fields do not move)
    for field in _table_fields(data, lsbl):
        value = struct.unpack_from("<I", data, field)[0]
        struct.pack_into("<I", out, field, (relocate(first + 2 * value) - first) // 2)
    # 6. the block index: its entries sit in the blob or after it, so each field moves to its new place
    for field in _index_fields(data, lsbl, count):
        value = struct.unpack_from("<I", data, field)[0]
        struct.pack_into("<I", out, relocate(field), (relocate(first + 2 * value) - first) // 2)

    _check_rebuild(bytes(out), new_starts, slots, new_text, indexes)
    # 7. the checksum last: the game refuses a header whose checksum is wrong (return 3 in 0x004072F0)
    struct.pack_into("<I", out, CHECKSUM_FIELD, caff_hash(out))
    return bytes(out)


def caff_hash(data: bytes) -> int:
    """The header checksum: ELF/PJW hash over the first 0x180 bytes with the checksum field zeroed.

    The game adds the bytes as signed chars (0x004072F0): ``h = (h << 4) + (int8) b``; when the top nibble is set,
    it folds back into the low bits.
    """
    header = bytearray(data[:SECTION_BASE])
    header[CHECKSUM_FIELD:CHECKSUM_FIELD + 4] = b"\x00\x00\x00\x00"
    value = 0
    for byte in header:
        signed = byte - 256 if byte >= 128 else byte
        value = ((value << 4) + signed) & 0xFFFFFFFF
        top = value & 0xF0000000
        if top:
            value ^= (top >> 24) | top
    return value


def check(data: bytes) -> None:
    """Raise CaffError unless the header checksum and the section sizes match the file.

    The game reads the section size and the data size from the header to size its buffers, so a bank whose header
    disagrees with its length would load past its buffer.
    """
    if len(data) < SECTION_BASE or not data.startswith(MAGIC):
        raise CaffError("not a CAFF file")
    stored = struct.unpack_from("<I", data, CHECKSUM_FIELD)[0]
    if stored != caff_hash(data):
        raise CaffError(f"header checksum {stored:08X} does not match the file ({caff_hash(data):08X})")
    for field in SECTION_SIZE_FIELDS:
        if struct.unpack_from("<I", data, field)[0] != len(data) - SECTION_BASE:
            raise CaffError(f"section size at +0x{field:02X} does not match the file length")
    if SECTION_BASE + struct.unpack_from("<I", data, DATA_SIZE_FIELD)[0] > len(data):
        raise CaffError("the data size runs past the end of the file")


def _check_rebuild(out: bytes, new_starts: List[int], slots: Sequence[Slot], new_text: dict, indexes: List[int]):
    """Every edited string reads back at its new start."""
    for index in indexes:
        if index not in new_text:
            continue
        start = new_starts[index]
        raw = new_text[index].encode("utf-16le") + b"\x00\x00"
        if out[start:start + len(raw)] != raw:
            raise CaffError(f"rebuild: string {index} is not at its new position")
