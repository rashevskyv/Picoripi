"""AFS archives (core/containers/afs.py): synthetic archives for the layout and the refusals, plus the owner's
Grandia II disc when it is on disk (skipped otherwise). The real-disc test reads three archives through the GD-ROM
reader and checks that an unchanged archive comes back byte for byte and a grown entry reads back intact."""
import os
import struct

import pytest

from core.containers import afs
from core.containers.afs import AfsError
from core.containers.gdrom import GdRomImage, GdRomStream

REAL_CUE = r"E:\Emulators\RomHacking\Grandia\Grandia II\Dreamcast\ISO\Grandia II (USA).cue"


def make_afs(payloads, first=0x800, trailer=b""):
    """An AFS archive: the table, then every payload at a 0x800 boundary, then the optional trailer block."""
    count = len(payloads)
    out = bytearray(first)
    out[0:4] = b"AFS\x00"
    struct.pack_into("<I", out, 4, count)
    cursor = first
    for index, payload in enumerate(payloads):
        if payload:
            struct.pack_into("<II", out, 8 + 8 * index, cursor, len(payload))
            out.extend(b"\x00" * (cursor - len(out)))
            out.extend(payload)
            cursor = (cursor + len(payload) + 0x7FF) // 0x800 * 0x800
        else:
            struct.pack_into("<II", out, 8 + 8 * index, 0, 0)
    last_end = max((o + s for o, s in [struct.unpack_from("<II", out, 8 + 8 * i) for i in range(count)]), default=first)
    trailer_pair = (last_end, len(trailer)) if trailer else (0, 0)
    struct.pack_into("<II", out, 8 + 8 * count, *trailer_pair)
    out.extend(trailer)
    out.extend(b"\x00" * ((-len(out)) % 0x800))
    return bytes(out)


def test_parse_lists_entries_in_table_order_with_their_offsets():
    data = make_afs([b"alpha", b"", b"gamma-gamma"])
    entries = afs.parse(data)
    assert [(e.index, e.size) for e in entries] == [(0, 5), (1, 0), (2, 11)]
    assert entries[2].offset == 0x800 + 0x800
    assert entries[2].name == "0002"
    assert data[entries[0].offset:entries[0].offset + 5] == b"alpha"


def test_unchanged_archive_comes_back_byte_for_byte_with_a_trailer():
    data = make_afs([b"a" * 300, b"b" * 2100], trailer=b"TRAILER-BLOCK")
    assert afs.write(data, {}) == data


def test_a_grown_entry_moves_the_entries_behind_it_and_keeps_their_bytes():
    data = make_afs([b"a" * 300, b"b" * 2100, b"c" * 40])
    out = afs.write(data, {0: b"a" * 5000})
    entries = afs.parse(out)
    assert entries[0].size == 5000
    assert out[entries[0].offset:entries[0].offset + 5000] == b"a" * 5000
    assert out[entries[1].offset:entries[1].offset + 2100] == b"b" * 2100
    assert out[entries[2].offset:entries[2].offset + 40] == b"c" * 40
    assert entries[1].offset % 0x800 == 0 and entries[2].offset % 0x800 == 0
    assert len(out) % 0x800 == 0


def test_a_shrunk_entry_keeps_the_archive_on_its_boundaries():
    data = make_afs([b"a" * 5000, b"b" * 10])
    out = afs.write(data, {0: b"x"})
    entries = afs.parse(out)
    assert entries[0].size == 1
    assert out[entries[1].offset:entries[1].offset + 10] == b"b" * 10
    assert len(out) % 0x800 == 0


def test_an_empty_entry_past_the_new_end_is_moved_to_the_end():
    data = bytearray(make_afs([b"a" * 5000, b""]))
    struct.pack_into("<II", data, 8 + 8, 0x2000, 0)   # the empty entry points at the old end of the first
    out = afs.write(bytes(data), {0: b"x"})
    entries = afs.parse(out)
    assert entries[0].size == 1
    assert entries[1].size == 0 and entries[1].offset <= len(out)


def test_the_trailer_block_follows_the_last_entry_when_that_entry_grows():
    trailer = bytes(range(64))
    data = make_afs([b"a" * 100, b"b" * 100], trailer=trailer)
    out = afs.write(data, {1: b"b" * 3000})
    entries = afs.parse(out)
    last_end = entries[1].offset + entries[1].size
    count = len(entries)
    trailer_offset, trailer_size = struct.unpack_from("<II", out, 8 + 8 * count)
    assert trailer_offset == last_end
    assert trailer_size == len(trailer)
    assert out[trailer_offset:trailer_offset + trailer_size] == trailer


def test_an_empty_entry_cannot_be_filled():
    data = make_afs([b"a" * 10, b""])
    with pytest.raises(AfsError):
        afs.write(data, {1: b"x"})


def test_an_index_outside_the_table_is_refused():
    data = make_afs([b"a" * 10])
    with pytest.raises(AfsError):
        afs.write(data, {3: b"x"})


def test_a_file_that_is_not_afs_is_refused():
    with pytest.raises(AfsError):
        afs.parse(b"CRI\x00" + b"\x00" * 2044)


def test_a_table_that_runs_past_the_file_is_refused():
    data = struct.pack("<4sI", b"AFS\x00", 4000) + b"\x00" * 16
    with pytest.raises(AfsError):
        afs.parse(data)


def test_an_entry_that_runs_past_the_file_is_refused():
    data = bytearray(make_afs([b"a" * 10]))
    struct.pack_into("<II", data, 8, 0x800, 0x100000)
    with pytest.raises(AfsError):
        afs.parse(bytes(data))


@pytest.mark.skipif(not os.path.isfile(REAL_CUE), reason="the owner's Grandia II image is not on disk")
def test_real_grandia_archives_round_trip_and_take_a_longer_entry():
    stream = GdRomStream(REAL_CUE)
    try:
        img = GdRomImage(stream)
        by_path = {entry.path: entry for entry in img.entries()}
        for path in ("files/MAP/A000.AFS", "files/BTL/SYS.AFS", "files/MAP/MGRP_SEB.AFS"):
            data = img.read(by_path[path])
            assert afs.write(data, {}) == data, path
            entries = afs.parse(data)
            target = next(e for e in entries if e.size)
            payload = data[target.offset:target.offset + target.size] + b"UA"
            out = afs.write(data, {target.index: payload})
            new = afs.parse(out)
            assert out[new[target.index].offset:new[target.index].offset + new[target.index].size] == payload, path
            assert len(out) % 0x800 == 0, path
    finally:
        stream.close()
