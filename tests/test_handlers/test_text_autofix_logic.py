import pytest
from unittest.mock import MagicMock, patch
from handlers.text_autofix_logic import TextAutofixLogic
from PyQt5.QtWidgets import QMessageBox

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

@patch('PyQt5.QtWidgets.QMessageBox.information')
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
    
    mock_autofix.ui_updater.populate_strings_for_block.assert_called_once()


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

@patch('handlers.text_autofix_logic.calculate_string_width')
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

@patch('handlers.text_autofix_logic.calculate_string_width')
def test_TextAutofixLogic_fix_width_exceeded_corner(mock_calc, mock_autofix, mock_mw):
    mock_calc.return_value = 200
    mock_mw.line_width_warning_threshold_pixels = 100
    mock_mw.font_map = {}
    
    # word exceeds initially
    text = "Long Word"
    assert "\n" in mock_autofix._fix_width_exceeded(text)

def test_TextAutofixLogic_fix_blue_sublines_corner(mock_autofix, mock_mw):
    assert mock_autofix._fix_blue_sublines("1") == "1"
    assert mock_autofix._fix_blue_sublines("line1\n \nline3") == "line1\n \nline3"
    assert "line1" in mock_autofix._fix_blue_sublines("line1.\nline2")

def test_TextAutofixLogic_cleanup_spaces_corner(mock_autofix, mock_mw):
    assert mock_autofix._cleanup_spaces_around_tags("{Color:White} ,") == "{Color:White},"
    assert mock_autofix._cleanup_spaces_around_tags("no spaces here") == "no spaces here"

@patch('PyQt5.QtWidgets.QMessageBox.warning')
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
    
    mock_autofix._fix_empty_odd_sublines = MagicMock(side_effect=lambda x: x)
    mock_autofix._fix_short_lines = MagicMock(side_effect=lambda x: x)
    mock_autofix._fix_width_exceeded = MagicMock(side_effect=lambda x: x)
    mock_autofix._fix_blue_sublines = MagicMock(side_effect=lambda x: x)
    mock_autofix._fix_leading_spaces_in_sublines = MagicMock(side_effect=lambda x: x)
    mock_autofix._cleanup_spaces_around_tags = MagicMock(side_effect=lambda x: x)
    
    # No changes branch
    mock_autofix.auto_fix_current_string()
    if hasattr(mock_mw, 'statusBar'):
        mock_mw.statusBar.showMessage.assert_called_with("Auto-fix: No changes made.", 2000)

    # Max iteration branch (warning)
    mock_autofix._fix_empty_odd_sublines.side_effect = lambda x: x + "!"
    mock_autofix.auto_fix_current_string()
    mock_warn.assert_called_once()
