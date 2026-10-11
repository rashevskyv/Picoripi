"""Layton Brothers: Mystery Room plugin: the exported strings of the Unity data files load and save in one shape."""
from plugins.testing import check_loads, check_validator


def test_plugin_loads_and_validates():
    check_loads("layton_mr")
    check_validator("layton_mr")


def test_strings_load_as_one_block_and_save_in_the_same_shape():
    rules = check_loads("layton_mr")
    exported = {"strings": ["[#ffffff]Exit the game?", "File No. %M_ID000%"]}
    blocks, _names = rules.load_data_from_json_obj(exported)
    assert blocks == [exported["strings"]]
    assert rules.save_data_to_json_obj([["[#ffffff]Exit?", "File No. %M_ID000%"]], {}) == {
        "strings": ["[#ffffff]Exit?", "File No. %M_ID000%"]}
