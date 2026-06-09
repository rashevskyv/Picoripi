import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QWidget
from components.search_panel import SearchPanelWidget, SearchLineEdit

class MockMainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.theme = "light"
        self.spellchecker_manager = MagicMock()
        self.spellchecker_manager.enabled = True
        self.spellchecker_manager.hunspell = MagicMock()
        self.spellchecker_manager._suggestions_cache = {}

def test_search_panel_spellcheck_trigger(qapp):
    mw = MockMainWindow()
    panel = SearchPanelWidget(mw)
    line_edit = panel.search_query_edit.lineEdit()
    
    # Configure spellchecker mock
    mw.spellchecker_manager.is_misspelled.side_effect = lambda word: word == "wrongword"
    
    # Check that styleSheet remains empty
    line_edit.setText("correct")
    panel.trigger_spellcheck()
    assert line_edit.styleSheet() == ""
    
    line_edit.setText("wrongword")
    panel.trigger_spellcheck()
    assert line_edit.styleSheet() == ""
    
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
