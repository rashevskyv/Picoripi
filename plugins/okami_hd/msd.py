"""Okami HD message sections (MSD) inside the .bin / .dat / .pac containers: split into strings and rebuild them.

Container: u32 count, count x u32 section offsets, count x 4-character tag; section i ends where section i + 1
starts (the last one ends at the end of the file). Only ``MSD`` sections are read here; the others stay as bytes.

Two MSD layouts are read (English files; checked on every English MSD section of the Switch data):
  list   01 00 00 00 | 0c 00 00 00 | u32 X | body. X is 0 in the English files. The body is 0x0000-terminated
         u16 strings.
  table  u16 count | u16 X | count x (u32 offset, u32 0) | records. The offsets are relative to the section
         start; the first one is the end of the table. A record starts with a header of 4 units
         (8203 656d 3531 field) or of 1 unit, then 0x0000-terminated strings.
Any other section is kept as raw bytes.

Rebuilding is exact: with no change, ``serialize(parse(data)) == data``. A text change is accepted only when every
record keeps its byte length, because the file also has a RUNOFS64 table of absolute offsets (``ROF`` section) that
this code does not rewrite. Nothing here reads or writes files.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

LIST_HEADER = bytes.fromhex("01000000 0c000000")   # the first 8 bytes; the list header is 12 bytes (with X)
TABLE_HEADER_ME51 = (0x8203, 0x656D, 0x3531)  # "me51" record header, as units
SECTION_TAG = b"MSD"
TERMINATOR = b"\x00\x00"


class MsdError(ValueError):
    """The bytes are not a container or an MSD section this module reads."""


@dataclass
class Record:
    """One string group: ``head`` (raw header bytes), ``strings`` (each raw, without its terminator), ``tail``."""
    head: bytes
    strings: List[bytes]
    tail: bytes

    def byte_length(self) -> int:
        return len(self.head) + sum(len(s) + len(TERMINATOR) for s in self.strings) + len(self.tail)

    def serialize(self) -> bytes:
        return self.head + b"".join(s + TERMINATOR for s in self.strings) + self.tail


@dataclass
class MsdSection:
    """One MSD section. ``layout`` is "list" or "table"; ``prefix`` is the raw bytes before the records."""
    layout: str
    prefix: bytes
    records: List[Record]
    tail: bytes = b""          # raw bytes after the last record (table layout only)

    def serialize(self) -> bytes:
        if self.layout == "list":
            return self.prefix + self.records[0].serialize() if self.records else self.prefix
        table_end = len(self.prefix)
        body = b"".join(record.serialize() for record in self.records)
        offsets = []
        position = table_end
        for record in self.records:
            offsets.append(position)
            position += record.byte_length()
        table = bytearray(self.prefix)
        for index, offset in enumerate(offsets):
            struct.pack_into("<I", table, 4 + 8 * index, offset)
        return bytes(table) + body + self.tail


@dataclass
class Container:
    """A parsed container: the original bytes and where each section lies."""
    data: bytes
    tags: List[str]
    spans: List[Tuple[int, int]] = field(default_factory=list)

    def section_bytes(self, index: int) -> bytes:
        start, end = self.spans[index]
        return self.data[start:end]


def _units(raw: bytes) -> List[int]:
    return [struct.unpack_from("<H", raw, i)[0] for i in range(0, len(raw) - 1, 2)]


def _split_strings(raw: bytes) -> Tuple[List[bytes], bytes]:
    """Split raw bytes into 0x0000-terminated strings (raw, no terminator) and the unterminated tail."""
    strings: List[bytes] = []
    start = 0
    for pos in range(0, len(raw) - 1, 2):
        if raw[pos] == 0 and raw[pos + 1] == 0:
            strings.append(raw[start:pos])
            start = pos + 2
    return strings, raw[start:]


def parse_container(data: bytes) -> Container:
    """The section spans of a container. Raises MsdError when the header does not fit the file."""
    if len(data) < 8:
        raise MsdError("container too short")
    count = struct.unpack_from("<I", data, 0)[0]
    if not 1 <= count <= 256:
        raise MsdError("container count out of range")
    tag_at = 4 + 4 * count
    if tag_at + 4 * count > len(data):
        raise MsdError("container header is larger than the file")
    offsets = [struct.unpack_from("<I", data, 4 + 4 * i)[0] for i in range(count)]
    if any(offset > len(data) for offset in offsets) or offsets != sorted(offsets):
        raise MsdError("container offsets are not ordered")
    tags = [data[tag_at + 4 * i:tag_at + 4 * i + 4].rstrip(b"\x00").decode("latin-1") for i in range(count)]
    ends = offsets[1:] + [len(data)]
    return Container(data=data, tags=tags, spans=list(zip(offsets, ends)))


def parse_section(raw: bytes) -> Optional[MsdSection]:
    """The MSD section in ``raw``, or None when its layout is not one of the two read here."""
    if raw[:8] == LIST_HEADER and len(raw) >= 12:
        body = raw[12:]
        strings, tail = _split_strings(body)
        return MsdSection(layout="list", prefix=raw[:12], records=[Record(b"", strings, tail)])
    if len(raw) < 4:
        return None
    count, _x = struct.unpack_from("<HH", raw, 0)
    table_end = 4 + 8 * count
    if count == 0 or table_end > len(raw):
        return None
    offsets = [struct.unpack_from("<I", raw, 4 + 8 * i)[0] for i in range(count)]
    if offsets[0] != table_end or offsets != sorted(offsets) or offsets[-1] > len(raw):
        return None
    records: List[Record] = []
    for index, start in enumerate(offsets):
        end = offsets[index + 1] if index + 1 < count else len(raw)
        chunk = raw[start:end]
        units = _units(chunk)
        head_units = 4 if tuple(units[:3]) == TABLE_HEADER_ME51 else 1
        if len(units) < head_units:
            return None
        head = chunk[:2 * head_units]
        strings, tail = _split_strings(chunk[2 * head_units:])
        records.append(Record(head, strings, tail))
    return MsdSection(layout="table", prefix=raw[:table_end], records=records)


def serialize_container(container: Container, sections: dict) -> bytes:
    """The container bytes with the sections in ``sections`` (index -> new bytes) replaced.

    Every section keeps its place in the file, so offsets in the container header do not change when a section
    keeps its length. A section that changes length is rejected by the caller (``replace_strings``).
    """
    out = bytearray(container.data)
    for index, new_bytes in sections.items():
        start, end = container.spans[index]
        if len(new_bytes) != end - start:
            raise MsdError("section length changed; the file offsets would move")
        out[start:end] = new_bytes
    return bytes(out)


def strings_of(section: MsdSection) -> List[bytes]:
    """All strings of a section, in file order."""
    return [s for record in section.records for s in record.strings]


def replace_strings(section: MsdSection, new_strings: Sequence[bytes]) -> MsdSection:
    """A copy of ``section`` with its strings replaced in file order. The count must match and every record must keep
    its byte length; otherwise MsdError is raised and nothing is changed."""
    old = strings_of(section)
    if len(new_strings) != len(old):
        raise MsdError(f"string count changed ({len(new_strings)} for {len(old)})")
    out_records: List[Record] = []
    cursor = 0
    for record in section.records:
        count = len(record.strings)
        fresh = list(new_strings[cursor:cursor + count])
        cursor += count
        new_record = Record(record.head, fresh, record.tail)
        if new_record.byte_length() != record.byte_length():
            raise MsdError("a string changed length; the record must keep its byte length")
        out_records.append(new_record)
    return MsdSection(layout=section.layout, prefix=section.prefix, records=out_records, tail=section.tail)


def is_msd(container: Container, index: int) -> bool:
    return container.tags[index] == SECTION_TAG.decode("ascii")
