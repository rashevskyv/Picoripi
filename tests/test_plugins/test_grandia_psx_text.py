"""Grandia PS1 text, read side (plugins/grandia/psx_text.py): battle record chains and dialogue runs on synthetic bytes,
and the owner's disc 1 battle file when present."""
import os

import pytest

from plugins.grandia import psx_text

REAL_IMG = r"D:\RomHacking_tmp\grandia-ps1\psx\disc1\Grandia disc 1.img"


def chain(names):
    return b"".join(name.encode("latin-1") + b"\x00\x03" for name in names)


def test_battle_chain_reads_every_record_in_order():
    names = ["Party"] + [f"Skill{i}" for i in range(14)]
    data = b"\x11" * 40 + b"\x03" + chain(names) + b"\x22" * 20
    records = psx_text.battle_records(data)
    assert [text.decode("latin-1") for _, text in records] == names
    assert psx_text.is_ps1_text(data)


def test_short_chain_is_not_battle_text():
    data = chain(["Attack", "Magic", "Items"])
    assert psx_text.battle_records(data) == []
    assert not psx_text.is_ps1_text(data)


def test_chain_breaks_at_a_gap_and_keeps_the_longer_side():
    names = [f"Name{i}" for i in range(18)]
    data = chain(names[:13]) + b"\x01\x01\x01" + chain(names[13:])
    records = psx_text.battle_records(data)
    assert len(records) == 13 and records[0][1] == b"Name0"


def test_dialogue_runs_stop_at_control_bytes():
    data = b"\x30\x7e She's really popular.\x01Hey, c'mon,\x07\x02\x0e Hi"
    texts = [text for _, text in psx_text.dialogue_runs(data)]
    assert texts == [b"0~ She's really popular.", b"Hey, c'mon,"]


def test_blocks_prefer_battle_chain_then_runs():
    battle = chain([f"Item{i}" for i in range(13)])
    texts, names = psx_text.blocks(battle)
    assert texts[0] == "Item0" and len(texts) == 13
    assert len(names) == 13
    texts2, _ = psx_text.blocks(b"\x01 Hello there, Justin.\x02")
    assert texts2 == [" Hello there, Justin."]


@pytest.mark.skipif(not os.path.exists(REAL_IMG), reason="the owner's Grandia disc 1 is not on disk")
def test_real_battle_file_has_the_party_chain():
    from core.containers.psx_disc import open_psx

    image = open_psx(REAL_IMG.replace(".img", ".cue"))
    entry = {f.path: f for f in image.files()}["BATLE/B001.BBG"]
    data = image.read_file(entry)
    records = psx_text.battle_records(data)
    texts = [text for _, text in records]
    assert b"Party" in texts and b"Justin" in texts and b"Magic" in texts
    assert b"Magic" in [text for _, text in records]
    image.stream.close()


def test_plugin_identifies_a_psx_cue_as_base(tmp_path):
    from plugins.grandia.rules import GameRules
    from test_core.test_psx_disc import make_disc

    cue = make_disc(tmp_path)
    assert GameRules().identify_source(cue) == {"role": "base", "platform": "psx"}
    assert {p["id"] for p in GameRules().get_platforms()} == {"gdrom", "psx"}
