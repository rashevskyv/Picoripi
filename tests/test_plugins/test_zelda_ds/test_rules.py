"""Zelda DS plugin rules: a BMG file loads as its messages; saving writes back only the edited message."""
from plugins.zelda_ds.bmg import Bmg
from plugins.zelda_ds.rules import GameRules

from .test_bmg import make_bmg, utf16


def test_load_then_save_with_one_edit_changes_only_that_message():
    data = make_bmg([utf16("first"), utf16("second")], lead=b"\x00\x00")
    rules = GameRules()
    strings, _ = rules.load_data_from_json_obj(data)
    assert strings == [["first", "second"]]
    strings[0][1] = "second, edited"
    out = rules.save_data_to_json_obj(strings, {})
    assert Bmg(out).texts() == ["first", "second, edited"]


def test_save_without_edits_gives_the_file_back():
    data = make_bmg([utf16("only")])
    rules = GameRules()
    strings, _ = rules.load_data_from_json_obj(data)
    assert rules.save_data_to_json_obj(strings, {}) == data


def test_a_file_that_is_not_bmg_loads_as_no_texts():
    rules = GameRules()
    strings, _ = rules.load_data_from_json_obj(b"not a message file")
    assert strings == [[]]
