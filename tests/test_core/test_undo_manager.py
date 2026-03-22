import pytest
import time
from unittest.mock import MagicMock, patch
from core.undo_manager import UndoManager, UndoAction, GroupAction, StructuralAction


@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.current_block_idx = 0
    mw.current_string_idx = 0
    mw.is_programmatically_changing_text = False
    
    # Mock editor
    mw.edited_text_edit = MagicMock()
    mw.edited_text_edit.textCursor().position.return_value = 5
    
    # Mock data processor
    mw.data_processor = MagicMock()
    mw.data_processor._get_string_from_source.return_value = "old\ntext"
    
    # Mock project & structure
    mw.block_names = {0: "Block0"}
    mw.project_manager = MagicMock()
    mw.project_manager.project.virtual_folders = []
    mw.project_manager.project.metadata = {}
    
    # Mock updater
    mw.ui_updater = MagicMock()
    
    # Mock utils
    mw.utils = MagicMock()
    mw.utils.convert_dots_to_spaces_from_editor.side_effect = lambda x: x
    
    return mw


@pytest.fixture
def um(mock_mw):
    return UndoManager(mock_mw)


def test_UndoManager_initialization(um):
    assert um.undo_stack == []
    assert um.redo_stack == []
    assert um.is_undoing_redoing is False
    assert um.current_group is None


def test_UndoManager_clear(um):
    um.undo_stack.append("item")
    um.redo_stack.append("item")
    um.clear()
    assert um.undo_stack == []
    assert um.redo_stack == []


def test_UndoManager_record_action_basic(um):
    um.record_action("TEXT_EDIT", 0, 0, "old", "new")
    assert len(um.undo_stack) == 1
    action = um.undo_stack[0]
    assert isinstance(action, UndoAction)
    assert action.action_type == "TEXT_EDIT"
    assert action.old_text == "old"
    assert action.new_text == "new"
    # Should clear redo stack
    um.redo_stack.append("item")
    um.record_action("TEXT_EDIT", 0, 0, "new", "newer")
    assert len(um.redo_stack) == 0
    assert len(um.undo_stack) == 2


def test_UndoManager_record_action_same_text(um):
    um.record_action("TEXT_EDIT", 0, 0, "same", "same")
    assert len(um.undo_stack) == 0


def test_UndoManager_record_action_grouping_text_edit(um):
    # Test that simple typing (additions) gets grouped into one action
    um.record_action("TEXT_EDIT", 0, 0, "a", "ab")
    assert len(um.undo_stack) == 1
    
    # Wait, grouping threshold is 3.5 seconds. Second action should group.
    um.record_action("TEXT_EDIT", 0, 0, "ab", "abc")
    assert len(um.undo_stack) == 1
    action = um.undo_stack[0]
    assert action.old_text == "a"
    assert action.new_text == "abc"


def test_UndoManager_record_action_grouping_break_word_boundary(um):
    um.record_action("TEXT_EDIT", 0, 0, "word", "word1")
    assert len(um.undo_stack) == 1
    
    # Space is not a word char, should break grouping
    um.record_action("TEXT_EDIT", 0, 0, "word1", "word1 ")
    assert len(um.undo_stack) == 2


def test_UndoManager_groups(um):
    um.begin_group()
    assert um.current_group == []
    
    um.record_action("REVERT", 0, 0, "o1", "n1")
    um.record_action("REVERT", 0, 1, "o2", "n2")
    
    assert len(um.undo_stack) == 0
    
    um.end_group("COMPOSITE")
    assert len(um.undo_stack) == 1
    group = um.undo_stack[0]
    assert isinstance(group, GroupAction)
    assert len(group.actions) == 2
    assert group.actions[0].old_text == "o1"


def test_UndoManager_record_navigation(um):
    um.record_navigation(1, 2, 0, 0)
    assert len(um.undo_stack) == 1
    action = um.undo_stack[0]
    assert action.action_type == "NAVIGATE"
    assert action.block_idx == 1
    assert action.string_idx == 2
    assert action.metadata["prev_block"] == 0
    assert action.metadata["prev_string"] == 0


def test_UndoManager_record_structural_action(um, mock_mw):
    before = um.get_project_snapshot()
    
    # Change project slightly to simulate structural change
    mock_mw.block_names[0] = "NewName"
    
    um.record_structural_action(before, "RENAME", "renamed block 0")
    
    assert len(um.undo_stack) == 1
    action = um.undo_stack[0]
    assert isinstance(action, StructuralAction)
    assert action.action_type == "RENAME"
    assert action.before_snapshot["block_names"][0] == "Block0"
    assert action.after_snapshot["block_names"][0] == "NewName"


def test_UndoManager_undo_redo_basic(um, mock_mw):
    um.record_action("TEXT_EDIT", 0, 0, "old", "new")
    assert len(um.undo_stack) == 1
    
    um.undo()
    assert len(um.undo_stack) == 0
    assert len(um.redo_stack) == 1
    
    # Verify apply_data was called with old_text
    mock_mw.data_processor.update_edited_data.assert_called_with(0, 0, "old")
    
    um.redo()
    assert len(um.undo_stack) == 1
    assert len(um.redo_stack) == 0
    
    # Verify apply_data was called with new_text
    mock_mw.data_processor.update_edited_data.assert_called_with(0, 0, "new")


def test_UndoManager_undo_redo_group(um, mock_mw):
    um.begin_group()
    um.record_action("T1", 0, 0, "o1", "n1")
    um.record_action("T2", 0, 1, "o2", "n2")
    um.end_group()
    
    um.undo()
    # Should undo in reverse order: 1 then 0
    calls = mock_mw.data_processor.update_edited_data.call_args_list
    assert calls[-2][0] == (0, 1, "o2")
    assert calls[-1][0] == (0, 0, "o1")
    
    um.redo()
    # Should redo in forward order: 0 then 1
    calls = mock_mw.data_processor.update_edited_data.call_args_list
    assert calls[-2][0] == (0, 0, "n1")
    assert calls[-1][0] == (0, 1, "n2")


def test_UndoManager_undo_structural(um, mock_mw):
    before = um.get_project_snapshot()
    mock_mw.block_names[0] = "NewName"
    um.record_structural_action(before, "RENAME", "renamed")
    
    um.undo()
    assert mock_mw.block_names[0] == "Block0"
    
    um.redo()
    assert mock_mw.block_names[0] == "NewName"


def test_UndoManager_undo_navigation(um, mock_mw):
    um.record_navigation(1, 2, 0, 0)
    
    with patch.object(um, '_navigate_to') as mock_nav:
        um.undo()
        mock_nav.assert_called_with(0, 0, None)
        
        um.redo()
        mock_nav.assert_called_with(1, 2, None)
