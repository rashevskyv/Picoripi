"""Game archive of Conker's Bad Fur Day (US ROM): code chunks and the data section, read and rebuilt.

Layout at ``ARCHIVE_START`` (relative offsets below): word 0 is the data section's start. Words 1..n are the code
chunk starts, XOR-encoded with ``OFFSET_KEY``; the list ends with the code end and a zero word. Each code chunk is
one RZIP entry (``n64_archive``). The data section is one RZIP entry at the data start. The archive ends where the
flat RZIP stream begins (``ARCHIVE_END``).

``parse`` reads the archive. ``build`` writes it again. Unchanged chunks keep their stored bytes, so an unchanged
archive is rebuilt byte for byte. A changed chunk is re-encoded (zlib level 9). The chunks after it, the padding and
the data section move by the growth. The header keeps its size and the trailing bytes keep the archive span.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, List

from . import n64_archive as na

ARCHIVE_START = 0x42450
ARCHIVE_END = 0x1A37E0          # the flat RZIP stream starts here (storage map)
OFFSET_KEY = 0x8039CCCA
CODE_BASE = 0x15000000          # RAM address of the decoded code's first byte
CHUNK_BYTES = 4096              # decoded size of a code chunk; the stored chunk must stay within it too


@dataclass
class Archive:
    header: bytes                 # ARCHIVE_START .. first chunk, as read (the table is rewritten by build)
    data_start: int              # relative to ARCHIVE_START, as read
    offsets: List[int]            # chunk starts (relative), then the code end
    stored: List[bytes]           # stored RZIP bytes of each code chunk
    padding: bytes                # code end .. data start
    data_stored: bytes            # stored RZIP bytes of the data section
    trailer: bytes                # data end .. ARCHIVE_END
    changed: Dict[int, bytes] = field(default_factory=dict)  # stored bytes of changed chunks, by index
    changed_payload: Dict[int, bytes] = field(default_factory=dict)  # their decoded bytes

    @property
    def chunk_count(self) -> int:
        return len(self.stored)

    def decoded(self, index: int) -> bytes:
        if index in self.changed_payload:
            return self.changed_payload[index]
        return na.decode_rzip(self.stored[index])[0]

    def decoded_code(self) -> bytes:
        return b"".join(self.decoded(i) for i in range(self.chunk_count))

    def data(self) -> bytes:
        return na.decode_rzip(self.data_stored)[0]

    def set_chunk(self, index: int, payload: bytes, level: int = 9) -> None:
        """Replace one code chunk's decoded bytes. The length must not change: the code's RAM layout depends on it."""
        if len(payload) != len(self.decoded(index)):
            raise na.RomError("a code chunk keeps its decoded length")
        self.changed_payload[index] = bytes(payload)
        self.changed[index] = na.encode_rzip(bytes(payload), level)


def parse(rom: bytes) -> Archive:
    """Read the archive from a normalized US ROM."""
    raw = bytes(rom[ARCHIVE_START:ARCHIVE_END])
    data_start = struct.unpack_from(">I", raw, 0)[0]
    encoded: List[int] = []
    index = 1
    while True:
        word = struct.unpack_from(">I", raw, index * 4)[0]
        if word == 0:
            break
        encoded.append(word ^ OFFSET_KEY)
        index += 1
    if len(encoded) < 2 or encoded != sorted(encoded) or encoded[0] < (len(encoded) + 2) * 4:
        raise na.RomError("game archive offset table is not valid")
    code_end = encoded[-1]
    if not code_end <= data_start < len(raw):
        raise na.RomError("game archive data start lies outside the archive")
    stored: List[bytes] = []
    for start, end in zip(encoded, encoded[1:]):
        blob = raw[start:end]
        na.decode_rzip(blob)  # must be a valid RZIP entry; zero padding after the stream is kept as stored
        stored.append(blob)
    _payload, used = na.decode_rzip(raw[data_start:])
    return Archive(header=raw[:encoded[0]], data_start=data_start, offsets=encoded, stored=stored,
                   padding=raw[code_end:data_start], data_stored=raw[data_start:data_start + used],
                   trailer=raw[data_start + used:])


def build(archive: Archive) -> bytes:
    """The archive's bytes at ``ARCHIVE_START``. Raises ``RomError`` when it does not fit the span."""
    first = archive.offsets[0]
    stored: List[bytes] = []
    for index, blob in enumerate(archive.stored):
        if index in archive.changed:
            if len(archive.changed[index]) > CHUNK_BYTES:
                raise na.RomError(f"code chunk {index} is {len(archive.changed[index])} bytes stored; the limit is {CHUNK_BYTES}")
            stored.append(archive.changed[index])
        else:
            stored.append(blob)
    starts: List[int] = []
    cursor = first
    for blob in stored:
        starts.append(cursor)
        cursor += len(blob)
    code_end = cursor
    # the data section stays where it is while the code still fits in front of it; otherwise it moves with the code
    data_start = archive.data_start if code_end <= archive.data_start else code_end + len(archive.padding)
    if data_start < code_end:
        raise na.RomError("the code reaches the data section")
    end_of_data = data_start + len(archive.data_stored)
    if end_of_data > ARCHIVE_END - ARCHIVE_START:
        raise na.RomError(f"the archive would end at {end_of_data:#x}, past the flat stream")
    header = bytearray(archive.header)
    words = [data_start] + [start ^ OFFSET_KEY for start in starts] + [code_end ^ OFFSET_KEY]
    if len(words) * 4 + 4 > len(header):
        raise na.RomError("the offset table does not fit its header")
    header[:len(words) * 4] = b"".join(struct.pack(">I", word) for word in words)
    header[len(words) * 4:len(words) * 4 + 4] = b"\x00\x00\x00\x00"
    body = bytearray(header)
    for blob in stored:
        body += blob
    body += b"\x00" * (data_start - code_end)
    body += archive.data_stored
    span = ARCHIVE_END - ARCHIVE_START
    room = span - len(body)
    if room < 0:
        raise na.RomError("the archive does not fit its span")
    # the trailer keeps the span: it is cut by the growth and never longer than the room left
    trail = archive.trailer[:room]
    return bytes(body) + trail + b"\xff" * (room - len(trail))
