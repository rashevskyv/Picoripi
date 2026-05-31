import pytest
import json
from unittest.mock import MagicMock, patch
from pathlib import Path
from core.data_state_processor import DataStateProcessor

def test_save_current_edits_native_packing():
    # 1. Setup mocks mimicking project mode with archive files
    mw = MagicMock()
    mw.data_store = mw
    mw.data_store.data = [
        ["original_0_0", "original_0_1"]
    ]
    mw.data_store.edited_file_data = []
    mw.data_store.edited_data = {(0, 0): "translated_0_0"}
    mw.data_store.block_names = {0: "Block0"}
    mw.data_store.unsaved_changes = True
    mw.data_store.unsaved_block_indices = {0}
    mw.data_store.current_block_idx = 0
    mw.data_store.current_string_idx = 0
    
    mw.data_store.json_path = "original.json"
    mw.data_store.edited_json_path = "edited.json"
    mw.issue_scan_handler = MagicMock()
    
    # Enable project mode mocks
    mw.project_manager = MagicMock()
    mw.project_manager.project = MagicMock()
    
    # Setup mock block representing an archive member
    mock_block = MagicMock()
    mock_block.translation_file = ".extracted/translation/bmgres.arc/zel_unit.bmg"
    mw.project_manager.project.blocks = [mock_block]
    
    # Map index 0 to project block 0
    mw.block_to_project_file_map = {0: 0}
    
    # Setup base game rules mock
    mw.current_game_rules = MagicMock()
    mw.current_game_rules.original_keys = ["key0"]
    mw.current_game_rules.last_loaded_bmg = MagicMock()
    mw.current_game_rules.save_data_to_json_obj.return_value = b"NEW_BMG_BYTES"
    mw.current_game_rules.load_data_from_json_obj.return_value = (mw.data_store.data, None)
    
    # Setup project manager absolute path resolution
    # For relative BMG inside extracted folder
    def mock_get_absolute_path(rel_path, is_translation=False):
        if str(rel_path).startswith(".extracted/"):
            return f"C:/Temp/project/.extracted/translation/bmgres.arc/zel_unit.bmg"
        else:
            return f"C:/Temp/project/translation/{rel_path}"
            
    mw.project_manager.get_absolute_path.side_effect = mock_get_absolute_path
    
    # Mock ContainerManager and container
    mock_container = MagicMock()
    mock_container.pack.return_value = b"PACKED_ARC_BYTES"
    
    # Mock DSP
    dsp = DataStateProcessor(mw)
    
    # Patch Path operations, BMGFile, and ContainerManager
    with patch("core.containers.ContainerManager.open") as mock_cm_open, \
         patch("bmg_tool.BMGFile") as mock_bmg_file, \
         patch("core.data_state_processor.Path") as mock_path:
         
         # Mock path exists and writes
         mock_path_instance = MagicMock()
         mock_path_instance.exists.return_value = True
         mock_path_instance.read_bytes.return_value = b"NEW_BMG_BYTES"
         mock_path.return_value = mock_path_instance
         
         # Mock BMGFile instance
         mock_bmg_instance = MagicMock()
         mock_bmg_file.return_value = mock_bmg_instance
         
         # Mock container opening
         mw.project_manager.get_archive_container.return_value = mock_container
         mock_container.read_file.return_value = b"ORIGINAL_BMG_BYTES_FROM_DISK"
         
         # 2. Run save_current_edits
         result = dsp.save_current_edits(ask_confirmation=False)
         
         # 3. Assert success and correctness
         assert result is True
         
         # Verify BMG pre-loading: BMGFile load was called with original bytes from disk
         mock_bmg_instance.load.assert_called_once_with(b"ORIGINAL_BMG_BYTES_FROM_DISK")
         assert mw.current_game_rules.last_loaded_bmg == mock_bmg_instance
         
         # Verify container overlay: write_file was called with BMG path inside archive and modified bytes
         mock_container.write_file.assert_called_once_with("zel_unit.bmg", b"NEW_BMG_BYTES")
         
         # Verify container pack was executed
         mock_container.pack.assert_called_once()
         
         # Verify packed bytes were written to the correct absolute destination archive path
         mock_path.assert_any_call("C:/Temp/project/translation/bmgres.arc")
         mock_path_instance.write_bytes.assert_called_once_with(b"PACKED_ARC_BYTES")
         
         # Verify issues cache saving was triggered
         mw.issue_scan_handler._save_issues_cache.assert_called_once()
