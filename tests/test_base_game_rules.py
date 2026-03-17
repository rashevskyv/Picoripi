# --- START OF FILE tests/test_base_game_rules.py ---
"""
Tests for plugins/base_game_rules.py — base plugin class behaviour.
Safety net for refactoring: Issue #5 (plugin markers), plugin changes.
"""
import pytest
from plugins.base_game_rules import BaseGameRules


@pytest.fixture
def rules():
    """BaseGameRules instance (no MainWindow)."""
    return BaseGameRules(main_window_ref=None)


# ── load_data_from_json_obj ─────────────────────────────────────────

class TestLoadData:
    def test_load_list(self, rules):
        """JSON list is returned as-is (wrapped in outer list already)."""
        data = [["line1", "line2"], ["line3"]]
        result, block_names = rules.load_data_from_json_obj(data)
        assert result == data
        assert block_names == {}

    def test_load_kruptar_format(self, rules):
        """String with {END} markers is split into separate strings."""
        text = "Hello\n{END}\n\nWorld\n{END}"
        result, block_names = rules.load_data_from_json_obj(text)
        assert len(result) == 1  # One block
        assert len(result[0]) == 2  # Two strings
        assert "Hello" in result[0][0]
        assert "World" in result[0][1]

    def test_load_plain_text(self, rules):
        """Plain text without {END} is split by newlines."""
        text = "line1\nline2\nline3"
        result, block_names = rules.load_data_from_json_obj(text)
        assert len(result) == 1
        assert len(result[0]) == 3

    def test_load_empty_list(self, rules):
        """Empty list input returns a list containing one empty block."""
        result, block_names = rules.load_data_from_json_obj([])
        assert result == [[]]

    def test_load_dict_returns_empty(self, rules):
        """Dict input (unsupported) returns empty list."""
        result, block_names = rules.load_data_from_json_obj({"key": "val"})
        assert result == []


# ── save_data_to_json_obj ───────────────────────────────────────────

class TestSaveData:
    def test_save_single_block(self, rules):
        """Single block is saved in Kruptar format with {END}."""
        data = [["Hello", "World"]]
        result = rules.save_data_to_json_obj(data, {})
        assert isinstance(result, str)
        assert "{END}" in result
        assert "Hello" in result
        assert "World" in result

    def test_save_multi_block(self, rules):
        """Multiple blocks are returned as-is (list)."""
        data = [["a"], ["b"]]
        result = rules.save_data_to_json_obj(data, {})
        assert result == data


# ── Enter characters ────────────────────────────────────────────────

class TestEnterChars:
    def test_enter_char(self, rules):
        assert rules.get_enter_char() == '\n'

    def test_shift_enter_char(self, rules):
        assert rules.get_shift_enter_char() == '\n'

    def test_ctrl_enter_char(self, rules):
        assert rules.get_ctrl_enter_char() == '\n'


# ── Defaults ────────────────────────────────────────────────────────

class TestDefaults:
    def test_convert_editor_text(self, rules):
        """Base class does not transform editor text."""
        assert rules.convert_editor_text_to_data("test") == "test"

    def test_default_tag_mappings_empty(self, rules):
        assert rules.get_default_tag_mappings() == {}

    def test_problem_definitions_empty(self, rules):
        assert rules.get_problem_definitions() == {}

    def test_analyze_subline_empty(self, rules):
        """Base class returns no problems."""
        problems = rules.analyze_subline(
            text="hello", next_text=None,
            subline_number_in_data_string=0, qtextblock_number_in_editor=0,
            is_last_subline_in_data_string=True, editor_font_map={},
            editor_line_width_threshold=200,
            full_data_string_text_for_logical_check="hello"
        )
        assert problems == set()

    def test_autofix_returns_unchanged(self, rules):
        """Base class autofix returns text unchanged."""
        text, changed = rules.autofix_data_string("hello", {}, 200)
        assert text == "hello"
        assert changed is False

    def test_process_pasted_segment(self, rules):
        result, status, msg = rules.process_pasted_segment("text", "original", "player")
        assert result == "text"
        assert status == "OK"

    def test_legitimate_tags_empty(self, rules):
        assert rules.get_legitimate_tags() == set()

    def test_plugin_actions_empty(self, rules):
        assert rules.get_plugin_actions() == []

    def test_width_override_none(self, rules):
        assert rules.calculate_string_width_override("text", {}, 8) is None

    def test_editor_page_size(self, rules):
        assert rules.get_editor_page_size() == 2

    def test_display_name_no_mw(self, rules):
        """Without MainWindow, display name falls back."""
        name = rules.get_display_name()
        assert "Base Game" in name

    def test_get_text_representation_for_editor(self, rules):
        assert rules.get_text_representation_for_editor("hello") == "hello"

    def test_get_short_problem_name_unknown(self, rules):
        """Unknown problem ID returns the ID itself."""
        assert rules.get_short_problem_name("UNKNOWN") == "UNKNOWN"
