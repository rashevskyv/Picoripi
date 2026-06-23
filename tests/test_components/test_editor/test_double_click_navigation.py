import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtCore import Qt, QPoint, QPointF, QEvent

from components.editor.line_number_area import LineNumberArea
from components.editor.line_numbered_text_edit import LineNumberedTextEdit
from components.editor.mouse_handlers import LNETMouseHandlers
from handlers.list_selection_handler import ListSelectionHandler


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_line_number_area_double_click(app):
    """Test that double clicking on LineNumberArea calls handle_line_number_double_click on codeEditor."""
    real_widget = QWidget()
    area = LineNumberArea(real_widget)
    
    mock_editor = MagicMock()
    area.codeEditor = mock_editor
    
    # Simulate double click
    event = QMouseEvent(
        QEvent.Type.MouseButtonDblClick,
        QPointF(5.0, 10.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    
    area.mouseDoubleClickEvent(event)
    mock_editor.handle_line_number_double_click.assert_called_once_with(10)



def test_line_numbered_text_edit_double_click_delegation(app):
    """Test that LineNumberedTextEdit delegates double click to mouse_handler."""
    editor = LineNumberedTextEdit()
    editor.mouse_handler = MagicMock()
    
    editor.handle_line_number_double_click(15)
    editor.mouse_handler.handle_line_number_double_click.assert_called_once_with(15)


def test_mouse_handlers_double_click_trigger(app):
    """Test that LNETMouseHandlers double click calls scroll_to_current_string_in_preview on list_selection_handler."""
    mock_editor = MagicMock()
    mock_window = MagicMock()
    mock_editor.window.return_value = mock_window
    
    handler = LNETMouseHandlers(mock_editor)
    
    handler.handle_line_number_double_click(20)
    mock_window.list_selection_handler.scroll_to_current_string_in_preview.assert_called_once()


def test_scroll_to_current_string_in_preview_logic(app):
    """Test the core logic of scroll_to_current_string_in_preview in ListSelectionHandler."""
    mock_mw = MagicMock()
    mock_ds = MagicMock()
    mock_mw.data_store = mock_ds
    
    # Setup data store mock
    mock_ds.current_string_idx = 42
    mock_ds.displayed_string_indices = [10, 20, 42, 50]
    
    # Setup preview_text_edit mock
    mock_preview = MagicMock()
    mock_doc = MagicMock()
    mock_block = MagicMock()
    
    mock_preview.document.return_value = mock_doc
    mock_doc.blockCount.return_value = 100
    mock_doc.findBlockByNumber.return_value = mock_block
    mock_block.isValid.return_value = True
    
    mock_mw.preview_text_edit = mock_preview
    
    # Initialize handler
    handler = ListSelectionHandler(mock_mw, MagicMock(), MagicMock())
    handler._cursor_visible_timer = MagicMock()
    
    with patch("handlers.list_selection_handler.QTextCursor") as mock_cursor_class:
        
        mock_cursor = MagicMock()
        mock_cursor_class.return_value = mock_cursor
        
        handler.scroll_to_current_string_in_preview()
        
        # Verify preview text edit highlights and cursors are updated
        mock_doc.findBlockByNumber.assert_called_once_with(2)  # 42 is at index 2 in displayed_string_indices
        mock_cursor_class.assert_called_once_with(mock_block)
        mock_preview.setTextCursor.assert_called_once_with(mock_cursor)
        mock_preview.set_selected_lines.assert_called_once_with([2])
        handler._cursor_visible_timer.start.assert_called_once_with(10)

