"""Pokémon tag aliases (``default_tag_mappings`` in each plugin's config.json).

Every alias restores to a raw tag, the game's own codec encodes and decodes that text unchanged, and the alias passes
the plugin's tag checker. The real-data test reads the workspace and skips without it: every raw tag of the table
must occur in the text of at least one game of that plugin.
"""
import importlib
import json
import re
from pathlib import Path

import pytest

import romhacking_root
from core.translation.placeholder_manager import AIPlaceholderManager
from plugins.common import gen4msg, gen5msg, gfmsg
from plugins.pokemon_md_3ds import message

PLUGINS_DIR = Path(__file__).resolve().parents[3] / "plugins"
CHARMAP = PLUGINS_DIR / "pokemon_gen4" / "charmaps" / "charmap_dp_hgss.txt"
TAG = re.compile(r"\{[^{}\n]*\}|\[[^\[\]\n]*\]")


def _gen4(text: str) -> str:
    codec = gen4msg.Codec(str(CHARMAP))
    return codec.decode_line(codec.encode_line(text))


def _gen5(text: str) -> str:
    return gen5msg.to_editor(gen5msg.from_editor(text))


def _gfm(text: str) -> str:
    return gfmsg.to_editor(gfmsg.from_editor(text))


def _md(text: str) -> str:
    return message.decode(message.encode(text, "gti"), "gti")


ROUND_TRIP = {
    "pokemon_gen4": _gen4,
    "pokemon_gen5": _gen5,
    "pokemon_gen6": _gfm,
    "pokemon_gen7": _gfm,
    "pokemon_md_3ds": _md,
}

# The workspace games of each plugin (project folder names under the Pokemon root).
GAMES = {
    "pokemon_gen4": ["Platinum", "Diamond and Pearl", "HeartGold and SoulSilver"],
    "pokemon_gen5": ["Black and White", "Black 2 and White 2"],
    "pokemon_gen6": ["X and Y", "Omega Ruby and Alpha Sapphire"],
    "pokemon_gen7": ["Sun and Moon", "Ultra Sun and Ultra Moon"],
    "pokemon_md_3ds": ["Mystery Dungeon Gates to Infinity", "Super Mystery Dungeon"],
}


def _table(plugin: str) -> dict:
    return json.loads((PLUGINS_DIR / plugin / "config.json").read_text(encoding="utf-8"))["default_tag_mappings"]


@pytest.mark.parametrize("plugin", sorted(ROUND_TRIP))
def test_every_alias_restores_and_round_trips_through_the_codec(plugin):
    table = _table(plugin)
    assert table, "the plugin ships no default tag aliases"
    for alias, raw in table.items():
        assert alias != raw
        restored = AIPlaceholderManager().restore_placeholders(f"x {alias} y", None, default_tag_mappings=table)
        assert restored == f"x {raw} y", alias
        assert ROUND_TRIP[plugin](restored) == restored, alias


@pytest.mark.parametrize("plugin", sorted(ROUND_TRIP))
def test_every_alias_is_a_legitimate_tag_for_the_plugin(plugin):
    tag_manager = importlib.import_module(f"plugins.{plugin}.tag_manager").TagManager(None)
    for alias in _table(plugin):
        assert tag_manager.is_tag_legitimate(alias), alias


@pytest.mark.parametrize("plugin", sorted(GAMES))
def test_every_raw_tag_of_the_table_occurs_in_the_real_game_text(plugin):
    table = _table(plugin)
    seen = set()
    rules = importlib.import_module(f"plugins.{plugin}.rules").GameRules(None)
    for game in GAMES[plugin]:
        project = romhacking_root.missing("Pokemon", game, "picoripi", "project.uiproj")
        if project:
            continue
        source = romhacking_root.path("Pokemon", game, "source")
        data = json.loads(romhacking_root.path("Pokemon", game, "picoripi", "project.uiproj").read_text(encoding="utf-8"))
        for block in data["blocks"]:
            path = source / block["source_file"].replace("\\", "/")
            if not path.is_file():
                continue
            blocks, _names = rules.load_data_from_json_obj(path.read_bytes())
            for text in (blocks[0] if blocks else []):
                seen.update(TAG.findall(text or ""))
    if not seen:
        pytest.skip("no Pokemon workspace on disk for " + plugin)
    missing = [raw for raw in table.values() if raw not in seen]
    assert not missing, missing
