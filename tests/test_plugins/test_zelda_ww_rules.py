import pytest
from unittest.mock import MagicMock, patch
from plugins.zelda_ww.rules import GameRules

@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.line_width_warning_threshold_pixels = 200
    mw.font_map = {}
    mw.show_multiple_spaces_as_dots = False
    mw.newline_display_symbol = "↵"
    mw.tag_color_rgba = "#FF8C00"
    mw.tag_bold = True
    mw.tag_italic = False
    mw.tag_underline = False
    mw.newline_color_rgba = "#A020F0"
    mw.newline_bold = True
    mw.newline_italic = False
    mw.newline_underline = False
    mw.edited_text_edit = None # Avoid palette issues
    return mw

@pytest.fixture
def rules(mock_mw):
    return GameRules(mock_mw)

def test_ZeldaWW_display_name(rules):
    assert rules.get_display_name() == "Zelda: The Wind Waker"

def test_ZeldaWW_tag_legitimacy(rules):
    assert rules.is_tag_legitimate("[Color:Red]") is True
    assert rules.is_tag_legitimate("[AnyTag]") is True
    assert rules.is_tag_legitimate("{Curly}") is False

def test_ZeldaWW_analyze_data_string_width(rules):
    # Mocking calculate_string_width - providing enough values
    with patch('plugins.zelda_ww.problem_analyzer.calculate_string_width', side_effect=[250, 100, 100, 100, 100]):
        problems = rules.problem_analyzer.analyze_data_string("Long line\nShort", {}, 200)
        assert rules.problem_ids.PROBLEM_WIDTH_EXCEEDED in problems[0]
        assert rules.problem_ids.PROBLEM_WIDTH_EXCEEDED not in problems[1]

def test_ZeldaWW_analyze_empty_first_line_of_page(rules):
    text = "\nContent\nLine 3\nLine 4\n\nPage 2"
    problems = rules.problem_analyzer.analyze_data_string(text, {}, 200)
    # Line 0 (index 0) is empty and followed by content in same page
    assert rules.problem_ids.PROBLEM_EMPTY_FIRST_LINE_OF_PAGE in problems[0]
    # Line 4 (index 4) is start of next page, also empty
    assert rules.problem_ids.PROBLEM_EMPTY_FIRST_LINE_OF_PAGE in problems[4]

def test_ZeldaWW_fix_empty_odd_sublines(rules):
    # Zelda WW often expects odd lines (1st, 3rd logic-wise, but here it's 1-indexed (i+1)%2)
    # If index 0 is empty (odd 1), it's removed? 
    # Current logic: (i+1)%2 != 0 means i=0, 2, 4... is odd.
    text = "\nValid line\n\nAnother line"
    fixed, changed = rules.text_fixer._fix_empty_odd_sublines_zww(text)
    assert changed is True
    assert fixed == "Valid line\nAnother line"

def test_ZeldaWW_cleanup_spaces_around_tags(rules):
    text = "[Tag] item"
    fixed, changed = rules.text_fixer._cleanup_spaces_around_tags_zww(text)
    assert changed is True
    assert fixed == "[Tag]item" # Removed space after tag

def test_ZeldaWW_cleanup_spaces_closing_color_tag(rules):
    # [/C] followed by punctuation should NOT remove space? 
    # Logic: if is_closing_tag and char_after is punctuation, should_remove_space = True?
    # Wait, line 108: if is_closing_tag: if char_after is punctuation: should_remove_space = True.
    # If NOT punctuation: should_remove_space = False.
    text = "[/C] ."
    fixed, changed = rules.text_fixer._cleanup_spaces_around_tags_zww(text)
    assert changed is True
    assert fixed == "[/C]."
    
    text = "[/C] word"
    fixed, changed = rules.text_fixer._cleanup_spaces_around_tags_zww(text)
    assert changed is False # word is not punctuation, so space is kept?
    # Correction: line 111 says "else: should_remove_space = True" (for non-closing tags)
    # For closing tag, if NOT punctuation, it goes through line 113 "if not should_remove_space: result_parts.append(space_content)"
    assert fixed == "[/C] word"

@patch('plugins.common.text_fixer.calculate_string_width', return_value=10)
@patch('plugins.zelda_ww.problem_analyzer.calculate_string_width', return_value=10)
def test_ZeldaWW_autofix_integration(mock_calc_pa, mock_calc_tf, rules):
    # Empty first line of page (index 0) + some text
    text = "\n[Tag]  word"
    # 1. page fix -> removes index 0 -> "[Tag]  word"
    # 2. odd subline fix (i=0 "[Tag] word" contains tag, so skips)
    # 3. cleanup spaces -> "[Tag] word" (removes one space)
    fixed, changed = rules.autofix_data_string(text, {}, 200)
    assert changed is True
    assert fixed == "[Tag] word"
