# tests/test_handlers/test_text_formatter.py

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
    
    with patch('handlers.translation.text_formatter.calculate_string_width', return_value=10):
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


def test_text_formatter_preserves_deliberate_newlines():
    mw = MagicMock()
    mw.game_dialog_max_width_pixels = 200
    mw.line_width_warning_threshold_pixels = 100
    mw.lines_per_page = 4
    mw.current_font_map = {"a": {"width": 10}, " ": {"width": 5}}
    mw.font_map = {}
    mw.icon_sequences = []
    mw.default_tag_mappings = {}
    mw.string_metadata = {}

    mock_rules = MagicMock()
    mock_rules.get_shift_enter_char.return_value = "\n"
    mock_rules.convert_editor_text_to_data.side_effect = lambda x: x
    mw.current_game_rules = mock_rules

    formatter = TextFormatter(mw)

    # Each line "aaaaa" is 50px (5 * 10). Both are <= 100px warning_threshold.
    # Deliberate newline should be preserved.
    res = formatter.format_and_wrap_translation("aaaaa\naaaaa", 0, 0)
    assert res == "aaaaa\naaaaa"

    # Line 1: "aaaaa aaaaa aaaaa" = 15 chars * 10 + 2 * 5 = 160px.
    # Exceeds 100px. So it should wrap.
    # Line 2: "aaaaa" = 50px. Fits <= 100px.
    res_wrapped = formatter.format_and_wrap_translation("aaaaa aaaaa aaaaa\naaaaa", 0, 0)
    assert "aaaaa aaaaa\naaaaa\naaaaa" in res_wrapped


def _fit_window(source):
    """A window 100 px wide, one pixel per character; the plugin keeps text as it is."""
    from types import SimpleNamespace
    rules = MagicMock()
    rules.get_shift_enter_char.return_value = "\n"
    rules.convert_editor_text_to_data.side_effect = lambda x: x
    rules.get_text_representation_for_editor.side_effect = lambda x: x
    rules.get_string_layout.return_value = {}
    rules.get_preview_window_style.return_value = {}
    return SimpleNamespace(
        game_dialog_max_width_pixels=100, line_width_warning_threshold_pixels=90, lines_per_page=3,
        current_font_map={}, font_map={}, string_metadata={}, icon_sequences=[], default_tag_mappings={},
        current_game_rules=rules, data_store=SimpleNamespace(data=[[source]]))


def test_fit_keeps_the_models_lines_for_a_lines_string():
    """A menu or a name: one source line is one output line, however wide (the width warning shows the rest)."""
    with patch('handlers.translation.text_formatter.calculate_string_width', side_effect=lambda s, *a, **k: len(s) * 10):
        wide = "дуже довгий пункт меню\nдва\nтри"
        assert TextFormatter(_fit_window("Save\nLoad\nQuit")).fit_translation_to_window(wide, 0, 0) == wide


def test_fit_typesets_prose_with_the_games_font_whatever_the_model_broke():
    """A dialogue line: the words of the page are reflowed to the target width; no word is left alone at the end."""
    with patch('handlers.translation.text_formatter.calculate_string_width', side_effect=lambda s, *a, **k: len(s) * 10):
        window = _fit_window("Hello there, friend. How are you?")
        assert TextFormatter(window).fit_translation_to_window("один два три чотир", 0, 0) == "один два\nтри чотир"


def test_fit_rewraps_the_whole_page_so_no_word_is_left_alone():
    """Live run 2026-10-03: only the too-wide line was split, leaving «закінчаться» on a line of its own."""
    window = _fit_window("Say something long here, please.")
    window.game_dialog_max_width_pixels, window.line_width_warning_threshold_pixels = 200, 180
    with patch('handlers.translation.text_formatter.calculate_string_width', side_effect=lambda s, *a, **k: len(s) * 10):
        fitted = TextFormatter(window).fit_translation_to_window("один два\nдуже довгий рядок тут і ще\nтри", 0, 0)
    assert fitted == "один два дуже\nдовгий рядок тут\nі ще три"
