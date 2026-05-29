import pytest
from unittest.mock import MagicMock
from plugins.plain_text.rules import GameRules

@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.lines_per_page = 4
    mw.tag_color_rgba = "#FF8C00"
    mw.tag_bold = True
    mw.tag_italic = False
    mw.tag_underline = False
    mw.newline_color_rgba = "#A020F0"
    mw.newline_bold = True
    mw.newline_italic = False
    mw.newline_underline = False
    mw.edited_text_edit = None
    return mw

@pytest.fixture
def rules(mock_mw):
    return GameRules(mock_mw)

def test_single_word_subline_detection(rules):
    # 1. Single-line text with single word should not trigger warnings
    text = "Hello"
    problems = rules.problem_analyzer.analyze_data_string(text, {}, 200)
    assert len(problems) == 1
    assert rules.problem_analyzer.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE not in problems[0]
    assert rules.problem_analyzer.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE_NON_START not in problems[0]

    # 2. Multi-line text with single word at index 1 (not start of page)
    # Should not trigger warnings at all
    text = "Line 1\nHello"
    problems = rules.problem_analyzer.analyze_data_string(text, {}, 200)
    assert len(problems) == 2
    assert rules.problem_analyzer.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE not in problems[1]
    assert rules.problem_analyzer.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE_NON_START not in problems[1]

    # 3. Multi-line text with single word starting with capital at index 4 (start of page 2)
    # e.g., "Button" or "Hello" or "Formatting..."
    # Should be OK (no warnings) even if there is content after it!
    for word in ["Button", "Hello", "Formatting...", "Ok."]:
        # Case A: no content after
        text = f"L1\nL2\nL3\nL4\n{word}"
        problems = rules.problem_analyzer.analyze_data_string(text, {}, 200)
        assert len(problems) == 5
        assert rules.problem_analyzer.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE not in problems[4]
        assert rules.problem_analyzer.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE_NON_START not in problems[4]

        # Case B: has content after
        text = f"L1\nL2\nL3\nL4\n{word}\nWorld"
        problems = rules.problem_analyzer.analyze_data_string(text, {}, 200)
        assert len(problems) == 6
        assert rules.problem_analyzer.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE not in problems[4]
        assert rules.problem_analyzer.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE_NON_START not in problems[4]

    # 4. Multi-line text with single word at index 4 (start of page 2)
    # and no content after it on page 2 (end of string)
    # and it starts with a small letter (e.g., "saving?" or "button")
    # Should trigger brown warning: PROBLEM_SINGLE_WORD_SUBLINE_NON_START
    for word in ["saving?", "button"]:
        text = f"L1\nL2\nL3\nL4\n{word}"
        problems = rules.problem_analyzer.analyze_data_string(text, {}, 200)
        assert len(problems) == 5
        assert rules.problem_analyzer.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE not in problems[4]
        assert rules.problem_analyzer.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE_NON_START in problems[4]
