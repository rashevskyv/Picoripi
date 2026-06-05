import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QMessageBox
from handlers.bookmark_handler import BookmarkHandler

class MockMainWindow:
    def __init__(self):
        self.bookmarks = []
        self.bookmarks_menu = MagicMock()
        self.add_bookmark_action = MagicMock()
        self.clear_bookmarks_action = MagicMock()
        self.settings_manager = MagicMock()
        
        self.data_store = MagicMock()
        self.data_store.current_block_idx = 0
        self.data_store.current_string_idx = 5
        self.data_store.block_names = {"0": "test_block.json"}
        self.data_store.data = [["line 1", "line 2", "line 3", "line 4", "line 5", "Target text"]]
        
        self.list_selection_handler = MagicMock()
        self.block_list_widget = MagicMock()
        
        # Mock project_manager
        self.project_manager = MagicMock()
        self.project_manager.project = MagicMock()
        self.project_manager.project.name = "Test Project"

@pytest.fixture
def mock_mw():
    return MockMainWindow()

@pytest.fixture
def handler(mock_mw):
    dp = MagicMock()
    # Mock get_current_string_text
    dp.get_current_string_text.return_value = ("Target text", {})
    ui = MagicMock()
    return BookmarkHandler(mock_mw, dp, ui)

def test_add_bookmark_success(handler, mock_mw):
    with patch('PyQt5.QtWidgets.QInputDialog.getText') as mock_input:
        mock_input.return_value = ("My Custom Bookmark", True)
        
        handler.add_bookmark()
        
        # Verify bookmark was added
        assert len(mock_mw.bookmarks) == 1
        b = mock_mw.bookmarks[0]
        assert b["name"] == "My Custom Bookmark"
        assert b["block_idx"] == 0
        assert b["string_idx"] == 5
        assert b["project_name"] == "Test Project"
        assert b["block_name"] == "test_block.json"
        
        # Verify settings saved
        mock_mw.settings_manager.save_settings.assert_called_once()
        # Verify project settings saved since project is active
        mock_mw.project_manager.save_settings_to_project.assert_called_once_with(mock_mw)
        # Verify menu was cleared and updated
        assert mock_mw.bookmarks_menu.clear.called

def test_add_bookmark_cancelled(handler, mock_mw):
    with patch('PyQt5.QtWidgets.QInputDialog.getText') as mock_input:
        mock_input.return_value = ("My Custom Bookmark", False)
        
        handler.add_bookmark()
        
        # Verify no bookmark was added
        assert len(mock_mw.bookmarks) == 0
        mock_mw.settings_manager.save_settings.assert_not_called()

def test_clear_bookmarks(handler, mock_mw):
    mock_mw.bookmarks = [{"id": "1", "name": "B1"}]
    
    with patch('PyQt5.QtWidgets.QMessageBox.question') as mock_question:
        # User clicks No
        mock_question.return_value = QMessageBox.No
        handler.clear_bookmarks()
        assert len(mock_mw.bookmarks) == 1
        
        # User clicks Yes
        mock_question.return_value = QMessageBox.Yes
        handler.clear_bookmarks()
        assert len(mock_mw.bookmarks) == 0
        mock_mw.settings_manager.save_settings.assert_called_once()
        mock_mw.project_manager.save_settings_to_project.assert_called_once_with(mock_mw)

def test_jump_to_bookmark_same_block(handler, mock_mw):
    mock_mw.bookmarks = [{
        "id": "b-id",
        "name": "B1",
        "project_name": "Test Project",
        "block_idx": 0,
        "string_idx": 10
    }]
    
    # Block index is already 0, so no block switch needed
    mock_mw.data_store.current_block_idx = 0
    
    handler.jump_to_bookmark("b-id")
    
    mock_mw.list_selection_handler.select_string_by_absolute_index.assert_called_once_with(10)
    mock_mw.block_list_widget.setCurrentItem.assert_not_called()

def test_jump_to_bookmark_different_project_warning(handler, mock_mw):
    mock_mw.bookmarks = [{
        "id": "b-id",
        "name": "B1",
        "project_name": "Other Project",
        "block_idx": 0,
        "string_idx": 10
    }]
    
    with patch('PyQt5.QtWidgets.QMessageBox.warning') as mock_warning:
        handler.jump_to_bookmark("b-id")
        mock_warning.assert_called_once()
        mock_mw.list_selection_handler.select_string_by_absolute_index.assert_not_called()


def test_delete_bookmark_no(handler, mock_mw):
    mock_mw.bookmarks = [{"id": "b-id", "name": "B1"}]
    with patch('PyQt5.QtWidgets.QMessageBox.question') as mock_question:
        mock_question.return_value = QMessageBox.No
        handler.delete_bookmark("b-id")
        assert len(mock_mw.bookmarks) == 1
        mock_mw.settings_manager.save_settings.assert_not_called()


def test_delete_bookmark_yes(handler, mock_mw):
    mock_mw.bookmarks = [{"id": "b-id", "name": "B1"}]
    with patch('PyQt5.QtWidgets.QMessageBox.question') as mock_question:
        mock_question.return_value = QMessageBox.Yes
        handler.delete_bookmark("b-id")
        assert len(mock_mw.bookmarks) == 0
        mock_mw.settings_manager.save_settings.assert_called_once()
        mock_mw.project_manager.save_settings_to_project.assert_called_once_with(mock_mw)
        assert mock_mw.bookmarks_menu.clear.called


def test_delete_bookmark_not_found(handler, mock_mw):
    mock_mw.bookmarks = [{"id": "b-id", "name": "B1"}]
    with patch('PyQt5.QtWidgets.QMessageBox.question') as mock_question:
        handler.delete_bookmark("other-id")
        mock_question.assert_not_called()
        assert len(mock_mw.bookmarks) == 1

