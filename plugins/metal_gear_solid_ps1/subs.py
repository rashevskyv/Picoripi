"""Subtitles of cutscenes (DEMO.DAT), voices (VOX.DAT) and movies (ZMOVIE.STR), and the ``.subs`` file.

The game keeps a subtitle block in a type-3 packet of a demo / voice stream and in the first sectors of
a movie. A block (little endian): ``u32 start, u32 end, u16 data offset, u16 subtitle offset, u32 glyph
offset``, lip-sync data, then entries ``u32 size (0 = the last), u32 start, u32 duration, u32 0`` and the
line (NUL, padded to 4), then the block's own 12x12 glyphs. A block of zeros has no subtitles.

The workspace's unpack step copies every distinct block of both discs into ``subs/demo.subs``,
``subs/vox.subs`` and ``subs/movie.subs`` (the containers are hundreds of MB); this plugin edits the
lines there, the build step puts each block back everywhere it came from. ``.subs`` (little endian):
``b"MGS1SUB\\x01"``, ``u32 count``, then per block ``u32 room`` (the most bytes it may take),
``u32 places``, ``places`` x ``(u8 disc, u8 kind, u16 0, u32 a, u32 b)`` (demo / vox: the stream's offset
and the packet's offset in the file; movie: the first sector and the sector count), ``u32 size`` and the
block.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

MAGIC = b"MGS1SUB\x01"
KINDS = ("demo", "vox", "movie")


class FormatError(ValueError):
    """Not a subtitle block or ``.subs`` file this plugin understands."""


@dataclass
class Entry:
    start: int
    duration: int
    extra: int
    text: bytes


@dataclass
class Block:
    raw: bytes
    entries: List[Entry] = field(default_factory=list)
    head: bytes = b""          # the header and lip-sync data, up to the subtitle offset
    glyphs: bytes = b""

    @classmethod
    def parse(cls, raw: bytes) -> "Block":
        if len(raw) < 16:
            raise FormatError("subtitle block too short")
        _start, _end, data_at, subs_at, glyphs_at = struct.unpack_from("<IIHHI", raw, 0)
        if not 16 <= subs_at <= len(raw) or data_at > subs_at or glyphs_at > len(raw):
            raise FormatError("not a subtitle block")
        block = cls(bytes(raw), head=bytes(raw[:subs_at]), glyphs=bytes(raw[glyphs_at:]))
        if raw[subs_at:subs_at + 12] == bytes(12):
            return block
        pos = subs_at
        while True:
            if pos + 16 > len(raw):
                raise FormatError("subtitle entry runs past the block")
            size, start, duration, extra = struct.unpack_from("<4I", raw, pos)
            stop = raw.find(b"\0", pos + 16)
            if stop < 0:
                raise FormatError("subtitle line has no end")
            block.entries.append(Entry(start, duration, extra, bytes(raw[pos + 16:stop])))
            if size == 0:
                break
            if size < 16 or pos + size > len(raw):
                raise FormatError(f"bad subtitle entry at {pos:#x}")
            pos += size
        return block

    def build(self, texts: Optional[Sequence[bytes]] = None) -> bytes:
        """The block with new lines (same timing); unchanged lines give the original bytes."""
        if texts is None or list(texts) == [entry.text for entry in self.entries]:
            return self.raw
        body = bytearray()
        for number, (entry, text) in enumerate(zip(self.entries, texts)):
            padded = text + bytes(4 - len(text) % 4)
            size = 0 if number == len(self.entries) - 1 else 16 + len(padded)
            body += struct.pack("<4I", size, entry.start, entry.duration, entry.extra) + padded
        out = bytearray(self.head) + body
        struct.pack_into("<I", out, 12, len(out))
        return bytes(out + self.glyphs)


@dataclass
class Record:
    room: int
    places: List[Tuple[int, int, int, int]]          # (disc, kind, a, b)
    raw: bytes

    @property
    def kind(self) -> str:
        return KINDS[self.places[0][1]] if self.places else "demo"


def is_subs(data: bytes) -> bool:
    return data[:8] == MAGIC


def read(data: bytes) -> List[Record]:
    if not is_subs(data):
        raise FormatError("not a .subs file")
    count = struct.unpack_from("<I", data, 8)[0]
    pos, records = 12, []
    for _ in range(count):
        room, places = struct.unpack_from("<II", data, pos)
        pos += 8
        where = []
        for _place in range(places):
            disc, kind, _pad, a, b = struct.unpack_from("<BBHII", data, pos)
            where.append((disc, kind, a, b))
            pos += 12
        size = struct.unpack_from("<I", data, pos)[0]
        records.append(Record(room, where, bytes(data[pos + 4:pos + 4 + size])))
        pos += 4 + size
    return records


def write(records: Sequence[Record]) -> bytes:
    out = bytearray(MAGIC + struct.pack("<I", len(records)))
    for record in records:
        out += struct.pack("<II", record.room, len(record.places))
        for disc, kind, a, b in record.places:
            out += struct.pack("<BBHII", disc, kind, 0, a, b)
        out += struct.pack("<I", len(record.raw)) + record.raw
    return bytes(out)
