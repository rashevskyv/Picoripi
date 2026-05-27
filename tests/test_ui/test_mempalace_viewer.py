import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QApplication, QTableWidgetItem, QWidget
from PyQt5.QtCore import Qt
from ui.mempalace_viewer_dialog import MemePalaceViewerDialog

@pytest.fixture(scope="module")
def qapp():
    """Ensure a QApplication exists for widget testing."""
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app

def test_mempalace_viewer_init(qapp):
    mock_mw = MagicMock()
    mock_mw.project_manager = MagicMock()
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.project_file = "d:/test/proj.uiproj"
    mock_mw.data_store.data = []
    
    parent_widget = QWidget()
    
    with patch('ui.mempalace_viewer_dialog.MemePalaceClient') as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_wings.return_value = [{"name": "Zelda_TP"}]
        mock_client.get_rooms.return_value = [{"name": "Global_Cast_Profiles"}, {"name": "Foreword"}]
        mock_client.get_relations.return_value = []
        mock_client_cls.return_value = mock_client
        
        dialog = MemePalaceViewerDialog(mock_mw, parent=parent_widget)
        assert dialog.client == mock_client
        assert dialog.wing_combo.count() == 1
        
        # Test closeEvent
        mock_mw.mempalace_viewer_dialog = dialog
        dialog.close()
        assert mock_mw.mempalace_viewer_dialog is None

def test_mempalace_viewer_double_click_navigation(qapp):
    mock_mw = MagicMock()
    mock_mw.project_manager = MagicMock()
    
    # Mock project blocks to match block label "zel_00"
    mock_block = MagicMock()
    mock_block.name = "zel_00"
    mock_mw.project_manager.project.blocks = [mock_block]
    
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.block_names = {"0": "zel_00"}
    mock_mw.data_store.current_block_idx = 0
    mock_mw.block_list_widget = MagicMock()
    
    # Mock QTreeWidget item traversal
    mock_tree_item = MagicMock()
    mock_tree_item.data.return_value = 0 # block index 0
    
    parent_widget = QWidget()
    
    class MockIterator:
        def __init__(self, item):
            self.item = item
            self.called = False
        def value(self):
            if not self.called:
                return self.item
            return None
        def __iadd__(self, other):
            self.called = True
            return self

    with patch('ui.mempalace_viewer_dialog.MemePalaceClient') as mock_client_cls, \
         patch('PyQt5.QtWidgets.QTreeWidgetItemIterator') as mock_iterator_cls, \
         patch('PyQt5.QtCore.QTimer.singleShot') as mock_timer_singleshot:
        
        # Set up tree iterator using the robust MockIterator helper
        mock_iterator = MockIterator(mock_tree_item)
        mock_iterator_cls.return_value = mock_iterator
        
        mock_client = MagicMock()
        mock_client.get_wings.return_value = [{"name": "Zelda_TP"}]
        mock_client.get_rooms.return_value = []
        mock_client.get_relations.return_value = []
        mock_client_cls.return_value = mock_client
        
        dialog = MemePalaceViewerDialog(mock_mw, parent=parent_widget)
        
        # Set up dialogues table with dummy cell
        dialog.dialogues_table.setRowCount(1)
        item = QTableWidgetItem("zel_00_Str_353")
        dialog.dialogues_table.setItem(0, 0, item)
        
        # Trigger double click handler
        dialog._handle_dialogue_double_clicked(0, 0)
        
        # Verify main window is raised and focused
        mock_mw.raise_.assert_called_once()
        mock_mw.activateWindow.assert_called_once()
        
        # Verify block in tree was selected
        mock_mw.block_list_widget.setCurrentItem.assert_called_once_with(mock_tree_item)
        
        # Verify single shot timer scheduled the string selection
        mock_timer_singleshot.assert_called_once()
        args, kwargs = mock_timer_singleshot.call_args
        # Call the scheduled lambda to ensure select_string_by_absolute_index is triggered
        args[1]()
        mock_mw.list_selection_handler.select_string_by_absolute_index.assert_called_once_with(353)
