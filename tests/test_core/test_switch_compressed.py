"""The compression layer of a Switch RomFS section: the LZ4 block decoder and the logical view, on hand-made bytes.

Every table and block is built here from the layout in ``core/containers/switch_compressed.py``; nothing is encrypted,
so these tests need no key and no pycryptodome.
"""
import io
import struct

import pytest

from core.containers.console_crypto import RangeView
from core.containers.image_files import ImageError
from core.containers.switch_compressed import CompressedView, is_compressed, lz4_decode

LEVEL = 0x200
TABLE = 0x400          # from the level
SET = 0x4000
BLOCKS = TABLE + 0x4000 * 2   # the blocks follow the two table nodes; their stored offsets count from the level


def _literals(data):
    """An LZ4 sequence of literals only (the last sequence of a block)."""
    out = bytearray([min(len(data), 15) << 4])
    if len(data) >= 15:
        rest = len(data) - 15
        while rest >= 255:
            out.append(255)
            rest -= 255
        out.append(rest)
    return bytes(out) + data


def _table_fsh(entries, *, magic=b"BKTR", table_at=TABLE):
    """An FS header with a one-node table: ``entries`` are (logical, stored offset from the level, type, stored size)."""
    fsh = bytearray(0x200)
    fsh[0x90:0x98] = struct.pack("<Q", LEVEL)
    fsh[0x178:0x194] = struct.pack("<qq4sII", table_at, 0x8000, magic, 1, len(entries))
    return bytes(fsh)


def _section(blocks, entries, logical_end):
    """The stored section: the level prefix, the one-node table at ``table_at``, then the blocks (level-relative)."""
    rel = bytearray(TABLE + 0x4000 * 2)
    rel[TABLE:TABLE + 0x10] = struct.pack("<iiq", 0, 1, logical_end)
    rel[TABLE + SET:TABLE + SET + 0x10] = struct.pack("<iiq", 0, len(entries), logical_end)
    for index, (virt, phys, kind, size) in enumerate(entries):
        at = TABLE + SET + 0x10 + index * 0x18
        rel[at:at + 0x18] = struct.pack("<qqBbHI", virt, phys, kind, 0, 0, size)
    rel += bytes(blocks)
    return bytes(LEVEL) + bytes(rel)


def _view(stored, fsh):
    return CompressedView(RangeView(io.BytesIO(stored), 0, len(stored)), fsh)


def _pattern(size):
    return bytes((index * 7 + 3) & 0xFF for index in range(size))


def test_lz4_literals_only_block_decodes():
    assert lz4_decode(_literals(b"hello"), 5) == b"hello"


def test_lz4_long_literal_run_uses_the_length_extension():
    data = _pattern(300)
    assert lz4_decode(_literals(data), 300) == data


def test_lz4_overlapping_match_repeats_the_last_bytes():
    # sequence 1: literals "ab", then a match of 10 bytes at offset 2; sequence 2: literal "Z" to the end
    block = bytes([0x26]) + b"ab" + struct.pack("<H", 2) + bytes([0x10]) + b"Z"
    assert lz4_decode(block, 13) == b"ab" + b"ab" * 5 + b"Z"


@pytest.mark.parametrize("block, size", [
    (bytes([0x26]) + b"ab" + struct.pack("<H", 0) + bytes([0x10]) + b"Z", 13),     # offset 0
    (bytes([0x26]) + b"ab" + struct.pack("<H", 9) + bytes([0x10]) + b"Z", 13),     # offset before the output
    (bytes([0x50]) + b"ab", 5),                                                    # literals run past the input
    (bytes([0x20]) + b"ab" + b"", 2),                                          # a match offset is cut short
    (_literals(b"hello"), 6),                                                      # the output is the wrong size
    (bytes([0xF0, 0xFF, 0xFF]), 300),                                              # the length extension is cut short
    (bytes([0x26]) + b"ab" + struct.pack("<H", 2), 13),                            # the block ends after a match
])
def test_damaged_lz4_block_is_an_image_error(block, size):
    with pytest.raises(ImageError):
        lz4_decode(block, size)


def test_a_match_longer_than_the_output_is_refused_before_it_is_copied():
    block = bytes([0x2F]) + b"ab" + struct.pack("<H", 2) + bytes([0xFF, 0x00]) + bytes([0x10]) + b"Z"
    with pytest.raises(ImageError):
        lz4_decode(block, 13)


def test_logical_view_mixes_stored_zero_and_lz4_blocks_and_keeps_the_bytes_before_the_level():
    romfs = _pattern(0x300)
    raw_lz4 = _literals(romfs[0x100:0x300])
    blocks = romfs[:0x100] + raw_lz4
    entries = [(0, BLOCKS, 0, 0xFFFFFFFF), (0x100, BLOCKS + 0x100, 3, len(raw_lz4)), (0x300, 0, 1, 0xFFFFFFFF)]
    logical_end = 0x400
    stored = _section(blocks, entries, logical_end)
    view = _view(stored, _table_fsh(entries))
    view_bytes = view.read(view.size)

    assert view.size == LEVEL + logical_end
    assert view_bytes[:LEVEL] == stored[:LEVEL]
    assert view_bytes[LEVEL:LEVEL + 0x300] == romfs
    assert view_bytes[LEVEL + 0x300:] == bytes(0x100)


def test_reads_in_small_pieces_across_block_edges_match_one_read():
    romfs = _pattern(0x300)
    raw_lz4 = _literals(romfs[0x100:0x300])
    entries = [(0, BLOCKS, 0, 0xFFFFFFFF), (0x100, BLOCKS + 0x100, 3, len(raw_lz4))]
    stored = _section(romfs[:0x100] + raw_lz4, entries, 0x300)
    view = _view(stored, _table_fsh(entries))

    whole = view.read(view.size)
    view.seek(0)
    pieces = b"".join(view.read(7) for _ in range(0, view.size, 7))

    assert pieces == whole
    assert whole[LEVEL:] == romfs


def test_a_damaged_block_is_an_image_error_when_it_is_read():
    raw_lz4 = bytes([0xF0, 0xFF, 0xFF, 0xFF])
    entries = [(0, BLOCKS, 0, 0xFFFFFFFF), (0x100, BLOCKS + 0x100, 3, len(raw_lz4))]
    stored = _section(bytes(0x100) + raw_lz4, entries, 0x200)
    view = _view(stored, _table_fsh(entries))

    view.seek(LEVEL + 0x100)
    with pytest.raises(ImageError):
        view.read(0x10)


def test_a_table_that_is_not_bktr_is_not_compressed():
    fsh = _table_fsh([(0, 0, 0, 0xFFFFFFFF)], magic=b"XXXX")

    assert not is_compressed(fsh)
    with pytest.raises(ImageError, match="no compression table"):
        _view(_section(bytes(0x100), [(0, 0, 0, 0xFFFFFFFF)], 0x100), fsh)


def test_an_unsorted_table_is_refused():
    entries = [(0, 0, 0, 0xFFFFFFFF), (0x200, 0x100, 0, 0xFFFFFFFF), (0x100, 0x100, 0, 0xFFFFFFFF)]
    with pytest.raises(ImageError, match="not sorted"):
        _view(_section(bytes(0x300), entries, 0x300), _table_fsh(entries))


def test_a_block_type_that_is_not_read_is_refused():
    entries = [(0, 0, 2, 0x10)]
    with pytest.raises(ImageError, match="compression type 2"):
        _view(_section(bytes(0x100), entries, 0x100), _table_fsh(entries))
