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

def test_trigger_advanced_search_with_panel(qapp):
    """Test that trigger_advanced_search correctly retrieves parameters from search_panel_widget and calls open_advanced_search."""
    mock_main_window = MagicMock()
    mock_main_window.helper = MagicMock()
    
    # Mock search_panel_widget
    mock_panel = MagicMock()
    mock_panel.get_search_parameters.return_value = ("test_query", True, True, False, True)
    mock_main_window.search_panel_widget = mock_panel
    
    from ui.main_window.main_window_helper import MainWindowHelper
    
    helper = MainWindowHelper(mock_main_window)
    # Mock the open_advanced_search method on helper
    helper.open_advanced_search = MagicMock()
    
    helper.trigger_advanced_search()
    
    # Verify open_advanced_search was called with the correct parameters retrieved from the panel
    helper.open_advanced_search.assert_called_once_with("test_query", True, True, False, True)

def test_trigger_advanced_search_without_panel(qapp):
    """Test that trigger_advanced_search uses default parameters when search_panel_widget is missing."""
    mock_main_window = MagicMock()
    mock_main_window.search_panel_widget = None
    
    from ui.main_window.main_window_helper import MainWindowHelper
    
    helper = MainWindowHelper(mock_main_window)
    helper.open_advanced_search = MagicMock()
    
    helper.trigger_advanced_search()
    
    # Verify open_advanced_search was called with default parameters
    helper.open_advanced_search.assert_called_once_with("", False, False, True, False)

def test_open_advanced_search_no_matches_opens_dialog(qapp):
    """Test that open_advanced_search opens SearchReviewDialog even when there are no matches for the query."""
    from unittest.mock import patch
    mock_main_window = MagicMock()
    mock_main_window.data_store.data = [["Some original text"]]
    mock_main_window.data_store.edited_data = {}
    mock_main_window.data_store.current_block_idx = 0
    mock_main_window.active_search_dialog = None  # prevent MagicMock auto-attribute from being truthy
    
    # Mock data processor text retrieval
    mock_main_window.data_processor.get_current_string_text.return_value = ("Some original text", None)
    
    from ui.main_window.main_window_helper import MainWindowHelper
    helper = MainWindowHelper(mock_main_window)
    
    # Patch SearchReviewDialog and QMessageBox
    with patch('dialogs.search_review_dialog.SearchReviewDialog') as mock_dialog_class, \
         patch('PyQt6.QtWidgets.QMessageBox.information') as mock_info:
         
        mock_dialog_inst = MagicMock()
        mock_dialog_class.return_value = mock_dialog_inst
        mock_dialog_inst.exec.return_value = False  # just close
        
        # Query that has no matches (e.g. "non_existent")
        helper.open_advanced_search("non_existent", False, False, True, False)
        
        # QMessageBox should NOT be called
        mock_info.assert_not_called()
        
        # SearchReviewDialog should be instantiated and shown
        mock_dialog_class.assert_called_once()
        mock_dialog_inst.show.assert_called_once()

def test_search_review_dialog_jump_to_item_with_modifier(qapp):
    """Test that jump_to_item_from_list always navigates and show_current_item is called with from_click=True."""
    from unittest.mock import patch
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QMainWindow
    from dialogs.search_review_dialog import SearchReviewDialog
    
    class MockMainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.data_store = MagicMock()
            self.data_store.data = [["Text"]]
            self.data_store.current_block_idx = 0
            self.data_store.current_string_idx = 0
            self.data_processor = MagicMock()
            self.ui_updater = MagicMock()
            
    mw = MockMainWindow()
    
    # Instantiate the dialog
    dialog = SearchReviewDialog(
        mw, 
        text="Line 1\nLine 2", 
        query="Line", 
        line_numbers=[0, 1], 
        block_indices=[0, 0]
    )
    dialog.find_matches()
    
    dialog._navigate_to_block_and_string = MagicMock()
    dialog.clear_current_item_highlight = MagicMock()
    dialog.show_current_item = MagicMock()
    
    # Mock item and its row
    mock_item = MagicMock()
    dialog.matches_list.row = MagicMock(return_value=1)
    
    with patch('PyQt6.QtWidgets.QApplication.keyboardModifiers', return_value=Qt.KeyboardModifier.NoModifier):
        dialog.jump_to_item_from_list(mock_item)
    
    # Navigate should be called and show_current_item should be called with from_click=True
    dialog._navigate_to_block_and_string.assert_called_once_with(0, 1)
    dialog.show_current_item.assert_called_once_with(from_click=True)

def test_maybe_edit_prompt_with_ctypes_ctrl_pressed(qapp):
    """Test that _maybe_edit_prompt triggers PromptEditorDialog when Ctrl key is pressed via ctypes."""
    from unittest.mock import patch
    from PyQt6.QtWidgets import QMainWindow
    from handlers.translation_handler import TranslationHandler
    
    mw = QMainWindow()
    mw.prompt_editor_enabled = False
    
    handler = TranslationHandler(mw, MagicMock(), MagicMock())
    
    with patch('ctypes.windll.user32.GetAsyncKeyState') as mock_get_async_key_state, \
         patch('ctypes.windll.user32.GetKeyState') as mock_get_key_state, \
         patch('handlers.translation_handler.PromptEditorDialog') as mock_dialog_class:
         
        # Simulate Ctrl is pressed (high-order bit set)
        mock_get_async_key_state.return_value = 0x8000
        mock_get_key_state.return_value = 0
        
        mock_dialog_inst = MagicMock()
        mock_dialog_class.return_value = mock_dialog_inst
        mock_dialog_inst.exec.return_value = 0 # rejected/cancelled
        
        result = handler._maybe_edit_prompt(
            title="Test",
            system_prompt="sys",
            user_prompt="user"
        )
        
        mock_get_async_key_state.assert_called_once_with(0x11)
        mock_dialog_class.assert_called_once()
        assert result is None

def test_search_review_dialog_jump_to_item_with_ctrl_or_shift(qapp):
    """Test that jump_to_item_from_list does NOT navigate when Ctrl or Shift modifiers are held."""
    from unittest.mock import patch
    from PyQt6.QtWidgets import QMainWindow
    from dialogs.search_review_dialog import SearchReviewDialog
    from PyQt6.QtCore import Qt
    
    class MockMainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.data_store = MagicMock()
            self.data_store.data = [["Text"]]
            self.data_store.current_block_idx = 0
            self.data_store.current_string_idx = 0
            self.data_processor = MagicMock()
            self.ui_updater = MagicMock()
            
    mw = MockMainWindow()
    
    dialog = SearchReviewDialog(
        mw, 
        text="Line 1\nLine 2", 
        query="Line", 
        line_numbers=[0, 1], 
        block_indices=[0, 0]
    )
    dialog.find_matches()
    
    dialog._navigate_to_block_and_string = MagicMock()
    dialog.clear_current_item_highlight = MagicMock()
    dialog.show_current_item = MagicMock()
    
    mock_item = MagicMock()
    dialog.matches_list.row = MagicMock(return_value=1)
    
    # Patch keyboardModifiers to simulate Ctrl key pressed
    with patch('PyQt6.QtWidgets.QApplication.keyboardModifiers', return_value=Qt.KeyboardModifier.ControlModifier):
        dialog.jump_to_item_from_list(mock_item)
        
    # Verify that navigation and highlight clearing were NOT called
    dialog._navigate_to_block_and_string.assert_not_called()
    dialog.show_current_item.assert_not_called()
    
    # Patch keyboardModifiers to simulate Shift key pressed
    dialog._navigate_to_block_and_string.reset_mock()
    dialog.show_current_item.reset_mock()
    with patch('PyQt6.QtWidgets.QApplication.keyboardModifiers', return_value=Qt.KeyboardModifier.ShiftModifier):
        dialog.jump_to_item_from_list(mock_item)
        
    dialog._navigate_to_block_and_string.assert_not_called()
    dialog.show_current_item.assert_not_called()






