"""Donkey Kong Country (SNES) plugin: text.json round trip, slot lengths and the real ROM text (when present)."""
import json
from pathlib import Path

from plugins.donkey_kong_country import rules as dkc_rules
from plugins.testing import check_loads, check_round_trip, check_validator

PLUGIN = "donkey_kong_country"
SOURCE = Path(r"E:\Emulators\RomHacking\Donkey Kong\Donkey Kong Country 1\Switch\source")
SOURCE_DKC2 = Path(r"E:\Emulators\RomHacking\Donkey Kong\Donkey Kong Country 2\Switch\source")
SOURCE_DKC3 = Path(r"E:\Emulators\RomHacking\Donkey Kong\Donkey Kong Country 3\Switch\source")
SAMPLE = json.dumps({"format": dkc_rules.FORMAT, "game": "test", "groups": [
    {"name": "Level and map names", "items": [
        {"id": "DKC1.0038A6D1", "rom": "0x38A6D1", "max_bytes": 17, "text": "Blackout Basement"}]},
    {"name": "Kong hint dialogue", "items": [
        {"id": "DKC1.002DE0BA", "rom": "0x2DE0BA", "max_bytes": 24, "text": "It's a mid point marker."}]}]},
    ensure_ascii=False, indent=1) + "\n"


def test_the_plugin_loads_round_trips_and_validates():
    check_loads(PLUGIN)
    check_round_trip(PLUGIN, SAMPLE)
    check_validator(PLUGIN)


def test_an_unchanged_save_is_the_same_file_and_texts_go_in_by_position():
    rules = check_loads(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    assert names == {"0": "Level and map names", "1": "Kong hint dialogue"}
    assert rules.save_data_to_json_obj(blocks, names) == SAMPLE
    saved = json.loads(rules.save_data_to_json_obj([["Jungle Hijinxs"], ["Hi!"]], names))
    assert saved["groups"][0]["items"][0] == {"id": "DKC1.0038A6D1", "rom": "0x38A6D1", "max_bytes": 17,
                                              "text": "Jungle Hijinxs"}
    assert saved["groups"][1]["items"][0]["text"] == "Hi!"


def test_the_real_text_file_round_trips_when_the_workspace_exists():
    text_file = SOURCE / "text.json"
    if not text_file.is_file():
        return
    content = text_file.read_text(encoding="utf-8")
    rules = check_loads(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(content)
    assert [len(block) for block in blocks] == [19, 79, 304, 135, 1049]
    assert rules.save_data_to_json_obj(blocks, names) == content


def test_the_dkc2_and_dkc3_text_files_round_trip_when_the_workspaces_exist():
    expected = {SOURCE_DKC2: [31, 52, 1787, 485, 296, 13], SOURCE_DKC3: [8, 40, 232, 30, 52]}
    for folder, counts in expected.items():
        text_file = folder / "text.json"
        if not text_file.is_file():
            continue
        content = text_file.read_text(encoding="utf-8")
        rules = check_loads(PLUGIN)
        blocks, names = rules.load_data_from_json_obj(content)
        assert [len(block) for block in blocks] == counts
        assert rules.save_data_to_json_obj(blocks, names) == content
