import pytest
import pickle
from pathlib import Path
from unittest.mock import MagicMock, patch
from core.data_store import AppDataStore
from core.data_state_processor import DataStateProcessor

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

def test_get_session_file_path(dsp, mock_mw, tmp_path):
    # Case 1: Project mode
    mock_mw.project_manager.project_dir = str(tmp_path / "proj")
    mock_mw.project_manager.project = MagicMock()
    path = dsp.get_session_file_path()
    assert path == Path(tmp_path / "proj" / ".picoripi_session")

    # Case 2: Single file mode
    mock_mw.project_manager.project_dir = None
    mock_mw.project_manager.project = None
    mock_mw.data_store.edited_json_path = str(tmp_path / "file_edited.json")
    path = dsp.get_session_file_path()
    assert path == Path(tmp_path / ".picoripi_session")

    # Case 3: No active path
    mock_mw.data_store.edited_json_path = None
    path = dsp.get_session_file_path()
    assert path is None

def test_autosave_and_load_session(dsp, mock_mw, tmp_path):
    mock_mw.project_manager.project_dir = str(tmp_path)
    mock_mw.project_manager.project = MagicMock()
    
    # Set up some state
    mock_mw.data_store.edited_data = {(0, 0): "changed_val", (1, 5): "another_changed_val"}
    mock_mw.data_store.current_block_idx = 1
    mock_mw.data_store.current_string_idx = 5
    mock_mw.data_store.current_category_name = "test_cat"

    # Autosave
    dsp._autosave_session(force=True)

    session_file = Path(tmp_path) / ".picoripi_session"
    assert session_file.exists()

    # Clear current state
    mock_mw.data_store = AppDataStore()
    assert mock_mw.data_store.edited_data == {}

    # Load session
    res = dsp.load_session_file()
    assert res is True
    assert mock_mw.data_store.edited_data == {(0, 0): "changed_val", (1, 5): "another_changed_val"}
    assert mock_mw.data_store.current_block_idx == 1
    assert mock_mw.data_store.current_string_idx == 5
    assert mock_mw.data_store.current_category_name == "test_cat"

    # Verify clear
    dsp.clear_session_file()
    assert not session_file.exists()

def test_save_specific_edits(dsp, mock_mw, tmp_path):
    mock_mw.project_manager.project_dir = str(tmp_path)
    mock_mw.project_manager.project = MagicMock()
    mock_mw.data_store.edited_json_path = str(tmp_path / "edited.json")
    
    mock_mw.data_store.data = [
        ["orig0", "orig1"],
        ["orig2", "orig3"]
    ]
    mock_mw.data_store.edited_file_data = [
        ["orig0", "orig1"],
        ["orig2", "orig3"]
    ]
    
    # Make edits to three strings
    mock_mw.data_store.edited_data = {
        (0, 0): "new0_0",
        (0, 1): "new0_1",
        (1, 0): "new1_0"
    }
    mock_mw.data_store.unsaved_changes = True

    # Save only (0, 0) and (1, 0)
    strings_to_save = [(0, 0), (1, 0)]
    
    # We mock _perform_save_impl to simulate successful save and return true
    with patch.object(dsp, '_perform_save_impl', return_value=(True, [], [])) as mock_save:
        res = dsp.save_specific_edits(strings_to_save, ask_confirmation=False)
        assert res is True
        mock_save.assert_called_once()
        
        # Verify that output_data_list passed to mock_save contains only changes for selected keys
        # output_data_list should be:
        # Block 0: ["new0_0", "orig1"] (new0_1 should not be saved yet!)
        # Block 1: ["new1_0", "orig3"]
        saved_data = mock_save.call_args[0][0]
        assert saved_data[0] == ["new0_0", "orig1"]
        assert saved_data[1] == ["new1_0", "orig3"]
        
    # Unsaved changes list in data_store should now only contain (0, 1)
    assert mock_mw.data_store.edited_data == {(0, 1): "new0_1"}
    assert mock_mw.data_store.unsaved_changes is True

def test_dirty_flag_behavior(dsp, mock_mw, tmp_path):
    mock_mw.project_manager.project_dir = str(tmp_path)
    mock_mw.project_manager.project = MagicMock()
    
    # 1. Initial state is not dirty
    assert dsp._session_dirty is False
    
    # 2. schedule_autosave sets dirty to True
    dsp.schedule_autosave()
    assert dsp._session_dirty is True
    
    # 3. _autosave_session() when dirty=False should skip writing
    session_file = Path(tmp_path) / ".picoripi_session"
    dsp._session_dirty = False
    
    # Mock pickle.dump to see if it is called
    with patch("pickle.dump") as mock_dump:
        dsp._autosave_session(force=False)
        mock_dump.assert_not_called()
        assert not session_file.exists()
        
    # 4. _autosave_session() with force=True should write even if dirty=False
    with patch("pickle.dump") as mock_dump:
        dsp._autosave_session(force=True)
        mock_dump.assert_called_once()
        assert dsp._session_dirty is False  # becomes clean after save
        
    # 5. _autosave_session() with dirty=True should write
    dsp._session_dirty = True
    with patch("pickle.dump") as mock_dump:
        dsp._autosave_session(force=False)
        mock_dump.assert_called_once()
        assert dsp._session_dirty is False  # becomes clean after save

def test_load_session_resets_dirty(dsp, mock_mw, tmp_path):
    mock_mw.project_manager.project_dir = str(tmp_path)
    mock_mw.project_manager.project = MagicMock()
    
    # Save a valid session dummy
    dsp._session_dirty = True
    dsp._autosave_session()
    
    # Make dirty again
    dsp._session_dirty = True
    if dsp.autosave_timer:
        dsp.autosave_timer.start()
        
    # Load
    res = dsp.load_session_file()
    assert res is True
    assert dsp._session_dirty is False
    if dsp.autosave_timer:
        assert not dsp.autosave_timer.isActive()

def test_update_edited_data_triggers_autosave(dsp, mock_mw, tmp_path):
    mock_mw.project_manager.project_dir = str(tmp_path)
    mock_mw.project_manager.project = MagicMock()
    
    mock_mw.data_store.edited_data = {}
    mock_mw.data_store.data = [["orig"]]
    mock_mw.data_store.edited_file_data = [["orig"]]
    
    with patch.object(dsp, 'schedule_autosave') as mock_sched:
        dsp.update_edited_data(0, 0, "new")
        mock_sched.assert_called_once()

def test_save_specific_edits_forces_autosave(dsp, mock_mw, tmp_path):
    mock_mw.project_manager.project_dir = str(tmp_path)
    mock_mw.project_manager.project = MagicMock()
    mock_mw.data_store.edited_json_path = str(tmp_path / "edited.json")
    
    mock_mw.data_store.data = [["orig"]]
    mock_mw.data_store.edited_file_data = [["orig"]]
    mock_mw.data_store.edited_data = {(0, 0): "new"}
    
    with patch.object(dsp, '_perform_save_impl', return_value=(True, [], [])) as mock_save, \
         patch.object(dsp, '_autosave_session') as mock_autosave:
        dsp.save_specific_edits([(0, 0)], ask_confirmation=False)
        mock_autosave.assert_called_once_with(force=True)

