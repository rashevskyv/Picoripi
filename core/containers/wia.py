"""WIA and RVZ disc images (Dolphin's compressed GameCube and Wii formats), read as the plain disc they hold.

``WiaStream`` is a read-only binary stream of the decoded disc: ``seek``, ``tell`` and ``read`` work as on a plain
ISO, so ``GameCubeImage`` reads it unchanged. Groups (chunk_size bytes of disc each) are decoded when a read needs
them; the last two decoded groups are kept. Nothing else is held in memory.

Read: GameCube discs of any of these methods: none, bzip2, LZMA, LZMA2 (WIA and RVZ) and Zstandard (RVZ). RVZ
packing (the junk padding stored as a seed) is reproduced with the Lagged Fibonacci generator of the RVZ spec. Refused
with a reason: Wii partitions (they need decryption and hash rebuilding), the Purge method, and any other value.
The file is untrusted: every table, stored group, decompressed group and junk run is checked against the size its header
or table declares (and ``MAX_CHUNK``) before it is read, decoded or generated, and refused with ``ImageError`` past it.
Specification: Dolphin's docs/WiaAndRvz.md (WIA format 1.00 and the RVZ additions). Facts only; the decoder is written
from the spec.
"""
from __future__ import annotations

import bisect
import bz2
import lzma
import struct
from collections import OrderedDict
from typing import BinaryIO, Dict, List, Optional, Tuple

from core import zstd_frame
from core.containers.image_files import ImageError

MAGIC_WIA = b"WIA\x01"
MAGIC_RVZ = b"RVZ\x01"
HEAD_SIZE = 0x48
DISC_SIZE = 0xDC
DHEAD_SIZE = 0x80
SECTOR = 0x8000
MIB2 = 0x200000
MAX_CHUNK = 64 << 20

NONE, PURGE, BZIP2, LZMA, LZMA2, ZSTD = range(6)
METHOD_NAMES = {PURGE: "Purge", BZIP2: "bzip2", LZMA: "LZMA", LZMA2: "LZMA2", ZSTD: "Zstandard"}
GC_DISC, WII_DISC = 1, 2
SEED_SIZE = 68
LFG_K, LFG_J = 521, 32
JUNK_FLAG = 0x80000000
CACHE_GROUPS = 2


def is_wia_or_rvz(head: bytes) -> bool:
    return head[:4] in (MAGIC_WIA, MAGIC_RVZ)


class _Lfg:
    """The Lagged Fibonacci generator of the RVZ spec (f = xor, j = 32, k = 521), in the spec's own arithmetic.

    The state is the 521-word buffer. It starts from the 17 seed words (big endian), is filled with the recurrence,
    advanced four times, and advanced once after every 521 words written. Bytes come out as the spec writes them:
    the word's top byte, then bits 18 to 25, then bits 8 to 15, then the low byte.
    """

    def __init__(self, seed: bytes, offset: int) -> None:
        buf = list(struct.unpack(">17I", seed)) + [0] * (LFG_K - 17)
        for i in range(17, LFG_K):
            buf[i] = ((buf[i - 17] << 23) ^ (buf[i - 16] >> 9) ^ buf[i - 1]) & 0xFFFFFFFF
        self._buf = buf
        for _ in range(4):
            self._advance()
        self._period: Optional[bytes] = None
        self._pos = 0
        self.read(offset % SECTOR)   # the state moves on to the disc offset of the data

    def _advance(self) -> None:
        buf = self._buf
        for i in range(LFG_J):
            buf[i] ^= buf[i + LFG_K - LFG_J]
        for start in range(LFG_J, LFG_K, LFG_J):   # each block reads the block before it, already updated
            end = min(start + LFG_J, LFG_K)
            buf[start:end] = [x ^ y for x, y in zip(buf[start:end], buf[start - LFG_J:end - LFG_J])]

    def _render(self) -> bytes:
        buf = self._buf
        out = bytearray(LFG_K * 4)
        out[0::4] = bytes(x >> 24 for x in buf)
        out[1::4] = bytes((x >> 18) & 0xFF for x in buf)
        out[2::4] = bytes((x >> 8) & 0xFF for x in buf)
        out[3::4] = bytes(x & 0xFF for x in buf)
        return bytes(out)

    def read(self, size: int) -> bytes:
        out = bytearray()
        period_size = LFG_K * 4
        while size > 0:
            if self._period is None:
                self._period = self._render()
            if self._pos == period_size:
                self._advance()
                self._period = self._render()
                self._pos = 0
            take = min(size, period_size - self._pos)
            out += self._period[self._pos:self._pos + take]
            self._pos += take
            size -= take
        return bytes(out)


def junk_bytes(seed: bytes, offset: int, size: int) -> bytes:
    """``size`` junk bytes that a junk segment starting at disc offset ``offset`` holds, from its 68-byte seed."""
    if len(seed) != SEED_SIZE:
        raise ImageError("a junk seed must be 68 bytes")
    return _Lfg(seed, offset).read(size)


def _lzma_filters(method: int, props: bytes, expected: int) -> list:
    if method == LZMA:
        if len(props) < 5 or props[0] >= 9 * 5 * 5:
            raise ImageError("the LZMA properties of this image are not valid")
        d = props[0]
        lc = d % 9
        d //= 9
        pb = d // 5
        lp = d % 5
        dict_size = struct.unpack_from("<I", props, 1)[0]
        return [{"id": lzma.FILTER_LZMA1, "lc": lc, "lp": lp, "pb": pb,
                 "dict_size": min(max(dict_size, 4096), max(4096, expected))}]
    if not props or props[0] > 40:
        raise ImageError("the LZMA2 properties of this image are not valid")
    p = props[0]
    dict_size = 0xFFFFFFFF if p == 40 else (2 | (p & 1)) << (p // 2 + 11)
    return [{"id": lzma.FILTER_LZMA2, "dict_size": min(max(dict_size, 4096), max(4096, expected))}]


def _decompress(method: int, data: bytes, props: bytes, expected: int, what: str) -> bytes:
    """``data`` decompressed; refused when it holds more than ``expected`` bytes (one byte past it is ever made)."""
    if method not in (BZIP2, LZMA, LZMA2, ZSTD):
        raise ImageError(f"{what}: unknown compression method {method}")
    try:
        if method == BZIP2:
            out = bz2.BZ2Decompressor().decompress(data, expected + 1)
        elif method == ZSTD:
            out = zstd_frame.decompress(data, what, expected + 1)
        else:
            decoder = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=_lzma_filters(method, props, expected))
            out = decoder.decompress(data, expected + 1)
    except ImageError:
        raise
    except Exception as error:   # the codec's own error types; the reason goes to the user
        raise ImageError(f"{what}: the {METHOD_NAMES.get(method, 'compressed')} data does not decompress ({error})")
    if len(out) > expected:
        raise ImageError(f"{what}: decompresses to more than the {expected} bytes the image declares")
    return out


def _unpack_rvz(packed: bytes, logical: int, disc_start: int) -> bytes:
    """Undo the RVZ packing of one group: literal runs and junk segments (seed plus length)."""
    out = bytearray()
    pos = 0
    while pos < len(packed):
        if pos + 4 > len(packed):
            raise ImageError("an RVZ group ends inside a segment header")
        size = struct.unpack_from(">I", packed, pos)[0]
        pos += 4
        if size & JUNK_FLAG:
            size &= ~JUNK_FLAG
            if pos + SEED_SIZE > len(packed):
                raise ImageError("an RVZ group ends inside a junk seed")
            seed = packed[pos:pos + SEED_SIZE]
            pos += SEED_SIZE
            if len(out) + size > logical:   # checked before the junk is generated
                raise ImageError("an RVZ group is longer than its disc data")
            out += junk_bytes(seed, disc_start + len(out), size)
        else:
            if pos + size > len(packed):
                raise ImageError("an RVZ group ends inside a literal run")
            if len(out) + size > logical:
                raise ImageError("an RVZ group is longer than its disc data")
            out += packed[pos:pos + size]
            pos += size
    if len(out) != logical:
        raise ImageError("an RVZ group is shorter than its disc data")
    return bytes(out)


class WiaStream:
    """The decoded disc of a WIA or RVZ file as a read-only stream. ``close`` closes the file only if ``owns``."""

    def __init__(self, stream: BinaryIO, owns: bool = False) -> None:
        self._file = stream
        self._owns = owns
        self._pos = 0
        self._cache: "OrderedDict[int, bytes]" = OrderedDict()
        head = self._read_file(0, HEAD_SIZE + DISC_SIZE)
        if len(head) < HEAD_SIZE + DISC_SIZE or not is_wia_or_rvz(head):
            raise ImageError("not a WIA or RVZ image")
        self._rvz = head[:4] == MAGIC_RVZ
        (self.size,) = struct.unpack_from(">Q", head, 0x24)
        # wia_disc_t starts at 0x48 (the spec's table): offsets below are from that start.
        disc = HEAD_SIZE
        disc_type, method, _level, chunk = struct.unpack_from(">IIII", head, disc)
        self._dhead = head[disc + 0x10:disc + 0x10 + DHEAD_SIZE]
        n_part = struct.unpack_from(">I", head, disc + 0x90)[0]
        n_raw = struct.unpack_from(">I", head, disc + 0xB4)[0]
        raw_off, raw_size = struct.unpack_from(">QI", head, disc + 0xB8)
        n_groups = struct.unpack_from(">I", head, disc + 0xC4)[0]
        group_off, group_size = struct.unpack_from(">QI", head, disc + 0xC8)
        props_len = min(head[disc + 0xD4], 7)
        props = head[disc + 0xD5:disc + 0xD5 + props_len]
        if disc_type == WII_DISC or n_part:
            raise ImageError("a Wii WIA or RVZ image: its partitions need decryption, which Picoripi does not read yet")
        if disc_type != GC_DISC:
            raise ImageError(f"a WIA or RVZ image of disc type {disc_type}: not read")
        if method == PURGE:
            raise ImageError("a WIA or RVZ image with the Purge method: not read; convert it to a plain ISO first")
        if method not in METHOD_NAMES and method != NONE:
            raise ImageError(f"a WIA or RVZ image with unknown compression {method}")
        if method == ZSTD and not self._rvz:
            raise ImageError("a WIA image with Zstandard: not a WIA method")
        if self._rvz:
            power_of_two = chunk >= SECTOR and chunk & (chunk - 1) == 0
            if not (power_of_two or (chunk > 0 and chunk % MIB2 == 0)):
                raise ImageError("an RVZ chunk size must be a power of two of at least 32 KiB or a multiple of 2 MiB")
        elif chunk <= 0 or chunk % MIB2:
            raise ImageError("a WIA chunk size must be a multiple of 2 MiB")
        if chunk > MAX_CHUNK:
            raise ImageError("the chunk size of this image is too large to read")
        if self.size == 0:
            raise ImageError("the disc size in this image is zero")
        self._method = method
        self._props = props
        self._chunk = chunk
        self._groups = self._read_groups(group_off, group_size, n_groups, method, props)
        self._segment_of_group: Dict[int, Tuple[int, int]] = {}
        self._segments = self._read_raw_entries(raw_off, raw_size, n_raw, method, props, chunk)
        self._starts = [start for start, _end, _gi in self._segments]

    def _read_file(self, offset: int, size: int) -> bytes:
        self._file.seek(offset)
        return self._file.read(size)

    def _table(self, offset: int, size: int, count: int, entry: int, method: int, props: bytes, what: str) -> bytes:
        if count * entry > MAX_CHUNK or size > MAX_CHUNK:   # a 4 GiB disc in 32 KiB groups needs 1.5 MiB
            raise ImageError(f"the {what} table is too large to read ({count} entries in {size} bytes)")
        blob = self._read_file(offset, size)
        if len(blob) != size:
            raise ImageError(f"the {what} table is cut short")
        if method != NONE:
            blob = _decompress(method, blob, props, count * entry, what)
        if len(blob) != count * entry:
            raise ImageError(f"the {what} table does not hold its {count} entries")
        return blob

    def _read_groups(self, offset: int, size: int, count: int, method: int, props: bytes) -> List[Tuple[int, int, int]]:
        entry = 12 if self._rvz else 8
        blob = self._table(offset, size, count, entry, method, props, "group")
        groups = []
        for index in range(count):
            if self._rvz:
                off4, data_size, packed = struct.unpack_from(">III", blob, index * entry)
            else:
                off4, data_size = struct.unpack_from(">II", blob, index * entry)
                packed = 0
            groups.append((off4, data_size, packed))
        return groups

    def _read_raw_entries(self, offset: int, size: int, count: int, method: int, props: bytes,
                          chunk: int) -> List[Tuple[int, int, int]]:
        blob = self._table(offset, size, count, 24, method, props, "raw data")
        segments: List[Tuple[int, int, int]] = []
        for index in range(count):
            disc_off, disc_size, group_index, n_groups = struct.unpack_from(">QQII", blob, index * 24)
            start = disc_off - disc_off % SECTOR   # the first entry starts at 0x80: round down to the sector
            disc_size += disc_off - start
            if n_groups != -(-disc_size // chunk) or group_index + n_groups > len(self._groups):
                raise ImageError("the raw data table does not match its groups")
            for k in range(n_groups):
                begin = start + k * chunk
                end = min(begin + chunk, start + disc_size)
                segments.append((begin, end, group_index + k))
                self._segment_of_group[group_index + k] = (begin, end)
        segments.sort()
        return segments

    def _group(self, index: int) -> bytes:
        cached = self._cache.get(index)
        if cached is not None:
            self._cache.move_to_end(index)
            return cached
        start, end = self._segment_of_group[index]
        data = self._decode_group(index, start, end - start)
        self._cache[index] = data
        if len(self._cache) > CACHE_GROUPS:
            self._cache.popitem(last=False)
        return data

    def _decode_group(self, group: int, disc_start: int, logical: int) -> bytes:
        off4, field, packed = self._groups[group]
        if self._rvz:
            compressed = bool(field & JUNK_FLAG)
            size = field & ~JUNK_FLAG
        else:
            compressed = self._method != NONE
            size = field
        what = f"group {group}"
        if size > 2 * self._chunk or packed > 2 * self._chunk:   # stored or packed: never twice the disc data
            raise ImageError(f"{what} declares {max(size, packed)} bytes, more than a group of {self._chunk} can hold")
        if size == 0:
            return bytes(logical)   # every byte of this group is zero
        raw = self._read_file(off4 * 4, size)
        if len(raw) != size:
            raise ImageError("the image ends inside a group")
        if compressed and self._method != NONE:
            raw = _decompress(self._method, raw, self._props, packed or logical, what)
        if self._rvz and packed:
            return _unpack_rvz(raw, logical, disc_start)
        if len(raw) != logical:
            raise ImageError(f"{what} holds {len(raw)} bytes, its disc data is {logical}")
        return raw

    # The stream interface

    def read(self, size: int = -1) -> bytes:
        end = self.size if size is None or size < 0 else min(self.size, self._pos + size)
        if self._pos >= end:
            return b""
        out = bytearray(end - self._pos)
        lo_total, hi_total = self._pos, end
        for start, seg_end, group in self._segments_for(lo_total, hi_total):
            lo, hi = max(start, lo_total), min(seg_end, hi_total)
            data = self._group(group)
            out[lo - lo_total:hi - lo_total] = data[lo - start:hi - start]
        if lo_total < DHEAD_SIZE:   # the first 0x80 bytes come from the header, not from the groups
            head_hi = min(hi_total, DHEAD_SIZE)
            out[:head_hi - lo_total] = self._dhead[lo_total:head_hi]
        self._pos = end
        return bytes(out)

    def _segments_for(self, lo: int, hi: int) -> List[Tuple[int, int, int]]:
        last = bisect.bisect_left(self._starts, hi)
        return [segment for segment in self._segments[:last] if segment[1] > lo]

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            target = offset
        elif whence == 1:
            target = self._pos + offset
        elif whence == 2:
            target = self.size + offset
        else:
            raise ValueError("bad whence")
        if target < 0:
            raise ValueError("negative position")
        self._pos = target
        return target

    def tell(self) -> int:
        return self._pos

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def close(self) -> None:
        if self._owns:
            self._file.close()

    def __enter__(self) -> "WiaStream":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def open_disc(path) -> BinaryIO:
    """A plain binary stream of the disc at ``path``: the file itself, or the decoded WIA or RVZ image.

    The caller closes it. Used by readers and the disc writer, so an RVZ source reads as its ISO.
    """
    file = open(path, "rb")
    head = file.read(4)
    file.seek(0)
    if is_wia_or_rvz(head):
        try:
            return WiaStream(file, owns=True)
        except BaseException:   # a refused image (Wii, Purge, broken tables) must not leave the file open
            file.close()
            raise
    return file
