"""Subtitles of demo.dat, vox.dat and movie.dat, and the ``.subs`` file that carries them.

The three files are streams of big-endian records, one cutscene or voice clip per 0x800-aligned
slot. A slot starts with one 16-byte stream header per stream (``00000010 00000010 00000000
<lang << 16 | type>``), then records ``u32 lang << 16 | type, u32 size, u32 frame, u32 0,
payload``, then an end record of type 0xF0, then zeros up to the next slot.

A subtitle record (type 4) has a little-endian payload: ``u32 length`` of the entries, then
entries ``u32 start, u32 end, u32 speaker, u32 entry_size, text`` (NUL-terminated, padded to 4;
the speaker is the 24-bit name hash of the character, 0 in cutscenes). Languages: 1 English,
2 French, 3 German, 4 Italian, 5 Spanish, 7 Japanese (followed by its own kanji bitmaps).

The workspace's unpack step copies every subtitle record into a ``.subs`` file (the containers
are hundreds of MB). This plugin edits the records there; the build step puts them back into
the container, moving the rest of the slot by the change in size. A slot can only grow into its
own zero padding; when the English text needs more, the French-to-Spanish records of that slot
lose their text (the US game never shows them).

``.subs``: ``b"MGSSUBS\\x01"``, 4 bytes of kind (``demo``, or ``vox``/``mov`` and a NUL),
``u32 count``, then per record ``u32 offset`` (in the container),
``u32 original size``, ``u32 slot start``, ``u32 slot end`` (next slot), ``u32 data end`` (after
the end record), ``u32 size``, and ``size`` bytes of the record. All big-endian.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

MAGIC = b"MGSSUBS\x01"
SUBTITLE = 4
END = 0xF0
SECTOR = 0x800
ENGLISH = 1
FOREIGN = (2, 3, 4, 5)
_ITEM = struct.Struct(">6I")


class FormatError(ValueError):
    """Not a subtitle file or record this plugin understands."""


def _align(value: int, step: int) -> int:
    return (value + step - 1) // step * step


@dataclass
class Entry:
    start: int
    end: int
    speaker: int
    text: bytes


@dataclass
class Record:
    """One subtitle record, as stored (``raw``) and parsed."""

    offset: int = 0
    original_size: int = 0
    slot_start: int = 0
    slot_end: int = 0
    data_end: int = 0
    raw: bytes = b""
    lang: int = 0
    frame: int = 0
    entries: List[Entry] = field(default_factory=list)
    extra: bytes = b""               # what follows the entries (the Japanese kanji bitmaps)

    @classmethod
    def parse(cls, raw: bytes, **where) -> "Record":
        if len(raw) < 0x14:
            raise FormatError("subtitle record too short")
        word, size, frame, _zero = struct.unpack_from(">4I", raw, 0)
        if word & 0xFFFF != SUBTITLE or size != len(raw):
            raise FormatError(f"not a subtitle record ({word:#x}, size {size:#x} of {len(raw):#x})")
        length = struct.unpack_from("<I", raw, 0x10)[0]
        end = 0x14 + length
        if end > len(raw):
            raise FormatError("subtitle entries run past the record")
        entries: List[Entry] = []
        pos = 0x14
        while pos + 16 <= end:
            start, stop, speaker, entry_size = struct.unpack_from("<4I", raw, pos)
            if entry_size < 16 or pos + entry_size > end:
                raise FormatError(f"bad subtitle entry at {pos:#x}")
            text = raw[pos + 16:pos + entry_size].split(b"\0", 1)[0]
            entries.append(Entry(start, stop, speaker, bytes(text)))
            pos += entry_size
        return cls(raw=bytes(raw), lang=word >> 16, frame=frame, entries=entries,
                   extra=bytes(raw[end:]).rstrip(b"\0"), **where)

    def build(self, texts: Optional[List[bytes]] = None) -> bytes:
        """The record with new entry texts (same order and timing); unchanged texts give ``raw``."""
        if texts is None or texts == [entry.text for entry in self.entries]:
            return self.raw
        return self.layout(texts)

    def layout(self, texts: List[bytes]) -> bytes:
        """The record laid out from scratch with these entry texts."""
        body = bytearray()
        for entry, text in zip(self.entries, texts):
            padded = text + b"\0" * (_align(len(text) + 1, 4) - len(text))
            body += struct.pack("<4I", entry.start, entry.end, entry.speaker, 16 + len(padded)) + padded
        size = (0x14 + len(body) + len(self.extra)) // 16 * 16 + 16     # always at least one pad byte
        out = bytearray(struct.pack(">4I", (self.lang << 16) | SUBTITLE, size, self.frame, 0))
        out += struct.pack("<I", len(body)) + body + self.extra
        out += bytes(size - len(out))
        return bytes(out)


KINDS = {b"demo": "cutscene", b"vox\0": "voice", b"mov\0": "movie"}


def kind_of(data: bytes) -> str:
    """``cutscene``, ``voice`` or ``movie``: what the records of a ``.subs`` file are."""
    if data[:8] != MAGIC:
        raise FormatError("not a .subs file")
    return KINDS.get(bytes(data[8:12]), "cutscene")


def read(data: bytes) -> List[Record]:
    """The records of a ``.subs`` file."""
    kind_of(data)
    count = struct.unpack_from(">I", data, 12)[0]
    pos, records = 16, []
    for _ in range(count):
        offset, original, slot_start, slot_end, data_end, size = _ITEM.unpack_from(data, pos)
        pos += _ITEM.size
        raw = data[pos:pos + size]
        pos += size
        records.append(Record.parse(raw, offset=offset, original_size=original, slot_start=slot_start,
                                    slot_end=slot_end, data_end=data_end))
    return records


def write(records: List[Record], raws: Optional[Dict[int, bytes]] = None, kind: str = "cutscene") -> bytes:
    """A ``.subs`` file; ``raws`` replaces the bytes of some records (by list index)."""
    tag = {value: key for key, value in KINDS.items()}[kind]
    out = bytearray(MAGIC + tag + struct.pack(">I", len(records)))
    for index, record in enumerate(records):
        raw = (raws or {}).get(index, record.raw)
        out += _ITEM.pack(record.offset, record.original_size, record.slot_start, record.slot_end,
                          record.data_end, len(raw)) + raw
    return bytes(out)


def rebuild(records: List[Record], texts: Dict[int, List[bytes]]) -> Tuple[Dict[int, bytes], List[str]]:
    """New bytes of the records whose English texts change (record index -> texts).

    Returns ``(raws, notes)``: when a slot would outgrow its padding, the foreign records of the
    slot lose their texts (one note per slot); a slot that still does not fit raises FormatError.
    """
    raws: Dict[int, bytes] = {index: records[index].build(new) for index, new in texts.items()}
    notes: List[str] = []
    slots: Dict[int, List[int]] = {}
    for index, record in enumerate(records):
        slots.setdefault(record.slot_start, []).append(index)
    for slot, members in slots.items():
        if not any(index in raws for index in members):
            continue

        def growth() -> int:
            return sum(len(raws.get(i, records[i].raw)) - records[i].original_size for i in members)

        room = records[members[0]].slot_end - records[members[0]].data_end
        if growth() <= room:
            continue
        for index in members:
            if records[index].lang in FOREIGN:
                raws[index] = records[index].build([b""] * len(records[index].entries))
        notes.append(f"slot {slot:#x}: foreign subtitles emptied to make room")
        if growth() > room:
            raise FormatError(f"subtitles of the slot at {slot:#x} are {growth() - room} bytes too long")
    return raws, notes


# -- the containers (used by the unpack step and the tests) -----------------------------------


def scan(container: bytes) -> List[Record]:
    """Every subtitle record of a demo.dat / vox.dat / movie.dat, with its slot."""
    found: List[Record] = []
    pos, size = 0, len(container)
    while pos + 16 <= size:
        slot_start = pos
        while pos + 16 <= size and container[pos:pos + 8] == b"\0\0\0\x10\0\0\0\x10":
            pos += 16
        if pos == slot_start:                      # not a slot: try the next sector
            pos = _align(pos + 1, SECTOR)
            continue
        slot_records: List[Tuple[int, int]] = []
        data_end = None
        while pos + 16 <= size:
            word, length = struct.unpack_from(">2I", container, pos)
            if length < 16 or pos + length > size:
                break
            if word & 0xFFFF == SUBTITLE:
                slot_records.append((pos, length))
            pos += length
            if word == END:
                data_end = pos
                break
        if data_end is None:
            raise FormatError(f"slot at {slot_start:#x} has no end record")
        slot_end = _align(data_end, SECTOR)
        while slot_end < size and not any(container[slot_end:slot_end + SECTOR]):
            slot_end += SECTOR                     # an empty sector after the slot is free too
        for offset, length in slot_records:
            found.append(Record.parse(container[offset:offset + length], offset=offset, original_size=length,
                                      slot_start=slot_start, slot_end=min(slot_end, size), data_end=data_end))
        pos = _align(data_end, SECTOR)
    return found
