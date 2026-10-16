"""Unreal Engine IoStore containers: a ``.utoc`` table of contents (TOC version 5) and its ``.ucas`` data file.

TOC layout (little-endian, header 144 bytes): magic ``-==--==--==--==-``, version (1 byte at 16), header size, entry
count, compression block count and entry size (12), compression method name count and length, compression block size,
directory index size, partition count, container id, encryption key guid, container flags (1 byte at 80), perfect hash
seed count, partition size, chunks without a perfect hash. Then the tables, in this order: chunk ids (12 bytes each),
chunk offset and length (5 + 5 bytes, big-endian), perfect hash seeds (4), chunks without a hash (4), compression
blocks (offset 5, compressed size 3, uncompressed size 3, method 1; little-endian), method names (fixed length, NUL
padded), the directory index, and the chunk metadata (33 bytes each, not read).

Each chunk starts at a block boundary in the uncompressed space (offset = block index * block size); the last block
of a chunk may be shorter. Verified on the game's pakchunk0 container (all blocks in range, raw size at most the block
size).

Container flags: 0x01 compressed, 0x02 encrypted, 0x04 signed, 0x08 indexed. Encrypted and signed containers and
partitioned containers (more than one partition) are refused. Compression method n (1-based) is name n in the table;
0 means stored. Blocks are decompressed with ``core.unreal.oodle.Oodle``.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from core.unreal.oodle import Oodle

MAGIC = b"-==--==--==--==-"
HEADER_SIZE = 144
NONE = 0xFFFFFFFF
FLAG_COMPRESSED = 0x01
FLAG_ENCRYPTED = 0x02
FLAG_SIGNED = 0x04
FLAG_INDEXED = 0x08


class IoStoreError(ValueError):
    pass


@dataclass(frozen=True)
class Chunk:
    index: int
    chunk_id: bytes          # 12 bytes; the chunk type is the last byte
    offset: int              # offset in the uncompressed container
    length: int

    @property
    def chunk_type(self) -> int:
        return self.chunk_id[11]


@dataclass(frozen=True)
class Block:
    offset: int              # offset in the .ucas file
    comp_size: int
    raw_size: int
    method: int              # 0 = stored, n = method name n (1-based)


@dataclass
class Toc:
    version: int
    container_flags: int
    block_size: int
    method_names: List[str]
    chunks: List[Chunk]
    blocks: List[Block]
    directory: bytes
    meta_size: int = 0
    container_id: int = 0
    partition_count: int = 1
    counts: Dict[str, int] = field(default_factory=dict)


def _be(data: bytes) -> int:
    return int.from_bytes(data, "big")


def _le(data: bytes) -> int:
    return int.from_bytes(data, "little")


def parse_toc(data: bytes) -> Toc:
    """Parse the bytes of a ``.utoc`` file. Raises IoStoreError for anything not read."""
    if len(data) < HEADER_SIZE or data[:16] != MAGIC:
        raise IoStoreError("not an IoStore table of contents (magic)")
    version = data[16]
    header_size, entry_count, block_count, block_entry_size = struct.unpack_from("<IIII", data, 20)
    method_count, method_len, block_size, directory_size, partition_count = struct.unpack_from("<IIIII", data, 36)
    container_id = struct.unpack_from("<Q", data, 56)[0]
    container_flags = data[80]
    seed_count = struct.unpack_from("<I", data, 84)[0]
    without_hash = struct.unpack_from("<I", data, 96)[0]
    if header_size != HEADER_SIZE:
        raise IoStoreError(f"TOC header size {header_size}, expected {HEADER_SIZE}")
    if block_entry_size != 12:
        raise IoStoreError(f"compression block entry size {block_entry_size}, expected 12")
    if container_flags & FLAG_ENCRYPTED:
        raise IoStoreError("encrypted container: needs the game's AES key")
    if container_flags & FLAG_SIGNED:
        raise IoStoreError("signed container: the block signatures are not read")
    if partition_count != 1:
        raise IoStoreError(f"{partition_count} partitions: partitioned containers are not read")
    pos = HEADER_SIZE
    ids = [data[pos + 12 * i:pos + 12 * i + 12] for i in range(entry_count)]
    pos += 12 * entry_count
    offsets = []
    for i in range(entry_count):
        at = pos + 10 * i
        offsets.append((_be(data[at:at + 5]), _be(data[at + 5:at + 10])))
    pos += 10 * entry_count
    pos += 4 * seed_count + 4 * without_hash
    blocks: List[Block] = []
    for i in range(block_count):
        at = pos + 12 * i
        blocks.append(Block(_le(data[at:at + 5]), _le(data[at + 5:at + 8]), _le(data[at + 8:at + 11]), data[at + 11]))
    pos += 12 * block_count
    names = []
    for i in range(method_count):
        raw = data[pos + method_len * i:pos + method_len * (i + 1)]
        names.append(raw.split(b"\0", 1)[0].decode("ascii", "replace"))
    pos += method_count * method_len
    directory = data[pos:pos + directory_size]
    pos += directory_size
    if entry_count and (len(data) - pos) % entry_count:
        raise IoStoreError("the chunk metadata does not divide evenly: the table layout is not what this reader expects")
    meta_size = (len(data) - pos) // entry_count if entry_count else 0
    chunks = [Chunk(i, ids[i], offsets[i][0], offsets[i][1]) for i in range(entry_count)]
    counts = {"entries": entry_count, "blocks": block_count, "methods": method_count, "seeds": seed_count,
              "without_hash": without_hash, "directory": directory_size}
    return Toc(version, container_flags, block_size, names, chunks, blocks, directory, meta_size,
               container_id, partition_count, counts)


def parse_directory(blob: bytes) -> Tuple[str, List[Tuple[str, int]]]:
    """The mount point and ``[(path, chunk index)]`` of an indexed container's directory index."""
    if not blob:
        return "", []
    mount, pos = _fstring(blob, 0)
    (dir_count,) = struct.unpack_from("<i", blob, pos)
    pos += 4
    dirs = [struct.unpack_from("<IIII", blob, pos + 16 * i) for i in range(dir_count)]
    pos += 16 * dir_count
    (file_count,) = struct.unpack_from("<i", blob, pos)
    pos += 4
    files = [struct.unpack_from("<III", blob, pos + 12 * i) for i in range(file_count)]
    pos += 12 * file_count
    (str_count,) = struct.unpack_from("<i", blob, pos)
    pos += 4
    strings = []
    for _ in range(str_count):
        text, pos = _fstring(blob, pos)
        strings.append(text)
    out: List[Tuple[str, int]] = []
    if not dirs:
        return mount, out
    stack = [(0, "")]
    seen = set()
    while stack:
        index, prefix = stack.pop()
        if index in seen or index >= dir_count:
            continue
        seen.add(index)
        name_i, first_child, next_sibling, first_file = dirs[index]
        here = prefix + (strings[name_i] + "/" if name_i != NONE else "")
        f = first_file
        while f != NONE and f < file_count:
            name_i_f, next_file, user_data = files[f]
            out.append((mount + here + strings[name_i_f], user_data))
            f = next_file
        if first_child != NONE:
            stack.append((first_child, here))
        if next_sibling != NONE:
            stack.append((next_sibling, prefix))
    return mount, out


def _fstring(blob: bytes, pos: int) -> Tuple[str, int]:
    n = struct.unpack_from("<i", blob, pos)[0]
    pos += 4
    if n == 0:
        return "", pos
    if n < 0:
        end = pos - 2 * n
        return blob[pos:end - 2].decode("utf-16le"), end
    return blob[pos:pos + n - 1].decode("ascii", "replace"), pos + n


class IoStore:
    """A container: ``chunk_bytes(chunk)`` gives the uncompressed bytes of one chunk; ``files()`` lists the paths."""

    def __init__(self, toc_path: Union[str, Path], oodle: Optional[Oodle] = None):
        self.toc_path = Path(toc_path)
        self.cas_path = self.toc_path.with_suffix(".ucas")
        self.oodle = oodle
        self.toc = parse_toc(self.toc_path.read_bytes())
        self._cache: Tuple[int, bytes] = (-1, b"")
        self._directory: Optional[Tuple[str, List[Tuple[str, int]]]] = None

    def files(self) -> List[Tuple[str, int]]:
        """``[(path, chunk index)]`` from the directory index; empty when the container is not indexed."""
        if self._directory is None:
            if not self.toc.container_flags & FLAG_INDEXED:
                self._directory = ("", [])
            else:
                self._directory = parse_directory(self.toc.directory)
        return self._directory[1]

    def chunk_bytes(self, chunk: Chunk) -> bytes:
        size = self.toc.block_size
        out = bytearray()
        pos, end = chunk.offset, chunk.offset + chunk.length
        while pos < end:
            bi = pos // size
            raw = self._block(bi)
            start = pos - bi * size
            take = min(len(raw) - start, end - pos)
            if take <= 0:
                raise IoStoreError(f"chunk {chunk.index}: block {bi} ends before the chunk does")
            out += raw[start:start + take]
            pos += take
        return bytes(out)

    def _block(self, index: int) -> bytes:
        if self._cache[0] == index:
            return self._cache[1]
        block = self.toc.blocks[index]
        with open(self.cas_path, "rb") as stream:
            stream.seek(block.offset)
            packed = stream.read(block.comp_size)
        raw = self._decode(block, packed, index)
        self._cache = (index, raw)
        return raw

    def _decode(self, block: Block, packed: bytes, index: int) -> bytes:
        if block.method == 0:
            return packed
        name = self.toc.method_names[block.method - 1] if 0 < block.method <= len(self.toc.method_names) else ""
        if name != "Oodle":
            raise IoStoreError(f"block {index}: compression {name or block.method!r} is not read")
        if len(packed) == block.raw_size:
            return packed
        if self.oodle is None:
            raise IoStoreError("Oodle blocks need the Oodle library (pass oodle=...)")
        return self.oodle.decompress(packed, block.raw_size)
