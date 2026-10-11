"""Unreal Engine ``.pak`` files, version 8 (Unreal Engine 4): read the index and the entries, write an unencrypted pak.

Layout (little-endian): entries (each a record header followed by its data, compressed blocks when the method is not
0), the index (mount point, entry count, then per entry: name, the record header fields), the footer: encryption
key guid (16), encrypted-index flag (1), magic 0x5A6F12E1, version (4), index offset (8), index size (8), SHA-1 of
the index (20), then five compression method names (32 bytes each; method n is the n-th name, 1-based, 0 = none).

Record header: offset (8, 0 in the index copy), size (8), uncompressed size (8), method (4), SHA-1 (20); when the
method is not 0: block count (4) and the (start, end) of each block (8 + 8, relative to the record's offset); then
the encrypted flag (1) and the compression block size (4). Uncompressed data follows the 53-byte header.

Zstd comes from the standard library (``compression.zstd``, Python 3.14+); zlib from ``zlib``. Encrypted indexes and
entries are refused (the keys are the game's; none is needed for the games read so far).
"""
from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

MAGIC = 0x5A6F12E1
FOOTER_SIZE_V8 = 16 + 1 + 4 + 4 + 8 + 8 + 20 + 5 * 32
NAME_SIZE = 32
METHOD_NAMES_V8 = ("Zlib", "Gzip", "Oodle")  # written when a pak has no names of its own


class PakError(ValueError):
    pass


@dataclass
class Entry:
    name: str
    offset: int
    size: int
    usize: int
    method: int
    blocks: List[tuple] = field(default_factory=list)
    block_size: int = 0
    encrypted: int = 0


@dataclass
class Pak:
    """A pak opened for reading: ``read(offset, size)`` gives bytes of the pak file."""

    read: Callable[[int, int], bytes]
    size: int
    version: int
    mount: str
    entries: List[Entry]
    methods: List[str]
    closer: Optional[Callable[[], None]] = field(default=None, repr=False)  # closes the file of open_path

    def close(self) -> None:
        """Release the pak file, when ``open_path`` opened one. Safe to call twice."""
        if self.closer is not None:
            self.closer()
            self.closer = None

    def __enter__(self) -> "Pak":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def names(self) -> List[str]:
        return [entry.name for entry in self.entries]

    def data(self, entry: Entry) -> bytes:
        """The uncompressed bytes of an entry."""
        if entry.encrypted:
            raise PakError(f"{entry.name}: encrypted entries are not read")
        base = entry.offset
        if entry.method == 0:
            out = self.read(base + 53, entry.usize)
        else:
            name = self.methods[entry.method - 1] if 0 < entry.method <= len(self.methods) else ""
            parts = []
            for start, end in entry.blocks:
                raw = self.read(base + start, end - start)
                if name == "Zstd":
                    from compression import zstd
                    parts.append(zstd.decompress(raw))
                elif name in ("Zlib", "Gzip"):
                    parts.append(zlib.decompress(raw, 47 if name == "Gzip" else 15))
                else:
                    raise PakError(f"{entry.name}: compression {name or entry.method!r} is not read")
            out = b"".join(parts)
        if len(out) != entry.usize:
            raise PakError(f"{entry.name}: {len(out)} bytes, the index says {entry.usize}")
        return out


def _fstring(index: bytes, pos: int):
    n = struct.unpack_from("<i", index, pos)[0]
    pos += 4
    if n == 0:
        return "", pos
    if n < 0:
        end = pos - 2 * n - 2
        return index[pos:end].decode("utf-16le"), end + 2
    return index[pos:pos + n - 1].decode("ascii", "replace"), pos + n


def open_pak(read: Callable[[int, int], bytes], size: int) -> Pak:
    """Parse a pak of ``size`` bytes; ``read(offset, length)`` returns its bytes."""
    tail = read(size - FOOTER_SIZE_V8, FOOTER_SIZE_V8)
    if struct.unpack_from("<I", tail, 17)[0] != MAGIC:
        raise PakError("not an Unreal pak (no footer magic)")
    encrypted_index = tail[16]
    version = struct.unpack_from("<I", tail, 21)[0]
    index_offset, index_size = struct.unpack_from("<QQ", tail, 25)
    if version < 8:
        raise PakError(f"pak version {version} is not read (version 8 and later are)")
    names_at = FOOTER_SIZE_V8 - 5 * NAME_SIZE
    methods = [tail[names_at + i * NAME_SIZE:names_at + (i + 1) * NAME_SIZE].split(b"\0", 1)[0].decode("ascii", "replace")
               for i in range(5)]
    methods = [m for m in methods if m]
    if encrypted_index:
        raise PakError("encrypted index: needs the game's AES key")
    index = read(index_offset, index_size)
    mount, pos = _fstring(index, 0)
    count = struct.unpack_from("<I", index, pos)[0]
    pos += 4
    entries: List[Entry] = []
    for _ in range(count):
        name, pos = _fstring(index, pos)
        offset, size_, usize, method = struct.unpack_from("<QQQI", index, pos)
        pos += 28 + 20
        blocks: List[tuple] = []
        if method:
            nb = struct.unpack_from("<I", index, pos)[0]
            pos += 4
            blocks = [struct.unpack_from("<QQ", index, pos + 16 * i) for i in range(nb)]
            pos += 16 * nb
        encrypted, block_size = struct.unpack_from("<BI", index, pos)
        pos += 5
        entries.append(Entry(name, offset, size_, usize, method, blocks, block_size, encrypted))
    return Pak(read, size, version, mount, entries, methods)


def open_path(path: Path) -> Pak:
    """Open a pak file. Close the returned pak (``close()`` or ``with``) to release the file."""
    stream = open(path, "rb")
    try:
        size = Path(path).stat().st_size

        def read(offset: int, length: int) -> bytes:
            stream.seek(offset)
            return stream.read(length)
        opened = open_pak(read, size)
    except BaseException:
        stream.close()
        raise
    opened.closer = stream.close
    return opened


def _fstring_bytes(text: str) -> bytes:
    raw = text.encode("ascii") + b"\0"
    return struct.pack("<i", len(raw)) + raw


def write_pak(path: Path, files: Dict[str, bytes], mount: str = "../../../") -> None:
    """An unencrypted version 8 pak of ``files`` (name -> bytes), entries uncompressed (method 0)."""
    out = bytearray()
    records: List[tuple] = []
    for name, data in sorted(files.items()):
        offset = len(out)
        sha = hashlib.sha1(data).digest()
        header = struct.pack("<QQQI", 0, len(data), len(data), 0) + sha + b"\x00" + struct.pack("<I", 0)
        out += header + data
        records.append((name, offset, len(data), sha))
    index = bytearray(_fstring_bytes(mount) + struct.pack("<I", len(records)))
    for name, offset, size, sha in records:
        index += _fstring_bytes(name)
        index += struct.pack("<QQQI", offset, size, size, 0) + sha + b"\x00" + struct.pack("<I", 0)
    index_offset = len(out)
    out += index
    footer = bytearray(16)                                       # encryption key guid: none
    footer += struct.pack("<B", 0)                               # index not encrypted
    footer += struct.pack("<I", MAGIC) + struct.pack("<I", 8)
    footer += struct.pack("<QQ", index_offset, len(index)) + hashlib.sha1(bytes(index)).digest()
    names = (METHOD_NAMES_V8 + ("", "", ""))[:5]
    for name in names:
        footer += name.encode("ascii").ljust(NAME_SIZE, b"\0")
    out += footer
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(bytes(out))
    tmp.replace(path)
