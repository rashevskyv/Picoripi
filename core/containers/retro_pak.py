"""Retro Studios ``RFRM`` packages (``.pak``, ``.pak.patch``) of Metroid Prime 4: Beyond and Prime Remastered.

A package is an ``RFRM`` form (``RFRM``, u64 body size, u64 0, fourcc id, u32 reader and writer version: 0x20
bytes) with id ``PACK``. Its first child is a ``TOCC`` form whose chunks (fourcc, u64 size, u32, u64 skip:
0x18 bytes, then ``skip`` bytes, then the body) are:

- ``ADIR``: u32 count, then per asset: fourcc type, 16-byte GUID, u32 reader / writer version, u64 offset,
  u64 size, u64 stored size and -- in TOCC v4 (Prime 4, 60-byte entries) -- a u64 the game fills for
  compressed assets (52-byte entries in Prime Remastered). Several entries may share one offset.
- ``META``: u32 count, (GUID, u32 offset) pairs, then at each offset a u32 size and that many bytes:
  per-asset metadata (a texture's GPU buffer layout, see ``core.texture_formats.txtr``).
- ``STRG``: u32 count, then (byte-swapped fourcc, GUID, u32 length, name): asset names.

Every asset is an ``RFRM`` form itself. A stored size different from the size means a compressed asset:
u32 mode, then the stream. Modes 1-3 are Retro's LZSS on 1-, 2- and 4-byte units; modes 12-14 are the
same LZ with its flag, literal and match tokens in one MSB-first bit stream and the match length and
distance as three static canonical Huffman codes kept in the game's executable (``HuffmanTables``).

``repack`` streams a package into a new file with some assets replaced; a replacement is stored
uncompressed, which the game accepts. The engine prefers an asset found in ``Patch/*.pak.patch`` over the
same GUID in an ordinary package.
"""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional, Tuple

FORM = struct.Struct("<4sQQ4sII")       # RFRM header
CHUNK = struct.Struct("<4sQIQ")         # chunk header
_COPY_BLOCK = 1 << 23


@dataclass
class Asset:
    """One ADIR entry (``index``: its position in the directory)."""

    index: int
    type: str
    guid: bytes
    version: int
    writer: int
    offset: int
    size: int
    stored: int
    blocks: int = 0
    names: List[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        """The GUID as hex text (the form ``source\\`` file names and tables use)."""
        return self.guid.hex()

    @property
    def name(self) -> str:
        """The asset's first name, else its GUID."""
        return self.names[0] if self.names else self.id

    @property
    def compressed(self) -> bool:
        return self.stored != self.size


def form_header(data: bytes, at: int = 0) -> Tuple[str, int, int, int]:
    """``(id, body size, reader version, writer version)`` of the ``RFRM`` form at ``at``."""
    magic, size, _zero, kind, reader, writer = FORM.unpack_from(data, at)
    if magic != b"RFRM":
        raise ValueError(f"Not an RFRM form at {at:#x}")
    return kind.decode("latin-1"), size, reader, writer


def chunks(data: bytes, start: int = FORM.size, end: Optional[int] = None):
    """``(id, header offset, body offset, body size)`` of every chunk from ``start`` to ``end``."""
    end = len(data) if end is None else end
    position = start
    while position < end:
        kind, size, _unk, skip = CHUNK.unpack_from(data, position)
        body = position + CHUNK.size + skip
        if body + size > end:
            raise ValueError(f"Chunk {kind!r} at {position:#x} runs past the end")
        yield kind.decode("latin-1"), position, body, size
        position = body + size


class Pak:
    """A package's directory, read without loading the assets (files reach 2 GB)."""

    def __init__(self, path):
        self.path = Path(path)
        with open(self.path, "rb") as stream:
            head = stream.read(2 * FORM.size)
            kind, _size, _r, _w = form_header(head)
            toc_kind, toc_size, self.toc_version, _w = form_header(head, FORM.size)
            if kind != "PACK" or toc_kind != "TOCC":
                raise ValueError(f"{self.path.name}: not a Retro package")
            self.header = head + stream.read(toc_size)
        self.assets: List[Asset] = []
        self.meta: Dict[bytes, bytes] = {}
        self.meta_at: Dict[bytes, int] = {}      # GUID -> offset of the metadata bytes in ``header``
        self.adir_at = 0
        self.entry_size = 0
        names: Dict[bytes, List[str]] = {}
        for kind, _at, body, size in chunks(self.header, 2 * FORM.size):
            if kind == "ADIR":
                count = struct.unpack_from("<I", self.header, body)[0]
                self.adir_at, self.entry_size = body + 4, (size - 4) // count if count else 60
                for i in range(count):
                    at = self.adir_at + i * self.entry_size
                    kind_, guid, ver, wri, off, full, stored = struct.unpack_from("<4s16sIIQQQ", self.header, at)
                    blocks = struct.unpack_from("<Q", self.header, at + 52)[0] if self.entry_size >= 60 else 0
                    self.assets.append(Asset(i, kind_.decode("latin-1"), guid, ver, wri, off, full, stored, blocks))
            elif kind == "META":
                count = struct.unpack_from("<I", self.header, body)[0]
                for i in range(count):
                    guid, offset = struct.unpack_from("<16sI", self.header, body + 4 + i * 20)
                    length = struct.unpack_from("<I", self.header, body + offset)[0]
                    self.meta_at[guid] = body + offset + 4
                    self.meta[guid] = self.header[body + offset + 4:body + offset + 4 + length]
            elif kind == "STRG":
                count, position = struct.unpack_from("<I", self.header, body)[0], body + 4
                for _ in range(count):
                    guid, length = struct.unpack_from("<16sI", self.header, position + 4)
                    names.setdefault(guid, []).append(self.header[position + 24:position + 24 + length].decode("utf-8"))
                    position += 24 + length
        for asset in self.assets:
            asset.names = names.get(asset.guid, [])

    def find(self, kind: Optional[str] = None, name: Optional[str] = None) -> List[Asset]:
        """Assets of a type and/or name (each GUID once: the first directory entry)."""
        seen, out = set(), []
        for asset in self.assets:
            if asset.guid in seen or (kind and asset.type != kind) or (name and name not in asset.names):
                continue
            seen.add(asset.guid)
            out.append(asset)
        return out

    def by_guid(self, guid: bytes) -> Optional[Asset]:
        return next((asset for asset in self.assets if asset.guid == guid), None)

    def read_stored(self, asset: Asset) -> bytes:
        """The asset's bytes as stored in the package."""
        with open(self.path, "rb") as stream:
            stream.seek(asset.offset)
            data = stream.read(asset.stored)
        if len(data) != asset.stored:
            raise ValueError(f"{self.path.name}: asset {asset.name} runs past the end of the file")
        return data

    def read(self, asset: Asset, tables: Optional["HuffmanTables"] = None) -> bytes:
        """The asset's ``RFRM`` form, decompressed."""
        data = self.read_stored(asset)
        return decompress(data, asset.size, tables) if asset.compressed else data


# -- compression ---------------------------------------------------------------------------------------


def lzss(data: bytes, size: int, mode: int) -> bytes:
    """Retro LZSS (modes 1-3): a flag byte per 8 tokens (MSB first); a set flag is a 2-byte match
    (count nibble, 12-bit distance), a clear one a literal unit of ``2 ** (mode - 1)`` bytes."""
    unit = 1 << (mode - 1)
    out = bytearray()
    position, end = 0, len(data)
    while position < end and len(out) < size:
        flags = data[position]
        position += 1
        for bit in range(7, -1, -1):
            if position >= end or len(out) >= size:
                break
            if flags >> bit & 1:
                first, second = data[position], data[position + 1]
                position += 2
                count = ((first >> 4) + 4 - mode) * unit
                distance = ((first & 15) << 8 | second) * unit
                _copy_match(out, distance, count)
            else:
                out += data[position:position + unit]
                position += unit
    if len(out) != size:
        raise ValueError(f"LZSS stream gave {len(out)} bytes, expected {size}")
    return bytes(out)


def _copy_match(out: bytearray, distance: int, count: int) -> None:
    if not 0 < distance <= len(out):
        raise ValueError(f"LZ match reaches before the start of the data ({distance} > {len(out)})")
    start = len(out) - distance
    if distance >= count:
        out += out[start:start + count]
    else:
        for k in range(count):
            out.append(out[start + k])


class HuffmanTables:
    """The three static codes of modes 12-14: match length, distance low byte, distance high byte.

    Each is a table of 256 eight-byte entries ``(u16 code length, u8 entries left in this length,
    u8 symbol, u32 code)`` in canonical order, back to back in the game's executable. They are read from
    the user's own ``exefs/main`` (``from_executable``), never shipped.
    """

    # The first three entries of the length table: lengths 1, 2, 4 for symbols 0, 1, 2 (codes 0, 10, 1100).
    SIGNATURE = bytes.fromhex("0100010000000000" "0200010102000000" "040001020c000000")

    def __init__(self, raw: bytes):
        if len(raw) != 3 * 0x800:
            raise ValueError("Huffman tables are 3 x 2048 bytes")
        self.raw = bytes(raw)
        self.codes = [self._lookup(raw[i * 0x800:(i + 1) * 0x800]) for i in range(3)]

    @staticmethod
    def _lookup(table: bytes) -> Tuple[int, List[Tuple[int, int]]]:
        entries = [struct.unpack_from("<HBBI", table, i * 8) for i in range(256)]
        width = max(length for length, _left, _sym, _code in entries)
        if not 0 < width <= 24:
            raise ValueError("Not a Huffman table")
        look: List[Optional[Tuple[int, int]]] = [None] * (1 << width)
        for length, _left, symbol, code in entries:
            shift = width - length
            if code >> length:
                raise ValueError("Not a Huffman table")
            for k in range(code << shift, (code + 1) << shift):
                if look[k] is not None:
                    raise ValueError("Huffman codes overlap")
                look[k] = (symbol, length)
        if any(item is None for item in look):
            raise ValueError("Huffman code is incomplete")
        return width, look  # type: ignore[return-value]

    @classmethod
    def from_memory(cls, memory: bytes) -> "HuffmanTables":
        """Find the tables in an executable's memory image (the first place where all three parse)."""
        at = memory.find(cls.SIGNATURE)
        while at != -1:
            try:
                return cls(memory[at:at + 3 * 0x800])
            except (ValueError, struct.error):
                at = memory.find(cls.SIGNATURE, at + 1)
        raise ValueError("The compression tables were not found in this executable")

    @classmethod
    def from_executable(cls, path) -> "HuffmanTables":
        """From the game's ``exefs/main`` (NSO, sections LZ4-compressed or not)."""
        return cls.from_memory(nso_memory(Path(path).read_bytes()))


def nso_memory(nso: bytes) -> bytes:
    """The text, rodata and data segments of an NSO at their addresses."""
    if nso[:4] != b"NSO0":
        raise ValueError("Not an NSO executable")
    flags = struct.unpack_from("<I", nso, 12)[0]
    segments = []
    for index, at in enumerate((16, 32, 48)):
        offset, address, size = struct.unpack_from("<III", nso, at)
        stored = struct.unpack_from("<I", nso, 96 + index * 4)[0]
        data = nso[offset:offset + (stored if flags & (1 << index) else size)]
        segments.append((address, lz4_block(data, size) if flags & (1 << index) else data))
    memory = bytearray(max(address + len(data) for address, data in segments))
    for address, data in segments:
        memory[address:address + len(data)] = data
    return bytes(memory)


def lz4_block(data: bytes, size: int) -> bytes:
    """An LZ4 block (no frame header)."""
    out = bytearray()
    position = 0
    while position < len(data):
        token = data[position]
        position += 1
        literals = token >> 4
        if literals == 15:
            while True:
                extra = data[position]
                position += 1
                literals += extra
                if extra != 255:
                    break
        out += data[position:position + literals]
        position += literals
        if position >= len(data):
            break
        distance = data[position] | data[position + 1] << 8
        position += 2
        length = token & 15
        if length == 15:
            while True:
                extra = data[position]
                position += 1
                length += extra
                if extra != 255:
                    break
        _copy_match(out, distance, length + 4)
    if len(out) != size:
        raise ValueError(f"LZ4 block gave {len(out)} bytes, expected {size}")
    return bytes(out)


def huffman_lz(data: bytes, size: int, mode: int, tables: HuffmanTables) -> bytes:
    """Modes 12-14: flag bit 1 = match (length, distance low, distance high: one Huffman code each),
    0 = a literal of ``unit`` bytes; count = (length + 15 - mode) units, distance = (high:low) units."""
    unit = 1 << (mode - 12)
    extra = 15 - mode
    stream = bytes(data) + b"\0" * 8
    (w1, t1), (w2, t2), (w3, t3) = tables.codes
    out = bytearray()
    position = acc = have = 0
    literal_bits = 8 * unit
    while len(out) < size:
        if have < 40:
            acc = (acc << 32) | int.from_bytes(stream[position:position + 4], "big")
            position += 4
            have += 32
        have -= 1
        if acc >> have & 1:
            symbols = []
            for width, look in ((w1, t1), (w2, t2), (w3, t3)):
                if have < width:
                    acc = (acc << 32) | int.from_bytes(stream[position:position + 4], "big")
                    position += 4
                    have += 32
                symbol, length = look[(acc >> (have - width)) & ((1 << width) - 1)]
                have -= length
                symbols.append(symbol)
            _copy_match(out, (symbols[2] << 8 | symbols[1]) * unit, (symbols[0] + extra) * unit)
        else:
            if have < literal_bits:
                acc = (acc << 32) | int.from_bytes(stream[position:position + 4], "big")
                position += 4
                have += 32
            have -= literal_bits
            out += ((acc >> have) & ((1 << literal_bits) - 1)).to_bytes(unit, "big")
        acc &= (1 << have) - 1
        if position > len(stream):
            raise ValueError("Compressed stream ended early")
    del out[size:]
    return bytes(out)


def decompress(blob: bytes, size: int, tables: Optional[HuffmanTables] = None) -> bytes:
    """A compressed buffer (u32 mode + stream) to ``size`` bytes."""
    mode = struct.unpack_from("<I", blob)[0]
    data = blob[4:]
    if mode == 0:
        return bytes(data[:size])
    if mode in (1, 2, 3):
        return lzss(data, size, mode)
    if mode in (12, 13, 14):
        if tables is None:
            raise ValueError(f"Compression mode {mode} needs the game's tables (exefs main)")
        return huffman_lz(data, size, mode, tables)
    raise ValueError(f"Compression mode {mode} is not supported")


# -- textures ------------------------------------------------------------------------------------------
# A TXTR form is a HEAD chunk and a "GPU " chunk; the GPU chunk holds the pixel data in compressed
# buffers that the package's META entry for the texture describes (Prime 4)::
#
#     u32 7, u32 0, u32 allocation, u32 offset of the GPU chunk header, u32 alignment, u32 data size,
#     u32 n, n x (u8 read, u32 offset in the form, u32 size)   -- read 0 entry 0 is the form's header
#     u32 1, u32 stored size, u32 data offset, u32 data size, u32 blocks, ...
#
# One stream (two read ranges, 94 bytes) is a compressed buffer. A streamed texture (three ranges,
# 103 bytes) adds a second buffer for the start of the data, described by the last six u32 (stored size,
# data offset, data size, inner size, inner stored size, head): ``head`` raw bytes, a compressed buffer of
# the inner sizes, raw bytes again (``_split_buffer``). ``unpack_texture`` turns a form into its "exploded"
# copy (one mode-0 buffer, all data in order) and ``texture_meta`` writes the metadata of such a copy (the
# 94-byte form with one buffer, also for a texture that was streamed).


def _texture_ranges(meta: bytes) -> List[Tuple[int, int, int]]:
    count = struct.unpack_from("<I", meta, 24)[0]
    return [struct.unpack_from("<BII", meta, 28 + 9 * i) for i in range(count)]


def unpack_texture(form: bytes, meta: bytes, tables: Optional[HuffmanTables] = None) -> bytes:
    """A TXTR form with its GPU data decompressed into one uncompressed buffer."""
    if form_header(form)[0] != "TXTR":
        raise ValueError("Not a TXTR form")
    size = struct.unpack_from("<I", meta, 20)[0]
    ranges = _texture_ranges(meta)
    header_end = ranges[0][2]
    data = bytearray(size)
    first = 28 + 9 * len(ranges)
    stored, offset, length = struct.unpack_from("<III", meta, first + 4)
    _read, at, span = ranges[1]
    data[offset:offset + length] = decompress(form[at:at + span], length, tables)
    if len(ranges) == 3:
        stored, offset, length, inner, inner_stored, head = struct.unpack_from("<6I", meta, len(meta) - 24)
        _read, at, span = ranges[2]
        data[offset:offset + length] = _split_buffer(form[at:at + span], length, inner, inner_stored, head, tables)
    elif len(ranges) != 2:
        raise ValueError(f"Texture with {len(ranges)} read ranges is not supported")
    gpu = struct.pack("<I", 0) + bytes(data)
    return _with_gpu(form, header_end, gpu)


def _split_buffer(stream: bytes, length: int, inner: int, inner_stored: int, head: int, tables) -> bytes:
    """A streamed buffer: ``head`` raw bytes, a compressed buffer of ``inner_stored`` bytes (``inner`` once
    decompressed) and raw bytes again; the data is the decompressed part followed by both raw parts
    (checked on every streamed ASTC texture of 1.1.0: no error block). Equal inner sizes = stored as it is."""
    if inner == inner_stored and len(stream) == length:
        return bytes(stream)
    middle = decompress(stream[head:head + inner_stored], inner, tables)
    out = middle + stream[:head] + stream[head + inner_stored:]
    if len(out) != length:
        raise ValueError(f"Streamed texture buffer gave {len(out)} bytes, expected {length}")
    return out


def _with_gpu(form: bytes, header_end: int, gpu: bytes) -> bytes:
    out = bytearray(form[:header_end]) + gpu
    gpu_at = header_end - CHUNK.size
    if out[gpu_at:gpu_at + 4] != b"GPU ":
        raise ValueError("TXTR without a GPU chunk where the metadata says")
    struct.pack_into("<Q", out, gpu_at + 4, len(gpu))
    struct.pack_into("<Q", out, 4, len(out) - FORM.size)
    return bytes(out)


def texture_meta(form: bytes, meta: bytes) -> bytes:
    """Metadata for an exploded TXTR form (one mode-0 buffer), keeping the original's other fields."""
    ranges = _texture_ranges(meta)
    header_end = ranges[0][2]
    gpu = len(form) - header_end
    size = gpu - 4
    first = 28 + 9 * len(ranges)
    blocks = struct.unpack_from("<I", meta, first + 16)[0]
    out = bytearray(meta[:24])
    struct.pack_into("<I", out, 20, size)
    out += struct.pack("<I", 2) + struct.pack("<BII", 0, 0, header_end) + struct.pack("<BII", 0, header_end, gpu)
    out += struct.pack("<IIIII", 1, gpu, 0, size, blocks) + b"\0" * 28     # 94 bytes, as the game's own
    return bytes(out)


# -- writing -------------------------------------------------------------------------------------------


def _copy(source: BinaryIO, target: BinaryIO, count: int) -> None:
    while count:
        block = source.read(min(count, _COPY_BLOCK))
        if not block:
            raise ValueError("Package ended early")
        target.write(block)
        count -= len(block)


def _header_with_meta(pak: Pak, meta: Dict[bytes, bytes]) -> bytearray:
    """The package's directory with some assets' metadata replaced (the META chunk rebuilt when sizes change)."""
    header = bytearray(pak.header)
    unknown = [guid.hex() for guid in meta if guid not in pak.meta]
    if unknown:
        raise KeyError(f"No metadata for {', '.join(unknown)} in {pak.path.name}")
    if all(len(data) == len(pak.meta[guid]) for guid, data in meta.items()):
        for guid, data in meta.items():
            header[pak.meta_at[guid]:pak.meta_at[guid] + len(data)] = data
        return header
    chunk = next(c for c in chunks(header, 2 * FORM.size) if c[0] == "META")
    _kind, at, body, size = chunk
    order = sorted(pak.meta, key=lambda guid: pak.meta_at[guid])
    blobs = bytearray()
    table = bytearray(struct.pack("<I", len(order)))
    start = 4 + 20 * len(order)
    for guid in order:
        data = meta.get(guid, pak.meta[guid])
        table += struct.pack("<16sI", guid, start + len(blobs))
        blobs += struct.pack("<I", len(data)) + data
    new_body = bytes(table + blobs)
    out = header[:body] + new_body + header[body + size:]
    struct.pack_into("<Q", out, at + 4, len(new_body))
    grow = len(out) - len(header)
    for at_size in (4, FORM.size + 4):        # PACK and TOCC body sizes
        struct.pack_into("<Q", out, at_size, struct.unpack_from("<Q", out, at_size)[0] + grow)
    return out


def repack(source, target, replacements: Dict[bytes, bytes], meta: Optional[Dict[bytes, bytes]] = None) -> int:
    """Write ``source`` to ``target`` with the assets of ``replacements`` (GUID -> RFRM form) stored
    uncompressed and the metadata of ``meta`` (GUID -> bytes) replaced.

    Every other byte is copied: with nothing to replace the copy is identical. Writes a temporary file next
    to ``target`` and renames it. Returns the number of assets replaced.
    """
    pak = Pak(source)
    header = _header_with_meta(pak, meta or {})
    by_offset: Dict[int, List[Asset]] = {}
    for asset in pak.assets:
        by_offset.setdefault(asset.offset, []).append(asset)
    unknown = set(replacements) - {asset.guid for asset in pak.assets}
    if unknown:
        raise KeyError(f"Not in {pak.path.name}: {', '.join(sorted(g.hex() for g in unknown))}")
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    total = pak.path.stat().st_size
    delta = replaced = 0
    with open(pak.path, "rb") as src, open(temporary, "wb") as dst:
        dst.write(header)
        cursor = len(pak.header)
        for offset in sorted(by_offset):
            group = by_offset[offset]
            first = group[0]
            if offset < cursor:
                raise ValueError(f"{pak.path.name}: assets overlap at {offset:#x}")
            src.seek(cursor)
            _copy(src, dst, offset - cursor)
            new_offset = dst.tell()
            new = next((replacements[a.guid] for a in group if a.guid in replacements), None)
            if new is None:
                src.seek(offset)
                _copy(src, dst, first.stored)
                stored, size = first.stored, first.size
            else:
                dst.write(new)
                stored = size = len(new)
                replaced += 1
            for asset in group:
                at = pak.adir_at + asset.index * pak.entry_size
                struct.pack_into("<QQQ", header, at + 28, new_offset, size, stored)
                if new is not None and pak.entry_size >= 60:
                    struct.pack_into("<Q", header, at + 52, 0)
            delta += stored - first.stored
            cursor = offset + first.stored
        src.seek(cursor)
        _copy(src, dst, total - cursor)
        struct.pack_into("<Q", header, 4, struct.unpack_from("<Q", header, 4)[0] + delta)
        dst.seek(0)
        dst.write(header)
    os.replace(temporary, target)
    return replaced
