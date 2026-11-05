"""CRIWARE CPK archives (``.cpk``): the ``@UTF`` tables of the header and of the table of contents, and the files they name.

A CPK starts with ``CPK `` and its header table at 0x10. The header names the table of contents (``TocOffset``) and the
content area (``ContentOffset``). Each row of the TOC names one file: its folder, its name, its offset inside the content
area, its stored size and its unpacked size. A stored file smaller than its unpacked size is CRILAYLA-compressed.

``read_cpk`` reads only the tables. ``read_file`` reads one file through a seekable binary stream and never loads the
archive. Nothing here writes a CPK. Reading a file of an unknown storage kind or type is a ``CpkError``.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

CPK_MAGIC = b"CPK "
TOC_MAGIC = b"TOC "
UTF_MAGIC = b"@UTF"
CRILAYLA = b"CRILAYLA"
HEADER_AT = 0x10
UTF_HEADER = 0x20
CRILAYLA_HEADER = 0x10
CRILAYLA_UNCOMPRESSED = 0x100

# The storage kind of a UTF column: the high nibble of its flag byte.
STORAGE_MASK = 0xF0
STORAGE_ZERO = 0x10        # no value
STORAGE_CONSTANT = 0x30    # one value, stored once in the column definition
STORAGE_ROW = 0x50         # one value per row

# The type of a UTF column: the low nibble of its flag byte, with the size of one value.
TYPE_SIZE = {0x00: 1, 0x01: 1, 0x02: 2, 0x03: 2, 0x04: 4, 0x05: 4, 0x06: 8, 0x07: 8, 0x08: 4, 0x0A: 4, 0x0B: 8}


class CpkError(ValueError):
    """The bytes are not a CPK archive, or a table or file is cut short or unknown."""


@dataclass(frozen=True)
class CpkFile:
    """One file of a CPK: its path (folder and name), where its stored bytes are, and its sizes."""
    path: str
    offset: int          # absolute offset in the archive
    size: int            # stored size
    extract_size: int    # unpacked size; larger than ``size`` when the file is CRILAYLA-compressed


class _Reader:
    """Big-endian access to a ``@UTF`` table held in memory."""

    def __init__(self, data: bytes, at: int) -> None:
        if data[at:at + 4] != UTF_MAGIC:
            raise CpkError("a CPK table does not start with @UTF")
        self.data = data
        self.base = at + 8          # the offsets of the header are counted from here
        self.size = struct.unpack_from(">I", data, at + 4)[0]
        if at + 8 + self.size > len(data):
            raise CpkError("a CPK table is cut short")
        self.rows_at = self.base + struct.unpack_from(">H", data, self.base + 2)[0]
        self.strings_at = self.base + struct.unpack_from(">I", data, self.base + 4)[0]
        self.data_at = self.base + struct.unpack_from(">I", data, self.base + 8)[0]
        self.columns = struct.unpack_from(">H", data, self.base + 0x10)[0]
        self.row_width = struct.unpack_from(">H", data, self.base + 0x12)[0]
        self.rows = struct.unpack_from(">I", data, self.base + 0x14)[0]

    def string(self, offset: int) -> str:
        start = self.strings_at + offset
        end = self.data.find(b"\0", start)
        if end < 0:
            raise CpkError("a CPK string is not terminated")
        return self.data[start:end].decode("utf-8", "replace")

    def value(self, kind: int, at: int) -> Any:
        size = TYPE_SIZE.get(kind & 0x0F)
        if size is None:
            raise CpkError(f"unknown CPK column type 0x{kind:02X}")
        code = kind & 0x0F
        raw = self.data[at:at + size]
        if len(raw) != size:
            raise CpkError("a CPK value is cut short")
        if code in (0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07):
            fmt = {0x00: ">B", 0x01: ">b", 0x02: ">H", 0x03: ">h", 0x04: ">I", 0x05: ">i", 0x06: ">Q", 0x07: ">q"}[code]
            return struct.unpack(fmt, raw)[0]
        if code == 0x08:
            return struct.unpack(">f", raw)[0]
        if code == 0x0A:
            return self.string(struct.unpack(">I", raw)[0])
        return (struct.unpack_from(">I", raw, 0)[0], struct.unpack_from(">I", raw, 4)[0])   # 0x0B: data (offset, size)

    def table(self) -> List[Dict[str, Any]]:
        """The rows of the table as dicts keyed by column name."""
        at = UTF_HEADER + self.base - 8      # the first column definition follows the 0x20-byte header
        names: List[str] = []
        constants: Dict[str, Any] = {}
        kinds: List[int] = []
        for _ in range(self.columns):
            flags = self.data[at]
            name = self.string(struct.unpack_from(">I", self.data, at + 1)[0])
            at += 5
            storage = flags & STORAGE_MASK
            kind = flags
            names.append(name)
            kinds.append(kind)
            if storage == STORAGE_CONSTANT:
                constants[name] = self.value(kind, at)
                at += TYPE_SIZE[kind & 0x0F]
            elif storage not in (STORAGE_ZERO, STORAGE_ROW):
                raise CpkError(f"unknown CPK column storage 0x{storage:02X}")
        rows: List[Dict[str, Any]] = []
        for index in range(self.rows):
            row = dict(constants)
            at = self.rows_at + index * self.row_width
            for name, kind in zip(names, kinds):
                if kind & STORAGE_MASK != STORAGE_ROW:
                    continue
                row[name] = self.value(kind, at)
                at += TYPE_SIZE[kind & 0x0F]
            rows.append(row)
        return rows

    def value_positions(self) -> List[Dict[str, Tuple[int, int]]]:
        """Per row: ``{column: (type flags, offset of its value)}``. A constant column gives its definition's offset
        in every row. Offsets are in ``self.data``, so a writer can patch a value of fixed width in place."""
        at = UTF_HEADER + self.base - 8
        names: List[str] = []
        kinds: List[int] = []
        constant_at: Dict[str, int] = {}
        for _ in range(self.columns):
            flags = self.data[at]
            names.append(self.string(struct.unpack_from(">I", self.data, at + 1)[0]))
            kinds.append(flags)
            at += 5
            if flags & STORAGE_MASK == STORAGE_CONSTANT:
                constant_at[names[-1]] = at
                at += TYPE_SIZE[flags & 0x0F]
        rows: List[Dict[str, Tuple[int, int]]] = []
        for index in range(self.rows):
            row = {name: (kind, constant_at[name]) for name, kind in zip(names, kinds) if name in constant_at}
            at = self.rows_at + index * self.row_width
            for name, kind in zip(names, kinds):
                if kind & STORAGE_MASK == STORAGE_ROW:
                    row[name] = (kind, at)
                    at += TYPE_SIZE[kind & 0x0F]
            rows.append(row)
        return rows


def _table_at(data: bytes, at: int) -> List[Dict[str, Any]]:
    return _Reader(data, at).table()


def file_base_of(content_at: int, toc_at: int) -> int:
    """The archive offset that a row's FileOffset counts from.

    The FileOffset of each row counts from a base at most 0x800 (CriPakTools' rule): the content area when it lies
    before that cap, else the cap. A table of contents placed at the end of the archive does not move the base.
    """
    toc_base = min(toc_at, 0x800)
    return content_at if content_at < toc_base else toc_base


def read_cpk(stream: BinaryIO) -> List[CpkFile]:
    """The files of the CPK in ``stream``, read from its tables only."""
    stream.seek(0)
    head = stream.read(HEADER_AT + 8 + 0x8000)
    if head[:4] != CPK_MAGIC:
        raise CpkError("not a CPK archive")
    header = _table_at(head, HEADER_AT)
    if len(header) != 1:
        raise CpkError("a CPK header must hold one row")
    toc_at = int(header[0]["TocOffset"])
    toc_size = int(header[0]["TocSize"])
    content_at = int(header[0]["ContentOffset"])
    if toc_size < HEADER_AT + 8:
        raise CpkError("the table of contents is missing")
    stream.seek(toc_at)
    toc_data = stream.read(toc_size)
    if len(toc_data) != toc_size or toc_data[:4] != TOC_MAGIC:
        raise CpkError("the table of contents is missing")
    file_base = file_base_of(content_at, toc_at)
    files: List[CpkFile] = []
    for row in _table_at(toc_data, HEADER_AT):
        name = row.get("FileName")
        if not name:
            continue
        folder = row.get("DirName") or ""
        path = f"{folder}/{name}" if folder else name
        offset = file_base + int(row.get("FileOffset", 0))
        size = int(row.get("FileSize", 0))
        extract = int(row.get("ExtractSize", size))
        files.append(CpkFile(path, offset, size, extract))
    return files


def read_file(stream: BinaryIO, entry: CpkFile) -> bytes:
    """The unpacked bytes of one file of the archive."""
    stream.seek(entry.offset)
    raw = stream.read(entry.size)
    if len(raw) != entry.size:
        raise CpkError("a CPK file is cut short")
    if raw[:8] == CRILAYLA and entry.extract_size > entry.size:
        return crilayla_decompress(raw, entry.extract_size)
    return raw


def crilayla_decompress(raw: bytes, extract_size: Optional[int] = None) -> bytes:
    """Unpack a CRILAYLA stream (as CriPakTools reads it).

    Layout: ``CRILAYLA``; u32 LE at 8 = the unpacked size; u32 LE at 12 = the size of the compressed bit stream, which
    starts at 0x10. A raw 0x100-byte prefix follows the stream. The output is the prefix followed by the unpacked data.
    The bit stream and the output are both read and written backwards. A stream that is not used up exactly (bytes
    left unread, or the reader ran past its start) is a ``CpkError``: a wrong start offset decodes to garbage.
    """
    out, in_off, rest = _crilayla_decode(raw)
    # The bytes the reader did not reach, and the unused bits of the last byte it read, are zero padding.
    if rest or any(raw[CRILAYLA_HEADER:in_off + 1]):
        raise CpkError("a CRILAYLA stream is not used up exactly")
    if extract_size is not None and len(out) != extract_size:
        raise CpkError("a CRILAYLA stream does not unpack to the table's size")
    return out


def _crilayla_decode(raw: bytes) -> Tuple[bytes, int, int]:
    """The output, the next byte the bit reader would read, and the unread bits of the byte it read last."""
    if raw[:8] != CRILAYLA:
        raise CpkError("not a CRILAYLA stream")
    size = struct.unpack_from("<I", raw, 8)[0]
    stream_size = struct.unpack_from("<I", raw, 12)[0]
    prefix_at = CRILAYLA_HEADER + stream_size
    if prefix_at + CRILAYLA_UNCOMPRESSED > len(raw):
        raise CpkError("a CRILAYLA stream is cut short")
    total = CRILAYLA_UNCOMPRESSED + size
    out = bytearray(total)
    out[0:CRILAYLA_UNCOMPRESSED] = raw[prefix_at:prefix_at + CRILAYLA_UNCOMPRESSED]
    in_off = prefix_at - 1
    pool = 0
    bits_left = 0

    def get_bits(count: int) -> int:
        nonlocal in_off, pool, bits_left
        value = 0
        got = 0
        while got < count:
            if bits_left == 0:
                if in_off < CRILAYLA_HEADER:
                    raise CpkError("a CRILAYLA stream is cut short")
                pool = raw[in_off]
                bits_left = 8
                in_off -= 1
            take = min(bits_left, count - got)
            value = (value << take) | ((pool >> (bits_left - take)) & ((1 << take) - 1))
            bits_left -= take
            got += take
        return value

    out_end = CRILAYLA_UNCOMPRESSED + size - 1
    written = 0
    levels = (2, 3, 5, 8)
    while written < size:
        if get_bits(1):
            ref = out_end - written + get_bits(13) + 3
            length = 3
            for bits in levels:
                value = get_bits(bits)
                length += value
                if value != (1 << bits) - 1:
                    break
            else:
                while True:
                    value = get_bits(8)
                    length += value
                    if value != 0xFF:
                        break
            for _ in range(length):
                if written >= size:
                    break
                if ref < 0 or ref >= total:
                    raise CpkError("a CRILAYLA back reference is outside the output")
                out[out_end - written] = out[ref]
                ref -= 1
                written += 1
        else:
            if written >= size:
                break
            out[out_end - written] = get_bits(8)
            written += 1
    rest = pool & ((1 << bits_left) - 1)
    return bytes(out), in_off, rest
