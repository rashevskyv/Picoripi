import pytest
from PyQt6 import sip
from PyQt6.QtWidgets import QMainWindow, QTreeWidget, QTreeWidgetItem
from dialogs.search_review_dialog import SearchReviewDialog
from handlers.list_selection_handler import ListSelectionHandler
from ui.updaters.block_list_updater import BlockListUpdater
from unittest.mock import MagicMock

def test_SearchReviewDialog_save_changes_calls_mark_dirty(qapp):
    """Test that SearchReviewDialog.save_changes_to_project calls data_store.mark_dirty."""
    mock_main_window = MagicMock()
    mock_main_window.data_store.data = [["Original string"]]
    mock_main_window.data_store.edited_data = {}
    mock_main_window.data_store.current_block_idx = 0
    mock_main_window.data_store.current_string_idx = 0
    
    def get_text(b, s):
        return "Original string", None
        
    mock_main_window.data_processor.get_current_string_text.side_effect = get_text
    mock_main_window.undo_manager = None
    mock_main_window.ui_updater = MagicMock()
    
    # We must use MockMainWindow to satisfy parent checks
    class MockMainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.data_store = mock_main_window.data_store
            self.data_processor = mock_main_window.data_processor
            self.undo_manager = None
            self.project_manager = MagicMock()
            self.ui_updater = mock_main_window.ui_updater
            self.text_operation_handler = MagicMock()
            
    mw = MockMainWindow()
    
    dialog = SearchReviewDialog(mw, "Original string", "Original", line_numbers=[0], block_indices=[0])
    dialog.find_matches()
    dialog.pre_highlight_all_matches()
    
    # Change replacement text and replace
    dialog.replace_input.setText("New string")
    dialog.replace_match()
    
    # Trigger save_changes_to_project
    dialog.save_changes_to_project()
    
    # Verify that data_store.mark_dirty was called instead of project_manager.mark_block_unsaved
    mw.data_store.mark_dirty.assert_called_once_with(0)
    mw.project_manager.mark_block_unsaved.assert_not_called()

def test_list_selection_handler_block_selected_handles_deleted_items(qapp):
    """Test that list_selection_handler.block_selected safely returns when items are C++ deleted."""
    mock_main_window = MagicMock()
    mock_main_window.is_loading_data = False
    mock_main_window.data_store.current_block_idx = -1
    
    handler = ListSelectionHandler(mock_main_window, MagicMock(), MagicMock())
    handler._restoring_selection = False
    
    # Create Qt objects and delete them
    tree = QTreeWidget()
    current_item = QTreeWidgetItem(tree)
    previous_item = QTreeWidgetItem(tree)
    
    sip.delete(current_item)
    sip.delete(previous_item)
    
    # This should not raise "RuntimeError: wrapped C/C++ object has been deleted"
    handler.block_selected(current_item, previous_item)

def test_tree_folder_mixin_delete_folder_by_id_handles_deleted_item(qapp):
    """Test that TreeFolderMixin._delete_folder_by_id safely returns when item is C++ deleted."""
    from components.tree_folder_mixin import TreeFolderMixin
    
    class DummyTreeWidget(QTreeWidget, TreeFolderMixin):
        def __init__(self):
            super().__init__()
            self._mw = MagicMock()
            
        def window(self):
            return self._mw
            
    tree = DummyTreeWidget()
    item = QTreeWidgetItem(tree)
    
    # Setup mock project action handler
    mock_pah = MagicMock()
    # Mock delete_block_action to delete the QTreeWidgetItem under the hood
    def delete_action():
        sip.delete(item)
    mock_pah.delete_block_action.side_effect = delete_action
    tree._mw.project_action_handler = mock_pah
    
    # Try deleting the folder by id
    # This should not raise RuntimeError even when item is deleted inside delete_block_action
    tree._delete_folder_by_id(item, "some_folder_id")
