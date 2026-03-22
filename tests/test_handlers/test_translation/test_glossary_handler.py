import pytest
from unittest.mock import MagicMock, patch, ANY
from PyQt5.QtWidgets import QDialog, QMessageBox

from handlers.translation.glossary_handler import GlossaryHandler
from core.glossary_manager import GlossaryEntry, GlossaryOccurrence
from core.translation.providers import ProviderResponse

@pytest.fixture
def mock_main_handler():
    mh = MagicMock()
    mh.mw = MagicMock()
    mh.mw.tools_menu = MagicMock()
    mh.mw.data = [["Block 0 String 0", "Block 0 String 1"]]
    mh.mw.current_game_rules = MagicMock()
    mh.mw.current_game_rules.get_display_name.return_value = "Test Game"
    mh.ui_handler = MagicMock()
    mh.ai_lifecycle_manager = MagicMock()
    return mh

@pytest.fixture
def gh(mock_main_handler):
    with patch('handlers.translation.glossary_handler.GlossaryManager'), \
         patch('handlers.translation.glossary_handler.GlossaryPromptManager'), \
         patch('handlers.translation.glossary_handler.GlossaryOccurrenceUpdater'):
        handler = GlossaryHandler(mock_main_handler)
        handler._prompt_manager = MagicMock()
        handler._occurrence_updater = MagicMock()
        handler.glossary_manager = MagicMock()
        return handler

def test_gh_proxies(gh):
    gh._prompt_manager.current_prompts_path = "path"
    assert gh._current_prompts_path == "path"
    
    gh._occurrence_updater.translation_update_dialog = "dialog"
    assert gh.translation_update_dialog == "dialog"
    gh.translation_update_dialog = "new_dialog"
    assert gh._occurrence_updater.translation_update_dialog == "new_dialog"
    
    gh.load_prompts()
    gh._prompt_manager.load_prompts.assert_called_once()
    
    gh.save_prompt_section("s", "f", "v")
    gh._prompt_manager.save_prompt_section.assert_called_with("s", "f", "v")
    
    gh._get_glossary_prompt_template()
    gh._prompt_manager.get_glossary_prompt_template.assert_called_once()
    
    gh._update_glossary_highlighting()
    gh._prompt_manager._update_glossary_highlighting.assert_called_once()
    
    gh._ensure_glossary_loaded(glossary_text="t", plugin_name="p", glossary_path="pth")
    gh._prompt_manager._ensure_glossary_loaded.assert_called_with(glossary_text="t", plugin_name="p", glossary_path="pth")
    
    gh.request_glossary_occurrence_update(a=1)
    gh._occurrence_updater.request_glossary_occurrence_update.assert_called_with(a=1)
    
    gh.request_glossary_occurrence_batch_update(b=2)
    gh._occurrence_updater.request_glossary_occurrence_batch_update.assert_called_with(b=2)
    
    gh.request_glossary_notes_variation(c=3)
    gh._occurrence_updater.request_glossary_notes_variation.assert_called_with(c=3)
    
    gh._handle_occurrence_ai_result(d=4)
    gh._occurrence_updater.handle_occurrence_ai_result.assert_called_with(d=4)
    
    gh._handle_occurrence_batch_success(e=5)
    gh._occurrence_updater.handle_occurrence_batch_success.assert_called_with(e=5)
    
    gh._handle_occurrence_ai_error("err", True)
    gh._occurrence_updater._handle_occurrence_ai_error.assert_called_with("err", True)
    
    gh._handle_glossary_occurrence_update_success(1, 2)
    gh._occurrence_updater.handle_glossary_occurrence_update_success.assert_called_with(1, 2)
    
    gh._handle_glossary_occurrence_batch_success(3, 4)
    gh._occurrence_updater.handle_glossary_occurrence_batch_success.assert_called_with(3, 4)

@patch('handlers.translation.glossary_handler.QAction')
def test_gh_install_menu_actions(mock_action, gh):
    gh.main_handler._reset_session_action = None
    gh.install_menu_actions()
    
    # Needs to be called twice to cover the condition where actions exist
    # First time adds them
    assert gh._open_glossary_action is not None
    assert gh.main_handler._reset_session_action is not None
    
    # Second time doesn't recreate
    action1 = gh._open_glossary_action
    gh.install_menu_actions()
    assert gh._open_glossary_action == action1

def test_gh_initialize_glossary_highlighting(gh):
    gh.initialize_glossary_highlighting()
    gh._prompt_manager.initialize_highlighting.assert_called_once()

@patch('handlers.translation.glossary_handler.GlossaryDialog')
@patch('handlers.translation.glossary_handler.QMessageBox')
def test_gh_show_glossary_dialog(mock_box, mock_dialog, gh):
    mock_dialog_inst = mock_dialog.return_value
    
    # Prompts None
    gh._prompt_manager.load_prompts.return_value = (None, None)
    gh.show_glossary_dialog()
    assert gh.dialog is None
    
    # Empty glossary
    gh._prompt_manager.load_prompts.return_value = ("sys", "text")
    gh.glossary_manager.get_entries.return_value = []
    gh.show_glossary_dialog()
    mock_box.information.assert_called_once()
    mock_box.reset_mock()
    
    # No data
    gh.glossary_manager.get_entries.return_value = [GlossaryEntry("a", "b", "c")]
    gh.mw.data = None
    gh.show_glossary_dialog()
    mock_box.information.assert_called_once()
    mock_box.reset_mock()
    
    # Success
    gh.mw.data = [[]]
    gh.show_glossary_dialog("initial")
    assert gh.dialog == mock_dialog_inst
    mock_dialog_inst.show.assert_called_once()
    
    # Already shown
    mock_dialog_inst.isVisible.return_value = True
    gh.show_glossary_dialog()
    mock_dialog_inst.raise_.assert_called_once()
    mock_dialog_inst.activateWindow.assert_called_once()
    
    # Close
    gh._on_glossary_dialog_closed()
    assert gh.dialog is None

@patch('handlers.translation.glossary_handler.GlossaryEditDialog')
def test_gh_add_edit_glossary_entry(mock_dialog, gh):
    mock_dialog_inst = mock_dialog.return_value
    mock_dialog_inst.exec_.return_value = QDialog.Rejected
    
    # Test rejection
    gh.add_glossary_entry("Test")
    mock_dialog_inst.get_values.assert_not_called()
    
    # Test accepted, update translation
    mock_dialog_inst.exec_.return_value = QDialog.Accepted
    mock_dialog_inst.get_values.return_value = ("NewTrans", "NewNotes")
    
    gh.glossary_manager.get_entry.return_value = GlossaryEntry("Test", "OldTrans", "OldNotes")
    entry_mock = MagicMock()
    entry_mock.original = "Test"
    gh.glossary_manager.update_entry.return_value = entry_mock
    
    gh.edit_glossary_entry("Test", is_new=False)
    gh.glossary_manager.update_entry.assert_called_with("Test", "NewTrans", "NewNotes")
    gh.glossary_manager.save_to_disk.assert_called()
    gh._prompt_manager._update_glossary_highlighting.assert_called()
    gh._occurrence_updater.show_translation_update_dialog.assert_called()
    
    # Test accepted, only notes updated for existing entry
    mock_dialog_inst.get_values.return_value = ("", "NewNotes")
    entry = GlossaryEntry("Test", "Trans", "OldNotes")
    gh.glossary_manager.get_entry.return_value = entry
    gh.edit_glossary_entry("Test", is_new=False)
    gh.glossary_manager.update_entry.assert_called_with("Test", "Trans", "NewNotes")

@patch('handlers.translation.glossary_handler.GlossaryEditDialog')
def test_gh_ai_fill_glossary_entry(mock_dialog, gh):
    d = mock_dialog.return_value
    
    gh.main_handler._prepare_provider.return_value = None
    gh._ai_fill_glossary_entry("term", "context", d)
    d.set_ai_busy.assert_not_called()
    
    provider = MagicMock()
    gh.main_handler._prepare_provider.return_value = provider
    gh._prompt_manager.get_glossary_prompt_template.return_value = (None, None)
    gh._ai_fill_glossary_entry("term", "context", d)
    d.set_ai_busy.assert_not_called()
    
    gh._prompt_manager.get_glossary_prompt_template.return_value = ("t {{GAME_NAME}}", None)
    gh.main_handler._maybe_edit_prompt.return_value = None
    gh._ai_fill_glossary_entry("term", "context", d)
    d.set_ai_busy.assert_not_called()
    
    gh.main_handler._maybe_edit_prompt.return_value = ("sys", "user")
    gh._ai_fill_glossary_entry("term", "context", d)
    d.set_ai_busy.assert_called_with(True)
    gh.main_handler._run_ai_task.assert_called_once()

from components.glossary_edit_dialog import GlossaryEditDialog

@patch('handlers.translation.glossary_handler.QMessageBox')
def test_gh_handle_ai_fill(mock_box, gh):
    dialog = MagicMock(spec=GlossaryEditDialog)
    dialog.get_values.return_value = ("oldT", "oldN")
    ctx = {'dialog': dialog}
    
    # Error
    gh._handle_ai_fill_error("err", ctx)
    dialog.set_ai_busy.assert_called_with(False)
    mock_box.warning.assert_called_once()
    mock_box.reset_mock()
    
    # Success bad JSON
    gh.main_handler._clean_model_output.return_value = "invalid"
    gh._handle_ai_fill_success(ProviderResponse(), ctx)
    mock_box.warning.assert_called_once()
    mock_box.reset_mock()
    
    # Success no fields
    gh.main_handler._clean_model_output.return_value = "{}"
    gh._handle_ai_fill_success(ProviderResponse(), ctx)
    mock_box.information.assert_called_once()
    mock_box.reset_mock()
    
    # Success
    gh.main_handler._clean_model_output.return_value = '{"translation": "nT", "notes": "nN"}'
    gh._handle_ai_fill_success(ProviderResponse(), ctx)
    dialog.set_values.assert_called_with("nT", "nN")

def test_gh_start_glossary_notes_variation(gh):
    d = MagicMock()
    gh._occurrence_updater.request_glossary_notes_variation.return_value = False
    gh._start_glossary_notes_variation(term="t", translation="tr", notes="n", context_line="c", target_dialog=d)
    
    d.set_ai_busy.assert_called_with(False)

def test_gh_handle_notes_variation_from_dialog(gh):
    # Setup dialog
    gh.dialog = MagicMock()
    gh.mw.data = [["Block 0 String 0"]]
    
    occurrence = GlossaryOccurrence(GlossaryEntry("t", "tr", "n"), 0, 0, 0, 0, 0, "Block 0 String 0")
    gh.glossary_manager.build_occurrence_index.return_value = {"t": [occurrence]}
    
    gh._handle_notes_variation_from_dialog(GlossaryEntry("t", "tr", "n"))
    gh._occurrence_updater.request_glossary_notes_variation.assert_called_once()

@patch('handlers.translation.glossary_handler.QMessageBox')
def test_gh_handle_glossary_notes_variation_success(mock_box, gh):
    gh.main_handler.ai_lifecycle_manager._clean_model_output.return_value = "cleaned"
    gh.main_handler.ui_handler.parse_variation_payload.return_value = []
    
    gh._handle_glossary_notes_variation_success(ProviderResponse(), {})
    mock_box.information.assert_called_once()
    
    gh.main_handler.ui_handler.parse_variation_payload.return_value = ["v1"]
    gh.main_handler.ui_handler.show_variations_dialog.return_value = "v1"
    
    d = MagicMock()
    d.get_values.return_value = ("tr", "old")
    gh._handle_glossary_notes_variation_success(ProviderResponse(), {'dialog': d})
    d.set_values.assert_called_with("tr", "v1")

def test_gh_jump_to_occurrence(gh):
    occ = GlossaryOccurrence(GlossaryEntry("t", "tr", "n"), 0, 1, 2, 0, 0, "line")
    gh._jump_to_occurrence(occ)
    gh.main_handler.ui_handler._activate_entry.assert_called_with({'block_idx': 0, 'string_idx': 1, 'line_idx': 2})

def test_gh_handle_glossary_entry_update(gh):
    entry1 = GlossaryEntry("old", "tr", "n")
    gh.glossary_manager.get_entry.return_value = entry1
    gh.glossary_manager.update_entry.return_value = True
    
    gh._handle_glossary_entry_update("old", "new", "nn")
    gh.glossary_manager.update_entry.assert_called_with("old", "new", "nn")
    gh._prompt_manager._update_glossary_highlighting.assert_called()

def test_gh_handle_glossary_entry_delete(gh):
    gh.glossary_manager.delete_entry.return_value = True
    gh._handle_glossary_entry_delete("term")
    gh.glossary_manager.delete_entry.assert_called_with("term")
    gh._prompt_manager._update_glossary_highlighting.assert_called()
