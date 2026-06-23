import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QMessageBox, QInputDialog
from PyQt6.QtCore import Qt
from handlers.bookmark_handler import BookmarkHandler

@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.data_store = MagicMock()
    mw.data_store.current_block_idx = 0
    mw.data_store.current_string_idx = 5
    mw.data_store.block_names = {"0": "Block 0"}
    
    mw.bookmarks = []
    mw.settings_manager = MagicMock()
    mw.project_manager = MagicMock()
    mw.block_list_widget = MagicMock()
    mw.list_selection_handler = MagicMock()
    mw.bookmarks_menu = MagicMock()
    mw.add_bookmark_action = MagicMock()
    mw.clear_bookmarks_action = MagicMock()
    
    return mw

def test_bookmark_handler_init(mock_mw):
    handler = BookmarkHandler(mock_mw, MagicMock(), MagicMock())
    assert handler._pending_jump_string_idx is None

def test_bookmark_handler_add_bookmark_invalid(mock_mw):
    mock_mw.data_store.current_block_idx = -1
    handler = BookmarkHandler(mock_mw, MagicMock(), MagicMock())
    with patch.object(QMessageBox, 'warning') as mock_warn:
        handler.add_bookmark()
        mock_warn.assert_called_once()

def test_bookmark_handler_add_bookmark_success(mock_mw):
    data_processor = MagicMock()
    data_processor.get_current_string_text.return_value = ("Test line content", None)
    
    handler = BookmarkHandler(mock_mw, data_processor, MagicMock())
    
    # Mock QInputDialog
    with patch.object(QInputDialog, 'getText', return_value=("My Bookmark", True)) as mock_input:
        handler.add_bookmark()
        mock_input.assert_called_once()
        assert len(mock_mw.bookmarks) == 1
        assert mock_mw.bookmarks[0]["name"] == "My Bookmark"
        assert mock_mw.bookmarks[0]["block_idx"] == 0
        assert mock_mw.bookmarks[0]["string_idx"] == 5
        mock_mw.settings_manager.save_settings.assert_called_once()

def test_bookmark_handler_jump_to_bookmark_same_block(mock_mw):
    mock_mw.bookmarks = [{
        "id": "b1",
        "name": "B1",
        "block_idx": 0,
        "string_idx": 10
    }]
    
    handler = BookmarkHandler(mock_mw, MagicMock(), MagicMock())
    handler.jump_to_bookmark("b1")
    mock_mw.list_selection_handler.select_string_by_absolute_index.assert_called_with(10)

def test_bookmark_handler_jump_to_bookmark_diff_block(mock_mw):
    mock_mw.data_store.current_block_idx = 1
    mock_mw.bookmarks = [{
        "id": "b1",
        "name": "B1",
        "block_idx": 0,
        "string_idx": 10
    }]
    
    mock_item = MagicMock()
    mock_item.data.side_effect = lambda col, role: 0 if role == Qt.UserRole else None
    
    handler = BookmarkHandler(mock_mw, MagicMock(), MagicMock())
    
    with patch('handlers.bookmark_handler.QTreeWidgetItemIterator') as mock_iterator:
        mock_iter_val = MagicMock()
        mock_iterator.return_value = mock_iter_val
        
        # Iterator yields mock_item, then None
        vals = [mock_item, None]
        v_idx = 0
        mock_iter_val.value.side_effect = lambda: vals[v_idx] if v_idx < len(vals) else None
        
        def advance(other):
            nonlocal v_idx
            v_idx += 1
            return mock_iter_val
        mock_iter_val.__iadd__.side_effect = advance
        
        handler.jump_to_bookmark("b1")
        
        mock_mw.block_list_widget.setCurrentItem.assert_called_with(mock_item)
        assert handler._pending_jump_string_idx == 10

def test_bookmark_handler_on_jump_timer_timeout(mock_mw):
    handler = BookmarkHandler(mock_mw, MagicMock(), MagicMock())
    handler._pending_jump_string_idx = 15
    handler._on_jump_timer_timeout()
    mock_mw.list_selection_handler.select_string_by_absolute_index.assert_called_with(15)
    assert handler._pending_jump_string_idx is None

def test_bookmark_handler_clear_bookmarks(mock_mw):
    mock_mw.bookmarks = [{"id": "b1"}]
    handler = BookmarkHandler(mock_mw, MagicMock(), MagicMock())
    
    with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
        handler.clear_bookmarks()
        assert mock_mw.bookmarks == []
        mock_mw.settings_manager.save_settings.assert_called_once()

def test_bookmark_handler_delete_bookmark(mock_mw):
    mock_mw.bookmarks = [{"id": "b1", "name": "B1"}, {"id": "b2", "name": "B2"}]
    handler = BookmarkHandler(mock_mw, MagicMock(), MagicMock())
    
    with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
        handler.delete_bookmark("b1")
        assert len(mock_mw.bookmarks) == 1
        assert mock_mw.bookmarks[0]["id"] == "b2"

def test_bookmark_handler_update_bookmarks_menu(mock_mw):
    mock_mw.bookmarks = [{"id": "b1", "name": "B1", "block_name": "Block 0", "string_idx": 0}]
    handler = BookmarkHandler(mock_mw, MagicMock(), MagicMock())
    handler.update_bookmarks_menu()
    
    mock_mw.bookmarks_menu.clear.assert_called_once()
    mock_mw.bookmarks_menu.addAction.assert_called()
    mock_mw.bookmarks_menu.addMenu.assert_called_with("Delete Bookmark")
