"""Metal Gear Solid Master Collection Bonus Content (plugin metal_gear_mc_bonus): real-data round trip.

The tests read the workspace's source folder (``1_unpack.bat``) and skip when it is missing.
"""
from __future__ import annotations


import pytest

import romhacking_root

from core import m2_psb
from plugins.metal_gear_mc_bonus.rules import GameRules
from plugins.metal_gear_solid_mc import psb_text

SOURCE = romhacking_root.under('Metal Gear\\Master Collection Bonus\\Switch\\source')
PSB_FILES = sorted((SOURCE / "vol1").rglob("*.psb")) + sorted((SOURCE / "vol2").rglob("*.psb")) if SOURCE.is_dir() else []

needs_data = pytest.mark.skipif(not PSB_FILES, reason="Bonus Switch source is not unpacked")


@needs_data
def test_every_text_psb_round_trips_byte_exact():
    checked = 0
    for path in PSB_FILES:
        data = path.read_bytes()
        root, psb = m2_psb.load(data)
        if psb.version not in (2, 3):
            continue                                  # fonts and pictures: read only
        assert m2_psb.dump(root, psb.chunks, psb.version, psb.names, psb.strings) == data, path.name
        checked += 1
    assert checked > 100


@needs_data
def test_rules_load_and_save_unchanged_file_byte_exact():
    path = SOURCE / "vol1" / "system" / "config" / "notice.psb"
    data = path.read_bytes()
    rules = GameRules()
    lines, names = rules.load_data_from_json_obj(data)
    assert lines[0], "no text lines in notice.psb"
    assert rules.save_data_to_json_obj(lines, names) == data


@needs_data
def test_edited_line_reads_back_and_keeps_line_count():
    path = SOURCE / "vol1" / "system" / "config" / "notice.psb"
    data = path.read_bytes()
    lines = psb_text.lines(data, words=True)
    texts = [None] * len(lines)
    texts[0] = "UA TEST"
    new = psb_text.build(data, texts, words=True)
    assert new != data
    after = psb_text.lines(new, words=True)
    assert after[0][1] == "UA TEST"
    assert len(after) == len(lines)
