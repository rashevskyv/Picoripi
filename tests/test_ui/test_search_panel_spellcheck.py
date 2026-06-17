import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QTextCursor
from PyQt6.QtGui import QTextCharFormat
from components.search_panel import SearchPanelWidget, SearchLineEdit
from components.editor.line_numbered_text_edit import LineNumberedTextEdit
from utils.syntax_highlighter import JsonTagHighlighter

class MockMainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.theme = "light"
        self.spellchecker_manager = MagicMock()
        self.spellchecker_manager.enabled = True
        self.spellchecker_manager.hunspell = MagicMock()
        self.spellchecker_manager._suggestions_cache = {}
        
        # Mocks required for LineNumberedTextEdit
        self.preview_text_edit = None
        self.original_text_edit = None
        self.edited_text_edit = None
        self.data_store = MagicMock()
        self.data_store.current_block_idx = 0
        self.data_store.current_string_idx = 0
        self.font_map = {}
        self.icon_sequences = []
        self.line_width_warning_threshold_pixels = 300
        self.game_dialog_max_width_pixels = 320
        self.show_width_guideline = True
        self.editor_char_limit_line_pos = 100
        self.glossary_enabled = True

def test_search_panel_spellcheck_trigger(qapp):
    mw = MockMainWindow()
    panel = SearchPanelWidget(mw)
    line_edit = panel.search_query_edit.lineEdit()
    
    # Configure spellchecker mock
    mw.spellchecker_manager.is_misspelled.side_effect = lambda word: word == "wrongword"
    
    # Check that styleSheet remains correct
    line_edit.setText("correct")
    panel.trigger_spellcheck()
    assert line_edit.styleSheet() == "padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px;"
    
    line_edit.setText("wrongword")
    panel.trigger_spellcheck()
    assert line_edit.styleSheet() == "padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px;"
    
    # Test paintEvent
    from PyQt6.QtGui import QPaintEvent
    from PyQt6.QtCore import QRect
    event = QPaintEvent(QRect(0, 0, 100, 30))
    
    with patch('PyQt6.QtGui.QPainter.begin', return_value=True), \
         patch('PyQt6.QtGui.QPainter.end'), \
         patch('PyQt6.QtGui.QPainter.drawLine') as mock_draw_line, \
         patch('PyQt6.QtWidgets.QLineEdit.paintEvent') as mock_super_paint:
        # Give line_edit some size so binary search works
        line_edit.resize(200, 30)
        line_edit.paintEvent(event)
        assert mock_super_paint.called
        assert mock_draw_line.called  # Should draw wavy line because "wrongword" is misspelled

def test_search_line_edit_context_menu(qapp):
    mw = MockMainWindow()
    line_edit = SearchLineEdit(None, mw)
    
    mw.spellchecker_manager.is_misspelled.side_effect = lambda word: word == "wrongword"
    mw.spellchecker_manager._suggestions_cache = {"wrongword": ["correct1", "correct2"]}
    
    line_edit.setText("wrongword")
    line_edit.setCursorPosition(3) # Cursor inside "wrongword"
    
    with patch('PyQt6.QtWidgets.QMenu.exec') as mock_menu_exec:
        # Simulate context menu event
        class DummyEvent:
            def globalPos(self):
                return None
        line_edit.contextMenuEvent(DummyEvent())
        
        assert mock_menu_exec.called

def test_translation_editor_spellcheck_highlighting(qapp):
    """Test that highlightBlock applies spell-check underline for the misspelled word range."""
    from PyQt6.QtGui import QTextCharFormat
    mw = MockMainWindow()
    editor = LineNumberedTextEdit(mw)
    editor.setObjectName("edited_text_edit")
    mw.edited_text_edit = editor

    editor.highlighter.set_spellchecker_enabled(True)
    assert editor.highlighter._spellchecker_enabled is True

    editor.setPlainText("correct word wrongword spelling error")

    # Bypass the widget/context guard so highlighting always runs
    editor.highlighter._should_check_spelling = MagicMock(return_value=True)
    editor.highlighter._editor_widget_ref = editor

    # Pre-populate async matches: "wrongword" starts at offset 13, length 9
    editor.highlighter.set_async_highlights(
        glossary_matches=[],
        translation_matches=[],
        spellcheck_matches=[(13, 9)],
    )

    # Capture every setFormat call at the class level so Qt doesn't intercept
    captured = []
    orig_sf = type(editor.highlighter).setFormat

    def capturing_sf(self, start, length, fmt):
        captured.append((start, length, fmt.underlineStyle()))

    mock_block = MagicMock()
    mock_block.isValid.return_value = True
    mock_block.position.return_value = 0
    mock_block.blockNumber.return_value = 0

    with patch.object(editor.highlighter, "currentBlock", return_value=mock_block), \
         patch.object(type(editor.highlighter), "setFormat", capturing_sf):
        editor.highlighter.highlightBlock("correct word wrongword spelling error")

    # The spellcheck range (13, 9) must have been formatted with SpellCheckUnderline
    from PyQt6.QtGui import QTextCharFormat as TCF
    spell_underline = TCF.UnderlineStyle.SpellCheckUnderline
    found = any(
        start <= 13 < start + length and style == spell_underline
        for start, length, style in captured
    )
    assert found, f"Expected SpellCheckUnderline at offset 13; got calls: {captured}"
