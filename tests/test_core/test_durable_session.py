import pytest
import json
import pickle
from pathlib import Path
from unittest.mock import MagicMock, patch
from core.data_store import AppDataStore
from core.data_state_processor import DataStateProcessor
from core.undo_manager import UndoAction, GroupAction, StructuralAction

class MockMainWindow:
    def __init__(self):
        self.data_store = AppDataStore()
        self.project_manager = MagicMock()
        self.project_manager.project_dir = None
        self.project_manager.project = None
        self.ui_provider = MagicMock()
        self.ui_updater = MagicMock()
        self.helper = MagicMock()
        self.app_action_handler = MagicMock()
        self.current_game_rules = MagicMock()

@pytest.fixture
def mock_mw():
    return MockMainWindow()

@pytest.fixture
def dsp(mock_mw):
    return DataStateProcessor(mock_mw)

def test_get_durable_session_file_path(dsp, mock_mw, tmp_path):
    mock_mw.project_manager.project_dir = str(tmp_path)
    mock_mw.project_manager.project = MagicMock()
    
    path = dsp.get_durable_session_file_path()
    assert path == Path(tmp_path) / ".picoripi_session.json"

def test_serialize_and_deserialize_session(dsp):
    # Prepare mock snapshot
    action1 = UndoAction("edit", 0, 0, "old", "new", 123.45, 2, {"meta": "data"})
    action2 = UndoAction("edit", 0, 1, "old2", "new2", 124.45, None, None)
    group_action = GroupAction([action1, action2], "group_edit", 125.45)
    struct_action = StructuralAction("folder_move", {"snap": 1}, {"snap": 2}, "moved", 126.45)

    snapshot = {
        "json_path": "test.uiproj",
        "edited_json_path": "edited.json",
        "edited_data": {(0, 0): "new", (1, 2): "new_val"},
        "current_block_idx": 1,
        "unsaved_block_indices": {0, 1},
        "problems_per_subline": {
            (0, 0, 0): {"WIDTH_EXCEEDED"},
            (1, 2, 1): {"TAG_WARNING", "MISSING_SPACE"}
        },
        "undo_stack": [action1, group_action],
        "redo_stack": [struct_action],
        "block_names": {0: "block1", 1: "block2"},
        "block_to_project_file_map": {0: "file1.json", 1: "file2.json"},
        "unsaved_changes": True
    }

    # Serialize
    json_snapshot = dsp.serialize_session_to_json(snapshot)

    # Assert correct types in JSON representation
    assert isinstance(json_snapshot["edited_data"], dict)
    assert "0,0" in json_snapshot["edited_data"]
    assert json_snapshot["edited_data"]["0,0"] == "new"

    assert isinstance(json_snapshot["unsaved_block_indices"], list)
    assert set(json_snapshot["unsaved_block_indices"]) == {0, 1}

    assert isinstance(json_snapshot["problems_per_subline"], dict)
    assert "0,0,0" in json_snapshot["problems_per_subline"]
    assert json_snapshot["problems_per_subline"]["0,0,0"] == ["WIDTH_EXCEEDED"]

    assert json_snapshot["undo_stack"][0]["type"] == "UndoAction"
    assert json_snapshot["undo_stack"][0]["old_text"] == "old"
    assert json_snapshot["undo_stack"][1]["type"] == "GroupAction"
    assert json_snapshot["undo_stack"][1]["actions"][0]["new_text"] == "new"

    assert json_snapshot["redo_stack"][0]["type"] == "StructuralAction"
    assert json_snapshot["redo_stack"][0]["label"] == "moved"

    # Deserialize
    deserialized = dsp.deserialize_session_from_json(json_snapshot)

    # Assert restored types
    assert deserialized["edited_data"] == {(0, 0): "new", (1, 2): "new_val"}
    assert deserialized["unsaved_block_indices"] == {0, 1}
    assert deserialized["problems_per_subline"] == {
        (0, 0, 0): {"WIDTH_EXCEEDED"},
        (1, 2, 1): {"TAG_WARNING", "MISSING_SPACE"}
    }

    # Verify restored actions
    restored_action1 = deserialized["undo_stack"][0]
    assert isinstance(restored_action1, UndoAction)
    assert restored_action1.action_type == "edit"
    assert restored_action1.old_text == "old"
    assert restored_action1.new_text == "new"
    assert restored_action1.metadata == {"meta": "data"}

    restored_group = deserialized["undo_stack"][1]
    assert isinstance(restored_group, GroupAction)
    assert len(restored_group.actions) == 2
    assert restored_group.actions[0].new_text == "new"
    assert restored_group.actions[1].new_text == "new2"

    restored_struct = deserialized["redo_stack"][0]
    assert isinstance(restored_struct, StructuralAction)
    assert restored_struct.action_type == "folder_move"
    assert restored_struct.before_snapshot == {"snap": 1}
    assert restored_struct.label == "moved"

def test_save_and_load_durable_session_json(dsp, mock_mw, tmp_path):
    mock_mw.project_manager.project_dir = str(tmp_path)
    mock_mw.project_manager.project = MagicMock()

    mock_mw.data_store.edited_data = {(0, 0): "test_json"}
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_string_idx = 0

    dsp.schedule_autosave()
    assert dsp._session_dirty is True

    # Save durable session
    dsp._save_durable_session_json(force=True)

    json_file = Path(tmp_path) / ".picoripi_session.json"
    assert json_file.exists()

    with json_file.open('r', encoding='utf-8') as f:
        data = json.load(f)
    assert data["edited_data"]["0,0"] == "test_json"

    # Clear current state
    mock_mw.data_store = AppDataStore()

    # Load session (should prefer JSON)
    loaded = dsp.load_session_file()
    assert loaded is True
    assert mock_mw.data_store.edited_data == {(0, 0): "test_json"}
    assert dsp._session_dirty is False

def test_load_session_fallback_to_pickle(dsp, mock_mw, tmp_path):
    mock_mw.project_manager.project_dir = str(tmp_path)
    mock_mw.project_manager.project = MagicMock()

    # 1. Create a pickle session only (no json session)
    mock_mw.data_store.edited_data = {(0, 0): "pickle_only"}
    dsp._autosave_session(force=True)

    pickle_file = Path(tmp_path) / ".picoripi_session"
    json_file = Path(tmp_path) / ".picoripi_session.json"
    assert pickle_file.exists()
    assert not json_file.exists()

    # Clear state
    mock_mw.data_store = AppDataStore()

    # Load session: should fall back to pickle
    loaded = dsp.load_session_file()
    assert loaded is True
    assert mock_mw.data_store.edited_data == {(0, 0): "pickle_only"}

    # 2. Create invalid JSON file to force parsing error and test fallback to pickle
    mock_mw.data_store.edited_data = {(0, 0): "pickle_val_after_json_fail"}
    dsp._autosave_session(force=True)

    # Write corrupt JSON
    with json_file.open('w', encoding='utf-8') as f:
        f.write("{invalid json syntax: [}")

    # Clear state
    mock_mw.data_store = AppDataStore()

    # Load session: should fail JSON parse and fall back to Pickle
    loaded = dsp.load_session_file()
    assert loaded is True
    assert mock_mw.data_store.edited_data == {(0, 0): "pickle_val_after_json_fail"}


def test_load_session_prefers_newer_pickle_fallback(dsp, mock_mw, tmp_path):
    mock_mw.project_manager.project_dir = str(tmp_path)
    mock_mw.project_manager.project = MagicMock()

    json_file = Path(tmp_path) / ".picoripi_session.json"
    pickle_file = Path(tmp_path) / ".picoripi_session"

    # Case 1: Pickle is newer than JSON (Pickle: 200.0, JSON: 100.0)
    # Generate valid JSON snapshot
    mock_mw.data_store.edited_data = {(0, 0): "old_json_val"}
    snapshot_json = mock_mw.data_store.get_session_snapshot()
    snapshot_json["saved_at"] = 100.0
    
    json_snapshot = dsp.serialize_session_to_json(snapshot_json)
    with json_file.open('w', encoding='utf-8') as f:
        json.dump(json_snapshot, f)

    # Generate valid Pickle snapshot
    mock_mw.data_store.edited_data = {(0, 0): "new_pickle_val"}
    snapshot_pickle = mock_mw.data_store.get_session_snapshot()
    snapshot_pickle["saved_at"] = 200.0
    with pickle_file.open('wb') as f:
        pickle.dump(snapshot_pickle, f)

    # Clear state
    mock_mw.data_store = AppDataStore()

    # Load session: should load from Pickle and trigger atomic JSON sync
    loaded = dsp.load_session_file()
    assert loaded is True
    assert mock_mw.data_store.edited_data == {(0, 0): "new_pickle_val"}

    # Verify JSON was synced (saved_at in JSON should be >= 200.0)
    with json_file.open('r', encoding='utf-8') as f:
        synced_json = json.load(f)
    assert synced_json["edited_data"]["0,0"] == "new_pickle_val"
    assert synced_json["saved_at"] > 100.0

    # Case 2: JSON is newer than Pickle (Pickle: 300.0, JSON: 400.0)
    mock_mw.data_store.edited_data = {(0, 0): "newest_json_val"}
    snapshot_json2 = mock_mw.data_store.get_session_snapshot()
    snapshot_json2["saved_at"] = 400.0
    
    json_snapshot = dsp.serialize_session_to_json(snapshot_json2)
    with json_file.open('w', encoding='utf-8') as f:
        json.dump(json_snapshot, f)

    mock_mw.data_store.edited_data = {(0, 0): "older_pickle_val"}
    snapshot_pickle2 = mock_mw.data_store.get_session_snapshot()
    snapshot_pickle2["saved_at"] = 300.0
    with pickle_file.open('wb') as f:
        pickle.dump(snapshot_pickle2, f)

    # Clear state
    mock_mw.data_store = AppDataStore()

    # Load session: should load from JSON
    loaded = dsp.load_session_file()
    assert loaded is True
    assert mock_mw.data_store.edited_data == {(0, 0): "newest_json_val"}


def test_separate_dirty_flags(dsp, mock_mw, tmp_path):
    mock_mw.project_manager.project_dir = str(tmp_path)
    mock_mw.project_manager.project = MagicMock()

    # Initial state
    assert dsp._session_dirty is False
    assert dsp._durable_session_dirty is False

    # schedule_autosave sets both
    dsp.schedule_autosave()
    assert dsp._session_dirty is True
    assert dsp._durable_session_dirty is True

    # Pickle autosave clears only _session_dirty
    dsp._autosave_session()
    assert dsp._session_dirty is False
    assert dsp._durable_session_dirty is True

    # JSON save clears only _durable_session_dirty
    dsp._save_durable_session_json()
    assert dsp._session_dirty is False
    assert dsp._durable_session_dirty is False


def test_atomic_json_write(dsp, mock_mw, tmp_path):
    mock_mw.project_manager.project_dir = str(tmp_path)
    mock_mw.project_manager.project = MagicMock()
    json_file = Path(tmp_path) / ".picoripi_session.json"

    # Pre-populate valid json
    mock_mw.data_store.edited_data = {(0, 0): "valid_data"}
    snapshot = mock_mw.data_store.get_session_snapshot()
    snapshot["saved_at"] = 10.0
    json_snapshot = dsp.serialize_session_to_json(snapshot)
    with json_file.open('w', encoding='utf-8') as f:
        json.dump(json_snapshot, f)

    # Trigger save, but mock path.replace to fail/raise exception
    mock_mw.data_store.edited_data = {(0, 0): "new_corrupt_attempt"}
    dsp._durable_session_dirty = True

    with patch.object(Path, "replace", side_effect=IOError("atomic write failed")):
        dsp._save_durable_session_json(force=True)

    # Verify that the original valid JSON was not truncated or modified
    assert json_file.exists()
    with json_file.open('r', encoding='utf-8') as f:
        loaded = json.load(f)
    assert loaded["edited_data"]["0,0"] == "valid_data"


def test_durable_session_complex_undo_redo_roundtrip(dsp, mock_mw, tmp_path):
    mock_mw.project_manager.project_dir = str(tmp_path)
    mock_mw.project_manager.project = MagicMock()

    json_file = Path(tmp_path) / ".picoripi_session.json"

    # Setup complex actions in undo/redo stack
    action1 = UndoAction("edit", 0, 0, "old", "new", 123.45, 2, {"meta": "data"})
    action2 = UndoAction("edit", 0, 1, "old2", "new2", 124.45, None, None)
    group_action = GroupAction([action1, action2], "group_edit", 125.45)
    struct_action = StructuralAction("folder_move", {"snap": 1}, {"snap": 2}, "moved", 126.45)

    mock_mw.data_store.undo_stack = [action1, group_action]
    mock_mw.data_store.redo_stack = [struct_action]

    dsp.schedule_autosave()
    dsp._save_durable_session_json(force=True)
    assert json_file.exists()

    # Clear state
    mock_mw.data_store = AppDataStore()

    # Load session
    loaded = dsp.load_session_file()
    assert loaded is True

    # Assert undo/redo stacks are correctly restored with class instances
    assert len(mock_mw.data_store.undo_stack) == 2
    assert isinstance(mock_mw.data_store.undo_stack[0], UndoAction)
    assert mock_mw.data_store.undo_stack[0].old_text == "old"
    assert mock_mw.data_store.undo_stack[0].metadata == {"meta": "data"}

    assert isinstance(mock_mw.data_store.undo_stack[1], GroupAction)
    assert len(mock_mw.data_store.undo_stack[1].actions) == 2
    assert mock_mw.data_store.undo_stack[1].actions[1].new_text == "new2"

    assert len(mock_mw.data_store.redo_stack) == 1
    assert isinstance(mock_mw.data_store.redo_stack[0], StructuralAction)
    assert mock_mw.data_store.redo_stack[0].before_snapshot == {"snap": 1}
    assert mock_mw.data_store.redo_stack[0].label == "moved"


def test_newer_pickle_chosen_json_sync_fails_dirty_remains(dsp, mock_mw, tmp_path):
    mock_mw.project_manager.project_dir = str(tmp_path)
    mock_mw.project_manager.project = MagicMock()
    
    json_file = Path(tmp_path) / ".picoripi_session.json"
    pickle_file = Path(tmp_path) / ".picoripi_session"

    # Pickle is newer than JSON (Pickle: 200.0, JSON: 100.0)
    mock_mw.data_store.edited_data = {(0, 0): "old_json"}
    snapshot_json = mock_mw.data_store.get_session_snapshot()
    snapshot_json["saved_at"] = 100.0
    json_snapshot = dsp.serialize_session_to_json(snapshot_json)
    with json_file.open('w', encoding='utf-8') as f:
        json.dump(json_snapshot, f)

    mock_mw.data_store.edited_data = {(0, 0): "new_pickle"}
    snapshot_pickle = mock_mw.data_store.get_session_snapshot()
    snapshot_pickle["saved_at"] = 200.0
    with pickle_file.open('wb') as f:
        pickle.dump(snapshot_pickle, f)

    # Clear state
    mock_mw.data_store = AppDataStore()

    # Mock Path.replace to raise IOError to simulate sync failure
    with patch.object(Path, "replace", side_effect=IOError("write failed")):
        loaded = dsp.load_session_file()
        assert loaded is True
        # Since sync failed, _durable_session_dirty must remain True
        assert dsp._durable_session_dirty is True



