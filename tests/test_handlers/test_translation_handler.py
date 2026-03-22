import pytest
from unittest.mock import MagicMock, patch, ANY
import json
from PyQt5.QtWidgets import QMessageBox, QDialog
from PyQt5.QtCore import QPoint

from handlers.translation_handler import TranslationHandler
from core.translation.providers import ProviderResponse

@pytest.fixture
def mock_deps():
    mw = MagicMock()
    mw.translation_config = {}
    mw.current_block_idx = 1
    mw.current_string_idx = 2
    mw.preview_text_edit = MagicMock()
    dp = MagicMock()
    ui = MagicMock()
    return mw, dp, ui

@pytest.fixture
def th(mock_deps):
    mw, dp, ui = mock_deps
    
    with patch('handlers.translation_handler.GlossaryHandler'), \
         patch('handlers.translation_handler.AIPromptComposer'), \
         patch('handlers.translation_handler.TranslationUIHandler'), \
         patch('handlers.translation_handler.AILifecycleManager'), \
         patch('handlers.translation_handler.TranslationSessionManager'), \
         patch('handlers.translation_handler.QTimer'):
        handler = TranslationHandler(mw, dp, ui)
        
        # We should NOT mock ai_lifecycle_manager again so we can verify its methods
        handler.glossary_handler = MagicMock()
        handler.prompt_composer = MagicMock()
        handler.ui_handler = MagicMock()
        handler._session_manager = MagicMock()
        
        return handler

def test_th_initialization(th):
    assert th.start_new_session is True
    assert th.is_ai_running is False
    th.ai_lifecycle_manager.register_handler.assert_called()

def test_th_glossary_delegation(th):
    th.initialize_glossary_highlighting()
    th.glossary_handler.initialize_glossary_highlighting.assert_called_once()
    
    th.show_glossary_dialog("term")
    th.glossary_handler.show_glossary_dialog.assert_called_with("term")
    
    th.get_glossary_entry("term")
    th.glossary_handler.glossary_manager.get_entry.assert_called_with("term")
    
    th.add_glossary_entry("term", "ctx")
    th.glossary_handler.add_glossary_entry.assert_called_with("term", "ctx")
    
    th.edit_glossary_entry("term")
    th.glossary_handler.edit_glossary_entry.assert_called_with("term")

def test_th_append_selection_to_glossary(th):
    # No selection
    th.mw.preview_text_edit.get_selected_lines.return_value = []
    with patch('handlers.translation_handler.QMessageBox') as mock_box:
        th.append_selection_to_glossary()
        mock_box.information.assert_called_once()
    
    # Selection exists
    th.mw.preview_text_edit.get_selected_lines.return_value = [0, 1]
    th.glossary_handler._get_original_string.side_effect = lambda b, idx: f"line {idx}"
    th.append_selection_to_glossary()
    
    th.glossary_handler.add_glossary_entry.assert_called_with("line 0\nline 1")

@patch('handlers.translation_handler.GeminiProvider')
def test_th_reset_translation_session(mock_gemini, th):
    # Dict must have some key otherwise `if provider_settings:` will evaluate to False
    th.mw.translation_config = {'provider': 'gemini', 'providers': {'gemini': {'k': 'v'}}}
    th.reset_translation_session()
    
    th._session_manager.reset.assert_called_once()
    assert th._cached_system_prompt is None
    assert th.start_new_session is True
    mock_gemini.return_value.start_new_chat_session.assert_called_once()

@patch('handlers.translation_handler.PromptEditorDialog')
@patch('handlers.translation_handler.QApplication')
def test_th_maybe_edit_prompt(mock_app, mock_dialog, th):
    mock_app.keyboardModifiers.return_value = 0 # No modifiers
    th.mw.prompt_editor_enabled = False
    
    sys, usr = th._maybe_edit_prompt(title="T", system_prompt="s", user_prompt="u")
    assert sys == "s" and usr == "u"
    
    th.mw.prompt_editor_enabled = True
    d = mock_dialog.return_value
    d.exec_.return_value = QDialog.Rejected
    d.Accepted = QDialog.Accepted
    assert th._maybe_edit_prompt(title="T", system_prompt="s", user_prompt="u") is None
    
    d.exec_.return_value = QDialog.Accepted
    d.get_user_inputs.return_value = ("ns", "nu", True)
    
    th.glossary_handler._current_prompts_path = "path"
    th.glossary_handler.save_prompt_section.return_value = True
    
    res = th._maybe_edit_prompt(title="T", system_prompt="s", user_prompt="u", save_section="translation", save_field="system_prompt")
    assert res == ("ns", "nu")
    assert th._cached_system_prompt == "ns"

def test_th_session_preparation(th):
    th._provider_supports_sessions = False
    assert th._prepare_session_for_request(base_system_prompt="", full_system_prompt="", user_prompt="", task_type="") is None
    
    th._provider_supports_sessions = True
    th._session_manager.ensure_session.return_value = "state"
    
    res = th._prepare_session_for_request(base_system_prompt="bs", full_system_prompt="fs", user_prompt="u", task_type="")
    assert res['state'] == "state"
    assert res['user_message']['content'] == "u"
    assert th.start_new_session is False
    
    task_details = {}
    assert th._attach_session_to_task(task_details, base_system_prompt="bs", full_system_prompt="fs", user_prompt="u", task_type="") is True
    assert task_details['session_state'] == "state"

@patch('handlers.translation_handler.QMessageBox')
def test_th_prompt_for_revert_after_cancel(mock_box, th):
    # No worker
    th.worker = None
    th.prompt_for_revert_after_cancel()
    th.ui_handler.finish_ai_operation.assert_called_once()
    
    # Worker but not in pre-state
    th.ui_handler.reset_mock()
    th.worker = MagicMock()
    th.worker.task_details = {'block_idx': 1}
    th.pre_translation_state = {}
    th.prompt_for_revert_after_cancel()
    th.ui_handler.finish_ai_operation.assert_called_once()
    
    # Revert chosen (which is QMessageBox.No)
    th.ui_handler.reset_mock()
    th.pre_translation_state = {1: ["orig1", "orig2"]}
    mock_box.question.return_value = mock_box.No
    th.prompt_for_revert_after_cancel()
    
    th.data_processor.update_edited_data.assert_any_call(1, 0, "orig1")
    th.data_processor.update_edited_data.assert_any_call(1, 1, "orig2")
    assert 1 not in th.pre_translation_state
    
    # No revert chosen (which is QMessageBox.Yes)
    th.ui_handler.reset_mock()
    th.pre_translation_state = {1: ["orig"]}
    mock_box.question.return_value = mock_box.Yes
    th.prompt_for_revert_after_cancel()
    assert 1 not in th.pre_translation_state
    th.ui_handler.finish_ai_operation.assert_called_once()

@patch('handlers.translation_handler.QMessageBox')
def test_th_translate_current_string(mock_box, th):
    th.is_ai_running = True
    th.translate_current_string()
    mock_box.information.assert_called_once()
    
    th.is_ai_running = False
    with patch.object(th, '_translate_and_apply') as mock_apply:
        th.translate_current_string()
        mock_apply.assert_called_once()

@patch('handlers.translation_handler.QMessageBox')
def test_th_translate_preview_selection(mock_box, th):
    th.is_ai_running = False
    th.mw.preview_text_edit.get_selected_lines.return_value = [0, 1]
    
    th.ai_lifecycle_manager._prepare_provider.return_value = None
    th.translate_preview_selection(QPoint(0, 0)) # Fails early
    
    provider = MagicMock()
    th.ai_lifecycle_manager._prepare_provider.return_value = provider
    th.glossary_handler.load_prompts.return_value = ("sys", None)
    th.prompt_composer.compose_batch_request.return_value = ("sys_p", "user_p", {})
    
    with patch.object(th, '_maybe_edit_prompt') as mock_edit:
        mock_edit.return_value = ("e_sys", "e_user")
        with patch.object(th, '_initiate_batch_translation') as mock_init:
            th.translate_preview_selection(QPoint(0, 0))
            mock_init.assert_called_once()

@patch('handlers.translation_handler.QMessageBox')
def test_th_translate_current_block(mock_box, th):
    th.is_ai_running = False
    th.mw.data = [["s1", "s2"], ["s3"]]
    th.glossary_handler._get_original_block.return_value = ["s1", "s2"]
    
    provider = MagicMock()
    th.ai_lifecycle_manager._prepare_provider.return_value = provider
    
    with patch.object(th, '_initiate_batch_translation') as mock_init:
        th.translate_current_block(0)
        assert 0 in th.pre_translation_state
        mock_init.assert_called_once()

@patch('handlers.translation_handler.QMessageBox')
def test_th_resume_block_translation(mock_box, th):
    th.translation_progress = {}
    th.resume_block_translation(0)
    mock_box.information.assert_called_once()
    
    th.translation_progress = {0: {'source_items': [{'id': 0, 'text': 's'}]}}
    provider = MagicMock()
    th.ai_lifecycle_manager._prepare_provider.return_value = provider
    
    with patch.object(th, '_initiate_batch_translation') as mock_init:
        th.resume_block_translation(0)
        assert 0 in th.pre_translation_state
        mock_init.assert_called_once()

def test_th_handle_chunk_translated(th):
    ctx = {'block_idx': 1}
    th.translation_progress = {1: {'completed_chunks': set(), 'total_chunks': 1}}
    
    # Valid chunk
    chunk_text = '{"translated_strings": [{"id": 0, "translation": "t"}]}'
    th.ai_lifecycle_manager._trim_trailing_whitespace_from_lines.return_value = "t"
    th._handle_chunk_translated(0, chunk_text, ctx)
    th.data_processor.update_edited_data.assert_called_with(1, 0, "t", action_type="TRANSLATE")
    th.ui_handler.finish_ai_operation.assert_called_once()
    assert 1 not in th.translation_progress

def test_th_handle_preview_translation_success(th):
    ctx = {'block_idx': 1, 'source_items': [1, 2]}
    th.ai_lifecycle_manager._clean_model_output.return_value = '{"translated_strings": [{"id": 0, "translation": "t1"}, {"id": 1, "translation": "t2"}]}'
    th.ai_lifecycle_manager._trim_trailing_whitespace_from_lines.side_effect = lambda x: x
    
    th._handle_preview_translation_success(ProviderResponse(), ctx)
    th.data_processor.update_edited_data.assert_any_call(1, 0, "t1", action_type="TRANSLATE")
    th.data_processor.update_edited_data.assert_any_call(1, 1, "t2", action_type="TRANSLATE")
    th.ui_handler.finish_ai_operation.assert_called_once()

def test_th_handle_single_translation_success(th):
    ctx = {}
    th.ai_lifecycle_manager._clean_model_output.return_value = "trans"
    th.ai_lifecycle_manager._trim_trailing_whitespace_from_lines.return_value = "trans"
    th._handle_single_translation_success(ProviderResponse(), ctx)
    th.ui_handler.apply_full_translation.assert_called_with("trans")
    th.ui_handler.finish_ai_operation.assert_called_once()

@patch('handlers.translation_handler.QMessageBox')
def test_th_handle_variation_success(mock_box, th):
    ctx = {'is_inline': True}
    th.ai_lifecycle_manager._clean_model_output.return_value = "vars"
    th.ui_handler.parse_variation_payload.return_value = ["v1", "v2"]
    th.ui_handler.show_variations_dialog.return_value = "v1"
    
    th._handle_variation_success(ProviderResponse(), ctx)
    th.ui_handler.apply_inline_variation.assert_called_with("v1")

def test_th_translate_selected_lines(th):
    th.mw.preview_text_edit.get_selected_lines.return_value = [1]
    with patch.object(th, 'translate_preview_selection') as mock_prev:
        th.translate_selected_lines()
        mock_prev.assert_called_once()
        
    th.mw.preview_text_edit.get_selected_lines.return_value = []
    with patch.object(th, 'translate_current_string') as mock_curr:
        th.translate_selected_lines()
        mock_curr.assert_called_once()
