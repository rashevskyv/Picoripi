"""WIA and RVZ disc images (Dolphin's compressed GameCube and Wii formats), read as the plain disc they hold.

``WiaStream`` is a read-only binary stream of the decoded disc: ``seek``, ``tell`` and ``read`` work as on a plain
ISO, so ``GameCubeImage`` reads it unchanged. Groups (chunk_size bytes of disc each) are decoded when a read needs
them; the last two decoded groups are kept. Nothing else is held in memory.

Read: GameCube and Wii discs of any of these methods: none, bzip2, LZMA, LZMA2 (WIA and RVZ) and Zstandard (RVZ). RVZ
packing (the junk padding stored as a seed) is reproduced with the Lagged Fibonacci generator of the RVZ spec. A Wii
image stores each partition's data already decrypted, with the hash blocks removed: ``partition_view`` reads it (no
key is needed or opened), while the stream itself reads only the raw areas (headers, partition table, tickets) and
gives zeros inside a partition. The hash exception lists are skipped, never applied. Refused with a reason: the Purge
method and any other value.
The file is untrusted: every table, stored group, decompressed group and junk run is checked against the size its header
or table declares (and ``MAX_CHUNK``) before it is read, decoded or generated, and refused with ``ImageError`` past it.
Specification: Dolphin's docs/WiaAndRvz.md (WIA format 1.00 and the RVZ additions). Facts only; the decoder is written
from the spec.
"""
from __future__ import annotations

from core.i18n import tr

import bisect
import bz2
import lzma
import struct
from collections import OrderedDict
from typing import BinaryIO, Dict, List, Optional, Tuple

from core import zstd_frame
from core.containers.console_crypto import PlainView
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
SECTOR_DATA = 0x7C00          # a Wii partition sector without its 0x400-byte hash block
PART_STRUCT = 0x30            # wia_part_t: the title key, then two wia_part_data_t
MAX_PART_STRUCT = 0x400
MAX_PARTS = 128
LIST_DATA = 0x1F0000          # one hash exception list per 2 MiB of disc (this much partition data)
MAX_EXCEPTIONS = 52 * 64      # per list: Dolphin's own limit, enough for every hash and padding byte
EXCEPTION = 22                # u16 offset and a 20-byte SHA-1


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
        raise ImageError(tr("a junk seed must be 68 bytes"))
    return _Lfg(seed, offset).read(size)


def _lzma_filters(method: int, props: bytes, expected: int) -> list:
    if method == LZMA:
        if len(props) < 5 or props[0] >= 9 * 5 * 5:
            raise ImageError(tr("the LZMA properties of this image are not valid"))
        d = props[0]
        lc = d % 9
        d //= 9
        pb = d // 5
        lp = d % 5
        dict_size = struct.unpack_from("<I", props, 1)[0]
        return [{"id": lzma.FILTER_LZMA1, "lc": lc, "lp": lp, "pb": pb,
                 "dict_size": min(max(dict_size, 4096), max(4096, expected))}]
    if not props or props[0] > 40:
        raise ImageError(tr("the LZMA2 properties of this image are not valid"))
    p = props[0]
    dict_size = 0xFFFFFFFF if p == 40 else (2 | (p & 1)) << (p // 2 + 11)
    return [{"id": lzma.FILTER_LZMA2, "dict_size": min(max(dict_size, 4096), max(4096, expected))}]


def _decompress(method: int, data: bytes, props: bytes, expected: int, what: str) -> bytes:
    """``data`` decompressed; refused when it holds more than ``expected`` bytes (one byte past it is ever made)."""
    if method not in (BZIP2, LZMA, LZMA2, ZSTD):
        raise ImageError(tr("{0}: unknown compression method {1}", what, method))
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
        raise ImageError(tr("{0}: the {1} data does not decompress ({2})", what, METHOD_NAMES.get(method, 'compressed'), error))
    if len(out) > expected:
        raise ImageError(tr("{0}: decompresses to more than the {1} bytes the image declares", what, expected))
    return out


def _unpack_rvz(packed: bytes, logical: int, disc_start: int) -> bytes:
    """Undo the RVZ packing of one group: literal runs and junk segments (seed plus length)."""
    out = bytearray()
    pos = 0
    while pos < len(packed):
        if pos + 4 > len(packed):
            raise ImageError(tr("an RVZ group ends inside a segment header"))
        size = struct.unpack_from(">I", packed, pos)[0]
        pos += 4
        if size & JUNK_FLAG:
            size &= ~JUNK_FLAG
            if pos + SEED_SIZE > len(packed):
                raise ImageError(tr("an RVZ group ends inside a junk seed"))
            seed = packed[pos:pos + SEED_SIZE]
            pos += SEED_SIZE
            if len(out) + size > logical:   # checked before the junk is generated
                raise ImageError(tr("an RVZ group is longer than its disc data"))
            out += junk_bytes(seed, disc_start + len(out), size)
        else:
            if pos + size > len(packed):
                raise ImageError(tr("an RVZ group ends inside a literal run"))
            if len(out) + size > logical:
                raise ImageError(tr("an RVZ group is longer than its disc data"))
            out += packed[pos:pos + size]
            pos += size
    if len(out) != logical:
        raise ImageError(tr("an RVZ group is shorter than its disc data"))
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
            raise ImageError(tr("not a WIA or RVZ image"))
        self._rvz = head[:4] == MAGIC_RVZ
        (self.size,) = struct.unpack_from(">Q", head, 0x24)
        # wia_disc_t starts at 0x48 (the spec's table): offsets below are from that start.
        disc = HEAD_SIZE
        disc_type, method, _level, chunk = struct.unpack_from(">IIII", head, disc)
        self._dhead = head[disc + 0x10:disc + 0x10 + DHEAD_SIZE]
        n_part, part_size = struct.unpack_from(">II", head, disc + 0x90)
        part_off = struct.unpack_from(">Q", head, disc + 0x98)[0]
        n_raw = struct.unpack_from(">I", head, disc + 0xB4)[0]
        raw_off, raw_size = struct.unpack_from(">QI", head, disc + 0xB8)
        n_groups = struct.unpack_from(">I", head, disc + 0xC4)[0]
        group_off, group_size = struct.unpack_from(">QI", head, disc + 0xC8)
        props_len = min(head[disc + 0xD4], 7)
        props = head[disc + 0xD5:disc + 0xD5 + props_len]
        if disc_type not in (GC_DISC, WII_DISC):
            raise ImageError(tr("a WIA or RVZ image of disc type {0}: not read", disc_type))
        if disc_type == GC_DISC and n_part:
            raise ImageError(tr("a GameCube WIA or RVZ image cannot have Wii partitions"))
        if method == PURGE:
            raise ImageError(tr("a WIA or RVZ image with the Purge method: not read; convert it to a plain ISO first"))
        if method not in METHOD_NAMES and method != NONE:
            raise ImageError(tr("a WIA or RVZ image with unknown compression {0}", method))
        if method == ZSTD and not self._rvz:
            raise ImageError(tr("a WIA image with Zstandard: not a WIA method"))
        if self._rvz:
            power_of_two = chunk >= SECTOR and chunk & (chunk - 1) == 0
            if not (power_of_two or (chunk > 0 and chunk % MIB2 == 0)):
                raise ImageError(tr("an RVZ chunk size must be a power of two of at least 32 KiB or a multiple of 2 MiB"))
        elif chunk <= 0 or chunk % MIB2:
            raise ImageError(tr("a WIA chunk size must be a multiple of 2 MiB"))
        if chunk > MAX_CHUNK:
            raise ImageError(tr("the chunk size of this image is too large to read"))
        if self.size == 0:
            raise ImageError(tr("the disc size in this image is zero"))
        self._method = method
        self._props = props
        self._chunk = chunk
        self._groups = self._read_groups(group_off, group_size, n_groups, method, props)
        # group index -> (junk offset of its first byte, its data size, its hash exception lists)
        self._group_info: Dict[int, Tuple[int, int, int]] = {}
        self._segments = self._read_raw_entries(raw_off, raw_size, n_raw, method, props, chunk)
        self._starts = [start for start, _end, _gi in self._segments]
        self._partitions = self._read_partitions(part_off, n_part, part_size)

    def _read_file(self, offset: int, size: int) -> bytes:
        self._file.seek(offset)
        return self._file.read(size)

    def _table(self, offset: int, size: int, count: int, entry: int, method: int, props: bytes, what: str) -> bytes:
        if count * entry > MAX_CHUNK or size > MAX_CHUNK:   # a 4 GiB disc in 32 KiB groups needs 1.5 MiB
            raise ImageError(tr("the {0} table is too large to read ({1} entries in {2} bytes)", what, count, size))
        blob = self._read_file(offset, size)
        if len(blob) != size:
            raise ImageError(tr("the {0} table is cut short", what))
        if method != NONE:
            blob = _decompress(method, blob, props, count * entry, what)
        if len(blob) != count * entry:
            raise ImageError(tr("the {0} table does not hold its {1} entries", what, count))
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
                raise ImageError(tr("the raw data table does not match its groups"))
            for k in range(n_groups):
                begin = start + k * chunk
                end = min(begin + chunk, start + disc_size)
                segments.append((begin, end, group_index + k))
                self._group_info[group_index + k] = (begin, end - begin, 0)
        segments.sort()
        return segments

    def _read_partitions(self, offset: int, count: int, size: int) -> List[Tuple[int, List[Tuple[int, int, int]]]]:
        """Each Wii partition: (disc offset of its data, [(start, end, group)] in its decrypted data)."""
        if not count:
            return []
        if count > MAX_PARTS or not 0 < size <= MAX_PART_STRUCT:
            raise ImageError(tr("the partition table of this image is not valid"))
        blob = self._read_file(offset, count * size)
        if len(blob) != count * size:
            raise ImageError(tr("the partition table is cut short"))
        chunk_data = self._chunk // SECTOR * SECTOR_DATA if self._chunk >= SECTOR else 0
        lists = max(1, self._chunk // MIB2)
        partitions = []
        for index in range(count):
            entry = blob[index * size:(index + 1) * size].ljust(PART_STRUCT, b"\0")   # the spec pads a short struct
            pds = [struct.unpack_from(">IIII", entry, 0x10 + k * 0x10) for k in range(2)]
            first = pds[0][0]
            segments: List[Tuple[int, int, int]] = []
            for pd_first, n_sectors, group_index, n_groups in pds:
                if not n_sectors:
                    continue
                if pd_first < first:
                    raise ImageError(tr("the partition table of this image is not valid"))
                start = (pd_first - first) * SECTOR_DATA
                data_size = n_sectors * SECTOR_DATA
                if (not chunk_data or n_groups != -(-data_size // chunk_data)
                        or group_index + n_groups > len(self._groups)):
                    raise ImageError(tr("the partition table does not match its groups"))
                for k in range(n_groups):
                    begin = start + k * chunk_data
                    end = min(begin + chunk_data, start + data_size)
                    segments.append((begin, end, group_index + k))
                    # the junk offset counts from the start of this data entry, as Dolphin writes it
                    self._group_info[group_index + k] = (k * chunk_data, end - begin, lists)
            segments.sort()
            partitions.append((first * SECTOR, segments))
        return partitions

    def partition_view(self, data_at: int) -> "PartitionView":
        """The decrypted data of the Wii partition whose data starts at disc offset ``data_at``."""
        for start, segments in self._partitions:
            if start == data_at and segments:
                return PartitionView(self, segments)
        raise ImageError(tr("this image holds no Wii partition data at {0:#x}", data_at))

    def _group(self, index: int) -> bytes:
        cached = self._cache.get(index)
        if cached is not None:
            self._cache.move_to_end(index)
            return cached
        junk_at, logical, lists = self._group_info[index]
        data = self._decode_group(index, junk_at, logical, lists)
        self._cache[index] = data
        if len(self._cache) > CACHE_GROUPS:
            self._cache.popitem(last=False)
        return data

    @staticmethod
    def _skip_exceptions(data: bytes, lists: int, align: bool, what: str) -> int:
        """The offset after ``lists`` hash exception lists at the start of ``data`` (padded to 4 when ``align``)."""
        pos = 0
        for _ in range(lists):
            if pos + 2 > len(data):
                raise ImageError(tr("{0} ends inside its hash exceptions", what))
            count = struct.unpack_from(">H", data, pos)[0]
            if count > MAX_EXCEPTIONS:
                raise ImageError(tr("{0} declares {1} hash exceptions, more than a list can hold", what, count))
            pos += 2 + count * EXCEPTION
        if align:
            pos += -pos % 4
        if pos > len(data):
            raise ImageError(tr("{0} ends inside its hash exceptions", what))
        return pos

    def _decode_group(self, group: int, disc_start: int, logical: int, lists: int = 0) -> bytes:
        off4, field, packed = self._groups[group]
        if self._rvz:
            compressed = bool(field & JUNK_FLAG)
            size = field & ~JUNK_FLAG
        else:
            compressed = self._method != NONE
            size = field
        if size == 0:
            return bytes(logical)   # every byte of this group is zero
        what = f"group {group}"
        exceptions = lists * (2 + MAX_EXCEPTIONS * EXCEPTION)   # the most the hash exception lists can take
        if size > 2 * self._chunk + exceptions or packed > 2 * self._chunk:   # never twice the disc data
            raise ImageError(tr("{0} declares {1} bytes, more than a group of {2} can hold", what, max(size, packed), self._chunk))
        raw = self._read_file(off4 * 4, size)
        if len(raw) != size:
            raise ImageError(tr("the image ends inside a group"))
        stored = not (compressed and self._method != NONE)
        if not stored:
            raw = _decompress(self._method, raw, self._props, (packed or logical) + exceptions, what)
        if lists:   # stored lists are padded to 4 bytes; compressed ones are not
            raw = raw[self._skip_exceptions(raw, lists, stored, what):]
        if self._rvz and packed:
            return _unpack_rvz(raw, logical, disc_start)
        if len(raw) != logical:
            raise ImageError(tr("{0} holds {1} bytes, its disc data is {2}", what, len(raw), logical))
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


class PartitionView(PlainView):
    """The decrypted data of one Wii partition of a WIA or RVZ image (0x7C00 bytes per disc sector, no hashes).
    Gaps between its data entries read as zeros."""

    def __init__(self, image: WiaStream, segments: List[Tuple[int, int, int]]) -> None:
        super().__init__(segments[-1][1])
        self._image = image
        self._segments = segments
        self._starts = [start for start, _end, _gi in segments]

    def _plain(self, offset: int, size: int) -> bytes:
        out = bytearray(size)
        hi_total = offset + size
        last = bisect.bisect_left(self._starts, hi_total)
        for start, end, group in self._segments[:last]:
            if end <= offset:
                continue
            lo, hi = max(start, offset), min(end, hi_total)
            out[lo - offset:hi - offset] = self._image._group(group)[lo - start:hi - start]
        return bytes(out)


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
