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


def _sfnt(tables):
    """One face: the table directory of ``tables`` (tag -> (offset, bytes)) into a single collection file."""
    head = struct.pack(">IHHHH", 0x00010000, len(tables), 0, 0, 0)
    records = b"".join(struct.pack(">4sIII", tag, 0, offset, len(data)) for tag, (offset, data) in tables.items())
    return head + records


def test_ttc_faces_keep_their_table_bytes(tmp_path):
    from tools.wii_nand import ttc

    glyf = bytes(range(10))  # shared by both faces, 10 bytes (padded to 12 in the output)
    cmap = b"cmap-table"
    # layout: TTC header (12 + 2 offsets = 20 bytes), face 0 directory, face 1 directory, then tables
    directory = 12 + 16 * 2  # sfnt header and two table records
    face0_at, face1_at = 20, 20 + directory
    table_at = 20 + 2 * directory
    tables = {b"cmap": (table_at, cmap), b"glyf": (table_at + len(cmap), glyf)}
    face = _sfnt(tables)
    header = b"ttcf" + struct.pack(">II", 0x00010000, 2) + struct.pack(">II", face0_at, face1_at)
    blob = header + face + face + cmap + glyf
    assert len(blob) == table_at + len(cmap) + len(glyf)
    faces = ttc.split_ttc(blob)
    assert len(faces) == 2
    for out in faces:
        assert out[:4] == struct.pack(">I", 0x00010000)
        assert struct.unpack_from(">H", out, 4)[0] == 2
        for i in range(2):
            tag, _checksum, offset, length = struct.unpack_from(">4sIII", out, 12 + 16 * i)
            assert out[offset:offset + length] == tables[tag][1]
    with pytest.raises(ttc.TtcError):
        ttc.split_ttc(b"not a collection")
