"""Unreal Engine ``.pak`` files, versions 8 to 11: read the index and the entries, write an unencrypted version 8 pak.

Layout (little-endian): entries (each a record header followed by its data, compressed blocks when the method is not
0), the index, the footer: encryption key guid (16), encrypted-index flag (1), magic 0x5A6F12E1, version (4), index
offset (8), index size (8), SHA-1 of the index (20), then five compression method names (32 bytes each; method n is
the n-th name, 1-based, 0 = none).

Version 8 and 9 index: mount point, entry count, then per entry: name and the record header fields.
Version 10 and 11 index: mount point, entry count, path hash seed, the path hash index (skipped), the full directory
index (a separate blob: directory -> file -> location), the encoded entries (bit-packed records at a location), then a
count of non-encoded entries (refused when not 0). Names come from the directory index.

Record header: offset (8, 0 in the index copy), size (8), uncompressed size (8), method (4), SHA-1 (20); when the
method is not 0: block count (4) and the (start, end) of each block (8 + 8, relative to the record's offset); then
the encrypted flag (1) and the compression block size (4). Uncompressed data follows the 53-byte header.

Zstd comes from the standard library (``compression.zstd``, Python 3.14+); zlib from ``zlib``; Oodle from the caller's
``core.unreal.oodle.Oodle``. Encrypted indexes and entries are refused (the keys are the game's; none is needed for the
games read so far).
"""
from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core import zstd_frame
from core.unreal.oodle import Oodle, OodleError

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
    oodle: Optional[Oodle] = field(default=None, repr=False)  # decodes Oodle blocks; the caller passes it

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
            for (start, end), raw_size in zip(entry.blocks, _block_raw_sizes(entry)):
                raw = self.read(base + start, end - start)
                if name == "Zstd":
                    parts.append(_zstd_decompress(raw, entry.name))
                elif name in ("Zlib", "Gzip"):
                    parts.append(zlib.decompress(raw, 47 if name == "Gzip" else 15))
                elif name == "Oodle":
                    parts.append(self._oodle_block(raw, raw_size, entry.name))
                else:
                    raise PakError(f"{entry.name}: compression {name or entry.method!r} is not read")
            out = b"".join(parts)
        if len(out) != entry.usize:
            raise PakError(f"{entry.name}: {len(out)} bytes, the index says {entry.usize}")
        return out

    def _oodle_block(self, packed: bytes, raw_size: int, name: str) -> bytes:
        """One Oodle block. A block stored without compression has the raw size, so it is copied."""
        if len(packed) == raw_size:
            return packed
        if self.oodle is None:
            raise PakError(f"{name}: Oodle blocks need the Oodle library (open the pak with oodle=...)")
        try:
            return self.oodle.decompress(packed, raw_size)
        except OodleError as exc:
            raise PakError(f"{name}: {exc}") from None


def _block_raw_sizes(entry: Entry) -> List[int]:
    """The uncompressed size of each block: the block size, the last block takes the rest."""
    count = len(entry.blocks)
    if count == 0:
        return []
    if count == 1:
        return [entry.usize]
    if entry.block_size <= 0:
        raise PakError(f"{entry.name}: {count} blocks and no block size")
    sizes = [entry.block_size] * count
    sizes[-1] = entry.usize - entry.block_size * (count - 1)
    return sizes


def _zstd_decompress(raw: bytes, name: str) -> bytes:
    """One zstd frame (``core.zstd_frame``); a missing zstd module is a PakError."""
    try:
        return zstd_frame.decompress(raw, name)
    except zstd_frame.ZstdUnavailable as exc:
        raise PakError(str(exc)) from None


def _fstring(index: bytes, pos: int):
    n = struct.unpack_from("<i", index, pos)[0]
    pos += 4
    if n == 0:
        return "", pos
    if n < 0:
        end = pos - 2 * n - 2
        return index[pos:end].decode("utf-16le"), end + 2
    return index[pos:pos + n - 1].decode("ascii", "replace"), pos + n


def open_pak(read: Callable[[int, int], bytes], size: int, oodle: Optional[Oodle] = None) -> Pak:
    """Parse a pak of ``size`` bytes; ``read(offset, length)`` returns its bytes. ``oodle`` decodes Oodle blocks."""
    tail = read(size - FOOTER_SIZE_V8, FOOTER_SIZE_V8)
    if struct.unpack_from("<I", tail, 17)[0] != MAGIC:
        raise PakError("not an Unreal pak (no footer magic)")
    encrypted_index = tail[16]
    version = struct.unpack_from("<I", tail, 21)[0]
    index_offset, index_size = struct.unpack_from("<QQ", tail, 25)
    if version < 8:
        raise PakError(f"pak version {version} is not read (version 8 to 11 are)")
    names_at = FOOTER_SIZE_V8 - 5 * NAME_SIZE
    methods = [tail[names_at + i * NAME_SIZE:names_at + (i + 1) * NAME_SIZE].split(b"\0", 1)[0].decode("ascii", "replace")
               for i in range(5)]
    methods = [m for m in methods if m]
    if encrypted_index:
        raise PakError("encrypted index: needs the game's AES key")
    index = read(index_offset, index_size)
    if version >= 10:
        mount, entries = _read_index_v10(read, index)
    else:
        mount, entries = _read_index_flat(index)
    return Pak(read, size, version, mount, entries, methods, oodle=oodle)


def _read_index_flat(index: bytes):
    """Version 8 and 9 index: every entry is a name and a full record header."""
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
    return mount, entries


def _read_index_v10(read: Callable[[int, int], bytes], index: bytes):
    """Version 10 and 11 index: the names are in the full directory index, the records in the encoded entries."""
    mount, pos = _fstring(index, 0)
    count = struct.unpack_from("<i", index, pos)[0]
    pos += 4 + 8                                             # entry count, path hash seed
    if struct.unpack_from("<I", index, pos)[0]:              # path hash index: skipped, names come from directories
        pos += 4 + 16 + 20
    else:
        pos += 4
    if not struct.unpack_from("<I", index, pos)[0]:
        raise PakError("pak has no full directory index")
    pos += 4
    directory_offset, directory_size = struct.unpack_from("<qq", index, pos)
    pos += 16 + 20
    encoded_size = struct.unpack_from("<i", index, pos)[0]
    pos += 4
    encoded = index[pos:pos + encoded_size]
    pos += encoded_size
    non_encoded = struct.unpack_from("<i", index, pos)[0]
    if non_encoded:
        raise PakError(f"{non_encoded} non-encoded entries: not read")
    entries: List[Entry] = []
    for dir_name, files in _read_directory_index(read(directory_offset, directory_size)):
        folder = dir_name.lstrip("/")
        for file_name, location in files:
            if not 0 <= location < len(encoded):
                raise PakError(f"entry location {location} is outside the encoded entries")
            entry = _decode_encoded_entry(encoded, location)
            entry.name = mount + folder + file_name
            entries.append(entry)
    if len(entries) != count:
        raise PakError(f"the directory index has {len(entries)} files, the index says {count}")
    return mount, entries


def _read_directory_index(blob: bytes):
    """Yield ``(directory, [(file name, location), ...])`` from the full directory index."""
    (dir_count,) = struct.unpack_from("<i", blob, 0)
    pos = 4
    out = []
    for _ in range(dir_count):
        dir_name, pos = _fstring(blob, pos)
        (file_count,) = struct.unpack_from("<i", blob, pos)
        pos += 4
        files = []
        for _ in range(file_count):
            file_name, pos = _fstring(blob, pos)
            (location,) = struct.unpack_from("<i", blob, pos)
            pos += 4
            files.append((file_name, location))
        out.append((dir_name, files))
    return out


def _decode_encoded_entry(blob: bytes, pos: int) -> Entry:
    """One bit-packed record. Flags: bits 31, 30, 29 = offset, uncompressed size, size fit in 32 bits (else 64);
    bits 23-28 = method; bit 22 = encrypted; bits 6-21 = block count; bits 0-5 = block size / 2048 (0x3F: a u32)."""
    (flags,) = struct.unpack_from("<I", blob, pos)
    pos += 4
    method = (flags >> 23) & 0x3F
    block_count = (flags >> 6) & 0xFFFF
    encrypted = (flags >> 22) & 1
    if encrypted:
        raise PakError("encrypted entries are not read")
    block_size = flags & 0x3F
    if block_size == 0x3F:
        (block_size,) = struct.unpack_from("<I", blob, pos)
        pos += 4
    else:
        block_size <<= 11

    def wide(bit: int, pos: int):
        if (flags >> bit) & 1:
            return struct.unpack_from("<I", blob, pos)[0], pos + 4
        return struct.unpack_from("<Q", blob, pos)[0], pos + 8

    offset, pos = wide(31, pos)
    usize, pos = wide(30, pos)
    size = usize
    if method:
        size, pos = wide(29, pos)
    blocks: List[tuple] = []
    if method and block_count:
        header = 57 + 16 * block_count                       # the record header in the file (see the module doc)
        if block_count == 1:
            blocks = [(header, header + size)]
        else:
            start = header
            for _ in range(block_count):
                (block_len,) = struct.unpack_from("<I", blob, pos)
                pos += 4
                blocks.append((start, start + block_len))
                start += block_len
    return Entry("", offset, size, usize, method, blocks, block_size, 0)


def open_path(path: Path, oodle: Optional[Oodle] = None) -> Pak:
    """Open a pak file. Close the returned pak (``close()`` or ``with``) to release the file."""
    stream = open(path, "rb")
    try:
        size = Path(path).stat().st_size

        def read(offset: int, length: int) -> bytes:
            stream.seek(offset)
            return stream.read(length)
        opened = open_pak(read, size, oodle)
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
