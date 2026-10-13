"""Wind Waker family on the real message folders: counts, the derived tag table, round trips, the project.

Skipped on a machine without the unpacked game. The counts are the ones the plan prints; a change here means the
recognition, the tag table or the link alignment changed.
"""
import json
import os
from pathlib import Path

import pytest

from plugins.common.msbt import Msbt
from plugins.zelda_ww import family as fam
from plugins.zelda_ww.family import command_project
from plugins.zelda_tww.rules import GameRules
from plugins.zelda_ww import family_tags as ft
from plugins.zelda_ww.tags import to_editor

GC_MSG = Path(os.environ.get("PICORIPI_ROMHACKING", "RomHacking"), "Zelda/Wind Waker/GC/source/files/res/Msg")
HD_MSG = Path(os.environ.get("PICORIPI_ROMHACKING", "RomHacking"), "Zelda/Wind Waker/HD - Wii U/source/Message")
needs_game = pytest.mark.skipif(not (GC_MSG.is_dir() and HD_MSG.is_dir()),
                                reason="the unpacked Wind Waker message folders are not on this machine")


@pytest.fixture(scope="module")
def scan():
    return fam.scan_family([str(GC_MSG), str(HD_MSG)])


@needs_game
def test_plan_counts(scan):
    assert scan.plan().base == "gc"
    assert [m.key for m in scan.plan().members] == ["gc", "hd"]
    assert fam.count_units(scan) == {"base": 4426, "HD only": 1608, "linked": 3432}


@needs_game
def test_committed_tag_table_is_the_derivation_of_the_real_files():
    gc_units, hd_units = ft._ids_from_folders(GC_MSG, HD_MSG)
    derived = ft.derive(ft.id_pairs(gc_units, hd_units))
    assert derived["gc_to_hd"] == ft.load_map()
    assert len(ft.load_map()) == 154


@needs_game
def test_every_gc_message_with_mapped_tags_round_trips(scan):
    tags = scan.tags
    checked = 0
    for unit in scan.base_units:
        hd_text, missing = ft.gc_to_hd(unit.text, tags)
        if missing:
            continue
        back, back_missing = ft.hd_to_gc(hd_text, tags)
        assert back == unit.text and not back_missing, unit.uid
        checked += 1
    assert checked >= 4300


@needs_game
def test_unedited_hd_files_are_written_back_byte_for_byte():
    for path in sorted(HD_MSG.glob("*.msbt")):
        raw = path.read_bytes()
        msbt = Msbt(raw)
        texts = [to_editor(tokens) for tokens in msbt.messages]
        assert GameRules._save_msbt(Msbt(raw), texts) == raw, path.name


@needs_game
def test_subset_keeps_labels_attributes_and_messages():
    path = max(HD_MSG.glob("*.msbt"), key=lambda p: len(Msbt(p.read_bytes()).messages))
    raw = path.read_bytes()
    original = Msbt(raw)
    subset = Msbt(original.subset(list(range(len(original.messages))), original.messages))
    assert subset.messages == original.messages
    assert subset.labels == original.labels
    assert subset.section(b"ATR1") == original.section(b"ATR1")
    assert subset.section(b"TSY1") == original.section(b"TSY1")
    picked = Msbt(original.subset([1], [original.messages[1]]))
    assert picked.messages == [original.messages[1]]
    assert picked.labels == {0: original.labels[1]}


@needs_game
def test_project_builds_twice_with_the_planned_counts(tmp_path):
    config = {
        "sources": [str(GC_MSG), str(HD_MSG)],
        "store": "family_translations.json",
        "family_project": {"name": "test", "dir": "picoripi", "source": "picoripi_source",
                           "translation": "picoripi_translation"},
    }
    first = command_project(config, tmp_path)
    blocks = len(json.loads((tmp_path / "picoripi" / "project.uiproj").read_text(encoding="utf-8"))["blocks"])
    second = command_project(config, tmp_path)
    assert first == second == {".extracted": 4426, "HD only": 1608}
    assert len(json.loads((tmp_path / "picoripi" / "project.uiproj").read_text(encoding="utf-8"))["blocks"]) == blocks


@needs_game
def test_an_edit_in_the_shared_text_reaches_the_hd_file_with_hd_tags(tmp_path):
    scan = fam.scan_family([str(GC_MSG), str(HD_MSG)])
    source, translation = tmp_path / "source", tmp_path / "translation"
    fam.build_sources(scan, source)
    fam._copy_missing_subsets(scan, source, translation)
    tagged = next(u for u in scan.base_units if "{escape:" in u.text and u.uid in
                  {gc for _hd, (_p, gc) in scan.links.items()})
    hd_uid = next(hd for hd, (_p, gc) in scan.links.items() if gc == tagged.uid)
    edited = tagged.text + " UA TEST"
    fam._write_gc_archives(scan, translation, {tagged.uid: edited})
    store, warnings = fam.pull(scan, {}, translation)
    assert not warnings
    out = tmp_path / "hd_out"
    fam.write_hd_output(scan, store, translation, out)
    hd_name, index = hd_uid.rsplit("#", 1)
    written = Msbt((out / hd_name).read_bytes())
    expected, _missing = ft.gc_to_hd(edited, scan.tags)
    assert to_editor(written.messages[int(index)]) == expected
