"""The default tag aliases of the GFMSG Pokemon plugins: unique, real tags, and round trips on real strings."""
import json
import romhacking_root
from pathlib import Path

import pytest

from plugins.common import gfmsg
from plugins.testing import load_rules

PLUGIN_DIR = Path(__file__).parents[3] / "plugins"
PLUGINS = ("pokemon_nx", "pokemon_trinity")
SOURCES = {  # game -> (plugin, English message folder)
    "Sword and Shield": ("pokemon_nx", "bin/message/English"),
    "Legends Arceus": ("pokemon_nx", "bin/message/English"),
    "Scarlet and Violet": ("pokemon_trinity", "message/dat/English"),
    "Legends Z-A": ("pokemon_trinity", "ik_message/dat/English"),
}


class FakeMainWindow:
    """The one attribute the alias code reads from the main window."""

    def __init__(self, mappings):
        self.default_tag_mappings = mappings


def _table(plugin):
    return json.loads((PLUGIN_DIR / plugin / "config.json").read_text(encoding="utf-8"))["default_tag_mappings"]


@pytest.mark.parametrize("plugin", PLUGINS)
def test_aliases_are_unique_and_name_real_gfmsg_tags(plugin):
    table = _table(plugin)  # alias -> raw tag
    assert table and len(set(table.values())) == len(table)
    for alias, raw in table.items():
        assert gfmsg.TAG_RE.fullmatch(raw), raw
        assert alias.startswith("[") and alias.endswith("]"), alias


def test_both_gfmsg_plugins_share_one_table():
    assert _table("pokemon_nx") == _table("pokemon_trinity")


@pytest.mark.parametrize("plugin", PLUGINS)
def test_alias_and_tag_round_trip_on_a_sample(plugin):
    rules = load_rules(plugin, FakeMainWindow(_table(plugin)))
    text = "{VAR 0101 0000} learned {VAR 0107 0001}!{PAGE}\n{COLOR 0006}Lv. {VAR 0202 0000}{COLOR 0000}{SCROLL}[x]"
    aliased = rules.replace_tags_with_aliases(text)
    assert aliased == "[POKEMON] learned [MOVE]![PAGE]\n[COLOR6]Lv. [LEVEL][/COLOR][SCROLL][x]"
    assert rules.replace_aliases_with_tags(aliased) == text


@pytest.mark.parametrize("game", sorted(SOURCES))
def test_alias_round_trip_on_real_strings(game):
    plugin, sub = SOURCES[game]
    folder = romhacking_root.under('Pokemon') / game / "source" / sub
    if not folder.is_dir():
        pytest.skip("the game's unpacked text is not on disk")
    rules = load_rules(plugin, FakeMainWindow(_table(plugin)))
    checked = 0
    for dat in sorted(folder.rglob("*.dat"))[:40]:
        data = dat.read_bytes()
        if not gfmsg.is_gfmsg(data):
            continue
        for units, _flags in gfmsg.read(data):
            text = gfmsg.to_editor(units)
            assert rules.replace_aliases_with_tags(rules.replace_tags_with_aliases(text)) == text
            checked += 1
    assert checked > 100
