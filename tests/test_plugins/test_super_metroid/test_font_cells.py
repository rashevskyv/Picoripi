"""The plugin's font cell lists name the Ukrainian capitals drawn into the new cells (the editor shows them there)."""
import json
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "super_metroid" / "font_sources.json"


def _chars(label_prefix):
    descriptors = json.loads(PLUGIN.read_text(encoding="utf-8"))
    return next(d for d in descriptors if d["label"].startswith(label_prefix))["params"]["chars"]


def _cell16(tile):
    """A 16-column sheet: the cell index of a tile (the top tile of a big letter)."""
    return (tile // 32) * 16 + tile % 16


def test_big_menu_letters_sit_in_the_free_pairs():
    chars = _chars("File select, game over and options: big letters")
    for letter, top in zip("БГДЖЗИЙЛПУЦЧШЩЬЮЯ", [352 + i for i in range(8)] + [487 + i for i in range(9)]):
        assert chars[_cell16(top)] == letter


def test_credits_letters_and_apostrophe_sit_in_the_free_cells():
    small = _chars("Credits: job titles")
    for letter, tile in zip("ЄБГДЖЗИЙЛПУФЧЬЮЯ", [139, 140, 141, 142, 143, *range(155, 166)]):
        assert small[tile] == letter
    assert small[0xA6] == "'"
    big = _chars("Credits: names")
    for letter, top in {"П": 136, "Б": 137, "И": 138}.items():
        assert big[_cell16(top)] == letter
