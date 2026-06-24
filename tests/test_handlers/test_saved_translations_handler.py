import pytest
import json
from types import SimpleNamespace
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

def test_saved_translations_handler_export_original(mock_ctx):
    data_processor = MagicMock()
    data_processor._get_string_from_source.side_effect = lambda b_idx, s_idx, data, name: data[b_idx][s_idx]

    mock_ctx.project_manager.project.name = "MyProject"
    mock_ctx.project_manager.project.blocks = []

    handler = SavedTranslationsHandler(mock_ctx, data_processor, MagicMock())

    m_open = mock_open()
    with patch('builtins.open', m_open):
        with patch.object(QFileDialog, 'getSaveFileName', return_value=("/path/to/export_original.json", "json")):
            with patch.object(QMessageBox, 'information') as mock_info:
                with patch('handlers.saved_translations_handler.json.dump') as mock_dump:
                    handler.export_original_to_json_action()
                    m_open.assert_called_once_with("/path/to/export_original.json", 'w', encoding='utf-8')
                    mock_info.assert_called_once()
                    exported = mock_dump.call_args.args[0]
                    assert exported["project_name"] == "MyProject"
                    assert exported["files"] == {
                        "block_0": {
                            "": {
                                "0": "Line 1",
                                "1": "Line 2",
                            }
                        }
                    }

def test_saved_translations_handler_export_original_keeps_project_sub_blocks(mock_ctx):
    data_processor = MagicMock()
    data_processor._get_string_from_source.side_effect = lambda b_idx, s_idx, data, name: data[b_idx][s_idx]

    mock_ctx.data_store.data = [["Block A line"], ["Block B line"]]
    mock_ctx.data_store.block_names = {"0": "Block A", "1": "Block B"}
    mock_ctx.block_to_project_file_map = {0: 0, 1: 0}
    mock_ctx.project_manager.project.name = "MyProject"
    mock_ctx.project_manager.project.blocks = [
        SimpleNamespace(source_file="script.txt", internal_key=None)
    ]

    handler = SavedTranslationsHandler(mock_ctx, data_processor, MagicMock())

    with patch('builtins.open', mock_open()):
        with patch.object(QFileDialog, 'getSaveFileName', return_value=("/path/to/export_original.json", "json")):
            with patch.object(QMessageBox, 'information'):
                with patch('handlers.saved_translations_handler.json.dump') as mock_dump:
                    handler.export_original_to_json_action()
                    exported = mock_dump.call_args.args[0]
                    assert exported["files"] == {
                        "script.txt": {
                            "Block A": {"0": "Block A line"},
                            "Block B": {"0": "Block B line"},
                        }
                    }

def test_export_original_action_menu_connection():
    from ui.main_window.main_window_event_handler import MainWindowEventHandler
    mw = MagicMock()
    mw.export_original_action = MagicMock()
    mw.saved_translations_handler = MagicMock()

    handler = MainWindowEventHandler(mw)
    handler.connect_signals()

    mw.export_original_action.triggered.connect.assert_called_once_with(
        mw.saved_translations_handler.export_original_to_json_action
    )

def test_export_original_action_enabling():
    from handlers.app_action_handler import AppActionHandler
    mw = MagicMock()
    mw.export_original_action = MagicMock()

    data_processor = MagicMock()
    data_processor.load_session_file.return_value = True
    ui_updater = MagicMock()
    rules = MagicMock()

    handler = AppActionHandler(mw, data_processor, ui_updater, rules)
    with patch('PyQt6.QtCore.QTimer.singleShot'):
        handler.load_all_data_for_path("dummy.json")

    mw.export_original_action.setEnabled.assert_called_with(True)
