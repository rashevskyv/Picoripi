"""UnityFS writer: a bundle written by ``Bundle.build`` keeps the directory-combined bit (the game finds the directory with
it) and stores its blocks in 128 KiB pieces. A small bundle is made here, so the test needs no game files."""
import struct

from core.unity.unityfs import BLOCK_SIZE, Bundle

FLAG_DIRECTORY_COMBINED = 0x40


def _bundle(payload: bytes) -> bytes:
    """A format 7 UnityFS bundle with one stored block and one file named CAB-test (block info not compressed)."""
    info = bytes(16) + struct.pack(">i", 1) + struct.pack(">IIH", len(payload), len(payload), 0)
    info += struct.pack(">i", 1) + struct.pack(">qqI", 0, len(payload), 4) + b"CAB-test\x00"
    head = bytearray(b"UnityFS\x00") + struct.pack(">I", 7) + b"5.x.x\x00" + b"2019.4.27f1\x00"
    head += struct.pack(">q", 0) + struct.pack(">III", len(info), len(info), FLAG_DIRECTORY_COMBINED)
    head += b"\x00" * (-len(head) % 16)
    return bytes(head) + info + payload


def test_build_keeps_the_directory_bit_and_reads_back():
    original = _bundle(b"A" * 1000)
    built = Bundle(original).build({"CAB-test": b"B" * 2000})
    parsed = Bundle(built)
    assert parsed.flags & FLAG_DIRECTORY_COMBINED
    assert parsed.read("CAB-test") == b"B" * 2000
    assert parsed.size == len(built)


def test_build_stores_blocks_of_the_game_size():
    original = _bundle(b"A" * 1000)
    payload = bytes(range(256)) * (BLOCK_SIZE // 256 * 2 + 1)
    built = Bundle(original).build({"CAB-test": payload})
    parsed = Bundle(built)
    assert [block[0] for block in parsed.blocks] == [BLOCK_SIZE, BLOCK_SIZE, 256]
    assert all(block[2] == 0 for block in parsed.blocks)
    assert parsed.read("CAB-test") == payload
