"""Synthetic checks for tools/wii_nand: page layout, SFFS walk and cluster decryption (no game data)."""
import struct

import pytest

pytest.importorskip("Crypto.Cipher.AES")
from Crypto.Cipher import AES  # noqa: E402

from tools.wii_nand import nand  # noqa: E402


class SparseFlat:
    """A flat NAND data view with only the written parts set; other bytes read as zero."""

    def __init__(self):
        self.parts = []

    def write(self, offset, data):
        self.parts.append((offset, data))

    def read_flat(self, offset, length):
        out = bytearray(length)
        for start, data in self.parts:
            lo, hi = max(offset, start), min(offset + length, start + len(data))
            if lo < hi:
                out[lo - offset:hi - offset] = data[lo - start:hi - start]
        return bytes(out)


def _build_image(key: bytes, payload: bytes) -> SparseFlat:
    flat = SparseFlat()
    sb = bytearray(nand.SUPERBLOCK_SIZE)
    sb[0:4] = b"SFFS"
    struct.pack_into(">I", sb, 4, 7)  # version
    struct.pack_into(">H", sb, 12 + 1 * 2, 0xFFFB)  # FAT: cluster 1 ends its chain
    fst = nand.FST_OFFSET
    # entry 0: root directory, first child 1
    struct.pack_into(">BBHHI", sb, fst + 12, 2, 0, 1, 0xFFFF, 0)
    # entry 1: file "hello.txt", first cluster 1, size of payload
    off = fst + nand.FST_ENTRY_SIZE
    sb[off:off + 9] = b"hello.txt"
    struct.pack_into(">BBHHI", sb, off + 12, 1, 0, 1, 0xFFFF, len(payload))
    flat.write(nand.SUPERBLOCK_START, bytes(sb))
    plain = payload + bytes(nand.CLUSTER - len(payload))
    cipher = AES.new(key, AES.MODE_CBC, bytes(16)).encrypt(plain)
    flat.write(nand.CLUSTER * 1, cipher)
    return flat


def test_raw_reader_skips_ecc_bytes(tmp_path):
    raw = tmp_path / "dump.bin"
    pages = [bytes([p]) * nand.PAGE_DATA + b"\xee" * nand.PAGE_ECC for p in range(3)]
    raw.write_bytes(b"".join(pages))
    reader = nand.RawNandFile(raw)
    try:
        assert reader.read_flat(nand.PAGE_DATA - 2, 4) == b"\x00\x00\x01\x01"
    finally:
        reader.close()


def test_walk_decrypts_and_exports_file(tmp_path):
    key_block = bytes(range(1, 17))
    keys = bytes(0x158) + key_block + bytes(nand.KEYS_SIZE - 0x158 - 16)
    image = nand.NandImage(_build_image(key_block, b"hello"), keys)
    listing = image.walk(None)
    assert listing == [("/hello.txt", 5)]
    image.walk(tmp_path)
    assert (tmp_path / "hello.txt").read_bytes() == b"hello"


def test_missing_superblock_is_rejected():
    keys = bytes(nand.KEYS_SIZE)
    with pytest.raises(nand.NandError):
        nand.NandImage(SparseFlat(), keys)


def test_names_with_path_characters_are_escaped():
    assert nand.escape_name("a/b:c") == "a%2Fb%3Ac"
