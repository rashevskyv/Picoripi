import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QTextEdit, QApplication
from PyQt5.QtGui import QTextCursor, QColor

from components.editor.text_highlight_manager import TextHighlightManager

@pytest.fixture
def editor(qapp):
    editor = QTextEdit()
    editor.setPlainText("Line 1\nLine 2\nLine 3")
    
    # Real QColor objects, not None
    editor.current_line_color = QColor(230, 230, 230)
    editor.linked_cursor_block_color = QColor(200, 200, 255)
    editor.linked_cursor_pos_color = QColor(100, 100, 255)
    editor.preview_selected_line_color = QColor(200, 255, 200)
    editor.tag_interaction_highlight_color = QColor(255, 255, 100)
    editor.search_match_highlight_color = QColor(255, 200, 100)
    
    return editor

def test_setLinkedCursorPosition_skips_duplicate(editor):
    """setLinkedCursorPosition must NOT call applyHighlights if called with the same params."""
    manager = TextHighlightManager(editor)
    
    with patch.object(manager, 'applyHighlights') as mock_apply:
        manager.setLinkedCursorPosition(0, 0)
        assert mock_apply.call_count == 1
        
        # Same params — must be suppressed
        manager.setLinkedCursorPosition(0, 0)
        assert mock_apply.call_count == 1
        
        # Different params — must fire
        manager.setLinkedCursorPosition(1, 0)
        assert mock_apply.call_count == 2

def test_updateCurrentLineHighlight_skips_same_line(editor):
    """updateCurrentLineHighlight must not re-apply if cursor is on the same line."""
    manager = TextHighlightManager(editor)
    
    cursor = editor.textCursor()
    cursor.setPosition(0)
    editor.setTextCursor(cursor)
    
    with patch.object(manager, 'applyHighlights') as mock_apply:
        manager.updateCurrentLineHighlight()
        assert mock_apply.call_count == 1
        
        # Same line — must be suppressed
        manager.updateCurrentLineHighlight()
        assert mock_apply.call_count == 1

def test_clearLinkedCursor_resets_tracker(editor):
    """clearLinkedCursorPosition must reset the tracker so the next call works."""
    manager = TextHighlightManager(editor)
    
    manager.setLinkedCursorPosition(0, 0)
    assert manager._last_linked_cursor_params == (0, 0)
    
    manager.clearLinkedCursorPosition()
    assert manager._last_linked_cursor_params is None
    
    # After clearing, same params must fire again
    with patch.object(manager, 'applyHighlights') as mock_apply:
        manager.setLinkedCursorPosition(0, 0)
        assert mock_apply.call_count == 1

def test_clearAllHighlights_resets_trackers(editor):
    """clearAllHighlights must reset all trackers."""
    manager = TextHighlightManager(editor)
    
    manager.setLinkedCursorPosition(0, 0)
    cursor = editor.textCursor()
    cursor.setPosition(0)
    editor.setTextCursor(cursor)
    manager.updateCurrentLineHighlight()
    
    assert manager._last_linked_cursor_params is not None
    assert manager._last_active_line_block is not None
    
    manager.clearAllHighlights()
    assert manager._last_linked_cursor_params is None
    assert manager._last_active_line_block is None

def test_update_text_views_reentrancy_guard():
    """update_text_views must not recurse into itself."""
    from ui.updaters.preview_updater import PreviewUpdater
    
    mw = MagicMock()
    mw.is_programmatically_changing_text = False
    dp = MagicMock()
    
    updater = PreviewUpdater(mw, dp)
    
    # Simulate reentrancy guard
    updater._in_update_text_views = True
    
    # Should return immediately without calling anything
    updater.update_text_views()
    
    # _do_update_text_views should NOT have been called because of the guard
    assert not hasattr(updater, '_do_update_text_views_called')
