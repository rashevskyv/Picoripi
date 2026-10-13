"""Pokémon generation IV (pret decompilations pokediamond, pokeplatinum, pokeheartgold): the GMM and JSON message
sources, show and write back in place; real-data round trips of the workspaces."""
import romhacking_root
import json
from types import SimpleNamespace

import pytest

from plugins.pokemon_gen4 import ds_text
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "pokemon_gen4"
GMM = (
    '<?xml version="1.0"?>\n<body language="English">\n'
    '\t<row id="narc_0000_00000" index="0">\n\t\t<attribute name="window_context_name">used</attribute>\n'
    '\t\t<language name="English">The wild {STRVAR_1 1, 0} used\\nPound!\\r</language>\n\t</row>\n'
    '\t<row id="narc_0000_00001" index="1">\n'
    '\t\t<language name="English">Tom &amp; Jerry\\fNext</language>\n'
    '\t\t<language name="日本語">ほげ</language>\n\t</row>\n</body>\n'
)
PLATINUM = (
    '{\n  "key": 9291,\n  "messages": [\n'
    '    {\n      "id": "AcuityCavern_Text_UxieCry",\n      "en_US": "Kyouuuun!\\r"\n    },\n'
    '    {\n      "id": "AcuityCavern_Text_UxieDisappeared",\n      "en_US": [\n'
    '        "UXIE disappeared deep into its\\n",\n        "cavern..."\n      ]\n    }\n  ]\n}\n'
)


def test_the_plugin_loads_and_validates():
    check_loads(PLUGIN)
    check_validator(PLUGIN)


def test_gmm_rows_show_their_english_text_with_tags():
    assert ds_text.load(GMM) == ["The wild {STRVAR_1 1, 0} used\nPound!{\\r}", "Tom & Jerry{\\f}Next"]


def test_json_messages_join_their_list_items():
    assert ds_text.load(PLATINUM) == ["Kyouuuun!{\\r}", "UXIE disappeared deep into its\ncavern..."]


@pytest.mark.parametrize("text", [GMM, PLATINUM])
def test_an_unchanged_file_is_written_back_as_it_was(text):
    assert ds_text.write(text, ds_text.load(text)) == text
    check_round_trip(PLUGIN, text)


def test_a_changed_gmm_row_is_replaced_in_place():
    new = ds_text.write(GMM, [None, "Том & Джері{\\f}Далі\nще"])
    assert "Том &amp; Джері\\fДалі\\nще</language>" in new and "The wild {STRVAR_1 1, 0} used" in new
    assert "ほげ" in new and ds_text.load(new)[1] == "Том & Джері{\\f}Далі\nще"


def test_a_changed_json_message_keeps_its_shape_and_the_file_stays_valid():
    new = ds_text.write(PLATINUM, ["Кьююн!{\\r}", "УКСІ зник у глибині\nпечери..."])
    data = json.loads(new)
    assert data["messages"][0]["en_US"] == "Кьююн!\r"
    assert data["messages"][1]["en_US"] == ["УКСІ зник у глибині\n", "печери..."]
    assert data["key"] == 9291 and '"id": "AcuityCavern_Text_UxieCry"' in new


def test_the_plugin_saves_from_the_source_file():
    rules = load_rules(PLUGIN, SimpleNamespace())
    blocks, names = rules.load_data_from_json_obj(GMM)
    blocks[0][0] = "Дикий {STRVAR_1 1, 0}"
    rules.prepare_save_context(SimpleNamespace(existing_versions=lambda: iter([GMM.encode()])))
    assert "Дикий {STRVAR_1 1, 0}</language>" in rules.save_data_to_json_obj(blocks, names)


WORKSPACES = {"Diamond and Pearl": "files/msgdata/msg", "HeartGold and SoulSilver": "files/msgdata/msg",
              "Platinum": "res/text"}


@pytest.mark.parametrize("game", list(WORKSPACES))
def test_every_message_source_of_the_decompilation_writes_back_and_edits_cleanly(game):
    root = romhacking_root.under('Pokemon') / game / "source" / WORKSPACES[game]
    if not root.is_dir():
        pytest.skip(f"{root} is not on this machine")
    count = 0
    for path in sorted(root.iterdir()):
        text = path.read_bytes().decode("utf-8")
        units = ds_text.load(text)
        if not units:
            continue
        count += 1
        assert ds_text.write(text, units) == text, path.name
        edited = [u + "x" for u in units]
        assert ds_text.load(ds_text.write(text, edited)) == edited, path.name
    assert count > 100
