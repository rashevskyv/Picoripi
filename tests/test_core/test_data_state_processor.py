import pytest
import json
from unittest.mock import MagicMock, patch
from pathlib import Path
from PyQt5.QtWidgets import QMessageBox
from core.data_state_processor import DataStateProcessor

@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.data_store = mw
    mw.data_store.data = [
        ["original_0_0", "original_0_1"],
        ["original_1_0"]
    ]
    mw.data_store.edited_file_data = [] # By default same as data or empty
    mw.data_store.edited_data = {}
    mw.data_store.block_names = {0: "Block0", 1: "Block1"}
    mw.data_store.unsaved_changes = False
    mw.data_store.unsaved_block_indices = set()
    mw.data_store.current_block_idx = 0
    mw.data_store.current_string_idx = 0
    
    mw.data_store.json_path = "original.json"
    mw.data_store.edited_json_path = "edited.json"
    
    mw.project_manager = None
    mw.current_game_rules = MagicMock()
    mw.current_game_rules.save_data_to_json_obj.return_value = {"saved": "data"}
    mw.current_game_rules.load_data_from_json_obj.return_value = (mw.data_store.data, None)
    
    mw.ui_updater = MagicMock()
    mw.undo_manager = MagicMock()
    
    mw.app_action_handler._derive_edited_path.return_value = "edited.json"
    
    return mw

@pytest.fixture
def dsp(mock_mw):
    return DataStateProcessor(mock_mw)


def test_get_string_from_source_valid(dsp):
    data = [["A", "B"]]
    assert dsp._get_string_from_source(0, 1, data, "test") == "B"

def test_get_string_from_source_invalid(dsp):
    data = [["A", "B"]]
    assert dsp._get_string_from_source(1, 0, data, "test") is None
    assert dsp._get_string_from_source(0, 2, data, "test") is None
    assert dsp._get_string_from_source(-1, 0, data, "test") is None
    assert dsp._get_string_from_source(0, 0, None, "test") is None
    assert dsp._get_string_from_source(0, 0, ["Not a list"], "test") is None


def test_get_current_string_text_from_memory(dsp, mock_mw):
    mock_mw.edited_data = {(0, 1): "memory_edit"}
    text, src = dsp.get_current_string_text(0, 1)
    assert text == "memory_edit"
    assert src == "edited_data (in-memory)"


def test_get_current_string_text_from_edited_file(dsp, mock_mw):
    mock_mw.edited_file_data = [["file_0_0", "file_0_1"]]
    text, src = dsp.get_current_string_text(0, 1)
    assert text == "file_0_1"
    assert src == "edited_file_data"


def test_get_current_string_text_from_original(dsp):
    text, src = dsp.get_current_string_text(1, 0)
    assert text == "original_1_0"
    assert src == "original_data"


def test_get_current_string_text_invalid(dsp):
    text, src = dsp.get_current_string_text(-1, 0)
    assert text == ""
    assert src == "loading"
    
    text, src = dsp.get_current_string_text(99, 0)
    assert text == ""
    assert src == "initial_load"


def test_get_block_texts(dsp):
    texts = dsp.get_block_texts(0)
    assert texts == ["original_0_0", "original_0_1"]
    
    assert dsp.get_block_texts(-1) == []
    assert dsp.get_block_texts(99) == []


def test_update_edited_data_new_edit(dsp, mock_mw):
    mock_mw.undo_manager = MagicMock()
    
    changed = dsp.update_edited_data(0, 0, "new_text")
    
    assert changed is True
    assert mock_mw.unsaved_changes is True
    assert 0 in mock_mw.unsaved_block_indices
    assert mock_mw.edited_data[(0, 0)] == "new_text"
    
    mock_mw.undo_manager.record_action.assert_called_once_with(
        "TEXT_EDIT", 0, 0, "original_0_0", "new_text"
    )
    mock_mw.ui_updater.update_block_item_text_with_problem_count.assert_called_with(0)


def test_update_edited_data_revert_to_original(dsp, mock_mw):
    mock_mw.edited_data = {(0, 0): "changed"}
    mock_mw.unsaved_changes = True
    mock_mw.unsaved_block_indices = {0}
    
    changed = dsp.update_edited_data(0, 0, "original_0_0")
    
    assert changed is True  # transitioned from unsaved to saved
    assert mock_mw.unsaved_changes is False
    assert 0 not in mock_mw.unsaved_block_indices
    assert (0, 0) not in mock_mw.edited_data


def test_revert_strings_to_original(dsp, mock_mw):
    mock_mw.edited_data = {(0, 0): "changed0", (0, 1): "changed1"}
    
    dsp.revert_strings_to_original(0, [0, 1])
    
    assert (0, 0) not in mock_mw.edited_data
    assert (0, 1) not in mock_mw.edited_data
    mock_mw.undo_manager.begin_group.assert_called()
    mock_mw.undo_manager.end_group.assert_called_with("REVERT")
    mock_mw.ui_updater.populate_strings_for_block.assert_called()


@patch("core.data_state_processor.QMessageBox.question")
def test_perform_revert_strings_confirm_no(mock_qmb, dsp, mock_mw):
    mock_qmb.return_value = QMessageBox.No
    
    mock_mw.edited_data = {(0, 0): "changed"}
    dsp.perform_revert_strings(0, [0])
    
    # Should not be reverted
    assert (0, 0) in mock_mw.edited_data


@patch("core.data_state_processor.QMessageBox.question")
def test_perform_revert_strings_confirm_yes(mock_qmb, dsp, mock_mw):
    mock_qmb.return_value = QMessageBox.Yes
    mock_mw.edited_data = {(0, 0): "changed"}
    
    dsp.perform_revert_strings(0, [0])
    
    assert (0, 0) not in mock_mw.edited_data


def test_revert_blocks_to_original(dsp, mock_mw):
    mock_mw.edited_data = {(0, 0): "changed0", (1, 0): "changed1"}
    
    dsp.revert_blocks_to_original([0, 1])
    
    assert (0, 0) not in mock_mw.edited_data
    assert (1, 0) not in mock_mw.edited_data
    mock_mw.undo_manager.begin_group.assert_called()
    mock_mw.undo_manager.end_group.assert_called_with("REVERT_BLOCKS")


@patch("core.data_state_processor.QMessageBox.information")
@patch("core.data_state_processor.save_json_file")
def test_save_current_edits_no_project(mock_save, mock_info, dsp, mock_mw):
    mock_mw.unsaved_changes = True
    mock_mw.edited_data = {(0, 0): "edited_0_0"}
    mock_save.return_value = True
    
    result = dsp.save_current_edits(ask_confirmation=False)
    
    assert result is True
    mock_save.assert_called_once()
    assert mock_mw.unsaved_changes is False
    assert mock_mw.edited_data == {}
    
    # Verify final data was reloaded
    mock_mw.current_game_rules.load_data_from_json_obj.assert_called()


@patch("core.data_state_processor.QMessageBox.information")
def test_save_current_edits_no_changes(mock_info, dsp, mock_mw):
    mock_mw.unsaved_changes = False
    result = dsp.save_current_edits(ask_confirmation=True)
    assert result is True
    mock_info.assert_called_with(mock_mw, "Save", "No changes to save.")


@patch("core.data_state_processor.QMessageBox.question")
@patch("core.data_state_processor.QMessageBox.information")
@patch("core.data_state_processor.save_json_file")
def test_revert_edited_file_to_original_single_file(mock_save, mock_info, mock_qmb, dsp, mock_mw):
    mock_qmb.return_value = QMessageBox.Yes
    mock_save.return_value = True
    
    mock_mw.edited_data = {(0, 0): "changed"}
    
    result = dsp.revert_edited_file_to_original()
    
    assert result is True
    assert mock_mw.unsaved_changes is False
    assert mock_mw.edited_data == {}
    mock_save.assert_called_once()
    mock_info.assert_called_once()
