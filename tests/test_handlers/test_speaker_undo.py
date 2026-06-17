# tests/test_handlers/test_speaker_undo.py
import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QTreeWidgetItem
from PyQt6.QtCore import Qt
from handlers.list_selection_handler import ListSelectionHandler
from core.undo_manager import UndoManager, UndoAction

@pytest.fixture
def mock_project():
    project = MagicMock()
    block = MagicMock()
    block.metadata = {"character_assignments": {"0": "Hero"}}
    project.blocks = [block]
    return project

def test_speaker_change_undo_redo(qapp, mock_mw, mock_project):
    """Test that changing a speaker records an undo action, which can be undone and redone."""
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = mock_project
    mock_mw.block_to_project_file_map = {0: 0}
    
    # Setup mocks
    mock_mw.is_loading_data = False
    mock_mw._restoring_selection = False
    mock_mw.is_programmatically_changing_text = False
    mock_mw._restoring_session_state = False
    
    # Simulate current state
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_string_idx = 0
    mock_mw.data_store.current_speaker_name = "Hero"
    
    # Initialize managers and handlers
    mock_mw.undo_manager = UndoManager(mock_mw)
    mock_mw.ui_updater = MagicMock()
    mock_mw.ui_updater.block_list_updater = MagicMock()
    
    # Mock tree widget and items
    from PyQt6.QtWidgets import QTreeWidget
    tree = QTreeWidget()
    
    virtual_item = QTreeWidgetItem(["Hero"])
    virtual_item.setData(0, int(Qt.ItemDataRole.UserRole), -3)
    virtual_item.setData(0, int(Qt.ItemDataRole.UserRole + 15), "Hero")
    virtual_item.setData(0, int(Qt.ItemDataRole.UserRole + 13), [(0, 0)])
    tree.addTopLevelItem(virtual_item)
    
    villain_item = QTreeWidgetItem(["Villain"])
    villain_item.setData(0, int(Qt.ItemDataRole.UserRole), -3)
    villain_item.setData(0, int(Qt.ItemDataRole.UserRole + 15), "Villain")
    villain_item.setData(0, int(Qt.ItemDataRole.UserRole + 13), [(0, 0)])
    tree.addTopLevelItem(villain_item)
    
    tree.setCurrentItem(virtual_item)
    tree.select_block_by_index = MagicMock()  # custom method expected by UndoManager._navigate_to
    mock_mw.block_list_widget = tree
    
    handler = ListSelectionHandler(mock_mw, mock_mw.data_processor, mock_mw.ui_updater)
    mock_mw.list_selection_handler = handler
    
    # Mock string selection
    handler.string_selected_from_preview = MagicMock()
    
    # 1. Save new speaker "Villain" (which should record the action)
    with patch('PyQt6.QtCore.QTimer.singleShot', side_effect=lambda ms, func: func()):
        handler.save_speaker_for_current_string("Villain")
        
    # Verify metadata was updated
    assert mock_project.blocks[0].metadata["character_assignments"]["0"] == "Villain"
    
    # Verify undo action was recorded
    assert len(mock_mw.undo_manager.undo_stack) == 1
    action = mock_mw.undo_manager.undo_stack[0]
    assert isinstance(action, UndoAction)
    assert action.action_type == 'CHANGE_SPEAKER'
    assert action.old_text == 'Hero'
    assert action.new_text == 'Villain'
    
    # 2. Perform Undo
    with patch('PyQt6.QtCore.QTimer.singleShot', side_effect=lambda ms, func: func()):
        mock_mw.undo_manager.undo()
        
    # Verify speaker went back to "Hero" in metadata
    assert mock_project.blocks[0].metadata["character_assignments"]["0"] == "Hero"
    
    # Verify redo stack has the action now
    assert len(mock_mw.undo_manager.redo_stack) == 1
    
    # 3. Perform Redo
    with patch('PyQt6.QtCore.QTimer.singleShot', side_effect=lambda ms, func: func()):
        mock_mw.undo_manager.redo()
        
    # Verify speaker became "Villain" again
    assert mock_project.blocks[0].metadata["character_assignments"]["0"] == "Villain"
