import pytest
from unittest.mock import MagicMock
from plugins.base_game_rules import BaseGameRules

@pytest.fixture
def base_rules():
    mw = MagicMock()
    mw.data_store = mw
    return BaseGameRules(mw)

def test_BaseGameRules_load_data_list(base_rules):
    data = ["line1", "line2"]
    blocks, names = base_rules.load_data_from_json_obj(data)
    assert blocks == [["line1", "line2"]]

def test_BaseGameRules_load_data_dict(base_rules):
    data = {"strings": ["line1"]}
    blocks, names = base_rules.load_data_from_json_obj(data)
    assert blocks == [["line1"]]

def test_BaseGameRules_load_data_kruptar(base_rules):
    data = "Line 1\n{END}\nLine 2\n{END}"
    blocks, names = base_rules.load_data_from_json_obj(data)
    assert blocks == [["Line 1", "Line 2"]]

def test_BaseGameRules_save_data_kruptar(base_rules):
    data = [["Line 1", "Line 2"]]
    output = base_rules.save_data_to_json_obj(data, {})
    assert "Line 1\n{END}" in output
    assert "Line 2\n{END}" in output

def test_BaseGameRules_get_spellcheck_ignore_pattern(base_rules):
    pattern = base_rules.get_spellcheck_ignore_pattern()
    assert r'\{[^}]*\}' in pattern
    assert r'\[[^\]]*\]' in pattern

def test_BaseGameRules_get_text_representation_for_preview(base_rules):
    base_rules.mw.newline_display_symbol = "N"
    assert base_rules.get_text_representation_for_preview("line1\nline2") == "line1Nline2"
