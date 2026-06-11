import pytest
import json
import datetime
from unittest.mock import MagicMock, patch
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox

from core.saved_translations_manager import SavedTranslationsManager
from core.data_state_processor import DataStateProcessor

@pytest.fixture
def temp_project_dir(tmp_path):
    return tmp_path

@pytest.fixture
def mock_mw_for_saved(temp_project_dir):
    mw = MagicMock()
    
    # Setup data_store
    mw.data_store = mw
    mw.data_store.data = [
        ["original_0_0", "original_0_1"],
        ["original_1_0"]
    ]
    mw.data_store.edited_file_data = []
    mw.data_store.edited_data = {}
    mw.data_store.current_block_idx = 0
    mw.data_store.current_string_idx = 0
    mw.data_store.block_names = {"0": "Block0", "1": "Block1"}
    mw.data_store.json_path = str(temp_project_dir / "single_file.json")
    mw.data_store.edited_json_path = str(temp_project_dir / "single_file_edited.json")
    mw.data_store.unsaved_changes = False
    mw.data_store.unsaved_block_indices = set()
    
    # Setup project_manager
    mw.project_manager = MagicMock()
    mw.project_manager.project_dir = str(temp_project_dir)
    mw.project_manager.project = MagicMock()
    mw.project_manager.project.name = "TestProject"
    
    # Setup mock blocks for project
    block0 = MagicMock()
    block0.source_file = "src/block0.json"
    block0.internal_key = "bk0"
    
    block1 = MagicMock()
    block1.source_file = "src/block1.json"
    block1.internal_key = "bk1"
    
    mw.project_manager.project.blocks = [block0, block1]
    
    # Map block index to project block index
    mw.block_to_project_file_map = {0: 0, 1: 1}
    
    # Decoupled mock components
    mw.ui_updater = MagicMock()
    mw.undo_manager = MagicMock()
    mw.current_game_rules = MagicMock()
    
    return mw

@pytest.fixture
def manager(mock_mw_for_saved):
    return SavedTranslationsManager(mock_mw_for_saved)

@pytest.fixture
def dsp_for_saved(mock_mw_for_saved):
    return DataStateProcessor(mock_mw_for_saved)

def test_saved_translations_path_project_mode(manager, mock_mw_for_saved, temp_project_dir):
    path = manager._get_saved_translations_path()
    assert path == temp_project_dir / "saved_translations.json"

def test_saved_translations_path_single_file_mode(manager, mock_mw_for_saved, temp_project_dir):
    mock_mw_for_saved.project_manager = None
    path = manager._get_saved_translations_path()
    assert path == temp_project_dir / "single_file_saved_translations.json"

def test_load_and_save_translations(manager, temp_project_dir):
    assert manager.load_all_saved_translations() == {}
    
    data = {"key1": "translation1", "key2": "translation2"}
    assert manager.save_all_saved_translations(data) is True
    
    loaded = manager.load_all_saved_translations()
    assert loaded == data

def test_save_translation_single(manager, mock_mw_for_saved):
    # Unique key for block 0, string 0 in project mode:
    # "src/block0.json::bk0::0"
    manager.save_translation(0, 0, "New Translation Text")
    
    translations = manager.load_all_saved_translations()
    key = "src/block0.json::bk0::0"
    assert key in translations
    assert translations[key] == "New Translation Text"
    
    assert manager.has_saved_translation(0, 0) is True
    assert manager.get_saved_translation(0, 0) == "New Translation Text"

def test_save_translations_bulk(manager):
    items = [(0, "Trans 0"), (1, "Trans 1")]
    manager.save_translations_bulk(0, items)
    
    translations = manager.load_all_saved_translations()
    assert translations["src/block0.json::bk0::0"] == "Trans 0"
    assert translations["src/block0.json::bk0::1"] == "Trans 1"

from handlers.saved_translations_handler import SavedTranslationsHandler

@pytest.fixture
def handler(mock_mw_for_saved, manager):
    mock_mw_for_saved.saved_translations_manager = manager
    # Ensure ui_updater has basic structure to not fail during calls
    mock_mw_for_saved.ui_updater = MagicMock()
    if not hasattr(mock_mw_for_saved, 'data_processor') or not mock_mw_for_saved.data_processor:
        mock_mw_for_saved.data_processor = MagicMock()
    return SavedTranslationsHandler(mock_mw_for_saved, mock_mw_for_saved.data_processor, mock_mw_for_saved.ui_updater)


@patch("handlers.saved_translations_handler.QMessageBox.warning")
def test_restore_translation_not_found(mock_warning, handler):
    # No saved translation exists yet
    res = handler.restore_translation(0, 0)
    assert res is False
    mock_warning.assert_called_once()


def test_restore_translation_success(handler, mock_mw_for_saved):
    mock_mw_for_saved.data_processor = MagicMock()
    handler.data_processor = mock_mw_for_saved.data_processor
    mock_mw_for_saved.data_processor.get_current_string_text.return_value = ("original_0_0", "original_data")
    
    mock_mw_for_saved.saved_translations_manager.save_translation(0, 0, "Restored Text")
    res = handler.restore_translation(0, 0)
    
    assert res is True
    mock_mw_for_saved.data_processor.update_edited_data.assert_called_once_with(
        0, 0, "Restored Text", action_type="RESTORE"
    )


def test_restore_translations_for_strings(handler, mock_mw_for_saved):
    mock_mw_for_saved.data_processor = MagicMock()
    handler.data_processor = mock_mw_for_saved.data_processor
    mock_mw_for_saved.saved_translations_manager.save_translation(0, 0, "Restored 0")
    mock_mw_for_saved.saved_translations_manager.save_translation(0, 1, "Restored 1")
    
    handler.restore_translations_for_strings(0, [0, 1])
    
    assert mock_mw_for_saved.data_processor.update_edited_data.call_count == 2
    mock_mw_for_saved.data_processor.update_edited_data.assert_any_call(
        0, 0, "Restored 0", action_type="RESTORE", skip_ui_refresh=True
    )
    mock_mw_for_saved.data_processor.update_edited_data.assert_any_call(
        0, 1, "Restored 1", action_type="RESTORE", skip_ui_refresh=True
    )


@patch("handlers.saved_translations_handler.QFileDialog.getSaveFileName")
@patch("handlers.saved_translations_handler.QMessageBox.information")
def test_export_translations_action(mock_info, mock_fd, handler, mock_mw_for_saved, temp_project_dir):
    export_path = temp_project_dir / "exported_trans.json"
    mock_fd.return_value = (str(export_path), "JSON Files (*.json)")
    
    mock_mw_for_saved.data_processor = MagicMock()
    handler.data_processor = mock_mw_for_saved.data_processor
    # Mock string 0 as translated, string 1 as original
    mock_mw_for_saved.data_processor.is_string_translated.side_effect = lambda b, s: s == 0
    mock_mw_for_saved.data_processor.get_current_string_text.return_value = ("Exported Translation", "edited_data")
    
    handler.export_translations_to_json_action()
    
    assert export_path.exists()
    with export_path.open('r', encoding='utf-8') as f:
        data = json.load(f)
    
    assert "files" in data
    assert "src/block0.json" in data["files"]
    assert data["files"]["src/block0.json"]["bk0"]["0"] == "Exported Translation"
    mock_info.assert_called_once()


@patch("handlers.saved_translations_handler.QFileDialog.getOpenFileName")
@patch("handlers.saved_translations_handler.QMessageBox.question")
@patch("handlers.saved_translations_handler.QMessageBox.information")
def test_import_translations_action(mock_info, mock_q, mock_fd, handler, mock_mw_for_saved, temp_project_dir):
    mock_q.return_value = QMessageBox.StandardButton.Yes
    import_path = temp_project_dir / "import_trans.json"
    
    import_data = {
        "files": {
            "src/block0.json": {
                "bk0": {
                    "0": "Imported Translation Text"
                }
            }
        }
    }
    with import_path.open('w', encoding='utf-8') as f:
        json.dump(import_data, f)
        
    mock_fd.return_value = (str(import_path), "JSON Files (*.json)")
    
    mock_mw_for_saved.data_processor = MagicMock()
    handler.data_processor = mock_mw_for_saved.data_processor
    
    handler.import_translations_from_json_action()
    
    mock_mw_for_saved.data_processor.update_edited_data.assert_called_once_with(
        0, 0, "Imported Translation Text", action_type="IMPORT", skip_ui_refresh=True
    )
    mock_info.assert_called_once()

def test_auto_save_on_revert_strings(dsp_for_saved, mock_mw_for_saved, manager):
    # Setup manager and dsp on main window
    mock_mw_for_saved.saved_translations_manager = manager
    mock_mw_for_saved.data_processor = dsp_for_saved
    
    # We edit string 0 in block 0
    mock_mw_for_saved.edited_data = {(0, 0): "Translation text 0"}
    
    curr, _ = dsp_for_saved.get_current_string_text(0, 0)
    orig = dsp_for_saved._get_string_from_source(0, 0, mock_mw_for_saved.data_store.data, "original_source_data")
    print(f"DEBUG: curr={curr}, orig={orig}")
    
    # Revert it
    dsp_for_saved.revert_strings_to_original(0, [0])
    
    # Check that it got auto-saved to saved translations list
    translations = manager.load_all_saved_translations()
    print(f"DEBUG: translations={translations}")
    key = "src/block0.json::bk0::0"
    assert key in translations
    assert translations[key] == "Translation text 0"

def test_auto_save_on_revert_blocks(dsp_for_saved, mock_mw_for_saved, manager):
    # Setup manager and dsp on main window
    mock_mw_for_saved.saved_translations_manager = manager
    mock_mw_for_saved.data_processor = dsp_for_saved
    
    # We edit string 0 in block 0
    mock_mw_for_saved.edited_data = {(0, 0): "Translation text 0"}
    
    # Revert block
    dsp_for_saved.revert_blocks_to_original([0])
    
    # Check that it got auto-saved
    translations = manager.load_all_saved_translations()
    key = "src/block0.json::bk0::0"
    assert key in translations
    assert translations[key] == "Translation text 0"

def test_resolve_bmg_id_to_indices_with_brackets(mock_mw_for_saved):
    from handlers.list_selection_handler import ListSelectionHandler
    
    # We mock prompt_composer's _get_block_label
    composer = MagicMock()
    composer.prompt_composer._get_block_label.side_effect = lambda idx: "d_MN00" if idx == 0 else "other"
    mock_mw_for_saved.translation_handler = composer
    
    handler = ListSelectionHandler(mock_mw_for_saved, MagicMock(), MagicMock())
    
    # Non-bracketed
    res = handler.resolve_bmg_id_to_indices("d_MN00_Str_125")
    assert res == (0, 125)
    
    # Bracketed
    res_bracketed = handler.resolve_bmg_id_to_indices("[d_MN00_Str_125]")
    assert res_bracketed == (0, 125)
