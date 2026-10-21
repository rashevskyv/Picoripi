"""Conker: Live & Reloaded text files (CAFF ``default.bin``): find the dialogue strings and write them back in place.

A file starts with ``CAFF`` and holds an ``LSBL`` block. The u32 at ``LSBL + 32`` counts its dialogue strings.
Each string is UTF-16LE, NUL-terminated, and lies after ``LSBL + 48``. Key names (``cutscene_...``) and the
empty string are stored in the same blob and are not text, so they are skipped.

Only text that fits its slot can be written: a string keeps its byte capacity (its original length), and a shorter
text is padded with NUL units. Growth needs the block's offset table, which is not decoded yet (see OPEN_ITEMS).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence
import struct

MAGIC = b"CAFF"
LSBL = b"LSBL"
COUNT_OFFSET = 32
TEXT_START_OFFSET = 48
SKIPPED_PREFIXES = ("cutscene_",)
SKIPPED_NAMES = ("EmptyString",)


class CaffError(ValueError):
    """The bytes are not a CAFF text file this plugin reads."""


class SlotOverflow(ValueError):
    """A new text does not fit the capacity of its slot."""

    def __init__(self, index: int, needed: int, capacity: int):
        super().__init__(f"string {index}: {needed} bytes do not fit {capacity} bytes")
        self.index = index
        self.needed = needed
        self.capacity = capacity


@dataclass(frozen=True)
class Slot:
    """One dialogue string: its byte offset, its capacity in bytes (without the NUL) and its text."""

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


def read_slots(data: bytes) -> List[Slot]:
    """Return the dialogue strings of one CAFF text file, in file order."""
    if not data.startswith(MAGIC):
        raise CaffError("missing CAFF header")
    lsbl = data.find(LSBL)
    if lsbl < 0:
        raise CaffError("missing LSBL block")
    count = struct.unpack_from("<I", data, lsbl + COUNT_OFFSET)[0]
    slots: List[Slot] = []
    for offset, capacity, text in _scan_runs(data, lsbl + TEXT_START_OFFSET):
        if text.startswith(SKIPPED_PREFIXES) or text in SKIPPED_NAMES:
            continue
        slots.append(Slot(offset, capacity, text))
        if len(slots) == count:
            break
    if len(slots) != count:
        raise CaffError(f"found {len(slots)} strings, the block counts {count}")
    return slots


def has_letter(text: str) -> bool:
    """True for a string a translator reads: it holds an ASCII letter. Other runs are codes of the block."""
    return any("A" <= ch <= "Z" or "a" <= ch <= "z" for ch in text)


def translatable(slots: Sequence[Slot]) -> List[int]:
    """Indexes (into ``slots``) of the strings a translator edits, in file order."""
    return [index for index, slot in enumerate(slots) if has_letter(slot.text)]


def write_slots(data: bytes, texts: Sequence[str]) -> bytes:
    """Return the file with the translatable strings replaced by ``texts`` (in ``translatable`` order).

    Each text must fit its slot. The other runs stay as they are. No growth: a longer text raises SlotOverflow.
    """
    slots = read_slots(data)
    indexes = translatable(slots)
    if len(texts) != len(indexes):
        raise CaffError(f"{len(texts)} texts for {len(indexes)} strings")
    out = bytearray(data)
    for position, (index, text) in enumerate(zip(indexes, texts)):
        slot = slots[index]
        encoded = text.encode("utf-16le")
        if len(encoded) > slot.capacity:
            raise SlotOverflow(position, len(encoded), slot.capacity)
        out[slot.offset:slot.offset + slot.capacity] = encoded + b"\x00" * (slot.capacity - len(encoded))
    return bytes(out)
