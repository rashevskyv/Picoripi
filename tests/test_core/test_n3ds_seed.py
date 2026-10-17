"""9.6 seed crypto of a 3DS title (``core.containers.n3ds``): the KeyY of a seeded NCCH is SHA-256 of its signature
and the title's seed, and a seed the header's check word does not match is refused. No game or key file is read."""
import hashlib
import struct

import pytest

from core.containers import n3ds
from core.containers.image_files import ImageError

PROGRAM_ID = bytes.fromhex("00a9ba0000040000")          # the program id as the NCCH header holds it (little-endian)
SEED = bytes(range(16))


def _header(signature: bytes, seed: bytes = SEED) -> bytes:
    head = bytearray(0x200)
    head[:16] = signature
    head[0x114:0x118] = hashlib.sha256(seed + PROGRAM_ID).digest()[:4]
    head[0x118:0x120] = PROGRAM_ID
    return bytes(head)


class _Keys:
    def __init__(self, seeds):
        self.seeds = seeds


def test_seeded_key_y_is_the_hash_of_the_signature_and_the_seed():
    signature = bytes(range(100, 116))
    key_y = n3ds._seeded_key_y(_Keys({PROGRAM_ID: SEED}), _header(signature), signature)
    assert key_y == hashlib.sha256(signature + SEED).digest()[:16]


def test_a_title_without_a_seed_is_refused_with_the_reason():
    signature = bytes(16)
    with pytest.raises(ImageError, match="no seed"):
        n3ds._seeded_key_y(_Keys({}), _header(signature), signature)


def test_a_seed_that_does_not_match_the_check_word_is_refused():
    signature = bytes(16)
    with pytest.raises(ImageError, match="does not match"):
        n3ds._seeded_key_y(_Keys({PROGRAM_ID: bytes(16)}), _header(signature), signature)


def test_seed_database_is_read_next_to_the_key_file(tmp_path):
    entry = PROGRAM_ID + SEED + bytes(8)                     # 32 bytes: id, seed, padding
    (tmp_path / "seeddb.bin").write_bytes(struct.pack("<I", 1) + bytes(12) + entry)
    assert n3ds._seeds(str(tmp_path)) == {PROGRAM_ID: SEED}
