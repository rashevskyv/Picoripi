"""Nintendo Switch NCZ (a compressed NCA, as in an .nsz package): read its section table and decompress it to an NCA.

Layout, from nsz (``nsz/IndependentNczDecompressor.py``, ``nsz/Header.py``, ``nsz/BlockDecompressorReader.py``): the first
0x4000 bytes are the NCA header copied verbatim (still encrypted). At 0x4000 come ``NCZSECTN``, a u64 section count and
0x40-byte section entries. An optional ``NCZBLOCK`` header and one u32 size per block follow; without it the body is one
zstd stream. Each block is one zstd frame, or raw when its size equals its decompressed size. The body is the NCA from
0x4000 on, with the AES-CTR sections already decrypted. ``decompress_ncz`` writes the NCA back (header copy, then body),
so the reader can use its normal section views. All fields are little-endian. No key is read or kept here.
"""
from __future__ import annotations

import struct
from typing import BinaryIO, Callable, List, NamedTuple, Optional, Tuple

from core.containers.image_files import ImageError, ImageReader

NCA_HEADER_SIZE = 0x4000     # the NCA header copy at the start of an NCZ, and where its body starts
MAGIC_SECTIONS = b"NCZSECTN"
MAGIC_BLOCKS = b"NCZBLOCK"
SECTION_SIZE = 0x40
BLOCK_HEADER_SIZE = 0x18
MAX_SECTIONS = 4             # an NCA has at most four sections
MIN_BLOCK_EXP, MAX_BLOCK_EXP = 14, 32   # the block size is 2**exp bytes (nsz uses the same range)
CHUNK = 1 << 20


class Ncz(NamedTuple):
    """The section table and block list of an NCZ. Offsets are NCA offsets; ``body_at`` is a file offset."""
    sections: List[Tuple[int, int, int]]   # (offset, size, crypto type) of each section
    body_at: int                           # where the body starts in the NCZ file
    body_size: int                         # bytes of the NCA from 0x4000 on that the body holds
    block_exp: Optional[int]               # NCZBLOCK block size exponent; None for one zstd stream
    blocks: List[int]                      # compressed size of each NCZBLOCK block
    block_total: int                       # NCZBLOCK decompressedSize

    @property
    def nca_size(self) -> int:
        """The size of the NCA that decompressing this NCZ gives."""
        return NCA_HEADER_SIZE + self.body_size


def read_ncz(reader: ImageReader) -> Ncz:
    """The section table and block list of the NCZ that ``reader`` reads. ImageError when they are not sound."""
    if reader.size < NCA_HEADER_SIZE + 0x10 or reader.read_at(NCA_HEADER_SIZE, 8) != MAGIC_SECTIONS:
        raise ImageError("a compressed NCA has no NCZSECTN table")
    count = struct.unpack("<Q", reader.read_at(NCA_HEADER_SIZE + 8, 8))[0]
    if not 1 <= count <= MAX_SECTIONS:
        raise ImageError("a compressed NCA lists a bad number of sections")
    table = reader.read_at(NCA_HEADER_SIZE + 0x10, count * SECTION_SIZE)
    sections: List[Tuple[int, int, int]] = []
    end = NCA_HEADER_SIZE
    for index in range(count):
        offset, size, crypto = struct.unpack_from("<3Q", table, index * SECTION_SIZE)
        if index == 0 and offset < NCA_HEADER_SIZE:
            raise ImageError("a compressed NCA section starts inside the NCA header")
        if index and offset != end:
            raise ImageError("the sections of a compressed NCA are not contiguous")
        end = offset + size
        sections.append((offset, size, crypto))
    body_size = end - NCA_HEADER_SIZE
    if body_size <= 0:
        raise ImageError("a compressed NCA has no section data")
    body_at = NCA_HEADER_SIZE + 0x10 + count * SECTION_SIZE
    if reader.read_at(body_at, 8) != MAGIC_BLOCKS:
        return Ncz(sections, body_at, body_size, None, [], 0)
    head = reader.read_at(body_at, BLOCK_HEADER_SIZE)
    exp = head[11]
    if not MIN_BLOCK_EXP <= exp <= MAX_BLOCK_EXP:
        raise ImageError("a compressed NCA block size is out of range")
    block = 1 << exp
    blocks_count, total = struct.unpack_from("<IQ", head, 12)
    if total < body_size or blocks_count != -(-total // block):
        raise ImageError("the NCZBLOCK header does not fit the sections of its NCA")
    sizes = list(struct.unpack(f"<{blocks_count}I", reader.read_at(body_at + BLOCK_HEADER_SIZE, 4 * blocks_count)))
    if max(sizes) > block:
        raise ImageError("a compressed NCA block is larger than its block size")
    body_at += BLOCK_HEADER_SIZE + 4 * blocks_count
    return Ncz(sections, body_at, body_size, exp, sizes, total)


def decompress_ncz(reader: ImageReader, ncz: Ncz, out: BinaryIO, is_cancelled: Callable[[], bool]) -> bool:
    """Write the NCA of ``ncz`` to ``out``: its header copy, then the body. False when cancelled first (``out`` is then
    partial). The body is written in chunks, never held whole."""
    out.write(reader.read_at(0, NCA_HEADER_SIZE))
    if ncz.block_exp is None:
        done = _solid(reader, ncz, out, is_cancelled)
    else:
        done = _blocks(reader, ncz, out, is_cancelled)
    out.flush()
    return done


def _zstd():
    try:
        from compression import zstd   # the standard library, Python 3.14+
    except ImportError:
        raise ImageError("compressed Switch images need Python 3.14 (compression.zstd)") from None
    return zstd


def _solid(reader: ImageReader, ncz: Ncz, out: BinaryIO, is_cancelled: Callable[[], bool]) -> bool:
    zstd = _zstd()
    decoder = zstd.ZstdDecompressor()
    left = ncz.body_size
    pos = ncz.body_at
    try:
        while left > 0:
            if is_cancelled():
                return False
            feed = b""
            if decoder.needs_input:
                take = min(CHUNK, reader.size - pos)
                if take <= 0:
                    raise ImageError("the compressed NCA ends before its sections do")
                feed = reader.read_at(pos, take)
                pos += take
            data = decoder.decompress(feed, max_length=min(CHUNK, left))
            out.write(data)
            left -= len(data)
            if decoder.eof and left > 0:
                raise ImageError("the compressed NCA ends before its sections do")
            if not data and not decoder.needs_input and not decoder.eof:
                raise ImageError("the compressed NCA stalls")
    except zstd.ZstdError:
        raise ImageError("the compressed NCA is corrupt") from None
    return True


def _blocks(reader: ImageReader, ncz: Ncz, out: BinaryIO, is_cancelled: Callable[[], bool]) -> bool:
    size = 1 << ncz.block_exp
    left = ncz.body_size
    pos = ncz.body_at
    for index, packed in enumerate(ncz.blocks):
        if left == 0:
            break
        if is_cancelled():
            return False
        plain_size = min(size, ncz.block_total - index * size)
        if packed > plain_size:
            raise ImageError("a compressed NCA block is larger than its data")
        raw = reader.read_at(pos, packed)
        pos += packed
        data = raw if packed == plain_size else _frame(raw, plain_size)
        piece = data[:left]
        out.write(piece)
        left -= len(piece)
    return True


def _frame(raw: bytes, size: int) -> bytes:
    """One zstd frame of an NCZBLOCK block, which must decompress to exactly ``size`` bytes."""
    zstd = _zstd()
    decoder = zstd.ZstdDecompressor()
    try:
        data = decoder.decompress(raw, max_length=size + 1)
    except zstd.ZstdError:
        raise ImageError("a compressed NCA block is corrupt") from None
    if not decoder.eof or len(data) != size:
        raise ImageError("a compressed NCA block does not decompress to its size")
    return data
