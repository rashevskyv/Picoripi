import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QApplication, QWidget, QListWidgetItem
from PyQt5.QtCore import Qt
from ui.mempalace_builder_dialog import MemePalaceBuilderDialog

@pytest.fixture(scope="module")
def qapp():
    """Ensure a QApplication exists for widget testing."""
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app

def test_mempalace_builder_empty_lines_filtering(qapp):
    mock_mw = MagicMock()
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = None # Single-file mode
    
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.project_file = "d:/test/file.bmg"
    # Block 0 has one empty string, one whitespace-only string, and one valid string
    mock_mw.data_store.data = [
        ["", "   ", "Valid dialogue line"]
    ]
    mock_mw.data_store.block_names = {"0": "zel_00"}
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.edited_data = {}
    
    parent_widget = QWidget()
    
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    
    # 1. Verify blocks_list_widget was populated correctly
    assert dialog.blocks_list_widget.count() == 1
    item = dialog.blocks_list_widget.item(0)
    assert item.data(Qt.UserRole) == 0
    assert item.checkState() == Qt.Checked
    
    # 2. Gather selected strings
    dialog._gather_selected_strings_data()
    
    # 3. Verify that empty and whitespace strings are completely ignored
    assert len(dialog.bmg_strings) == 1
    assert dialog.bmg_strings[0] == "Valid dialogue line"
    
    # 4. Verify that s_idx is correctly preserved in ID as 2 (since indices were 0, 1, 2)
    assert len(dialog.bmg_ids) == 1
    assert dialog.bmg_ids[0] == "Block_0_Str_2" # Name fell back to Block_0 because "Message ID" is not in block_names
    assert dialog.bmg_block_names[0] == "Block_0"
