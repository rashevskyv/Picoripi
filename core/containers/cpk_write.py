"""Patch files of a CRIWARE CPK archive: replaced files are appended, the table of contents names them.

The archive keeps its header, its content and its order. Each replaced file is written uncompressed at the end of
the content area (aligned like the archive), and its TOC row gets the new FileOffset, FileSize and ExtractSize. The
old bytes stay in place as unused space. The table of contents and the ETOC move behind the new content, and the
header names their new offsets. Every other file keeps its bytes.
"""
from __future__ import annotations

import struct
from typing import BinaryIO, Dict, List, Tuple

from core.containers import cpk
from core.containers.cpk import CpkError, _Reader

COPY_CHUNK = 16 << 20
DEFAULT_ALIGN = 0x800
_PACK = {0x00: ">B", 0x01: ">b", 0x02: ">H", 0x03: ">h", 0x04: ">I", 0x05: ">i", 0x06: ">Q", 0x07: ">q"}


def _pack(kind: int, value: int) -> bytes:
    fmt = _PACK.get(kind & 0x0F)
    if fmt is None:
        raise CpkError(f"a CPK column of type 0x{kind:02X} cannot take a new value")
    return struct.pack(fmt, value)


def _patch(buffer: bytearray, positions: Dict[str, Tuple[int, int]], name: str, value: int) -> None:
    kind, at = positions[name]
    width = cpk.TYPE_SIZE[kind & 0x0F]
    buffer[at:at + width] = _pack(kind, value)


def _pad(position: int, align: int) -> int:
    return (-position) % align


def _header_table(head: bytes) -> _Reader:
    if head[:4] != cpk.CPK_MAGIC:
        raise CpkError("not a CPK archive")
    reader = _Reader(head, cpk.HEADER_AT)
    if reader.rows != 1:
        raise CpkError("a CPK header must hold one row")
    return reader


def patch(source: BinaryIO, replacements: Dict[str, bytes], out: BinaryIO) -> Dict[str, int]:
    """Write the archive of ``source`` to ``out`` with the files of ``replacements`` (archive path -> new bytes).

    Returns ``{archive path: new archive offset}`` of each replaced file. Raises CpkError when a path is not in the
    archive or a table is cut short. A replacement the same size as the file it replaces still moves to the end.
    """
    source.seek(0)
    head = source.read(cpk.HEADER_AT + 8 + 0x8000)
    header = _header_table(head)
    values = header.table()[0]
    head_positions = header.value_positions()[0]
    content_at = int(values["ContentOffset"])
    content_size = int(values["ContentSize"])
    toc_at, toc_size = int(values["TocOffset"]), int(values["TocSize"])
    etoc_at, etoc_size = int(values["EtocOffset"]), int(values["EtocSize"])
    align = int(values.get("Align") or DEFAULT_ALIGN)
    source.seek(toc_at)
    toc = bytearray(source.read(toc_size))
    if len(toc) != toc_size or toc[:4] != cpk.TOC_MAGIC:
        raise CpkError("the table of contents is missing")
    source.seek(etoc_at)
    etoc = source.read(etoc_size)
    if len(etoc) != etoc_size:
        raise CpkError("the ETOC is cut short")
    toc_table = _Reader(bytes(toc), cpk.HEADER_AT)
    rows = toc_table.table()
    row_positions = toc_table.value_positions()
    base = cpk.file_base_of(content_at, toc_at)
    row_of: Dict[str, int] = {}
    for index, row in enumerate(rows):
        name = row.get("FileName")
        if name:
            folder = row.get("DirName") or ""
            row_of[f"{folder}/{name}" if folder else name] = index
    missing = [path for path in replacements if path not in row_of]
    if missing:
        raise CpkError(f"not in the archive: {missing[0]}")

    # Plan the layout first: the header holds the final offsets, so it is written before the content.
    position = content_at + content_size
    placed: List[Tuple[str, int, bytes]] = []
    for path in sorted(replacements):
        position += _pad(position, align)
        placed.append((path, position, replacements[path]))
        position += len(replacements[path])
    position += _pad(position, align)
    new_toc_at = position
    position += len(toc)
    position += _pad(position, align)
    new_etoc_at = position
    position += len(etoc)

    for path, at, data in placed:
        index = row_of[path]
        fields = row_positions[index]
        _patch(toc, fields, "FileOffset", at - base)
        _patch(toc, fields, "FileSize", len(data))
        _patch(toc, fields, "ExtractSize", len(data))

    source.seek(0)
    hdr = bytearray(source.read(content_at))
    _patch(hdr, head_positions, "TocOffset", new_toc_at)
    _patch(hdr, head_positions, "EtocOffset", new_etoc_at)
    _patch(hdr, head_positions, "ContentSize", new_toc_at - content_at)

    out.write(hdr)
    source.seek(content_at)
    left = content_size
    while left:
        chunk = source.read(min(COPY_CHUNK, left))
        if not chunk:
            raise CpkError("a CPK file is cut short")
        out.write(chunk)
        left -= len(chunk)
    written = content_at + content_size
    for _path, at, data in placed:
        out.write(b"\0" * (at - written))
        out.write(data)
        written = at + len(data)
    out.write(b"\0" * (new_toc_at - written))
    out.write(toc)
    out.write(b"\0" * (new_etoc_at - new_toc_at - len(toc)))
    out.write(etoc)
    return {path: at for path, at, _data in placed}
