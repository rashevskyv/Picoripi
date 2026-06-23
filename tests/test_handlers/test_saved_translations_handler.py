import pytest
import json
from unittest.mock import MagicMock, patch, mock_open
from PyQt6.QtWidgets import QMessageBox, QFileDialog
from handlers.saved_translations_handler import SavedTranslationsHandler

@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.saved_translations_manager = MagicMock()
    ctx.undo_manager = MagicMock()
    ctx.text_operation_handler = MagicMock()
    ctx.project_manager = MagicMock()
    ctx.statusBar = MagicMock()
    ctx.block_to_project_file_map = {}
    
    ctx.data_store = MagicMock()
    ctx.data_store.current_block_idx = 0
    ctx.data_store.current_string_idx = 0
    ctx.data_store.data = [["Line 1", "Line 2"]]
    ctx.data_store.block_names = {"0": "block_0"}
    
    return ctx

def test_saved_translations_handler_restore_translation_not_found(mock_ctx):
    mock_ctx.saved_translations_manager.get_saved_translation.return_value = None
    data_processor = MagicMock()
    ui_updater = MagicMock()
    
    handler = SavedTranslationsHandler(mock_ctx, data_processor, ui_updater)
    
    with patch.object(QMessageBox, 'warning') as mock_warn:
        res = handler.restore_translation(0, 0)
        assert res is False
        mock_warn.assert_called_once()

def test_saved_translations_handler_restore_translation_success(mock_ctx):
    mock_ctx.saved_translations_manager.get_saved_translation.return_value = "Saved Translation"
    data_processor = MagicMock()
    data_processor.get_current_string_text.return_value = ("Original Line", None)
    ui_updater = MagicMock()
    
    handler = SavedTranslationsHandler(mock_ctx, data_processor, ui_updater)
    
    res = handler.restore_translation(0, 0)
    assert res is True
    data_processor.update_edited_data.assert_called_with(0, 0, "Saved Translation", action_type="RESTORE")
    ui_updater.update_text_views.assert_called_once()

def test_saved_translations_handler_restore_translations_for_strings(mock_ctx):
    mock_ctx.saved_translations_manager.load_all_saved_translations.return_value = {
        "0_0": "T0",
        "0_1": "T1"
    }
    mock_ctx.saved_translations_manager._get_string_unique_key.side_effect = lambda b, s: f"{b}_{s}"
    data_processor = MagicMock()
    ui_updater = MagicMock()
    
    handler = SavedTranslationsHandler(mock_ctx, data_processor, ui_updater)
    handler.restore_translations_for_strings(0, [0, 1])
    
    assert data_processor.update_edited_data.call_count == 2
    ui_updater.update_text_views.assert_called()

def test_saved_translations_handler_save_translation_action(mock_ctx):
    data_processor = MagicMock()
    data_processor.get_current_string_text.return_value = ("Edited translation", None)
    data_processor._get_string_from_source.return_value = "Original text"
    
    handler = SavedTranslationsHandler(mock_ctx, data_processor, MagicMock())
    
    with patch.object(QMessageBox, 'information') as mock_info:
        handler.save_translation_action()
        mock_ctx.saved_translations_manager.save_translation.assert_called_with(0, 0, "Edited translation")
        mock_info.assert_called_once()

def test_saved_translations_handler_export_translations(mock_ctx):
    data_processor = MagicMock()
    data_processor.is_string_translated.return_value = True
    data_processor.get_current_string_text.return_value = ("Translated String", None)
    
    mock_ctx.project_manager.project.name = "MyProject"
    mock_ctx.project_manager.project.blocks = []
    
    handler = SavedTranslationsHandler(mock_ctx, data_processor, MagicMock())
    
    m_open = mock_open()
    with patch('builtins.open', m_open):
        with patch.object(QFileDialog, 'getSaveFileName', return_value=("/path/to/export.json", "json")):
            with patch.object(QMessageBox, 'information') as mock_info:
                handler.export_translations_to_json_action()
                m_open.assert_called_once_with("/path/to/export.json", 'w', encoding='utf-8')
                mock_info.assert_called_once()

def test_saved_translations_handler_import_translations(mock_ctx):
    data_processor = MagicMock()
    mock_ctx.project_manager.project.blocks = []
    
    handler = SavedTranslationsHandler(mock_ctx, data_processor, MagicMock())
    
    json_data = json.dumps({
        "files": {
            "block_0": {
                "": {
                    "0": "Imported Translation"
                }
            }
        }
    })
    
    m_open = mock_open(read_data=json_data)
    with patch('builtins.open', m_open):
        with patch.object(QFileDialog, 'getOpenFileName', return_value=("/path/to/import.json", "json")):
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
                with patch.object(QMessageBox, 'information') as mock_info:
                    handler.import_translations_from_json_action()
                    data_processor.update_edited_data.assert_called_with(0, 0, "Imported Translation", action_type="IMPORT", skip_ui_refresh=True)
                    mock_info.assert_called_once()
