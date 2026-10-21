"""Wii WIA and RVZ images on synthetic discs: the partition data is stored decrypted, so it is read with no key.

A small writer here builds the raw area (disc header, partition table, partition header) and one partition whose data
groups start with hash exception lists, then the reader must give back the plain partition and its files.
"""
import bz2
import io
import random
import struct

import pytest

from core import zstd_frame
from core.containers import wia
from core.containers.image_files import ImageError
from core.containers.wii_disc import WII_MAGIC, WiiImage
from core.project_library import images

NONE, BZIP2, ZSTD = 0, 2, 5
SECTOR, SECTOR_DATA = 0x8000, 0x7C00
PART_AT, DATA_AT = 0x50000, 0x60000
FST = (struct.pack(">III", 1 << 24, 0, 3) + struct.pack(">III", 0, 0x9000 >> 2, 0x30)
       + struct.pack(">III", 6, 0xC000 >> 2, 0x20) + b"a.txt\0b.bin\0")


def _plain(sectors: int) -> bytearray:
    """The decrypted partition data: boot.bin, bi2, apploader, a DOL, the FST and two files."""
    plain = bytearray(random.Random(4).getrandbits(8) for _ in range(sectors * SECTOR_DATA))
    boot = bytearray(0x440)
    boot[:6] = b"RTSE01"
    struct.pack_into(">I", boot, 0x18, WII_MAGIC)
    struct.pack_into(">III", boot, 0x420, 0x3000 >> 2, 0x8000 >> 2, len(FST) >> 2)
    plain[:0x440] = boot
    plain[0x2440 + 0x14:0x2440 + 0x1C] = struct.pack(">II", 0x10, 0)
    plain[0x3000:0x3100] = bytes(0x100)
    struct.pack_into(">I", plain, 0x3000, 0x100)
    struct.pack_into(">I", plain, 0x3090, 0x40)
    plain[0x8000:0x8000 + len(FST)] = FST
    plain[0x9000:0x9030] = b"A" * 0x30
    plain[0xC000:0xC020] = b"B" * 0x20
    return plain


def _raw_area() -> bytes:
    raw = bytearray(DATA_AT)
    raw[:6] = b"RTSE01"
    struct.pack_into(">I", raw, 0x18, WII_MAGIC)
    struct.pack_into(">II", raw, 0x40000, 1, 0x40020 >> 2)
    struct.pack_into(">II", raw, 0x40020, PART_AT >> 2, 0)
    struct.pack_into(">II", raw, PART_AT + 0x2A4, 0x100, 0x2C0 >> 2)
    struct.pack_into(">II", raw, PART_AT + 0x2B8, (DATA_AT - PART_AT) >> 2, (4 * SECTOR) >> 2)
    return bytes(raw)


def _compress(method, data):
    return {NONE: lambda d: d, BZIP2: bz2.compress, ZSTD: lambda d: zstd_frame.compress(d, "test")}[method](data)


def build_wii(plain: bytes, *, rvz: bool, method: int, chunk: int, exceptions: int = 0, junk=None, raw=None,
              data_at: int = DATA_AT) -> bytes:
    """A Wii WIA or RVZ: the raw area as one raw entry, the partition as one data entry. ``junk`` is ``(offset in the
    partition data, size, seed)`` stored as an RVZ seed in its group."""
    raw = _raw_area() if raw is None else raw
    chunk_data = chunk // SECTOR * SECTOR_DATA
    lists = max(1, chunk // 0x200000)
    blobs, entries = [], []

    def group(data: bytes, packed: int, compress: bool) -> None:
        stored = _compress(method, data) if compress else data
        blobs.append(stored)
        entries.append((len(stored) | (wia.JUNK_FLAG if compress and rvz else 0), packed))

    for start in range(0, len(raw), chunk):
        group(raw[start:start + chunk], 0, method != NONE)
    raw_groups = len(entries)
    for number, start in enumerate(range(0, len(plain), chunk_data)):
        data = plain[start:start + chunk_data]
        head = b"".join(struct.pack(">H", exceptions) + bytes(22 * exceptions) for _ in range(lists))
        compress = method != NONE and (not rvz or number % 2 == 0)
        packed = 0
        if rvz and junk and start <= junk[0] < start + chunk_data:
            at, size, seed = junk[0] - start, junk[1], junk[2]
            body = (struct.pack(">I", at) + data[:at] + struct.pack(">I", size | wia.JUNK_FLAG) + seed
                    + struct.pack(">I", len(data) - at - size) + data[at + size:])
            packed, data = len(body), body
        if not compress:
            head += bytes(-len(head) % 4)
        group(head + data, packed, compress)
    head_len = 0x48 + 0xDC
    part_off = head_len
    part = bytes(16) + struct.pack(">IIII", data_at // SECTOR, len(plain) // SECTOR_DATA, raw_groups,
                                   len(entries) - raw_groups) + bytes(16)
    raw_table = _compress(method, struct.pack(">QQII", 0x80, len(raw) - 0x80, 0, raw_groups))
    body = bytearray(part + raw_table)
    body += bytes(-(head_len + len(body)) % 4)
    table = bytearray()
    for blob, (field, packed) in zip(blobs, entries):
        off4 = (head_len + len(body)) // 4
        body += blob + bytes(-len(blob) % 4)
        table += struct.pack(">III", off4, field, packed) if rvz else struct.pack(">II", off4, field)
    group_table = _compress(method, bytes(table))
    group_off = head_len + len(body)
    body += group_table
    head = bytearray(head_len)
    head[0:4] = wia.MAGIC_RVZ if rvz else wia.MAGIC_WIA
    struct.pack_into(">Q", head, 0x24, data_at + len(plain) // SECTOR_DATA * SECTOR)
    d = 0x48
    struct.pack_into(">IIII", head, d, 2, method, 0, chunk)
    head[d + 0x10:d + 0x90] = raw[:0x80]
    struct.pack_into(">IIQ", head, d + 0x90, 1, len(part), part_off)
    struct.pack_into(">IQI", head, d + 0xB4, 1, part_off + len(part), len(raw_table))
    struct.pack_into(">IQI", head, d + 0xC4, len(entries), group_off, len(group_table))
    return bytes(head) + bytes(body)


@pytest.mark.parametrize("rvz,method,chunk", [(True, ZSTD, 0x20000), (True, NONE, 0x8000), (False, BZIP2, 0x200000),
                                              (False, NONE, 0x200000)])
def test_the_partition_data_reads_back_without_a_key(rvz, method, chunk):
    plain = bytes(_plain(4))
    data = build_wii(plain, rvz=rvz, method=method, chunk=chunk, exceptions=2)
    with wia.WiaStream(io.BytesIO(data)) as disc:
        assert disc.read(6) == b"RTSE01"
        view = disc.partition_view(DATA_AT)
        assert view.size == len(plain) and view.read() == plain
        view.seek(SECTOR_DATA - 5)
        assert view.read(10) == plain[SECTOR_DATA - 5:SECTOR_DATA + 5]   # across two groups


def test_rvz_junk_inside_a_partition_counts_from_the_partition_data():
    plain = bytearray(_plain(2))
    seed = bytes(range(68))
    at, size = SECTOR_DATA + 0x1000, 0x2000
    plain[at:at + size] = wia.junk_bytes(seed, at, size)   # the offset counts from the start of the partition data
    data = build_wii(bytes(plain), rvz=True, method=NONE, chunk=0x8000, junk=(at, size, seed))
    with wia.WiaStream(io.BytesIO(data)) as disc:
        assert disc.partition_view(DATA_AT).read() == bytes(plain)


def test_the_wii_reader_lists_the_files_and_identify_needs_no_key(tmp_path):
    plain = bytes(_plain(4))
    image = tmp_path / "game.rvz"
    image.write_bytes(build_wii(plain, rvz=True, method=ZSTD, chunk=0x20000))
    found = images.identify(image)
    assert (found["kind"], found["game_id"], found["encrypted"], found["revision"]) == ("wii", "RTSE01", False, 0)
    assert images.needs_key(image) is None
    out = tmp_path / "out"
    images.extract(image, out, lambda p, t: None, lambda: False)
    assert (out / "files" / "a.txt").read_bytes() == b"A" * 0x30
    assert (out / "files" / "b.bin").read_bytes() == b"B" * 0x20
    assert (out / "sys" / "fst.bin").read_bytes() == FST
    with wia.open_disc(image) as disc:
        assert [entry.path for entry in WiiImage(disc, None).entries()][-2:] == ["files/a.txt", "files/b.bin"]


def test_a_partition_that_is_not_in_the_image_is_refused():
    data = build_wii(bytes(_plain(2)), rvz=True, method=NONE, chunk=0x8000)
    with wia.WiaStream(io.BytesIO(data)) as disc, pytest.raises(ImageError, match="no Wii partition"):
        disc.partition_view(0x123000)


def test_too_many_hash_exceptions_are_refused():
    data = build_wii(bytes(_plain(2)), rvz=True, method=NONE, chunk=0x8000, exceptions=wia.MAX_EXCEPTIONS + 1)
    with wia.WiaStream(io.BytesIO(data)) as disc, pytest.raises(ImageError, match="hash exceptions"):
        disc.partition_view(DATA_AT).read(16)


def test_a_partition_table_that_does_not_match_its_groups_is_refused():
    data = bytearray(build_wii(bytes(_plain(2)), rvz=True, method=NONE, chunk=0x8000))
    part_off = struct.unpack_from(">Q", data, 0x48 + 0x98)[0]
    struct.pack_into(">I", data, part_off + 0x1C, 99)   # pd[0].n_groups
    with pytest.raises(ImageError, match="partition table"):
        wia.WiaStream(io.BytesIO(bytes(data)))
