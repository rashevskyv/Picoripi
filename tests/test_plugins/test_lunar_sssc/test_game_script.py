"""Lunar game script: parsing, alignment to messages and the runtime helpers. Synthetic fixture only, no game text."""
from pathlib import Path

from core.i18n import tr
from plugins.lunar_sssc import game_script as gs

TRANSCRIPT = """Capture noise before the first scene.

01) MARKET [GS01]
[A bell rings.]
Ann: Welcome to the market, traveller. Buy something today.
Ben: The bread here is fresh every morning.

02) HARBOR [GS02]
Ann: Welcome to the market, traveller. Buy something today.
Cal: The ship leaves at dawn, so hurry along now.
"""

MESSAGES = [
    ("TEXT001/0/0", "{FA:01}Welcome to the market, traveller.{page}Buy something today."),
    ("TEXT001/0/1", "The bread here is fresh every morning."),
    ("TEXT001/0/2", "The ship leaves at dawn, so hurry along, now."),
    ("TEXT001/0/3", "Nothing in this fixture resembles the script at all."),
    ("TEXT001/0/4", "Yes."),
    ("TEXT001/0/5", "The bread here is fresh every morning.{page}A line no speech contains anywhere."),
]


def _index():
    scenes, lines = gs.parse(TRANSCRIPT)
    index, counts = gs.align(scenes, lines, MESSAGES)
    return index, counts, scenes


def test_parse_scenes_directions_and_speakers():
    scenes, lines = gs.parse(TRANSCRIPT)
    assert scenes["GS01"]["place"] == "Market"
    assert scenes["GS02"]["title"] == "Harbor"
    assert scenes["GS01"]["lines"] == 3
    assert scenes["GS01"]["speakers"] == ["Ann", "Ben"]
    assert lines[0].kind == "direction" and lines[0].pos == 1
    assert lines[2].speaker == "Ben" and lines[2].pos == 3


def test_parse_joins_continuation_lines_and_drops_asides():
    scenes, lines = gs.parse("01) VILLAGE [GS01]\nAnn: (sigh) First part\n      second part.\n")
    assert lines[0].speaker == "Ann"
    assert lines[0].text == "First part second part."


def test_align_places_exact_fuzzy_and_reports_the_rest():
    index, counts, _ = _index()
    assert index["strings"]["TEXT001/0/1"] == ["GS01", 3, "Ben"]
    assert index["strings"]["TEXT001/0/2"] == ["GS02", 2, "Cal"]
    assert "TEXT001/0/0" not in index["strings"]          # the same text in two scenes: ambiguous, left out
    assert "TEXT001/0/3" not in index["strings"]
    assert "TEXT001/0/4" not in index["strings"]          # too short to place
    assert index["strings"]["TEXT001/0/5"][0] == "GS01"   # first page matches, second does not: partial
    assert counts["placed"] == 2
    assert counts["partial"] == 1
    assert counts["ambiguous"] == 1
    # "Yes." has no key of its own, but it sits in runs with its neighbours, so it is unplaced, not too short
    assert counts["unplaced"] == 2
    assert counts["too_short"] == 0


def test_runtime_helpers_describe_and_outline_a_placed_message():
    index, _counts, _ = _index()
    found = gs.scene_of(index, "TEXT001/0/1")
    assert found["place"] == "Market"
    assert "Scene GS01 at Market, line 3 of 3" in gs.describe(found)
    assert "GS01 Market" in gs.outline(index, ["GS01"])
    assert gs.scene_of(index, "TEXT001/0/3") is None


def test_folder_nodes_group_by_place_and_keep_unplaced_messages():
    index, _counts, _ = _index()
    nodes = gs.folder_nodes(index, "TEXT001/0", 6, 7)
    assert nodes[0]["title"] == "Market"
    assert nodes[0]["children"][0]["title"] == "GS01 Market"
    assert (7, 1) in nodes[0]["children"][0]["rows"]
    tail = nodes[-1]
    assert tail["title"] == tr("Not placed in the script")
    assert (7, 3) in tail["rows"] and (7, 0) in tail["rows"]


def test_load_index_degrades_to_empty(tmp_path: Path):
    assert gs.load_index(tmp_path / "missing.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert gs.load_index(bad) == {}
