"""The default tag aliases of the BDSP plugin: unique, real tags, and round trips on real .bdmsg tables."""
import json
import romhacking_root
from pathlib import Path

import pytest

from plugins.pokemon_bdsp import msg
from plugins.testing import load_rules

CONFIG = Path(__file__).parents[3] / "plugins" / "pokemon_bdsp" / "config.json"
MESSAGES = romhacking_root.under('Pokemon') / "Brilliant Diamond and Shining Pearl" / "source" / "message"


class FakeMainWindow:
    """The one attribute the alias code reads from the main window."""

    def __init__(self, mappings):
        self.default_tag_mappings = mappings


def _table():
    return json.loads(CONFIG.read_text(encoding="utf-8"))["default_tag_mappings"]  # alias -> raw tag


def test_aliases_are_unique_and_name_real_tags():
    table = _table()
    assert table and len(set(table.values())) == len(table)
    for alias, raw in table.items():
        assert msg.TAG_RE.fullmatch(raw), raw
        assert alias.startswith("[") and alias.endswith("]"), alias


def test_alias_and_tag_round_trip_on_a_sample():
    rules = load_rules("pokemon_bdsp", FakeMainWindow(_table()))
    text = "{tag:10:1:0}’s {tag:0:1:1} used Pound!{scroll}\n<color=#F01E1EFF>A critical hit</color>{clear}"
    aliased = rules.replace_tags_with_aliases(text)
    assert aliased == "[TRAINER]’s [POKEMON2] used Pound![SCROLL]\n[COLOR1]A critical hit[/COLOR][PAGE]"
    assert rules.replace_aliases_with_tags(aliased) == text


def test_alias_round_trip_on_real_labels():
    if not MESSAGES.is_dir():
        pytest.skip("the game's unpacked messages are not on disk")
    rules = load_rules("pokemon_bdsp", FakeMainWindow(_table()))
    checked = 0
    for path in sorted(MESSAGES.rglob("*.bdmsg"))[:60]:
        _table_json, _indices, texts = msg.load_table(path.read_bytes())
        for text in texts:
            assert rules.replace_aliases_with_tags(rules.replace_tags_with_aliases(text)) == text
            checked += 1
    assert checked > 500
