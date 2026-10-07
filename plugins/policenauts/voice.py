"""Policenauts dialogue text: the subtitle records in the voice chunks of ``PN_VOXn.PAC``, kept as a PNV file.

The workspace's unpack step copies the header of every voice chunk (``"jXS``, 0x800 or 0x1000 bytes) out of
``NAUTS/PN_VOXn.PAC`` into ``PN_VOXn.PNV``::

    "PNVX", u32 chunk count, u32 PAC sectors, u32 0, (u32 sector, u32 header size) per chunk, the headers

A chunk header: u32 clip count at 0x20, u32 start of the text area at 0x28, then one 32-byte entry per
clip from 0x30 (audio offset and size, lip-sync offset, u32 text offset at +0x18). A clip's text is a
list of records: u32 size (0 on the last one), u32 start time, u32 duration, u32 0, the text and its
zero, padded to 4 bytes (size = 16 + text length + 1 rounded up to 4). The English patch's text of one
chunk overflows its header and is cut by the game; that chunk keeps its bytes unless it is edited.

Writing lays the clips' lists out again from the start of the text area and zeroes the rest; a chunk
whose text did not change keeps its original bytes.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Tuple

MAGIC = b"PNVX"
CHUNK_MAGIC = b'"jXS'


class VoiceError(ValueError):
    """Not a PNV file, or a chunk that does not parse."""


@dataclass
class Record:
    a: int
    b: int
    c: int
    text: bytes


@dataclass
class Chunk:
    sector: int
    header: bytes
    clips: List[List[Record]] = field(default_factory=list)
    cut: bool = False            # the text ran past the end of the header (the game shows it cut)


def _records(header: bytes, at: int) -> Tuple[List[Record], int, bool]:
    out: List[Record] = []
    size_total = len(header)
    while True:
        if at + 16 > size_total:
            return out, size_total, True
        size, a, b, c = struct.unpack_from("<4I", header, at)
        end = header.find(b"\0", at + 16)
        if end < 0:
            out.append(Record(a, b, c, header[at + 16:]))
            return out, size_total, True
        text = header[at + 16:end]
        out.append(Record(a, b, c, text))
        at += 16 + ((len(text) + 4) & ~3)
        if size == 0:
            return out, at, False


def parse_chunk(sector: int, header: bytes) -> Chunk:
    if header[:4] != CHUNK_MAGIC or len(header) < 0x50:
        raise VoiceError(f"sector {sector}: not a voice chunk")
    count = struct.unpack_from("<I", header, 0x20)[0]
    if count > (len(header) - 0x30) // 32:
        raise VoiceError(f"sector {sector}: {count} clips")
    chunk = Chunk(sector, header)
    for clip in range(count):
        if chunk.cut:
            chunk.clips.append([])
            continue
        at = struct.unpack_from("<I", header, 0x30 + clip * 32 + 0x18)[0]
        records, _end, cut = _records(header, at)
        chunk.clips.append(records)
        chunk.cut = cut
    return chunk


def parse(data: bytes) -> List[Chunk]:
    """The chunks of a PNV file."""
    if data[:4] != MAGIC or len(data) < 16:
        raise VoiceError("not a PNV file")
    count = struct.unpack_from("<I", data, 4)[0]
    pos = 16 + count * 8
    chunks = []
    for i in range(count):
        sector, size = struct.unpack_from("<II", data, 16 + i * 8)
        if pos + size > len(data):
            raise VoiceError("PNV file is cut short")
        chunks.append(parse_chunk(sector, data[pos:pos + size]))
        pos += size
    return chunks


def build_chunk(chunk: Chunk) -> bytes:
    """The header with the clips' texts laid out again."""
    header = bytearray(chunk.header)
    start = struct.unpack_from("<I", header, 0x28)[0]
    body = bytearray()
    offsets = []
    for records in chunk.clips:
        offsets.append(start + len(body))
        records = records or [Record(0, 0, 0, b"")]
        for i, record in enumerate(records):
            size = 16 + ((len(record.text) + 4) & ~3)
            last = i == len(records) - 1
            body += struct.pack("<4I", 0 if last else size, record.a, record.b, record.c)
            body += record.text + bytes(size - 16 - len(record.text))
    if start + len(body) > len(header):
        raise VoiceError(f"sector {chunk.sector}: the text is {start + len(body) - len(header)} bytes longer "
                         f"than the chunk's header holds")
    header[start:] = bytes(body) + bytes(len(header) - start - len(body))
    for clip, offset in enumerate(offsets):
        struct.pack_into("<I", header, 0x30 + clip * 32 + 0x18, offset)
    return bytes(header)


def build(original: bytes, chunks: List[Chunk]) -> bytes:
    """The PNV file with the chunks' texts; an unchanged chunk keeps its original bytes."""
    old = parse(original)
    if len(old) != len(chunks):
        raise VoiceError("chunk count changed")
    count = len(chunks)
    out = bytearray(original[:16 + count * 8])
    for before, after in zip(old, chunks):
        if [[r.text for r in clip] for clip in before.clips] == [[r.text for r in clip] for clip in after.clips]:
            out += before.header
        else:
            out += build_chunk(after)
    return bytes(out)


def free_bytes(chunk: Chunk) -> int:
    """How many more bytes of text the chunk's header holds."""
    start = struct.unpack_from("<I", chunk.header, 0x28)[0]
    used = sum(16 + ((len(r.text) + 4) & ~3) for clip in chunk.clips for r in (clip or [Record(0, 0, 0, b"")]))
    return len(chunk.header) - start - used
