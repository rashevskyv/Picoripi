# tests/test_handlers/test_text_formatter.py

import pytest
from unittest.mock import MagicMock, patch
from handlers.translation.text_formatter import TextFormatter


def test_text_formatter_empty():
    mw = MagicMock()
    formatter = TextFormatter(mw)
    assert formatter.format_and_wrap_translation("", 0, 0) == ""
    assert formatter.format_and_wrap_translation(None, 0, 0) == ""


def test_text_formatter_basic():
    mw = MagicMock()
    mw.game_dialog_max_width_pixels = 460
    mw.line_width_warning_threshold_pixels = 410
    mw.lines_per_page = 4
    mw.current_font_map = None
    mw.font_map = {}
    mw.string_metadata = {}
    
    # Mock current game rules
    mock_rules = MagicMock()
    mock_rules.get_shift_enter_char.return_value = "\n"
    mock_rules.convert_editor_text_to_data.side_effect = lambda x: x
    mw.current_game_rules = mock_rules
    
    formatter = TextFormatter(mw)
    
    with patch('handlers.translation.text_formatter.calculate_string_width', return_value=10), \
         patch('handlers.translation.text_formatter.remove_all_tags', side_effect=lambda x: x):
        res = formatter.format_and_wrap_translation("Hello World", 0, 0)
        assert "Hello World" in res


def test_text_formatter_with_visible_tags():
    mw = MagicMock()
    mw.game_dialog_max_width_pixels = 200
    mw.line_width_warning_threshold_pixels = 100
    mw.lines_per_page = 4
    mw.current_font_map = {"a": 10, "b": 10, " ": 5, "{(btn)}": 50}
    mw.font_map = {}
    mw.icon_sequences = ["{(btn)}"]
    mw.default_tag_mappings = {"{(btn)}": "{(btn)}"}
    mw.string_metadata = {}

    mock_rules = MagicMock()
    mock_rules.get_shift_enter_char.return_value = "\n"
    mock_rules.convert_editor_text_to_data.side_effect = lambda x: x
    mw.current_game_rules = mock_rules

    formatter = TextFormatter(mw)
    res = formatter.format_and_wrap_translation("aaaa {(btn)} bbbb", 0, 0)
    # Total width with tag as 50:
    # "aaaa" = 40px, " " = 5px, "{(btn)}" = 50px -> "aaaa {(btn)}" = 95px (<= 100 warning_threshold)
    # If we add " bbbb" (5px + 40px = 45px), total is 140px (> 100 warning_threshold).
    # So "bbbb" should wrap to the next line.
    assert res == "aaaa {(btn)}\nbbbb"

