"""Silent Hill 3 (PC) ``.arc`` archives: layout, rebuild and the name catalog.

The real-data tests read the game's ``data`` folder and skip when the game is not installed here.
"""
import gzip
import struct
from pathlib import Path

import pytest

from core.containers import sh3_arc

DATA = Path(r"E:\Emulators\RomHacking\Silent Hill\Silent Hill 3\PC\ISO\data")
needs_game = pytest.mark.skipif(not (DATA / "msg.arc").is_file(), reason="Silent Hill 3 data not installed here")


def make_archive(entries, info=b"\x11\x22\x33\x44" * 3) -> bytes:
    count = len(entries)
    start = 0x10 + 16 * count + len(info)
    head = struct.pack("<4I", sh3_arc.MAGIC, count, len(info), 0)
    table = b""
    body = b""
    cursor = start
    for slot, raw in enumerate(entries):
        table += struct.pack("<4I", cursor, 0x100 + 4 * slot, len(raw), len(raw))
        body += raw
        cursor += len(raw)
    return head + table + info + body


def test_parse_and_rebuild_round_trip():
    data = make_archive([b"alpha", b"", b"gamma!!"])
    info_size, entries = sh3_arc.parse(data)
    assert info_size == 12
    assert [sh3_arc.entry_bytes(data, e) for e in entries] == [b"alpha", b"", b"gamma!!"]
    assert sh3_arc.rebuild(data, {}) == data


def test_rebuild_replaces_an_entry_and_keeps_the_info_block():
    data = make_archive([b"one", b"two", b"three"])
    out = sh3_arc.rebuild(data, {1: b"TWO-LONGER"})
    info_size, entries = sh3_arc.parse(out)
    assert info_size == 12
    assert [sh3_arc.entry_bytes(out, e) for e in entries] == [b"one", b"TWO-LONGER", b"three"]
    assert out[0x10 + 16 * 3:0x10 + 16 * 3 + 12] == b"\x11\x22\x33\x44" * 3


def test_parse_rejects_a_bad_magic():
    with pytest.raises(sh3_arc.ArcError):
        sh3_arc.parse(b"\0" * 32)


def test_catalog_maps_every_archive_to_its_names():
    catalog = sh3_arc.parse_catalog(gzip.compress(_catalog_sample()))
    assert catalog["msg"] == [(0, "data/msg/a_eng_msg.mes"), (1, "data/msg/b_jpn_msg.mes")]


def _catalog_sample() -> bytes:
    """A two-group catalog with the same record layout as the game's arc.arc."""
    def record(tag, index, name):
        raw = struct.pack("<HHI", tag, 0, index) + name + b"\0"
        size = (len(raw) + 3) & ~3
        return struct.pack("<HHI", tag, size, index) + name + b"\0" + bytes(size - 8 - len(name) - 1)

    def group(ext, count):
        raw = ext + b"\0"
        size = 8 + ((len(raw) + 3) & ~3)
        return struct.pack("<HHI", 2, size, count) + raw + bytes(size - 8 - len(raw))

    body = group(b"msg", 2) + record(3, 0, b"data/msg/a_eng_msg.mes") + record(3, 1, b"data/msg/b_jpn_msg.mes")
    head = struct.pack("<4I", sh3_arc.CATALOG_MAGIC, 0, 0, 0)
    return head + body


@needs_game
def test_msg_archive_layout_is_the_documented_one():
    data = (DATA / "msg.arc").read_bytes()
    info_size, entries = sh3_arc.parse(data)
    assert len(entries) == 371
    assert info_size == 0x618


@needs_game
def test_msg_archive_rebuilds_byte_for_byte():
    data = (DATA / "msg.arc").read_bytes()
    assert sh3_arc.rebuild(data, {}) == data


@needs_game
def test_catalog_names_match_the_archive_counts():
    catalog = sh3_arc.parse_catalog((DATA / "arc.arc").read_bytes())
    counts = {"tex": 69, "msg": 371, "pic": 305, "sdb": 40}
    for ext, count in counts.items():
        assert len(catalog[ext]) == count
    assert all(name.endswith(".mes") for _, name in catalog["msg"][:368] if "_msg" in name)
