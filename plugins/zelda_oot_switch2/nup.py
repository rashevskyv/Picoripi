r"""Nintendo Switch 2 ``.nup`` packages: an unencrypted exefs + romfs file tree behind a table of contents. Read-only.

Layout, little-endian, measured on The Legend of Zelda: Ocarina of Time (title 0400486024DEC000, version 131072):

- ``0x00`` ``NUP\x01``; ``0x40`` u64 package size.
- ``0x80`` ``TOC\x01``; ``0x88`` u64 directory count; ``0x90`` u64 file count; ``0x98`` u64 offset of the name
  pool from ``0x80``; ``0xA0`` u64 name pool size; ``0xB0`` u64 title id; ``0xC4`` u32 title version.
- ``0xF0`` directories, 24 bytes each: u32 name offset, u32 name length, u32 first child, u32 child count, 8 zero
  bytes. Directory 0 is the root (``exefs``, ``romfs``).
- Files, 80 bytes each: u32 name offset, u32 name length, u64 size, u64 data offset (from the package start),
  u64 stored size, SHA-256 of the unpacked data, u32 flags (bit 0: stored as one zstd frame), 12 zero bytes.
- Children, u32 each: an index below the directory count is a directory, any other is file ``index - count``.
- The name pool: every name back to back, UTF-8, no separators.

No keys: nothing is encrypted. ``python -m plugins.zelda_oot_switch2.nup <package.nup>`` lists the files (path,
size, offset, stored size, zstd flag) without unpacking anything.
"""
from __future__ import annotations

import hashlib
import struct
import sys
from dataclasses import dataclass
from typing import BinaryIO, List, Tuple

MAGIC = b"NUP\x01"
TOC_MAGIC = b"TOC\x01"
TOC = 0x80
DIRECTORIES = 0xF0
DIR_SIZE = 24
FILE_SIZE = 80
FLAG_ZSTD = 1


@dataclass(frozen=True)
class Entry:
    path: str
    size: int
    offset: int
    stored_size: int
    compressed: bool
    sha256: bytes


def is_nup(head: bytes) -> bool:
    return head[:4] == MAGIC and head[TOC:TOC + 4] == TOC_MAGIC


def title_of(head: bytes) -> Tuple[str, int]:
    """``(title id as 16 hex digits, title version)`` from the first 0xC8 bytes of a package."""
    return f"{struct.unpack_from('<Q', head, 0xB0)[0]:016X}", struct.unpack_from("<I", head, 0xC4)[0]


class Nup:
    """The table of contents of one package; ``read`` returns one file's bytes."""

    def __init__(self, stream: BinaryIO):
        self._stream = stream
        stream.seek(0)
        head = stream.read(DIRECTORIES)
        if len(head) < DIRECTORIES or not is_nup(head):
            raise ValueError("not a NUP package")
        self.title_id, self.version = title_of(head)
        dirs, files, pool_offset, pool_size = struct.unpack_from("<QQQQ", head, 0x88)
        end = TOC + pool_offset + pool_size
        meta = head + stream.read(end - DIRECTORIES)
        children_at = DIRECTORIES + dirs * DIR_SIZE + files * FILE_SIZE
        if len(meta) != end or children_at > TOC + pool_offset:
            raise ValueError("NUP table of contents is cut short")
        pool = meta[TOC + pool_offset:end]
        children = struct.unpack_from(f"<{(TOC + pool_offset - children_at) // 4}I", meta, children_at)

        def name(offset: int, length: int) -> str:
            return pool[offset:offset + length].decode("utf-8")

        self.entries: List[Entry] = []
        stack = [(0, "")]
        while stack:
            index, prefix = stack.pop()
            _no, _nl, first, count = struct.unpack_from("<4I", meta, DIRECTORIES + index * DIR_SIZE)
            for child in reversed(children[first:first + count]):
                if child < dirs:
                    no, nl = struct.unpack_from("<2I", meta, DIRECTORIES + child * DIR_SIZE)
                    stack.append((child, prefix + name(no, nl) + "/"))
                    continue
                no, nl, size, offset, stored, digest, flags = struct.unpack_from(
                    "<IIQQQ32sI", meta, DIRECTORIES + dirs * DIR_SIZE + (child - dirs) * FILE_SIZE)
                self.entries.append(Entry(prefix + name(no, nl), size, offset, stored, bool(flags & FLAG_ZSTD), digest))
        self.entries.sort(key=lambda entry: entry.path)

    def read(self, entry: Entry) -> bytes:
        """The unpacked bytes of one file, checked against its SHA-256."""
        self._stream.seek(entry.offset)
        data = self._stream.read(entry.stored_size)
        if entry.compressed:
            from compression import zstd   # Python 3.14+
            data = zstd.decompress(data)
        if len(data) != entry.size or hashlib.sha256(data).digest() != entry.sha256:
            raise ValueError(f"NUP file {entry.path} does not match its size or SHA-256")
        return data


def main(argv: List[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m plugins.zelda_oot_switch2.nup <package.nup>", file=sys.stderr)
        return 2
    with open(argv[0], "rb") as stream:
        package = Nup(stream)
        print(f"# title {package.title_id} version {package.version}, {len(package.entries)} files")
        for entry in package.entries:
            print(f"{entry.path}\t{entry.size}\t{entry.offset:#x}\t{entry.stored_size}\t{int(entry.compressed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
