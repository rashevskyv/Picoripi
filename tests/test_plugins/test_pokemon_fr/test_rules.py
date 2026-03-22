import pytest
from unittest.mock import MagicMock
from plugins.pokemon_fr.rules import GameRules
from plugins.base_game_rules import BaseGameRules

class MockMainWindow:
    def __init__(self):
        self.data_store = self
        self.show_multiple_spaces_as_dots = False
        self.default_tag_mappings = {}
        self.newline_display_symbol = "↵"
        self.plugin_handler = MagicMock()
        self.data_processor = MagicMock()
        self.original_text_edit = MagicMock()

@pytest.fixture
def rules(qapp):
    """Create GameRules with Qt app (required for QTextCharFormat etc)."""
    mw = MockMainWindow()
    return GameRules(mw)

def test_GameRules_init(rules):
    assert rules.mw is not None
    assert rules.tag_manager is not None
    assert rules.problem_analyzer is not None
    assert rules.text_fixer is not None

def test_GameRules_load_data_from_json_obj(rules):
    json_data = [["string1", "string2"]]
    result_data, result_names = rules.load_data_from_json_obj(json_data)
    assert isinstance(result_data, list)

def test_GameRules_save_data_to_json_obj(rules):
    data = [["string1", "string2"], ["string3"]]
    with pytest.raises(ValueError):
        rules.save_data_to_json_obj(data, {})

def test_GameRules_get_display_name(rules):
    name = rules.get_display_name()
    assert "Pok" in name

def test_GameRules_get_problem_definitions(rules):
    defs = rules.get_problem_definitions()
    assert isinstance(defs, dict)

def test_GameRules_get_syntax_highlighting_rules(rules):
    highlighting_rules = rules.get_syntax_highlighting_rules()
    assert isinstance(highlighting_rules, list)

def test_GameRules_get_legitimate_tags(rules):
    tags = rules.get_legitimate_tags()
    assert isinstance(tags, set)

def test_GameRules_analyze_subline(rules):
    problems = rules.analyze_subline(
        text="A" * 200,
        next_text=None,
        subline_number_in_data_string=0,
        qtextblock_number_in_editor=0,
        is_last_subline_in_data_string=True,
        editor_font_map={},
        editor_line_width_threshold=100,
        full_data_string_text_for_logical_check="A" * 200
    )
    assert isinstance(problems, set)

def test_GameRules_autofix_data_string(rules):
    result, changed = rules.autofix_data_string(
        data_string="Hello World",
        editor_font_map={},
        editor_line_width_threshold=9999
    )
    assert isinstance(result, str)
    assert isinstance(changed, bool)

def test_GameRules_process_pasted_segment(rules):
    result = rules.process_pasted_segment("Link", "Link", "[PLAYER]")
    assert isinstance(result, tuple)
    assert len(result) == 3

def test_GameRules_calculate_string_width_override(rules):
    width = rules.calculate_string_width_override("Hello", {}, 6)
    assert width is None or isinstance(width, int)


def test_GameRules_get_text_representation_for_preview(rules):
    result = rules.get_text_representation_for_preview("Hello\\nWorld")
    assert isinstance(result, str)

def test_GameRules_get_text_representation_for_editor(rules):
    result = rules.get_text_representation_for_editor("Hello World")
    assert result == "Hello World"

def test_GameRules_convert_editor_text_to_data(rules):
    text = "Hello World"
    assert rules.convert_editor_text_to_data(text) == text


def test_GameRules_get_editor_page_size(rules):
    assert rules.get_editor_page_size() == 2
