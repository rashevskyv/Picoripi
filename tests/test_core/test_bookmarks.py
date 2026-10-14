import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QMessageBox
from handlers.bookmark_handler import BookmarkHandler

class MockMainWindow:
    def __init__(self):
        self.bookmarks = []
        self.bookmarks_menu = MagicMock()
        self.add_bookmark_action = MagicMock()
        self.clear_bookmarks_action = MagicMock()
        # Bookmarks are stored in the project; each write is recorded here.
        self.global_saves = []
        self.settings_manager = MagicMock()
        self.settings_manager.save_settings.side_effect = (
            lambda *args, **kwargs: self.global_saves.append(args)
        )

        self.data_store = MagicMock()
        self.data_store.current_block_idx = 0
        self.data_store.current_string_idx = 5
        self.data_store.block_names = {"0": "test_block.json"}
        self.data_store.data = [["line 1", "line 2", "line 3", "line 4", "line 5", "Target text"]]

        self.list_selection_handler = MagicMock()
        self.selected_indices = []
        self.list_selection_handler.select_string_by_absolute_index.side_effect = self.selected_indices.append
        self.block_list_widget = MagicMock()
        self.block_switches = []
        self.block_list_widget.setCurrentItem.side_effect = self.block_switches.append

        # Mock project_manager
        self.project_manager = MagicMock()
        self.project_manager.project = MagicMock()
        self.project_manager.project.name = "Test Project"
        self.project_saves = []
        self.project_manager.save_settings_to_project.side_effect = self.project_saves.append

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
    with patch('PyQt6.QtWidgets.QInputDialog.getText') as mock_input:
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

        assert mock_mw.global_saves == []
        assert mock_mw.project_saves == [mock_mw]
        # Verify menu was cleared and updated
        assert mock_mw.bookmarks_menu.clear.called

def test_add_bookmark_cancelled(handler, mock_mw):
    with patch('PyQt6.QtWidgets.QInputDialog.getText') as mock_input:
        mock_input.return_value = ("My Custom Bookmark", False)

        handler.add_bookmark()

        # Verify no bookmark was added and nothing was written
        assert len(mock_mw.bookmarks) == 0
        assert mock_mw.global_saves == []
        assert mock_mw.project_saves == []

def test_clear_bookmarks(handler, mock_mw):
    mock_mw.bookmarks = [{"id": "1", "name": "B1"}]

    with patch('PyQt6.QtWidgets.QMessageBox.question') as mock_question:
        # User clicks No
        mock_question.return_value = QMessageBox.StandardButton.No
        handler.clear_bookmarks()
        assert len(mock_mw.bookmarks) == 1

        # User clicks Yes
        mock_question.return_value = QMessageBox.StandardButton.Yes
        handler.clear_bookmarks()
        assert len(mock_mw.bookmarks) == 0
        # Only the confirmed clear is written, and to the project only.
        assert mock_mw.global_saves == []
        assert mock_mw.project_saves == [mock_mw]


def test_add_bookmark_requires_project(handler, mock_mw):
    mock_mw.project_manager.project = None
    with patch("PyQt6.QtWidgets.QMessageBox.warning") as mock_warn:
        handler.add_bookmark()
    assert mock_warn.call_args.args[2] == 'Open a project before adding bookmarks.'
    assert mock_mw.bookmarks == []
    assert mock_mw.project_saves == []

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

    assert mock_mw.selected_indices == [10]
    assert mock_mw.block_switches == []

def test_jump_to_bookmark_different_project_warning(handler, mock_mw):
    mock_mw.bookmarks = [{
        "id": "b-id",
        "name": "B1",
        "project_name": "Other Project",
        "block_idx": 0,
        "string_idx": 10
    }]

    with patch('PyQt6.QtWidgets.QMessageBox.warning') as mock_warning:
        handler.jump_to_bookmark("b-id")
        assert mock_warning.call_args.args[2] == (
            "This bookmark belongs to project 'Other Project', "
            "but the currently active project is 'Test Project'."
        )
        assert mock_mw.selected_indices == []


def test_delete_bookmark_no(handler, mock_mw):
    mock_mw.bookmarks = [{"id": "b-id", "name": "B1"}]
    with patch('PyQt6.QtWidgets.QMessageBox.question') as mock_question:
        mock_question.return_value = QMessageBox.StandardButton.No
        handler.delete_bookmark("b-id")
        assert len(mock_mw.bookmarks) == 1
        assert mock_mw.global_saves == []
        assert mock_mw.project_saves == []


def test_delete_bookmark_yes(handler, mock_mw):
    mock_mw.bookmarks = [{"id": "b-id", "name": "B1"}]
    with patch('PyQt6.QtWidgets.QMessageBox.question') as mock_question:
        mock_question.return_value = QMessageBox.StandardButton.Yes
        handler.delete_bookmark("b-id")
        assert len(mock_mw.bookmarks) == 0
        assert mock_mw.global_saves == []
        assert mock_mw.project_saves == [mock_mw]
        assert mock_mw.bookmarks_menu.clear.called


def test_delete_bookmark_not_found(handler, mock_mw):
    mock_mw.bookmarks = [{"id": "b-id", "name": "B1"}]
    questions = []
    # Record any confirmation dialog; a missing id must not ask anything.
    with patch('PyQt6.QtWidgets.QMessageBox.question', side_effect=lambda *args: questions.append(args)):
        handler.delete_bookmark("other-id")
    assert questions == []
    assert len(mock_mw.bookmarks) == 1
