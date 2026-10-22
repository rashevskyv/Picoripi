"""Hades plugin: loads, validates, round-trips a file through the rules, and builds a LayeredFS mod (synthetic files)."""
from pathlib import Path

from plugins.hades import build
from plugins.hades.rules import EN_CSV, EN_SJSON, LANGUAGES
from plugins.hades.unpack import BASE_ID
from plugins.testing import check_loads, check_validator, load_rules

from .test_text import CSV, SJSON


def test_plugin_loads_and_validates():
    check_loads("hades")
    check_validator("hades")


def test_source_filter_keeps_english_text_and_subtitles_only():
    rules = load_rules("hades")
    assert rules.includes_source_file(EN_SJSON + "MiscText.en.sjson")
    assert rules.includes_source_file(LANGUAGES)
    assert rules.includes_source_file(EN_CSV + "Hades.csv")
    assert not rules.includes_source_file("Content/Game/Text/pl/MiscText.pl.sjson")
    assert not rules.includes_source_file("Content/Scripts/UIData.lua")


def test_sjson_file_round_trips_through_the_rules_unchanged():
    rules = load_rules("hades")
    blocks, names = rules.load_data_from_json_obj(SJSON)
    assert rules.save_data_to_json_obj(blocks, names) == SJSON


def test_csv_file_round_trips_through_the_rules_unchanged():
    rules = load_rules("hades")
    blocks, names = rules.load_data_from_json_obj(CSV)
    assert rules.save_data_to_json_obj(blocks, names) == CSV


def test_layeredfs_build_writes_changed_files_under_the_base_title(tmp_path: Path):
    source = tmp_path / "source" / "Content" / "Game" / "Text" / "en"
    source.mkdir(parents=True)
    (source / "MiscText.en.sjson").write_bytes(SJSON)
    translation = tmp_path / "translation" / "Content" / "Game" / "Text" / "en"
    translation.mkdir(parents=True)
    (translation / "MiscText.en.sjson").write_bytes(SJSON.replace(b"Stupid boy.", "Дурний.".encode("utf-8")))
    (translation / "Unchanged.sjson").write_bytes(SJSON)
    (tmp_path / "source" / "Content" / "Game" / "Text" / "en" / "Unchanged.sjson").write_bytes(SJSON)
    out = build.build_switch(str(tmp_path / "source"), str(tmp_path / "translation"), str(tmp_path / "out"),
                             lambda percent, text: None, lambda: False)
    romfs = Path(out) / "atmosphere" / "contents" / BASE_ID / "romfs" / "Content" / "Game" / "Text" / "en"
    assert (romfs / "MiscText.en.sjson").read_bytes().count("Дурний.".encode("utf-8")) == 1
    assert not (romfs / "Unchanged.sjson").exists()
