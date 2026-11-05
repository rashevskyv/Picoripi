"""STAGE.DAT: the header, the stage index, packed groups, and writing a stage again."""
import zlib

import pytest

from plugins.zoe2_ps2 import scx, stagedat as sd

from .helpers import SECTOR, make_dat, make_scx, make_stage


def _dat():
    script_a = make_scx([b"Save game.", b"Yes"])
    script_b = make_scx([b"Hand over Jehuty!"])
    a = make_stage("ca01", [("cache", [("mdz", b"model" * 30), ("scx", script_a), ("tex", bytes(range(256)) * 4)]),
                            ("sound", [b"s" * 3000])])
    b = make_stage("af01", [("cache", [("scx", script_b)])])
    return make_dat({"ca01": a, "af01": b}), script_a, script_b


def _reader(data):
    return lambda offset, count: data[offset:offset + count]


def test_the_header_and_stage_list_decode():
    dat, _a, _b = _dat()
    toc = sd.read_toc(_reader(dat))
    assert [name for name, _s in toc.stages] == ["ca01", "af01"] and toc.game == sd.GAME_ID


def test_a_stage_reads_its_groups_and_members():
    dat, script_a, _b = _dat()
    read = _reader(dat)
    toc = sd.read_toc(read)
    stage = sd.parse_stage(read, toc, *toc.stages[0])
    assert [g.plain for g in stage.groups] == [False, True]
    cache = stage.groups[0]
    member = [m for m in cache.members if m.ext == sd.str_code32("scx")][0]
    assert member.hash == sd.str_code32("ca01.scx")
    assert sd.member_bytes(read, stage, cache, member) == script_a
    assert sd.group_data(read, stage, stage.groups[1]) == b"s" * 3000


def test_a_stage_without_changes_is_written_back_byte_for_byte():
    dat, _a, _b = _dat()
    read = _reader(dat)
    toc = sd.read_toc(read)
    for name, sector in toc.stages:
        stage = sd.parse_stage(read, toc, name, sector)
        stored = sd.stage_bytes(read, toc, stage, {})
        assert stored == dat[sector * SECTOR:sector * SECTOR + len(stored)]


def test_a_changed_script_is_packed_again_and_the_other_files_stay():
    dat, _a, _b = _dat()
    read = _reader(dat)
    toc = sd.read_toc(read)
    stage = sd.parse_stage(read, toc, *toc.stages[0])
    parts = sd.split_members(sd.group_data(read, stage, stage.groups[0]), stage.groups[0])
    texts = scx.read_texts(parts[1])
    texts[0] = "Save the game now, please, and come back later."
    parts[1], _problems = scx.write_texts(parts[1], texts)
    new = sd.stage_bytes(read, toc, stage, {0: parts})
    assert len(new) % SECTOR == 0
    read2 = _reader(new)
    stage2 = sd.parse_stage(read2, toc, "ca01", 0)
    parts2 = sd.split_members(sd.group_data(read2, stage2, stage2.groups[0]), stage2.groups[0])
    assert scx.read_texts(parts2[1]) == texts
    assert parts2[0] == parts[0] and parts2[2] == parts[2]
    assert sd.group_data(read2, stage2, stage2.groups[1]) == b"s" * 3000


def test_the_group_key_round_trips_for_any_stream():
    stream = sd.ZLIB_HEAD + zlib.compress(b"x" * 1000)[2:]
    assert zlib.decompress(sd.decode_blob(sd.encode_blob(stream, 0xABCD))[:len(stream)]) == b"x" * 1000


def test_a_file_of_another_game_is_refused():
    with pytest.raises(sd.DatError):
        sd.read_toc(_reader(b"\x00" * 64))
