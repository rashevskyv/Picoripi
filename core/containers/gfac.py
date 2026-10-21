"""Good-Feel GFAC archives with GFCP-compressed payloads (Kirby's Epic Yarn, Wario Land: Shake It!, and related games).

Layout, read from the game's own files and checked against the decoded data:

- GFAC header (0x30 bytes): magic, version, compressed flag (0x08), table info offset (0x0C, always 0x2C),
  table info size (0x10), GFCP offset (0x14), payload size (0x18), file count (at 0x2C).
- Entry table at 0x30, 16 bytes per entry: checksum, name offset (the last entry has bit 31 set), size, data offset.
  Data offsets are file offsets. They index the decompressed payload as ``offset - gfcp_offset``.
- Names: NUL-terminated ASCII after the entry table.
- GFCP container: magic, version (1), compression type (0 none, 1 BPE), decompressed size, compressed size, payload.
  All fields little-endian.
- BPE (type 1): blocks of [pair table][token count, 2 bytes big-endian][tokens]. The pair table gives, for each
  code 0..255, either an identity entry (a literal byte) or a pair (left, right) that expands to left then right.

Checksum: checked across all 2,225 Wario Land packs. Each name always has the same checksum, including 21 names
that repeat in several packs with different sizes. So the field is a hash of the name, not of the data. It is
not CRC-32 or FNV, djb2, sdbm or Jenkins of the name. The writer copies it unchanged; edited data keeps the
name's checksum. Writing a new name would need the real hash, which is not known yet.
Alignment: every entry starts at ``align(previous end, 0x20)`` in all 2,225 packs, so ``GFAC_DATA_ALIGN`` is 0x20.
The BPE encoder is written from the format above; it does not reproduce the game's encoder byte for byte, so
only packs that were edited are re-encoded. Untouched packs keep their original bytes.
"""

from __future__ import annotations

import struct
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List

from .base_container import BaseArchiveContainer

GFAC_MAGIC = b"GFAC"
GFCP_MAGIC = b"GFCP"
GFCP_TYPE_NONE = 0
GFCP_TYPE_BPE = 1
GFAC_HEADER_SIZE = 0x30
GFAC_ENTRY_SIZE = 0x10
GFAC_DATA_ALIGN = 0x20
BPE_BLOCK_SIZE = 20000  # raw bytes per BPE block; token counts must fit 16 bits
_NAME_LAST_FLAG = 0x80000000
_NAME_MASK = 0x00FFFFFF


class GfacError(ValueError):
    """Raised for malformed or unsupported GFAC or GFCP data."""


@dataclass
class GfacEntry:
    """One file in a GFAC archive. ``checksum`` is kept as stored; ``data`` is the decompressed file."""

    name: str
    data: bytes
    checksum: int = 0


@dataclass
class GfacArchive:
    """A GFAC archive: header fields that must survive a rewrite, plus its entries."""

    entries: List[GfacEntry] = field(default_factory=list)
    version: int = 0x200
    compressed: bool = True
    gfcp_type: int = GFCP_TYPE_BPE


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def bpe_decode(payload: bytes, expected_size: int) -> bytes:
    """Decode the BPE blocks in ``payload`` until ``expected_size`` bytes are produced."""
    out = bytearray()
    pos = 0
    total = len(payload)
    while len(out) < expected_size:
        left = list(range(256))
        right = [0] * 256
        if pos >= total:
            raise GfacError("BPE payload ends before the declared size")
        code = 0
        head = payload[pos]
        pos += 1
        while True:
            if head > 127:
                code += head - 127
                head = 0
            if code == 256:
                break
            for _ in range(head + 1):
                if pos >= total:
                    raise GfacError("BPE pair table is truncated")
                value = payload[pos]
                pos += 1
                left[code] = value
                if value != code:
                    if pos >= total:
                        raise GfacError("BPE pair table is truncated")
                    right[code] = payload[pos]
                    pos += 1
                code += 1
            if code == 256:
                break
            if pos >= total:
                raise GfacError("BPE pair table is truncated")
            head = payload[pos]
            pos += 1
        if pos + 2 > total:
            raise GfacError("BPE block token count is truncated")
        count = (payload[pos] << 8) | payload[pos + 1]
        pos += 2
        if pos + count > total:
            raise GfacError("BPE block tokens are truncated")
        stack: List[int] = []
        while stack or count > 0:
            if stack:
                token = stack.pop()
            else:
                count -= 1
                token = payload[pos]
                pos += 1
            if left[token] == token:
                out.append(token)
            else:
                stack.append(right[token])
                stack.append(left[token])
    if len(out) != expected_size:
        raise GfacError("BPE output does not match the declared size")
    return bytes(out)


def _bpe_encode_block(block: bytes) -> bytes:
    """Encode one block. ponytail: greedy most-frequent-pair, full recount per round; fine for ~20 KB blocks."""
    buf = list(block)
    left = list(range(256))
    right = [0] * 256
    assigned: set = set()
    taken = set(block)
    while True:
        code = next((v for v in range(255, -1, -1) if v not in taken), None)
        if code is None:
            break
        counts = Counter(zip(buf, buf[1:]))
        if not counts:
            break
        (a, b), best = max(counts.items(), key=lambda item: (item[1], -item[0][0], -item[0][1]))
        if best < 3:
            break
        out: List[int] = []
        i = 0
        n = len(buf)
        while i < n:
            if i + 1 < n and buf[i] == a and buf[i + 1] == b:
                out.append(code)
                i += 2
            else:
                out.append(buf[i])
                i += 1
        buf = out
        left[code] = a
        right[code] = b
        assigned.add(code)
        taken.add(code)
    table = bytearray()
    value = 0
    while value < 256:
        run = min(128, 256 - value)
        table.append(run - 1)
        for c in range(value, value + run):
            table.append(left[c])
            if left[c] != c:
                table.append(right[c])
        value += run
    return bytes(table) + struct.pack(">H", len(buf)) + bytes(buf)


def bpe_encode(data: bytes) -> bytes:
    """Encode ``data`` as BPE blocks; ``bpe_decode`` restores it exactly."""
    out = bytearray()
    for start in range(0, len(data), BPE_BLOCK_SIZE):
        out += _bpe_encode_block(data[start:start + BPE_BLOCK_SIZE])
    return bytes(out)


def gfcp_unpack(raw: bytes, offset: int) -> bytes:
    """Return the decompressed bytes of the GFCP container at ``offset``."""
    if raw[offset:offset + 4] != GFCP_MAGIC:
        raise GfacError("GFCP magic not found")
    _version, gfcp_type, raw_size, comp_size = struct.unpack_from("<IIII", raw, offset + 4)
    payload = raw[offset + 0x14: offset + 0x14 + comp_size]
    if len(payload) != comp_size:
        raise GfacError("GFCP payload is truncated")
    if gfcp_type == GFCP_TYPE_NONE:
        return bytes(payload[:raw_size])
    if gfcp_type == GFCP_TYPE_BPE:
        return bpe_decode(payload, raw_size)
    raise GfacError("Unsupported GFCP compression type %d" % gfcp_type)


def gfcp_pack(data: bytes, gfcp_type: int = GFCP_TYPE_BPE) -> bytes:
    """Build a GFCP container holding ``data``."""
    if gfcp_type == GFCP_TYPE_NONE:
        payload = data
    elif gfcp_type == GFCP_TYPE_BPE:
        payload = bpe_encode(data)
    else:
        raise GfacError("Unsupported GFCP compression type %d" % gfcp_type)
    return GFCP_MAGIC + struct.pack("<IIII", 1, gfcp_type, len(data), len(payload)) + payload


def read_gfac(raw: bytes) -> GfacArchive:
    """Parse a GFAC archive and decompress its entries."""
    if raw[:4] != GFAC_MAGIC:
        raise GfacError("GFAC magic not found")
    version, compressed = struct.unpack_from("<II", raw, 4)
    gfcp_offset, _payload_size = struct.unpack_from("<II", raw, 0x14)
    count = struct.unpack_from("<I", raw, 0x2C)[0]
    if compressed:
        decompressed = gfcp_unpack(raw, gfcp_offset)
        gfcp_type = struct.unpack_from("<I", raw, gfcp_offset + 8)[0]
    else:
        decompressed = raw[gfcp_offset:]
        gfcp_type = GFCP_TYPE_NONE
    archive = GfacArchive(version=version, compressed=bool(compressed), gfcp_type=gfcp_type)
    for index in range(count):
        checksum, name_field, size, data_offset = struct.unpack_from(
            "<IIII", raw, GFAC_HEADER_SIZE + index * GFAC_ENTRY_SIZE)
        name_offset = name_field & _NAME_MASK
        name_end = raw.index(b"\0", name_offset)
        name = raw[name_offset:name_end].decode("ascii")
        start = data_offset - gfcp_offset
        data = decompressed[start:start + size]
        if len(data) != size:
            raise GfacError("Entry %s points past the payload" % name)
        archive.entries.append(GfacEntry(name=name, data=data, checksum=checksum))
    return archive


def write_gfac(archive: GfacArchive) -> bytes:
    """Build a GFAC archive from ``archive.entries``. Entries are aligned to 0x20 in the decompressed payload."""
    count = len(archive.entries)
    table_end = GFAC_HEADER_SIZE + count * GFAC_ENTRY_SIZE
    names = bytearray()
    name_offsets: List[int] = []
    for entry in archive.entries:
        name_offsets.append(table_end + len(names))
        names += entry.name.encode("ascii") + b"\0"
    info_end = table_end + len(names)
    gfcp_offset = _align(info_end, GFAC_DATA_ALIGN)
    plain = bytearray()
    data_offsets: List[int] = []
    for entry in archive.entries:
        plain += b"\0" * (_align(len(plain), GFAC_DATA_ALIGN) - len(plain))
        data_offsets.append(gfcp_offset + len(plain))
        plain += entry.data
    if archive.compressed:
        payload = gfcp_pack(bytes(plain), archive.gfcp_type)
    else:
        payload = bytes(plain)
    head = bytearray(GFAC_HEADER_SIZE)
    head[0:4] = GFAC_MAGIC
    struct.pack_into("<II", head, 4, archive.version, 1 if archive.compressed else 0)
    struct.pack_into("<I", head, 0x0C, 0x2C)
    struct.pack_into("<I", head, 0x10, info_end - 0x2C)
    struct.pack_into("<I", head, 0x14, gfcp_offset)
    struct.pack_into("<I", head, 0x18, len(payload))
    struct.pack_into("<I", head, 0x2C, count)
    table = bytearray()
    for index, entry in enumerate(archive.entries):
        last = _NAME_LAST_FLAG if index == count - 1 else 0
        table += struct.pack("<IIII", entry.checksum, name_offsets[index] | last, len(entry.data), data_offsets[index])
    body = bytes(head) + bytes(table) + bytes(names)
    body += b"\0" * (gfcp_offset - len(body))
    return body + payload


class GfacContainer(BaseArchiveContainer):
    """A GFAC pack as an archive: each entry is a file, so the texture and font sources can walk into it.

    Edits are staged per entry; ``pack`` re-encodes the pack with the same header fields and entry checksums.
    """

    MAGIC = GFAC_MAGIC

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return bytes(data[:4]) == GFAC_MAGIC

    def __init__(self, data: bytes) -> None:
        self._archive = read_gfac(bytes(data))
        self._entries = {entry.name: entry for entry in self._archive.entries}
        self._overlay: Dict[str, bytes] = {}

    def list_files(self) -> List[str]:
        return list(self._entries)

    def read_file(self, path: str) -> bytes:
        if path in self._overlay:
            return self._overlay[path]
        return self._entries[path].data

    def write_file(self, path: str, data: bytes) -> None:
        if path not in self._entries:
            raise KeyError(path)
        self._overlay[path] = bytes(data)

    def pack(self) -> bytes:
        for entry in self._archive.entries:
            if entry.name in self._overlay:
                entry.data = self._overlay[entry.name]
        return write_gfac(self._archive)
