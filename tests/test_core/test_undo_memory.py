import pytest
from core.undo_manager import UndoManager
from unittest.mock import MagicMock

@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.data_store = MagicMock()
    return mw

def test_undo_manager_large_text_handling(mock_mw):
    manager = UndoManager(mock_mw)
    
    # Large string: 1MB
    large_text_old = "A" * 1000000
    large_text_new = "B" * 1000000
    
    manager.record_action("TEXT_EDIT", 0, 0, large_text_old, large_text_new)
    
    action = manager.undo_stack[0]
    # Verify we can still get the original text back
    assert action.old_text == large_text_old
    assert action.new_text == large_text_new

def test_undo_manager_structural_memory(mock_mw):
    manager = UndoManager(mock_mw)
    
    # Large snapshot
    large_snapshot = {str(i): "data" * 100 for i in range(1000)}
    mock_mw.data_store.block_names = large_snapshot
    
    before = manager.get_project_snapshot()
    mock_mw.data_store.block_names = {**large_snapshot, "new": "data"}
    
    manager.record_structural_action(before, "STRUCT", "heavy")
    
    action = manager.undo_stack[0]
    assert action.before_snapshot == before
