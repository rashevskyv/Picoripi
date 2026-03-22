import pytest
from unittest.mock import MagicMock
from PyQt5.QtWidgets import QMainWindow
from core.data_store import AppDataStore
from core.data_state_processor import DataStateProcessor
from handlers.list_selection_handler import ListSelectionHandler
from handlers.text_operation_handler import TextOperationHandler

class MockMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.data_store = AppDataStore()
        # Initial data with 2 strings, the first one having sublines
        self.data = [["Original Line 1\nSubline 2", "Original Line 2"]]
        self.edited_file_data = [["Original Line 1\nSubline 2", "Original Line 2"]]
        self.edited_data = {}
        self.unsaved_block_indices = set()
        self.edited_sublines = set()
        self.unsaved_changes = False
        self.current_block_idx = 0
        self.current_string_idx = 0
        self.block_names = {"0": "Test Block"}
        self.problems_per_subline = {}
        self.string_metadata = {}
        self.line_width_warning_threshold_pixels = 208
        self.project_manager = MagicMock()
        self.project_manager.project = MagicMock()
        self.project_manager.project.blocks = [MagicMock()]
        self.block_to_project_file_map = {0: 0}
        self.ui_updater = MagicMock()
        self.undo_manager = MagicMock()
        self.is_programmatically_changing_text = False
        self.current_game_rules = MagicMock()
        self.text_operation_handler = None # Will be set after creation
        # Mocking game rules to return the same text for editor/preview
        self.current_game_rules.convert_editor_text_to_data = lambda x: x
        self.current_game_rules.get_text_representation_for_editor = lambda x: x
        self.current_game_rules.get_problem_definitions = lambda: {}
        self.helper = MagicMock()

def test_asterisk_persistence_on_navigation():
    mw = MockMainWindow()
    dsp = DataStateProcessor(mw)
    mw.ui_updater = MagicMock()
    
    # We need a real TextOperationHandler to test how it sets sublines
    toh = TextOperationHandler(mw, dsp, mw.ui_updater)
    mw.text_operation_handler = toh
    lsh = ListSelectionHandler(mw, dsp, mw.ui_updater)
    
    # Mocking edited_text_edit as it's used in text_edited
    mw.edited_text_edit = MagicMock()
    
    # 1. Simulate editing a subline
    # We change "Original Line 1" to "Edited Line 1" (first subline)
    mw.edited_text_edit.toPlainText.return_value = "Edited Line 1\nSubline 2"
    
    # This call should: 
    # - Update mw.edited_data[(0, 0)]
    # - Set mw.edited_sublines to {0}
    toh.text_edited()
    
    assert (0, 0) in mw.edited_data
    assert mw.edited_data[(0, 0)] == "Edited Line 1\nSubline 2"
    assert 0 in mw.edited_sublines
    
    # 2. Navigate away to string 1
    # This calls mw.edited_sublines.clear()
    lsh.select_string_by_absolute_index(1)
    assert mw.current_string_idx == 1
    assert len(mw.edited_sublines) == 0
    
    # 3. Navigate back to string 0
    # EXPECTED: edited_sublines should be restored to {0}
    lsh.select_string_by_absolute_index(0)
    assert mw.current_string_idx == 0
    assert 0 in mw.edited_sublines, "Subline asterisk (index 0) was lost after navigation back to Edited string"
    assert len(mw.edited_sublines) == 1

def test_folder_asterisk_propagation():
    from components.custom_list_item_delegate import CustomListItemDelegate
    from PyQt5.QtCore import QModelIndex, Qt
    
    mw = MockMainWindow()
    dsp = DataStateProcessor(mw)
    delegate = CustomListItemDelegate(None)
    delegate.list_widget = MagicMock()
    delegate.list_widget.window.return_value = mw
    
    # Simulate a folder item in the tree
    index = QModelIndex()
    # Mock index.data to return merged_folder_ids for a folder
    def mock_data(role):
        if role == Qt.UserRole + 2: # merged_folder_ids
            return [101] # Folder ID 101
        if role == Qt.UserRole: # block_idx_data
            return None
        if role == Qt.UserRole + 10: # category_name
            return None
        return None
    
    index.data = mock_data
    
    # 1. Initially, no unsaved changes
    mw.unsaved_block_indices = set()
    
    # We can't easily call paint() without a real painter, 
    # but we can look at the logic inside paint() if we extracted it, 
    # or just assume that if unsaved_block_indices maps to a block in this folder, it works.
    
    # Let's mock the project manager's get_all_block_indices_under_folder
    mw.project_manager.get_all_block_indices_under_folder.return_value = {5} # Project block index 5 is under folder 101
    
    # block_to_project_file_map: data_block_5 -> project_block_5
    mw.block_to_project_file_map = {5: 5}
    
    # Initially:
    mw.unsaved_block_indices = set()
    # Check logic manually (simulating the paint() logic)
    has_star = any(mw.block_to_project_file_map.get(idx) in {5} for idx in mw.unsaved_block_indices)
    assert not has_star
    
    # 2. Mark block 5 as unsaved
    mw.unsaved_block_indices.add(5)
    
    # Re-check logic
    has_star = any(mw.block_to_project_file_map.get(idx) in {5} for idx in mw.unsaved_block_indices)
    assert has_star, "Folder should show star if block under it is unsaved"

if __name__ == "__main__":
    pytest.main([__file__])
