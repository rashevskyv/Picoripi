"""The Zone of the Enders: The 2nd Runner plugin: loading, the editor's text, the validator."""
from plugins.testing import check_loads, check_validator
from plugins.zoe2_ps2.rules import GameRules

from .helpers import make_scx

PLUGIN = "zoe2_ps2"


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_a_script_loads_as_one_block_and_saves_back_unchanged():
    data = make_scx([b"Save game.", b"Press the \x83\x02 button|now."])
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(data)
    assert blocks == [["Save game.", "Press the {83:02} button\nnow."]] and names == {"0": "script"}
    assert rules.save_data_to_json_obj(blocks, names) == data


def test_the_disc_is_declared_and_the_build_target_is_a_ps2_image():
    rules = GameRules()
    assert rules.get_supported_images()[0]["id"] == "SLUS-20545"
    assert rules.get_build_targets()[0]["platforms"] == ["ps2"]
    assert [p["id"] for p in rules.get_platforms()] == ["ps2"]
