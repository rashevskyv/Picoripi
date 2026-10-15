"""WiiImage on synthetic Wii discs: the partition decrypt, the file layout and the refusals.

The discs are built here from random keys. The test encrypts them with its own AES calls, written from the Wii disc
spec, so only the spec decides what decrypts. No real disc or key file is used.
"""
from __future__ import annotations

import io
import os
import struct

import pytest

pytest.importorskip("Crypto.Cipher.AES", reason="the Wii image tests need pycryptodome")
from Crypto.Cipher import AES  # noqa: E402

from core.containers.image_files import ImageError  # noqa: E402
from core.containers.wii_disc import WII_MAGIC, WiiImage, load_common_key  # noqa: E402

TITLE_ID = b"\x00\x01\x00\x00RSTE"
PART_AT = 0x50000
DATA_AT = PART_AT + 0x8000
CLUSTER = 0x8000
DATA = 0x7C00
CLUSTERS = 3
DISC_SIZE = DATA_AT + CLUSTERS * CLUSTER
DEFAULT_FST_AT = 0x4000
A_TXT = os.urandom(0x30)
B_BIN = os.urandom(0x40)  # starts 0x10 bytes before the first cluster boundary, so it straddles it
BI2 = os.urandom(0x2000)
APPLOADER = bytearray(os.urandom(0x30))
struct.pack_into(">II", APPLOADER, 0x14, 0x10, 0)  # apploader code size 0x10, trailer 0: entry size 0x30
DOL = bytearray(0x140)  # one section at offset 0x100, size 0x40; the rest of the header stays zero
struct.pack_into(">I", DOL, 0x00, 0x100)
struct.pack_into(">I", DOL, 0x90, 0x40)
DOL[0x100:] = os.urandom(0x40)
FST = (struct.pack(">III", 1 << 24, 0, 4)           # root directory, its next index 4
       + struct.pack(">III", 1 << 24, 0, 3)         # dir/, its contents end before index 3
       + struct.pack(">III", 4, 0x5000 >> 2, 0x30)  # dir/a.txt, offset stored divided by 4
       + struct.pack(">III", 10, 0x7BF0 >> 2, 0x40)  # b.bin, offset stored divided by 4
       + b"dir\0a.txt\0b.bin\0")


@pytest.fixture
def common_key() -> bytes:
    return os.urandom(16)


def _plain(fst_at: int = DEFAULT_FST_AT) -> bytearray:
    """The decrypted partition data: boot.bin, bi2, apploader, FST, DOL and the two files."""
    plain = bytearray(CLUSTERS * DATA)
    boot = bytearray(0x440)
    struct.pack_into(">I", boot, 0x18, WII_MAGIC)
    struct.pack_into(">III", boot, 0x420, 0x3000 >> 2, fst_at >> 2, len(FST) >> 2)   # all three divided by 4
    plain[0:0x440] = boot
    plain[0x440:0x2440] = BI2
    plain[0x2440:0x2470] = APPLOADER
    plain[0x3000:0x3140] = DOL
    if fst_at + len(FST) <= len(plain):
        plain[fst_at:fst_at + len(FST)] = FST
    plain[0x5000:0x5030] = A_TXT
    plain[0x7BF0:0x7C30] = B_BIN
    return plain


def _disc(common_key: bytes, *, fst_at: int = DEFAULT_FST_AT, key_index: int = 0, magic: int = WII_MAGIC) -> bytearray:
    """A Wii disc: header, one data partition with a ticket, a TMD and three encrypted clusters."""
    title_key = os.urandom(16)
    disc = bytearray(DISC_SIZE)
    disc[0:6] = b"RSTE01"
    struct.pack_into(">I", disc, 0x18, magic)
    struct.pack_into(">II", disc, 0x40000, 1, 0x40020 >> 2)  # one group: one partition, table at 0x40020
    struct.pack_into(">II", disc, 0x40020, PART_AT >> 2, 0)  # partition at PART_AT, type 0 (data)
    disc[PART_AT + 0x1BF:PART_AT + 0x1CF] = AES.new(common_key, AES.MODE_CBC, TITLE_ID + bytes(8)).encrypt(title_key)
    disc[PART_AT + 0x1DC:PART_AT + 0x1E4] = TITLE_ID
    disc[PART_AT + 0x1F1] = key_index
    struct.pack_into(">I", disc, PART_AT + 0x2A4, 0x10)           # TMD size
    struct.pack_into(">I", disc, PART_AT + 0x2A8, 0x2C0 >> 2)     # TMD offset, stored divided by 4
    struct.pack_into(">I", disc, PART_AT + 0x2B8, 0x8000 >> 2)    # data offset
    struct.pack_into(">I", disc, PART_AT + 0x2BC, CLUSTERS * CLUSTER >> 2)  # data size
    plain = _plain(fst_at)
    for index in range(CLUSTERS):
        hash_block = AES.new(title_key, AES.MODE_CBC, bytes(16)).encrypt(os.urandom(0x400))
        iv = hash_block[0x3D0:0x3E0]  # the data IV is in the encrypted hash block
        data = AES.new(title_key, AES.MODE_CBC, iv).encrypt(bytes(plain[index * DATA:(index + 1) * DATA]))
        at = DATA_AT + index * CLUSTER
        disc[at:at + 0x400] = hash_block
        disc[at + 0x400:at + CLUSTER] = data
    return disc


def test_entries_and_contents_decrypt(common_key):
    image = WiiImage(io.BytesIO(_disc(common_key)), common_key)
    entries = image.entries()
    assert [entry.path for entry in entries] == [
        "sys/boot.bin", "sys/bi2.bin", "sys/apploader.img", "sys/fst.bin", "sys/main.dol",
        "files/dir/a.txt", "files/b.bin",
    ]
    contents = {entry.path: image.read(entry) for entry in entries}
    plain = _plain()
    assert contents["sys/boot.bin"] == bytes(plain[0:0x440])
    assert contents["sys/bi2.bin"] == bytes(plain[0x440:0x2440])
    assert contents["sys/apploader.img"] == bytes(APPLOADER)
    assert contents["sys/fst.bin"] == FST
    assert contents["sys/main.dol"] == bytes(DOL)
    assert contents["files/dir/a.txt"] == A_TXT
    assert contents["files/b.bin"] == B_BIN  # straddles the 0x7C00 boundary between two clusters


def test_wrong_key_is_refused(common_key):
    with pytest.raises(ImageError, match="does not decrypt the Wii image"):
        WiiImage(io.BytesIO(_disc(common_key)), os.urandom(16))


def test_bad_disc_magic_is_refused(common_key):
    with pytest.raises(ImageError, match="not a Wii disc image"):
        WiiImage(io.BytesIO(_disc(common_key, magic=0)), common_key)


def test_truncated_disc_is_refused(common_key):
    with pytest.raises(ImageError):
        WiiImage(io.BytesIO(bytes(_disc(common_key))[:0x60000]), common_key)


def test_bad_fst_pointer_is_refused(common_key):
    image = WiiImage(io.BytesIO(_disc(common_key, fst_at=0x7FFFF00)), common_key)
    with pytest.raises(ImageError):
        image.entries()


@pytest.mark.parametrize("key_index", [1, 2])
def test_korean_and_vwii_common_keys_are_not_supported(common_key, key_index):
    with pytest.raises(ImageError, match="not supported"):
        WiiImage(io.BytesIO(_disc(common_key, key_index=key_index)), common_key)


def test_disc_without_a_data_partition_is_refused(common_key):
    disc = _disc(common_key)
    struct.pack_into(">I", disc, 0x40024, 1)  # the partition's type becomes 1 (update)
    with pytest.raises(ImageError, match="no data partition"):
        WiiImage(io.BytesIO(disc), common_key)


def test_load_common_key_reads_the_key_at_0x158(tmp_path, common_key):
    keys = bytearray(0x400)
    keys[0x158:0x168] = common_key
    path = tmp_path / "keys.bin"
    path.write_bytes(bytes(keys))
    assert load_common_key(str(path)) == common_key


@pytest.mark.parametrize("size", [0x3FF, 0x401])
def test_load_common_key_refuses_a_bad_size_without_leaking_the_key(tmp_path, common_key, size):
    keys = bytearray(size)
    keys[0x158:0x168] = common_key
    path = tmp_path / "keys.bin"
    path.write_bytes(bytes(keys))
    with pytest.raises(ImageError, match="0x400 bytes") as info:
        load_common_key(str(path))
    assert common_key.hex() not in str(info.value)
    assert str(path) not in str(info.value)
