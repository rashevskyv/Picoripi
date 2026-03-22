import pytest
from unittest.mock import MagicMock, patch, ANY
import json
from PyQt5.QtWidgets import QMessageBox

from handlers.translation.glossary_occurrence_updater import GlossaryOccurrenceUpdater
from core.glossary_manager import GlossaryEntry, GlossaryOccurrence
from core.translation.providers import ProviderResponse

@pytest.fixture
def mock_gh():
    gh = MagicMock()
    gh.mw = MagicMock()
    gh.main_handler = MagicMock()
    gh.main_handler.ai_lifecycle_manager = MagicMock()
    return gh

@pytest.fixture
def updater(mock_gh):
    return GlossaryOccurrenceUpdater(mock_gh)

@patch('handlers.translation.glossary_occurrence_updater.GlossaryTranslationUpdateDialog')
def test_gou_show_translation_update_dialog(mock_dialog, updater):
    mock_dialog_inst = mock_dialog.return_value
    
    entry = GlossaryEntry("t", "tr")
    occ = GlossaryOccurrence(entry, 0, 0, 0, 0, 0, "line")
    
    # Show closed dialog
    updater.show_translation_update_dialog(entry=entry, previous_translation="old", occurrences=[occ])
    assert updater._current_translation_entry == entry
    assert updater._previous_translation_value == "old"
    assert updater.translation_update_dialog == mock_dialog_inst
    mock_dialog_inst.show.assert_called_once()
    
    # Show already open dialog
    mock_dialog_inst.isVisible.return_value = True
    updater.show_translation_update_dialog(entry=entry, previous_translation="old2", occurrences=[occ])
    mock_dialog_inst.raise_.assert_called_once()
    mock_dialog_inst.activateWindow.assert_called_once()

def test_gou_on_dialog_closed(updater):
    updater.translation_update_dialog = MagicMock()
    updater._pending_ai_occurrences = [1]
    updater._current_translation_entry = "e"
    updater._previous_translation_value = "v"
    updater._batch_prompt_override = "p"
    
    updater._on_dialog_closed()
    assert updater.translation_update_dialog is None
    assert updater._pending_ai_occurrences == []
    assert updater._current_translation_entry is None
    assert updater._previous_translation_value is None
    assert updater._batch_prompt_override is None

def test_gou_occurrence_helpers(updater):
    occ = GlossaryOccurrence(GlossaryEntry("t", "tr"), 1, 2, 3, 0, 0, "line")
    
    # Original text
    updater._gh._get_original_string.return_value = "orig"
    assert updater._get_occurrence_original_text(occ) == "orig"
    updater._gh._get_original_string.assert_called_with(1, 2)
    
    # Translation text
    updater._main_handler.data_processor.get_current_string_text.return_value = ("trans", {})
    assert updater._get_occurrence_translation_text(occ) == "trans"
    updater._main_handler.data_processor.get_current_string_text.assert_called_with(1, 2)
    
    # Apply translation
    updater._mw.current_block_idx = 1
    updater._mw.current_string_idx = 2
    updater._apply_occurrence_translation(occ, "new_t")
    
    updater._main_handler.data_processor.update_edited_data.assert_called_with(1, 2, "new_t")
    updater._mw.ui_updater.populate_strings_for_block.assert_called_with(1)
    updater._mw.ui_updater.update_text_views.assert_called()
    updater._mw.ui_updater.update_block_item_text_with_problem_count.assert_called_with(1)

def test_gou_request_ai_occurrence_update(updater):
    # No dialog
    updater._request_ai_occurrence_update(None, False)
    
    updater.translation_update_dialog = MagicMock()
    updater._current_translation_entry = GlossaryEntry("t", "tr")
    occ = GlossaryOccurrence(updater._current_translation_entry, 1, 2, 3, 0, 0, "line")
    
    updater._main_handler.data_processor.get_current_string_text.return_value = ("trans", {})
    
    with patch.object(updater, 'request_glossary_occurrence_update') as mock_req:
        mock_req.return_value = None
        updater._request_ai_occurrence_update(occ, False)
        
        updater.translation_update_dialog.set_ai_busy.assert_called_with(True)
        updater.translation_update_dialog.set_batch_active.assert_not_called()
        mock_req.assert_called_once()
        
        mock_req.reset_mock()
        updater._request_ai_occurrence_update(occ, True)
        updater.translation_update_dialog.set_batch_active.assert_called_with(True)
        mock_req.assert_called_once()

@patch('handlers.translation.glossary_occurrence_updater.QMessageBox')
def test_gou_request_glossary_occurrence_update(mock_box, updater):
    # No provider
    updater._main_handler.ai_lifecycle_manager._prepare_provider.return_value = None
    assert updater.request_glossary_occurrence_update(
        occurrence=None, original_text="", current_translation="", term="t",
        old_term_translation="", new_term_translation="", dialog=None, from_batch=False
    ) is None
    
    # Provider, no prompts
    provider = MagicMock()
    updater._main_handler.ai_lifecycle_manager._prepare_provider.return_value = provider
    updater._gh.load_prompts.return_value = (None, None)
    assert updater.request_glossary_occurrence_update(
        occurrence=None, original_text="", current_translation="", term="t",
        old_term_translation="", new_term_translation="", dialog=None, from_batch=False
    ) is None
    
    # Success, edit rejected
    updater._gh.load_prompts.return_value = ("sys", "txt")
    updater._main_handler.prompt_composer.compose_glossary_occurrence_update_request.return_value = ("c_sys", "c_user")
    updater._main_handler._maybe_edit_prompt.return_value = None
    assert updater.request_glossary_occurrence_update(
        occurrence=None, original_text="", current_translation="", term="t",
        old_term_translation="", new_term_translation="", dialog=None, from_batch=False
    ) is None
    
    # Success
    updater._main_handler._maybe_edit_prompt.return_value = ("e_sys", "e_user")
    res = updater.request_glossary_occurrence_update(
        occurrence=None, original_text="", current_translation="", term="t",
        old_term_translation="", new_term_translation="", dialog=None, from_batch=False
    )
    assert res == ("e_sys", "e_user")
    updater._main_handler.ai_lifecycle_manager.run_ai_task.assert_called_once()

def test_gou_ai_response_handlers(updater):
    occ = GlossaryOccurrence(GlossaryEntry("t", "tr"), 1, 2, 3, 0, 0, "line")
    
    # handle_occurrence_ai_result
    updater.translation_update_dialog = MagicMock()
    updater._pending_ai_occurrences = [occ]
    
    with patch.object(updater, '_resume_ai_occurrence_batch') as mock_res:
        updater.handle_occurrence_ai_result(occurrence=occ, updated_translation="u", from_batch=True)
        updater.translation_update_dialog.on_ai_result.assert_called_with(occ, "u")
        mock_res.assert_called_once()
        
        mock_res.reset_mock()
        updater._pending_ai_occurrences = []
        updater.handle_occurrence_ai_result(occurrence=occ, updated_translation="u", from_batch=True)
        updater.translation_update_dialog.set_ai_busy.assert_called_with(False)
        updater.translation_update_dialog.set_batch_active.assert_called_with(False)
        
        updater.handle_occurrence_ai_result(occurrence=occ, updated_translation="u", from_batch=False)
        assert updater._batch_prompt_override is None

    # Error
    updater._handle_occurrence_ai_error("err", False)
    updater.translation_update_dialog.on_ai_error.assert_called_with("err")
    assert updater._pending_ai_occurrences == []

def test_gou_handle_glossary_occurrence_update_success(updater):
    occ = GlossaryOccurrence(GlossaryEntry("t", "tr"), 1, 2, 3, 0, 0, "line")
    ctx = {"occurrence": occ, "from_batch": False, "composer_args": {"expected_lines": 1}}
    
    # Invalid JSON
    updater._main_handler.ai_lifecycle_manager._clean_model_output.return_value = "{"
    with patch.object(updater, '_handle_occurrence_ai_error') as mock_err:
        updater.handle_glossary_occurrence_update_success(ProviderResponse(), ctx)
        mock_err.assert_called_once()
        
    # Valid JSON
    updater._main_handler.ai_lifecycle_manager._clean_model_output.return_value = '{"translation": "new"}'
    updater._main_handler.ai_lifecycle_manager._trim_trailing_whitespace_from_lines.return_value = "new"
    with patch.object(updater, 'handle_occurrence_ai_result') as mock_res:
        updater.handle_glossary_occurrence_update_success(ProviderResponse(), ctx)
        mock_res.assert_called_with(occurrence=occ, updated_translation="new", from_batch=False)

def test_gou_handle_glossary_occurrence_batch_success(updater):
    ctx = {"from_batch": True, "expected_lines": {"0": 1}, "occurrence_lookup": {"0": MagicMock()}}
    
    # Valid JSON
    updater._main_handler.ai_lifecycle_manager._clean_model_output.return_value = '{"occurrences": [{"id": "0", "translation": "new"}]}'
    updater._main_handler.ai_lifecycle_manager._trim_trailing_whitespace_from_lines.return_value = "new"
    with patch.object(updater, 'handle_occurrence_batch_success') as mock_batch:
        updater.handle_glossary_occurrence_batch_success(ProviderResponse(), ctx)
        mock_batch.assert_called_with(results={"0": "new"}, context=ctx)

@patch('handlers.translation.glossary_occurrence_updater.QMessageBox')
def test_gou_request_glossary_notes_variation(mock_box, updater):
    # No provider
    updater._main_handler.ai_lifecycle_manager._prepare_provider.return_value = None
    assert not updater.request_glossary_notes_variation(term="t", translation="tr", current_notes="n", context_line=None, dialog=None)
    
    # Provider, no prompts
    provider = MagicMock()
    updater._main_handler.ai_lifecycle_manager._prepare_provider.return_value = provider
    updater._gh.load_prompts.return_value = (None, None)
    assert not updater.request_glossary_notes_variation(term="t", translation="tr", current_notes="n", context_line=None, dialog=None)

    # Success
    updater._gh.load_prompts.return_value = ("sys", "txt")
    updater._main_handler.prompt_composer.compose_variation_request.return_value = ("c_sys", "c_user")
    updater._main_handler._maybe_edit_prompt.return_value = ("e_sys", "e_user")
    
    assert updater.request_glossary_notes_variation(term="t", translation="tr", current_notes="n", context_line="ctx", dialog=None)
    updater._main_handler.ai_lifecycle_manager.run_ai_task.assert_called_once()
