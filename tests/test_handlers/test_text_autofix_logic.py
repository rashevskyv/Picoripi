import pytest
from unittest.mock import MagicMock, patch
from handlers.text_autofix_logic import TextAutofixLogic
from PyQt6.QtWidgets import QMessageBox

@pytest.fixture
def mock_autofix(mock_mw):
    return TextAutofixLogic(mock_mw, MagicMock(), mock_mw.ui_updater)

def test_TextAutofixLogic_init(mock_autofix, mock_mw):
    assert mock_autofix.mw == mock_mw

def test_TextAutofixLogicends_with_sentence_punctuation(mock_autofix):
    assert mock_autofix._ends_with_sentence_punctuation("text.") is True
    assert mock_autofix._ends_with_sentence_punctuation("text!") is True
    assert mock_autofix._ends_with_sentence_punctuation("text?") is True
    assert mock_autofix._ends_with_sentence_punctuation("text") is False
    assert mock_autofix._ends_with_sentence_punctuation("") is False

def test_TextAutofixLogicextract_first_word_with_tags(mock_autofix):
    assert mock_autofix._extract_first_word_with_tags("Hello world") == ("Hello", "world")
    assert mock_autofix._extract_first_word_with_tags("{Tag}Hello world") == ("{Tag}Hello", "world")
    assert mock_autofix._extract_first_word_with_tags("Hello{Tag} world") == ("Hello{Tag}", "world")

def test_TextAutofixLogicfix_empty_odd_sublines(mock_autofix):
    text = "line1\n\nline2"
    fixed_text = mock_autofix._fix_empty_odd_sublines(text)
    assert isinstance(fixed_text, str)

@patch('handlers.text_autofix_logic.calculate_string_width')
def test_TextAutofixLogicfix_short_lines(mock_calc, mock_autofix, mock_mw):
    mock_mw.current_block_idx = 0
    mock_mw.current_string_idx = 0
    mock_mw.helper.get_font_map_for_string.return_value = {}
    mock_mw.string_metadata = {}
    mock_mw.line_width_warning_threshold_pixels = 200

    mock_calc.side_effect = lambda *args, **kwargs: len(args[0]) * 10

    text = "This is a very long line that should be wrapped.\nAnd another line."
    fixed = mock_autofix._fix_short_lines(text)
    assert isinstance(fixed, str)

@patch('handlers.text_autofix_logic.calculate_string_width')
def test_TextAutofixLogicfix_width_exceeded(mock_calc, mock_autofix, mock_mw):
    mock_mw.current_block_idx = 0
    mock_mw.current_string_idx = 0
    mock_mw.helper.get_font_map_for_string.return_value = {}
    mock_mw.string_metadata = {}
    mock_mw.line_width_warning_threshold_pixels = 100

    mock_calc.side_effect = lambda *args, **kwargs: len(args[0]) * 10

    text = "Very long line that exceeds the 100 limit.\nShort."
    fixed = mock_autofix._fix_width_exceeded(text)
    assert "\n" in fixed

def test_TextAutofixLogicfix_blue_sublines(mock_autofix, mock_mw):
    mock_mw.current_game_rules = MagicMock()
    text = "{Color:White}text{Color:Blue}\nmore text"
    fixed = mock_autofix._fix_blue_sublines(text)
    assert isinstance(fixed, str)

def test_TextAutofixLogicfix_leading_spaces_in_sublines(mock_autofix, mock_mw):
    mock_mw.current_game_rules = MagicMock()
    assert isinstance(mock_autofix._fix_leading_spaces_in_sublines("line1\n line2"), str)

def test_TextAutofixLogiccleanup_spaces_around_tags(mock_autofix, mock_mw):
    mock_mw.current_game_rules = MagicMock()
    text = " {Tag} text "
    assert isinstance(mock_autofix._cleanup_spaces_around_tags(text), str)
    assert isinstance(mock_autofix._cleanup_spaces_around_tags("text {Tag}"), str)

@patch('PyQt6.QtWidgets.QMessageBox.information')
def test_TextAutofixLogic_auto_fix_current_string(mock_msgbox_info, mock_autofix, mock_mw):
    mock_mw.data = [["A string"]]
    mock_mw.current_block_idx = -1
    mock_mw.current_string_idx = -1
    mock_autofix.auto_fix_current_string()

    mock_mw.current_block_idx = 0
    mock_mw.current_string_idx = 0
    mock_autofix.data_processor.get_current_string_text.return_value = ("Original", False)

    mock_mw.edited_text_edit = MagicMock()
    mock_mw.edited_text_edit.toPlainText.return_value = " Translated  text\n with issues. "
    mock_mw.edited_text_edit.textCursor().position.return_value = 0
    mock_mw.edited_text_edit.document().characterCount.return_value = 10
    mock_mw.edited_text_edit.verticalScrollBar().value.return_value = 0
    mock_mw.edited_text_edit.horizontalScrollBar().value.return_value = 0
    mock_mw.edited_text_edit.document().isUndoAvailable.return_value = False

    # Mock all fix methods to just return the passed string to trace execution
    mock_autofix._fix_empty_odd_sublines = MagicMock(return_value="1")
    mock_autofix._fix_short_lines = MagicMock(return_value="2")
    mock_autofix._fix_width_exceeded = MagicMock(return_value="3")
    mock_autofix._fix_blue_sublines = MagicMock(return_value="4")
    mock_autofix._fix_leading_spaces_in_sublines = MagicMock(return_value="5")
    mock_autofix._cleanup_spaces_around_tags = MagicMock(return_value="Fixed Text")

    mock_autofix.auto_fix_current_string()

    mock_autofix.ui_updater.populate_current_view.assert_called_once_with()


def test_TextAutofixLogic_coverage_corner_cases(mock_autofix, mock_mw):
    # 1. ends_with_sentence_punctuation: chars like "!" and "'"
    assert mock_autofix._ends_with_sentence_punctuation("text!\"") is True
    assert mock_autofix._ends_with_sentence_punctuation("a\"") is False

    # 2. _extract_first_word_with_tags: spaces
    assert mock_autofix._extract_first_word_with_tags("   ") == ("", "   ")
    assert mock_autofix._extract_first_word_with_tags("Hello") == ("Hello", "")

    # 3. _fix_empty_odd_sublines: 1 line, tags, pop
    assert mock_autofix._fix_empty_odd_sublines("1line") == "1line"
    assert mock_autofix._fix_empty_odd_sublines("1\n{Tag}\n") == "1\n{Tag}"
    assert mock_autofix._fix_empty_odd_sublines("1\n0\n1") == "1\n0\n1"
    assert mock_autofix._fix_empty_odd_sublines("\n") == ""
    assert mock_autofix._fix_empty_odd_sublines("1\n\n\n\n") == "1\n"

@patch('utils.utils.calculate_string_width')
def test_TextAutofixLogic_fix_short_lines_merge(mock_calc, mock_autofix, mock_mw):
    mock_calc.return_value = 1
    mock_mw.line_width_warning_threshold_pixels = 2000
    mock_mw.font_map = {}

    # Simple word + word
    text = "Short\nline."
    assert mock_autofix._fix_short_lines(text) == "Short line."

    # Tag + Word
    text = "{Color:Red}\nline."
    assert mock_autofix._fix_short_lines(text) == "{Color:Red}\nline."

    # no elements in next line
    text = "Short\n\nline."
    # Current implementation might skip empty lines or handle them differently
    assert mock_autofix._fix_short_lines(text) == "Short\n\nline."

@patch('utils.utils.calculate_string_width')
def test_TextAutofixLogic_fix_width_exceeded_corner(mock_calc, mock_autofix, mock_mw):
    mock_calc.return_value = 200
    mock_mw.game_dialog_max_width_pixels = 100
    mock_mw.font_map = {}

    # word exceeds initially
    text = "Long Word"
    assert "\n" in mock_autofix._fix_width_exceeded(text)

def test_TextAutofixLogic_fix_blue_sublines_corner(mock_autofix, mock_mw):
    assert mock_autofix._fix_blue_sublines("1") == "1"
    assert mock_autofix._fix_blue_sublines("line1\n \nline3") == "line1\n \nline3"
    assert "line1" in mock_autofix._fix_blue_sublines("line1.\nline2")

def test_TextAutofixLogic_cleanup_spaces_corner(mock_autofix, mock_mw):
    mock_mw.default_tag_mappings = {
        "{Color:White}": "{Color:White}",
        "{color:white}": "{color:white}",
        "{escape:255:000000}": "{escape:255:000000}",
        "{color_default}": "{color_default}"
    }
    mock_mw.icon_sequences = ["{Color:White}", "{color:white}", "{escape:255:000000}", "{color_default}"]
    mock_mw.font_map = {"w": {"width": 10}, "o": {"width": 10}, "r": {"width": 10}, "d": {"width": 10}}

    assert mock_autofix._cleanup_spaces_around_tags("{Color:White} ,") == "{Color:White},"
    assert mock_autofix._cleanup_spaces_around_tags("no spaces here") == "no spaces here"

    # Spaces before words for white/closing tags should be preserved
    assert mock_autofix._cleanup_spaces_around_tags("{Color:White} word") == "{Color:White} word"
    assert mock_autofix._cleanup_spaces_around_tags("{color:white} word") == "{color:white} word"
    assert mock_autofix._cleanup_spaces_around_tags("{escape:255:000000} word") == "{escape:255:000000} word"
    assert mock_autofix._cleanup_spaces_around_tags("{color_default} word") == "{color_default} word"

    # Spaces before punctuation for white/closing tags should be removed
    assert mock_autofix._cleanup_spaces_around_tags("{Color:White} ,") == "{Color:White},"
    assert mock_autofix._cleanup_spaces_around_tags("{escape:255:000000} .") == "{escape:255:000000}."
    assert mock_autofix._cleanup_spaces_around_tags("{color_default} !") == "{color_default}!"

    # Spaces after non-white tags before words should be removed
    assert mock_autofix._cleanup_spaces_around_tags("{Color:Red} word") == "{Color:Red}word"

@patch('PyQt6.QtWidgets.QMessageBox.warning')
def test_TextAutofixLogic_auto_fix_current_string_corner(mock_warn, mock_autofix, mock_mw):
    mock_mw.current_block_idx = 0
    mock_mw.current_string_idx = 0
    mock_autofix.data_processor.get_current_string_text.return_value = ("Original", False)

    # Mock edited_text_edit methods to avoid TypeError in auto_fix_current_string
    mock_mw.edited_text_edit.document().characterCount.return_value = 10
    mock_mw.edited_text_edit.textCursor().position.return_value = 0
    mock_mw.edited_text_edit.document().isUndoAvailable.return_value = False
    mock_mw.edited_text_edit.verticalScrollBar().value.return_value = 0
    mock_mw.edited_text_edit.horizontalScrollBar().value.return_value = 0

    mock_autofix._fix_empty_odd_sublines = MagicMock(side_effect=lambda x, *args: x)
    mock_autofix._fix_short_lines = MagicMock(side_effect=lambda x, *args: x)
    mock_autofix._fix_width_exceeded = MagicMock(side_effect=lambda x, *args: x)
    mock_autofix._fix_blue_sublines = MagicMock(side_effect=lambda x, *args: x)
    mock_autofix._fix_leading_spaces_in_sublines = MagicMock(side_effect=lambda x, *args: x)
    mock_autofix._cleanup_spaces_around_tags = MagicMock(side_effect=lambda x, *args: x)

    # No changes branch
    mock_autofix.auto_fix_current_string()
    if hasattr(mock_mw, 'statusBar'):
        mock_mw.statusBar.showMessage.assert_called_with("Auto-fix: No changes made.", 2000)

    # Max iteration branch (warning)
    mock_autofix._fix_empty_odd_sublines.side_effect = lambda x: x + "!"
    mock_autofix.auto_fix_current_string()
    mock_warn.assert_called_once()


@patch('handlers.text_autofix_logic.calculate_string_width')
def test_TextAutofixLogic_fix_short_lines_boundary_cross(mock_calc, mock_autofix, mock_mw):
    mock_mw.lines_per_page = 4
    mock_mw.font_map = {}
    mock_calc.side_effect = lambda *args, **kwargs: len(args[0]) * 10

    # Mock analyzer's check_single_word_subline_generic and _is_single_word_ok_generic
    mock_mw.current_game_rules = MagicMock()
    mock_mw.current_game_rules.problem_analyzer._check_single_word_subline_generic.return_value = True
    mock_mw.current_game_rules.problem_analyzer._is_single_word_ok_generic.return_value = False

    # CASE A: fits (threshold is large)
    # line 4 (index 3) is boundary. next_line is line index 4 ("місця").
    # It should merge line index 3 ("Line 4") and index 4 ("місця") -> "Line 4 місця"
    text = "Line 1.\nLine 2.\nLine 3.\nLine 4\nмісця"
    # mock_calc for "Line 4" = 60, "місця" = 50, space = 10.
    # If limit is 200:
    res = mock_autofix._fix_short_lines(text, width_threshold=100, logical_hard_limit=200)
    assert res == "Line 1.\nLine 2.\nLine 3.\nLine 4 місця"


def test_shift_split_sentences():
    from utils.utils import shift_split_sentences
    # Test a basic shift where lines_per_page = 4
    text = "Line 1.\nLine 2.\nHere is a sentence\nthat spans across\nthe page boundary."
    res, changed = shift_split_sentences(text, 4)
    assert changed is True
    assert res == "Line 1.\nLine 2.\n\n\nHere is a sentence\nthat spans across\nthe page boundary."

    # Test that empty lines are preserved and act as boundaries when sum exceeds page size
    text_with_empty = "Line 1.\nLine 2a\nLine 2b\n\nLine 3a\nLine 3b"
    res_empty, changed_empty = shift_split_sentences(text_with_empty, 4)
    assert res_empty == "Line 1.\nLine 2a\nLine 2b\n\nLine 3a\nLine 3b"
    assert changed_empty is False

    # Test that escape page breaks trigger a page split
    text_with_escape = "Line 1.\n{escape:0:0007000a}Line 2."
    res_escape, changed_escape = shift_split_sentences(text_with_escape, 4)
    assert res_escape == "Line 1.\n\n\n\n{escape:0:0007000a}Line 2."
    assert changed_escape is True


def test_shift_split_sentences_aligned():
    from utils.utils import shift_split_sentences_aligned

    # Scenario 1: Same number of sentences, page break code in original must be copied to translation
    orig = "Line 1.\n[escape:0:0007000a]Line 2."
    trans = "Trans 1.\nTrans 2."
    res, changed = shift_split_sentences_aligned(trans, orig, 4)
    assert changed is True
    assert "[escape:0:0007000a]Trans 2." in res

    # Scenario 2: Old incorrect page break in trans must be cleaned and aligned according to original
    orig2 = "Line 1.\n[escape:0:0007000a]Line 2."
    trans2 = "[escape:0:0007000a]Trans 1.\nTrans 2."
    res2, changed2 = shift_split_sentences_aligned(trans2, orig2, 4)
    assert "[escape:0:0007000a]Trans 1." not in res2
    assert "[escape:0:0007000a]Trans 2." in res2


def test_shift_split_sentences_prevent_empty_lines():
    from utils.utils import shift_split_sentences, shift_split_sentences_aligned

    # Test shift_split_sentences with prevent_empty_lines
    text = "Line 1.\n{escape:0:0007000a}Line 2."

    # Without prevent_empty_lines (default: pad with empty lines to 4 lines per page)
    res_pad, _ = shift_split_sentences(text, 4, prevent_empty_lines=False)
    assert res_pad == "Line 1.\n\n\n\n{escape:0:0007000a}Line 2."

    # With prevent_empty_lines: next sentence starts with page break, so we do NOT pad!
    res_no_pad, _ = shift_split_sentences(text, 4, prevent_empty_lines=True)
    assert res_no_pad == "Line 1.\n{escape:0:0007000a}Line 2."

    # Test shift_split_sentences_aligned with prevent_empty_lines
    orig = "Orig 1.\n[escape:0:0007000a]Orig 2."
    trans = "Trans 1.\nTrans 2."

    # Without prevent_empty_lines (default)
    res_align_pad, _ = shift_split_sentences_aligned(trans, orig, 4, prevent_empty_lines=False)
    assert res_align_pad == "Trans 1.\n\n\n\n[escape:0:0007000a]Trans 2."

    # With prevent_empty_lines: next sentence starts with page break, do NOT pad
    res_align_no_pad, _ = shift_split_sentences_aligned(trans, orig, 4, prevent_empty_lines=True)
    assert res_align_no_pad == "Trans 1.\n[escape:0:0007000a]Trans 2."

    # Test shift_split_sentences_aligned with prevent_empty_lines where the sentence does NOT start with a page break
    orig_no_pb = "Orig 1.\nOrig 2 line 1\nOrig 2 line 2\nOrig 2 line 3\nOrig 2 line 4."  # sentence 1 ends on page 0, sentence 2 ends on page 1
    trans_no_pb = "Trans 1.\nTrans 2."

    # Without prevent_empty_lines (default) -> pads page 1 with empty lines
    res_align_pad_no_pb, _ = shift_split_sentences_aligned(trans_no_pb, orig_no_pb, 4, prevent_empty_lines=False)
    assert res_align_pad_no_pb == "Trans 1.\n\n\n\nTrans 2."

    # With prevent_empty_lines -> does not pad page 1
    res_align_no_pad_no_pb, _ = shift_split_sentences_aligned(trans_no_pb, orig_no_pb, 4, prevent_empty_lines=True)
    assert res_align_no_pad_no_pb == "Trans 1.\nTrans 2."


def test_shift_split_sentences_optimize_page_breaks():
    from utils.utils import shift_split_sentences
    # Scenario 1: Same number of sentences, page break code in original must be copied to translation
    # Sentence 1: 2 lines
    # Sentence 2: empty line (1 line)
    # Sentence 3: 2 lines
    # lines_per_page = 4
    # Without optimization, Sentence 3 would be pushed to next page due to the empty line.
    # With optimization, the intermediate empty line is removed because 2 + 2 <= 4.
    text = "Line 1\nLine 2.\n\nLine 3\nLine 4."
    res, changed = shift_split_sentences(text, 4)
    assert res == "Line 1\nLine 2.\nLine 3\nLine 4."
    assert changed is True

    # Scenario 2: Sum exceeds page size (3 + 2 = 5 > 4), so empty line should NOT be optimized out
    text2 = "Line 1\nLine 2\nLine 3.\n\nLine 4\nLine 5."
    res2, changed2 = shift_split_sentences(text2, 4)
    assert res2 == "Line 1\nLine 2\nLine 3.\n\nLine 4\nLine 5."
    assert changed2 is False


def test_TextAutofixLogic_fix_short_lines_with_visible_tags(mock_autofix, mock_mw):
    mock_mw.line_width_warning_threshold_pixels = 100
    mock_mw.lines_per_page = 4
    mock_mw.font_map = {"a": {"width": 10}, "b": {"width": 10}, " ": {"width": 5}, "{(btn)}": {"width": 50}}
    mock_mw.icon_sequences = ["{(btn)}"]
    mock_mw.default_tag_mappings = {"{(btn)}": "{(btn)}"}

    # Case 1: If {(btn)} is 50px, "aaaa {(btn)}" is 95px.
    # "bbbb" is 40px. Sum with space is 140px > 100px.
    # They should NOT merge.
    text = "aaaa {(btn)}\nbbbb"
    res = mock_autofix._fix_short_lines(text)
    assert res == "aaaa {(btn)}\nbbbb"

    # Case 2: If {(btn)} is 0px (e.g. not in font_map/mappings), "aaaa {(btn)}" would be 45px.
    # "bbbb" is 40px. Sum with space is 90px <= 100px.
    # They would merge.
    mock_mw.font_map = {"a": {"width": 10}, "b": {"width": 10}, " ": {"width": 5}}
    mock_mw.default_tag_mappings = {}
    mock_mw.icon_sequences = []
    res = mock_autofix._fix_short_lines(text)
    assert res == "aaaa {(btn)} bbbb"


def test_TextAutofixLogic_fix_short_lines_starts_with_visible_tag(mock_autofix, mock_mw):
    mock_mw.line_width_warning_threshold_pixels = 100
    mock_mw.lines_per_page = 4
    mock_mw.font_map = {"a": {"width": 10}, " ": {"width": 5}, "{(btn)}": {"width": 30}}
    mock_mw.icon_sequences = ["{(btn)}"]
    mock_mw.default_tag_mappings = {"{(btn)}": "{(btn)}"}

    text = "aaaa\n{(btn)}"
    res = mock_autofix._fix_short_lines(text)
    assert res == "aaaa {(btn)}"


def test_TextAutofixLogic_fix_short_lines_two_words_limit(mock_autofix, mock_mw):
    mock_mw.line_width_warning_threshold_pixels = 100
    mock_mw.lines_per_page = 4
    mock_mw.font_map = {"a": {"width": 10}, "b": {"width": 10}, " ": {"width": 5}}
    mock_mw.icon_sequences = []
    mock_mw.default_tag_mappings = {}

    # Both words fit: "aaaaa" (50) + " " (5) + "bb bb" (45) = 100 <= 100. Should merge.
    text = "aaaaa\nbb bb"
    res1 = mock_autofix._fix_short_lines(text)
    assert res1 == "aaaaa bb bb"

    # Only first word fits: "aaaaa" (50) + " " (5) + "bb bbb" (55) = 110 > 100. Should not merge.
    text = "aaaaa\nbb bbb"
    res2 = mock_autofix._fix_short_lines(text)
    assert res2 == "aaaaa\nbb bbb"

def test_text_autofix_logic_uses_real_game_rules_path(qapp):
    """
    Verify that TextAutofixLogic.auto_fix_current_string using a real GameRules
    instance (e.g. PlainTextRules) executes autofix successfully, updates
    the editor widget, and refreshes the UI.
    """
    from handlers.text_autofix_logic import TextAutofixLogic
    from plugins.plain_text.rules import GameRules as PlainTextRules
    from PyQt6.QtWidgets import QTextEdit

    mw = MagicMock()
    # Mock MainWindow attributes to avoid QColor instantiation errors in TagManager
    mw.tag_color_rgba = "#FF8C00"
    mw.newline_color_rgba = "#A020F0"
    mw.tag_bold = True
    mw.tag_italic = False
    mw.tag_underline = False
    mw.newline_bold = True
    mw.newline_italic = False
    mw.newline_underline = False
    mw.newline_display_symbol = ""
    mw.default_tag_mappings = {}
    mw.tag_warning_color = "#FF8C00"
    mw.tag_normal_color = "#FF8C00"
    mw.issue_warning_color = "#FF8C00"
    mw.issue_error_color = "#FF8C00"

    mw.data_store = mw
    mw.data_store.physical_block_idx = 0
    mw.data_store.current_string_idx = 0
    mw.line_width_warning_threshold_pixels = 100
    mw.game_dialog_max_width_pixels = 120
    mw.show_multiple_spaces_as_dots = False

    mw.current_game_rules = PlainTextRules(mw)

    data_processor = MagicMock()
    data_processor.get_current_string_text.return_value = ("Hello  World", False)

    ui_updater = MagicMock()

    editor = QTextEdit()
    editor.setText("Hello  World")
    mw.edited_text_edit = editor
    mw.string_metadata = {}
    mw.is_programmatically_changing_text = False

    handler = TextAutofixLogic(mw, data_processor, ui_updater)
    handler.auto_fix_current_string()

    assert editor.toPlainText() == "Hello World"
    ui_updater.populate_current_view.assert_called_once_with()



