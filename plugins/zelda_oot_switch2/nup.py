r"""Nintendo Switch 2 ``.nup`` packages: an unencrypted exefs + romfs file tree behind a table of contents.

Layout, little-endian, measured on The Legend of Zelda: Ocarina of Time (title 0400486024DEC000, version 131072):

- ``0x00`` ``NUP\x01``; ``0x08`` u64 table of contents offset (``0x80``); ``0x10`` u64 its size; ``0x18`` SHA-256
  of the table of contents (``0x80`` up to the data); ``0x38`` u64 data offset; ``0x40`` u64 package size;
  ``0x50`` 16 bytes that no MD5/SHA-1/SHA-256 of the package, its data or its trailer gives (kept as they are).
- ``0x80`` ``TOC\x01``; ``0x88`` u64 directory count; ``0x90`` u64 file count; ``0x98`` u64 offset of the name
  pool from ``0x80``; ``0xA0`` u64 name pool size; ``0xB0`` u64 title id; ``0xC4`` u32 title version; ``0xD0`` u64
  trailer offset; ``0xD8`` u64 trailer size.
- ``0xF0`` directories, 24 bytes each: u32 name offset, u32 name length, u32 first child, u32 child count, 8 zero
  bytes. Directory 0 is the root (``exefs``, ``romfs``).
- Files, 80 bytes each: u32 name offset, u32 name length, u64 size, u64 data offset (from the package start),
  u64 stored size, SHA-256 of the unpacked data, u32 flags (bit 0: stored as one zstd frame), 12 zero bytes.
- Children, u32 each: an index below the directory count is a directory, any other is file ``index - count``.
- The name pool: every name back to back, UTF-8, no separators.
- The data: each distinct file once, 16-aligned, zero padding; files with the same bytes share one offset.
- The trailer: typed blocks (u32 type, u32 size): the ``main.npdm`` copy, the JPEG icon, the version string, the
  title name. Nothing in it signs the package; the npdm's own signature covers only the npdm.

No keys: nothing is encrypted. ``python -m plugins.zelda_oot_switch2.nup <package.nup>`` lists the files (path,
size, offset, stored size, zstd flag) without unpacking anything. ``write`` makes a new package with some files
replaced; ``update`` rewrites such a package in place (only the bytes after the source's data), so a rebuild does
not copy the whole package again.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable, Dict, List, Optional, Tuple

from core.i18n import tr

MAGIC = b"NUP\x01"
TOC_MAGIC = b"TOC\x01"
TOC = 0x80
DIRECTORIES = 0xF0
DIR_SIZE = 24
FILE_SIZE = 80
FLAG_ZSTD = 1
ALIGN = 16
CHUNK = 64 << 20
SOURCE_RECORD = ".source.json"   # beside a written package: the source and package it was made from


@dataclass(frozen=True)
class Entry:
    path: str
    size: int
    offset: int
    stored_size: int
    compressed: bool
    sha256: bytes
    index: int = -1   # the file record's number in the table of contents


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
            raise ValueError(tr("This file is not a NUP package."))
        self.title_id, self.version = title_of(head)
        dirs, files, pool_offset, pool_size = struct.unpack_from("<QQQQ", head, 0x88)
        self.directory_count = dirs
        self.data_start = struct.unpack_from("<Q", head, 0x38)[0]
        self.trailer_offset, self.trailer_size = struct.unpack_from("<QQ", head, 0xD0)
        end = TOC + pool_offset + pool_size
        meta = head + stream.read(end - DIRECTORIES)
        children_at = DIRECTORIES + dirs * DIR_SIZE + files * FILE_SIZE
        if len(meta) != end or children_at > TOC + pool_offset:
            raise ValueError(tr("The table of contents of this NUP package is cut short."))
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
                    "<IIQQQ32sI", meta, self.record_at(child - dirs))
                self.entries.append(Entry(prefix + name(no, nl), size, offset, stored, bool(flags & FLAG_ZSTD),
                                          digest, child - dirs))
        self.entries.sort(key=lambda entry: entry.path)

    def record_at(self, index: int) -> int:
        """Where file record ``index`` starts in the package."""
        return DIRECTORIES + self.directory_count * DIR_SIZE + index * FILE_SIZE

    def read(self, entry: Entry) -> bytes:
        """The unpacked bytes of one file, checked against its SHA-256."""
        self._stream.seek(entry.offset)
        data = self._stream.read(entry.stored_size)
        if entry.compressed:
            from compression import zstd   # Python 3.14+
            data = zstd.decompress(data)
        if len(data) != entry.size or hashlib.sha256(data).digest() != entry.sha256:
            raise ValueError(tr("The file {0} in the NUP package does not match its size or SHA-256.", entry.path))
        return data


def write(source: str | os.PathLike, target: str | os.PathLike, changes: Dict[str, bytes],
          progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write ``source`` with the files in ``changes`` (package path -> new bytes) replaced, as ``target``.

    Every other byte stays as it is: the replaced files go after the old data (16-aligned, compressed when the
    original was), their records get the new size, offset, stored size and SHA-256, the trailer moves behind them,
    and the header gets the new table of contents hash and package size. The old copies stay where they were.
    ``target`` is written through a temporary file next to it and never equals ``source``. Returns ``target``,
    or None when cancelled.
    """
    source, target = Path(source), Path(target)
    if target.resolve() == source.resolve():
        raise ValueError(tr("The NUP package cannot be written over its source."))
    tmp = target.with_name(target.name + ".tmp")
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(source, "rb") as stream:
        package = Nup(stream)
        changes = _changed(package, changes)
        total = package.trailer_offset + sum(len(data) for data in changes.values())
        try:
            with open(tmp, "wb") as out:
                if not _copy(stream, out, package.trailer_offset, total, progress, is_cancelled):
                    out.close()
                    tmp.unlink()
                    return None
                _write_tail(stream, out, package, changes)
                out.flush()
                os.fsync(out.fileno())
        except BaseException:
            if tmp.exists():
                tmp.unlink()
            raise
    os.replace(tmp, target)
    _remember(source, target)
    progress(100, "")
    return str(target)


def update(source: str | os.PathLike, target: str | os.PathLike, changes: Dict[str, bytes],
           progress: Callable[[int, str], None]) -> str:
    """Rewrite ``target``, a package ``write`` made from ``source``, with ``changes`` instead; returns ``target``.

    Everything before the source's trailer is the source's own bytes in both, so only the replaced files, the
    trailer and the header are written: the result has the same bytes as a new ``write``. The source record is
    removed first and written last, so an update cut short is never taken for a good package (the next build
    copies everything again). Raises ValueError when ``target`` was not made from this ``source``.
    """
    source, target = Path(source), Path(target)
    if not is_update_of(source, target):
        raise ValueError(tr("The NUP package was not built from this source; build it again from the start."))
    _record(target).unlink()
    with open(source, "rb") as stream, open(target, "r+b") as out:
        package = Nup(stream)
        changes = _changed(package, changes)
        progress(10, "")
        out.seek(package.trailer_offset)
        end = _write_tail(stream, out, package, changes)
        out.truncate(end)
        out.flush()
        os.fsync(out.fileno())
    _remember(source, target)
    progress(100, "")
    return str(target)


def is_update_of(source: str | os.PathLike, target: str | os.PathLike) -> bool:
    """True when ``target`` is a package ``write`` or ``update`` made from ``source`` and unchanged since."""
    try:
        record = json.loads(_record(Path(target)).read_text(encoding="utf-8"))
        return record == _facts(Path(source), Path(target))
    except (OSError, ValueError):
        return False


def _record(target: Path) -> Path:
    return target.with_name(target.name + SOURCE_RECORD)


def _facts(source: Path, target: Path) -> Dict[str, object]:
    made, used = source.stat(), target.stat()
    return {"source": str(source.resolve()), "source_size": made.st_size, "source_mtime_ns": made.st_mtime_ns,
            "size": used.st_size, "mtime_ns": used.st_mtime_ns}


def _remember(source: Path, target: Path) -> None:
    record = _record(target)
    tmp = record.with_name(record.name + ".tmp")
    tmp.write_text(json.dumps(_facts(source, target)), encoding="utf-8")
    os.replace(tmp, record)


def _changed(package: Nup, changes: Dict[str, bytes]) -> Dict[str, bytes]:
    """The changes that differ from the package's own files; a path not in the package is refused."""
    by_path = {entry.path: entry for entry in package.entries}
    unknown = sorted(set(changes) - set(by_path))
    if unknown:
        raise ValueError(tr("{0}: not in the NUP package (new files are not written)", unknown[0]))
    return {path: data for path, data in changes.items() if hashlib.sha256(data).digest() != by_path[path].sha256}


def _write_tail(stream: BinaryIO, out: BinaryIO, package: Nup, changes: Dict[str, bytes]) -> int:
    """From the source's trailer offset on (``out`` stands there): the changed files, the trailer, then the header.

    Returns the new package size.
    """
    by_path = {entry.path: entry for entry in package.entries}
    stream.seek(0)
    meta = bytearray(stream.read(package.data_start))
    position = package.trailer_offset
    for path in sorted(changes):
        entry, data = by_path[path], changes[path]
        if entry.compressed:
            from compression import zstd   # Python 3.14+
            stored = zstd.compress(data)
        else:
            stored = data
        position = _pad(out, position)
        out.write(stored)
        struct.pack_into("<QQQ32s", meta, package.record_at(entry.index) + 8, len(data), position,
                         len(stored), hashlib.sha256(data).digest())
        position += len(stored)
    position = _pad(out, position)
    stream.seek(package.trailer_offset)
    trailer = stream.read()
    out.write(trailer)
    struct.pack_into("<Q", meta, 0xD0, position)
    struct.pack_into("<Q", meta, 0x40, position + len(trailer))
    meta[0x18:0x38] = hashlib.sha256(bytes(meta[TOC:package.data_start])).digest()
    out.seek(0)
    out.write(meta)
    return position + len(trailer)


def _copy(stream: BinaryIO, out: BinaryIO, length: int, total: int,
          progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> bool:
    stream.seek(0)
    done = 0
    while done < length:
        if is_cancelled():
            return False
        chunk = stream.read(min(CHUNK, length - done))
        if not chunk:
            raise ValueError(tr("The table of contents of this NUP package is cut short."))
        out.write(chunk)
        done += len(chunk)
        progress(done * 99 // max(total, 1), "")
    return True


def _pad(out: BinaryIO, position: int) -> int:
    padding = -position % ALIGN
    out.write(b"\0" * padding)
    return position + padding


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
