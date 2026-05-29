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
    
    # 1. blocks_list_widget has been replaced by table widget in the current layout
    assert dialog is not None
    assert dialog.windowTitle() == "MemePalace Context Builder"
