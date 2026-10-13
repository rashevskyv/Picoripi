"""Donkey Kong Country: Tropical Freeze on the user's own files (skipped without them): every English (USEN)
message table of the three text packages saves back byte for byte, and an edited message reads back."""
from pathlib import Path

import pytest

import romhacking_root

from plugins.donkey_kong_tropical_freeze.rules import GameRules

WS = romhacking_root.under("Donkey Kong/Donkey Kong Country Tropical Freeze/Switch")


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def test_every_english_table_saves_back_byte_for_byte():
    files = sorted(_need(WS / "source" / "text").glob("*.msbt"))
    assert len(files) == 6
    for path in files:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, names) == raw, path.name


def test_an_edited_message_reads_back():
    path = _need(WS / "source" / "text" / "MiscData__universe.msbt")
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(path.read_bytes())
    blocks[0][0] = "UA TEST"
    again = GameRules()
    assert again.load_data_from_json_obj(rules.save_data_to_json_obj(blocks, names))[0][0][0] == "UA TEST"
