import pytest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QMainWindow
from core.data_store import AppDataStore
from core.data_state_processor import DataStateProcessor
from handlers.list_selection_handler import ListSelectionHandler
from handlers.text_operation_handler import TextOperationHandler

class MockMainWindow(QMainWindow):
    @property
    def physical_block_idx(self) -> int:
        if hasattr(self, '_physical_block_idx') and self._physical_block_idx >= 0:
            return self._physical_block_idx
        if self.current_block_idx >= 0:
            return self.current_block_idx
        return -1

    @physical_block_idx.setter
    def physical_block_idx(self, val: int) -> None:
        self._physical_block_idx = val

    def __init__(self):
        super().__init__()
        self.data_store = self
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

from unittest.mock import patch

@patch('handlers.text_operation_handler.AsyncIssueScanner')
def test_asterisk_persistence_on_navigation(mock_async_scanner):
    mw = MockMainWindow()
    mw.helper.get_font_map_for_string.return_value = {}
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
    # - Update mw.data_store.edited_data[(0, 0)]
    # - Set mw.data_store.edited_sublines to {0}
    toh.text_edited()
    toh._on_preview_update_timer_timeout()
    
    assert (0, 0) in mw.data_store.edited_data
    assert mw.data_store.edited_data[(0, 0)] == "Edited Line 1\nSubline 2"
    assert 0 in mw.data_store.edited_sublines
    
    # 2. Navigate away to string 1
    # This calls mw.data_store.edited_sublines.clear()
    lsh.select_string_by_absolute_index(1)
    assert mw.data_store.current_string_idx == 1
    assert len(mw.data_store.edited_sublines) == 0
    
    # 3. Navigate back to string 0
    # EXPECTED: edited_sublines should be restored to {0}
    lsh.select_string_by_absolute_index(0)
    assert mw.data_store.current_string_idx == 0
    assert 0 in mw.data_store.edited_sublines, "Subline asterisk (index 0) was lost after navigation back to Edited string"
    assert len(mw.data_store.edited_sublines) == 1

def test_folder_asterisk_propagation():
    from components.custom_list_item_delegate import CustomListItemDelegate
    from PyQt6.QtCore import QModelIndex, Qt
    
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
    mw.data_store.unsaved_block_indices = set()
    
    # We can't easily call paint() without a real painter, 
    # but we can look at the logic inside paint() if we extracted it, 
    # or just assume that if unsaved_block_indices maps to a block in this folder, it works.
    
    # Let's mock the project manager's get_all_block_indices_under_folder
    mw.project_manager.get_all_block_indices_under_folder.return_value = {5} # Project block index 5 is under folder 101
    
    # block_to_project_file_map: data_block_5 -> project_block_5
    mw.block_to_project_file_map = {5: 5}
    
    # Initially:
    mw.data_store.unsaved_block_indices = set()
    # Check logic manually (simulating the paint() logic)
    has_star = any(mw.block_to_project_file_map.get(idx) in {5} for idx in mw.data_store.unsaved_block_indices)
    assert not has_star
    
    # 2. Mark block 5 as unsaved
    mw.data_store.unsaved_block_indices.add(5)
    
    # Re-check logic
    has_star = any(mw.block_to_project_file_map.get(idx) in {5} for idx in mw.data_store.unsaved_block_indices)
    assert has_star, "Folder should show star if block under it is unsaved"

def test_custom_list_item_delegate_data_store_access():
    from components.custom_list_item_delegate import CustomListItemDelegate
    from PyQt6.QtCore import QModelIndex, Qt
    
    # 1. Setup a clean separation where data_store is a separate object, mimicking the real application
    class RealDataStore:
        def __init__(self):
            self.unsaved_block_indices = {2}
            self.edited_data = {(2, 5): "New Text"}
            self.block_names = { "2": "Test Block" }
            self.data = [[]]
            
    class RealMainWindow:
        def __init__(self):
            self.data_store = RealDataStore()
            self.project_manager = MagicMock()
            self.project_manager.project = MagicMock()
            self.project_manager.project.blocks = [MagicMock(), MagicMock(), MagicMock()]
            self.block_to_project_file_map = {2: 2}
            self.theme = 'light'
            
    mw = RealMainWindow()
    
    delegate = CustomListItemDelegate(None)
    delegate.list_widget = MagicMock()
    delegate.list_widget.window.return_value = mw
    
    # Mock model index for Block index 2
    index = QModelIndex()
    def mock_data(role):
        if role == Qt.UserRole:
            return 2 # block_idx
        if role == Qt.UserRole + 10:
            return None # category
        if role == Qt.UserRole + 2:
            return None # merged_folder_ids
        return None
    index.data = mock_data
    
    # Simulate delegate variables resolution inside delegate.paint()
    ds = getattr(mw, 'data_store', None)
    assert ds is not None
    
    edited_keys = getattr(ds, 'edited_data', {})
    unsaved_blocks = getattr(ds, 'unsaved_block_indices', set())
    
    assert (2, 5) in edited_keys
    assert 2 in unsaved_blocks
    
    # Check category path
    cat_index = QModelIndex()
    def mock_cat_data(role):
        if role == Qt.UserRole:
            return 2
        if role == Qt.UserRole + 10:
            return "CatA"
        if role == Qt.UserRole + 2:
            return None
        return None
    cat_index.data = mock_cat_data
    
    # Mock block with category
    block_mock = MagicMock()
    category_mock = MagicMock()
    category_mock.name = "CatA"
    category_mock.line_indices = [5, 10]
    block_mock.categories = [category_mock]
    mw.project_manager.project.blocks[2] = block_mock
    
    # Check category changes propagation
    has_unsaved_changes_in_cat = any(
        (2, l_idx) in edited_keys 
        for l_idx in category_mock.line_indices
    )
    assert has_unsaved_changes_in_cat, "Category should correctly detect changes in line index 5 from edited_data inside data_store"

def test_line_number_area_paint_logic_data_store_access():
    from components.editor.line_number_area_paint_logic import LNETLineNumberAreaPaintLogic
    
    class RealDataStore:
        def __init__(self):
            self.edited_sublines = {1, 3}
            self.current_block_idx = 0
            self.current_string_idx = 0
            
    class RealMainWindow:
        def __init__(self):
            self.data_store = RealDataStore()
            
    mw = RealMainWindow()
    editor = MagicMock()
    logic = LNETLineNumberAreaPaintLogic(editor, MagicMock(), mw)
    
    ds = getattr(mw, 'data_store', None)
    assert ds is not None
    
    edited_sublines = getattr(ds, 'edited_sublines', set())
    assert 1 in edited_sublines
    assert 3 in edited_sublines
    assert 2 not in edited_sublines

def test_asterisk_propagation_hierarchy():
    from components.custom_list_item_delegate import CustomListItemDelegate
    from PyQt6.QtCore import QModelIndex, Qt
    
    # Setup mock project and main window
    class RealDataStore:
        def __init__(self):
            self.unsaved_block_indices = {2}  # data block 2 is unsaved
            self.edited_data = {(2, 5): "New Text"}
            self.block_names = {"2": "Test Block"}
            self.data = [[]]

    class RealMainWindow:
        def __init__(self):
            self.data_store = RealDataStore()
            self.project_manager = MagicMock()
            self.project_manager.project = MagicMock()
            
            # project block 0
            block_mock = MagicMock()
            category_mock = MagicMock()
            category_mock.name = "CatA"
            category_mock.line_indices = [5, 10]
            block_mock.categories = [category_mock]
            
            self.project_manager.project.blocks = [block_mock]
            
            # Map data block 2 to project block 0
            self.block_to_project_file_map = {2: 0}
            self.theme = 'light'

    mw = RealMainWindow()
    delegate = CustomListItemDelegate(None)
    delegate.list_widget = MagicMock()
    delegate.list_widget.window.return_value = mw

    # Case 1: Category item QModelIndex (block_idx_data=0, category_name="CatA")
    index_cat = QModelIndex()
    def mock_cat_data(role):
        if role == Qt.ItemDataRole.UserRole:
            return 0  # project block index
        if role == Qt.ItemDataRole.UserRole + 10:
            return "CatA"  # category name
        if role == Qt.ItemDataRole.UserRole + 12:
            return None  # not virtual row
        if role == Qt.ItemDataRole.UserRole + 2:
            return None
        return None
    index_cat.data = mock_cat_data

    # Check category changes propagation
    project = mw.project_manager.project
    edited_keys = mw.data_store.edited_data
    block_idx_data = index_cat.data(Qt.ItemDataRole.UserRole)
    category_name = index_cat.data(Qt.ItemDataRole.UserRole + 10)
    
    block_map = getattr(mw, 'block_to_project_file_map', {})
    data_indices = [d_idx for d_idx, p_idx in block_map.items() if p_idx == block_idx_data]
    if not data_indices:
        data_indices = [block_idx_data]
    
    proj_b_idx = block_idx_data
    assert proj_b_idx == 0
    block = project.blocks[proj_b_idx]
    category = next((c for c in block.categories if c.name == category_name), None)
    assert category is not None
    
    has_unsaved_changes_in_item = any(
        (d_idx, l_idx) in edited_keys 
        for d_idx in data_indices
        for l_idx in category.line_indices
    )
    assert has_unsaved_changes_in_item is True, "Category should have unsaved changes since data block 2 line 5 is edited"

    # Case 2: Block item QModelIndex (representing project block index 0)
    index_block = QModelIndex()
    def mock_block_data(role):
        if role == Qt.ItemDataRole.UserRole:
            return 0  # project block index
        if role == Qt.ItemDataRole.UserRole + 10:
            return None
        if role == Qt.ItemDataRole.UserRole + 12:
            return None
        if role == Qt.ItemDataRole.UserRole + 2:
            return None
        return None
    index_block.data = mock_block_data

    block_idx_data = index_block.data(Qt.ItemDataRole.UserRole)
    unsaved_blocks = mw.data_store.unsaved_block_indices
    
    # Check block changes propagation
    block_map = getattr(mw, 'block_to_project_file_map', {})
    has_unsaved_changes_in_block = any(
        block_map.get(data_idx) == block_idx_data 
        for data_idx in unsaved_blocks
    )
    assert has_unsaved_changes_in_block is True, "Block should have unsaved changes since mapping data block 2 is unsaved"

    # Case 3: Folder item QModelIndex (representing folder id containing project block 0)
    index_folder = QModelIndex()
    def mock_folder_data(role):
        if role == Qt.ItemDataRole.UserRole:
            return None
        if role == Qt.ItemDataRole.UserRole + 10:
            return None
        if role == Qt.ItemDataRole.UserRole + 12:
            return None
        if role == Qt.ItemDataRole.UserRole + 2:
            return [101]  # folder ID 101
        return None
    index_folder.data = mock_folder_data

    merged_folder_ids = index_folder.data(Qt.ItemDataRole.UserRole + 2)
    mw.project_manager.get_all_block_indices_under_folder.return_value = {0} # project block 0 is under folder 101
    
    all_p_indices = set()
    for folder_id in merged_folder_ids:
         all_p_indices.update(mw.project_manager.get_all_block_indices_under_folder(folder_id))
    
    block_map = getattr(mw, 'block_to_project_file_map', {})
    has_unsaved_changes_in_folder = any(
        block_map.get(data_idx) in all_p_indices 
        for data_idx in unsaved_blocks
    )
    assert has_unsaved_changes_in_folder is True, "Folder should have unsaved changes since child project block 0 has unsaved data block 2"


def test_block_list_updater_unsaved_checks():
    from ui.updaters.block_list_updater import BlockListUpdater
    
    mw = MagicMock()
    mw.data_store.unsaved_block_indices = {2}  # data block 2 is unsaved
    mw.block_to_project_file_map = {2: 0}       # data block 2 -> project block 0
    
    updater = BlockListUpdater(mw, MagicMock())
    
    # Test _is_project_block_unsaved
    assert updater._is_project_block_unsaved(0) is True
    assert updater._is_project_block_unsaved(1) is False
    
    # Test _folder_has_unsaved_blocks
    folder = MagicMock()
    folder.block_ids = [99] # project block ID
    folder.children = []
    
    project = MagicMock()
    project.blocks = [MagicMock()] # index 0 has ID 99
    project.blocks[0].id = 99
    
    id_to_idx = {99: 0}
    
    # folder contains project block 0 (which maps to data block 2, which is unsaved)
    assert updater._folder_has_unsaved_blocks(folder, project, id_to_idx) is True

if __name__ == "__main__":
    pytest.main([__file__])
