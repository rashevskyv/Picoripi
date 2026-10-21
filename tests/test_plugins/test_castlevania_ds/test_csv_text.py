"""Castlevania DS: the CSV text of a project, the font layouts of a translation and their use by the string bank.

Synthetic strings only: no game text and no ROM is read here.
"""
import json

import pytest

import romhacking_root
from plugins.castlevania_ds import codec, csv_text
from plugins.castlevania_ds.rules import TEXT_FORMAT
from plugins.testing import load_rules

PLUGIN = "castlevania_ds"
LAYOUT = "blackdragon_ua"
ROOT = romhacking_root.under("Castlevania")
WORKSPACES = {"dos": "Dawn of Sorrow", "por": "Portrait of Ruin", "ooe": "Order of Ecclesia"}


def test_csv_tags_become_the_game_codes():
    text = "{NAME 0x01}{PORTRAIT 0x08}\nHi{NEWCHAR}\\n\n{WAITINPUT}{SAMECHAR}\n{BUTTON Y}{ENDCHOICE 0x0005}[{CHOICE}"
    assert csv_text.from_csv(text) == bytes([0xE7, 0x01, 0xE3, 0x08, 0x28, 0x49, 0xE4, 0xE6, 0xE5, 0xE9, 0xF0,
                                             0xE1, 0x00, 0x05, 0x3B, 0xE2, 0x03])


def test_a_backslash_n_is_one_line_break_and_a_bare_newline_is_not_in_the_game():
    assert csv_text.from_csv("A\\n\nB") == bytes([0x21, 0xE6, 0x22])
    assert csv_text.from_csv("A\nB") == bytes([0x21, 0x22])


def test_the_layout_gives_its_letters_their_code_and_latin_look_alikes_too():
    assert csv_text.from_csv("А", LAYOUT) == bytes([0x21])
    assert csv_text.from_csv("A", LAYOUT) == bytes([0x21])
    assert codec.decode(bytes([0x21]), LAYOUT) == "А"
    assert codec.decode(bytes([0x21])) == "A"
    assert csv_text.from_csv("А") == bytes([codec.UA_SLOTS["А"]])     # without a layout: the codec's own cells


def test_the_three_new_cells_hold_the_letters_that_had_none():
    assert csv_text.from_csv("Ь", LAYOUT) == bytes([0x40])
    assert csv_text.from_csv("Ґ", LAYOUT) == bytes([0x68])
    assert csv_text.from_csv("ґ", LAYOUT) == bytes([0x3E])
    assert codec.decode(bytes([0x40, 0x68, 0x3E]), LAYOUT) == "ЬҐґ"
    assert csv_text.from_csv("ь", LAYOUT) != bytes([0x40])


def test_a_dash_without_a_glyph_has_its_fallback():
    assert csv_text.from_csv("—", LAYOUT) == csv_text.from_csv("-", LAYOUT)


def test_an_unknown_tag_is_an_error():
    with pytest.raises(csv_text.CsvError):
        csv_text.from_csv("{NO SUCH TAG}")


def test_rows_are_read_with_quotes_and_embedded_newlines(tmp_path):
    path = tmp_path / "rows.csv"
    path.write_bytes('0x10,"a, ""b""\nc"\n0x11,\n0x12,""\n'.encode("utf-8"))
    assert csv_text.read_rows([str(path)]) == {0x10: 'a, "b"\nc', 0x11: "", 0x12: ""}


def test_rows_replace_their_strings_and_the_rest_keep_their_bytes():
    bank = {"format": TEXT_FORMAT, "game": "dos", "regions": [["Names", 0, 2]],
            "strings": [bytes([0x21]).hex(), bytes([0x22]).hex(), bytes([0x23]).hex()]}
    out = csv_text.bank_from_rows({1: "Аб"}, bank, LAYOUT)
    assert out["strings"][0] == bytes([0x21]).hex() and out["strings"][2] == bytes([0x23]).hex()
    assert out["strings"][1] == csv_text.from_csv("Аб", LAYOUT).hex()
    assert out["layout"] == LAYOUT and bank.get("layout") is None
    with pytest.raises(csv_text.CsvError):
        csv_text.bank_from_rows({9: "x"}, bank, LAYOUT)


def test_a_translation_bank_with_a_layout_decodes_and_saves_with_it():
    strings = [bytes([0x21, 0x22]).hex(), bytes([0x23]).hex()]
    bank = {"format": TEXT_FORMAT, "game": "dos", "regions": [["Names", 0, 1]], "strings": strings, "layout": LAYOUT}
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(json.loads(json.dumps(bank)))
    assert blocks[0] == ["АВ", "С"]                                    # 21, 22 and 23 are letters in this layout
    blocks[0][1] = "Бб"
    saved = rules.save_data_to_json_obj(blocks, names)
    assert saved["layout"] == LAYOUT
    assert saved["strings"][1] == codec.encode("Бб", layout_name=LAYOUT).hex()
    assert saved["strings"][0] == strings[0]


def test_a_reference_bank_is_shown_by_block_and_string(tmp_path):
    winner = {"format": TEXT_FORMAT, "game": "dos", "regions": [["Names", 0, 1], ["Events", 2, 2]],
              "strings": [bytes([0x21]).hex(), bytes([0x40]).hex(), bytes([0x23]).hex()], "layout": LAYOUT}
    rules = load_rules(PLUGIN)
    rules.load_data_from_json_obj(winner)
    folder = tmp_path / "UA_CSV"
    folder.mkdir()
    reference = {**winner, "strings": [bytes([0x22]).hex(), bytes([0x40]).hex(), bytes([0x21]).hex()]}
    (folder / "strings.cvdstext").write_text(json.dumps(reference), encoding="utf-8")
    assert rules.supports_reference_patch() is True
    assert rules.get_reference_language_label() == "UA CSV"
    assert rules.load_reference_patch(str(folder)) == {(0, 0): "В", (0, 1): "Ь", (1, 0): "А"}
    short = tmp_path / "short.cvdstext"
    short.write_text(json.dumps({**reference, "strings": [bytes([0x22]).hex()]}), encoding="utf-8")
    assert rules.load_reference_patch(str(short)) == {}


# -- real data ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("key", list(WORKSPACES))
def test_the_ukrainian_translation_round_trips_through_its_layout(key):
    path = ROOT / WORKSPACES[key] / "translation" / key / "strings.cvdstext"
    if not path.is_file():
        pytest.skip(f"{key} translation not on disk")
    bank = json.loads(path.read_text(encoding="utf-8"))
    assert bank["layout"] == LAYOUT
    for raw in bank["strings"]:
        data = bytes.fromhex(raw)
        assert codec.encode(codec.decode(data, LAYOUT), layout_name=LAYOUT) == data
