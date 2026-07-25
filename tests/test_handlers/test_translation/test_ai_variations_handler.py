import pytest
from unittest.mock import MagicMock, patch, ANY

from handlers.translation.ai_variations_handler import AIVariationsHandler
from core.translation.providers import ProviderResponse


@pytest.fixture
def mock_main_handler():
    mh = MagicMock()
    
    # Setup mw mock first so BaseTranslationHandler gets the correct reference
    mw_mock = MagicMock()
    mw_mock.data_store = MagicMock()
    mw_mock.data_store.current_block_idx = 0
    mw_mock.data_store.current_string_idx = 0
    mw_mock.data_store.data = [["original_text"]]
    mw_mock.default_tag_mappings = {}
    mw_mock.undo_manager = MagicMock()
    
    mh.mw = mw_mock
    mh.is_ai_running = False
    mh.translation_progress = {}
    mh.pre_translation_state = {}
    
    mh.data_processor = MagicMock()
    mh.data_processor.get_current_string_text.return_value = ("current_translation", "source")
    
    mh.ui_updater = MagicMock()
    mh.glossary_handler = MagicMock()
    mh.glossary_handler._get_original_string.return_value = "original_text"
    mh.glossary_handler.load_prompts.return_value = ("system_prompt", "user_prompt")
    
    mh.prompt_composer = MagicMock()
    mh.prompt_composer.compose_variation_request.return_value = ("combined_system", "user_prompt")
    mh.prompt_composer.restore_placeholders.side_effect = lambda text, *args, **kwargs: text
    
    mh.ui_handler = MagicMock()
    mh.ui_handler.status_dialog.steps = ["step0", "step1", "step2", "step3"]
    mh.ui_handler.status_dialog.STATUS_IN_PROGRESS = "in_progress"
    mh.ui_handler.parse_variation_payload.side_effect = lambda text: [text]
    
    mh.ai_lifecycle_manager = MagicMock()
    mh.ai_lifecycle_manager._clean_model_output.return_value = "variant1"
    mh.ai_lifecycle_manager._trim_trailing_whitespace_from_lines.side_effect = lambda x: x
    
    mh._session_manager = MagicMock()
    mh._session_manager.get_state.return_value = {}
    
    mh._format_and_wrap_translation.side_effect = lambda text, *args: text
    mh._convert_translation_preserving_layout.side_effect = lambda text: text
    
    return mh


@pytest.fixture
def vh(mock_main_handler):
    return AIVariationsHandler(mock_main_handler)


@patch('PyQt6.QtWidgets.QMessageBox.information')
def test_generate_variation_no_translation(mock_info, vh, mock_main_handler):
    mock_main_handler.data_processor.get_current_string_text.return_value = (None, None)
    
    vh.generate_variation_for_current_string()
    mock_info.assert_called_once_with(ANY, "AI Variation", "There is no current translation to vary.")


@patch('PyQt6.QtWidgets.QMessageBox.information')
def test_generate_variation_cached(mock_info, vh, mock_main_handler):
    vh.variations_cache[(0, 0)] = {
        'variants': ['cached_variant'],
        'translation': 'current_translation'
    }
    
    mock_main_handler.ui_handler.show_variations_dialog.return_value = 'cached_variant'
    
    vh.generate_variation_for_current_string(force=False)
    
    mock_main_handler.ui_handler.show_variations_dialog.assert_called_once_with(['cached_variant'], show_refresh=True, parent=None)
    mock_main_handler._convert_translation_preserving_layout.assert_called_once_with('cached_variant')


@patch('PyQt6.QtWidgets.QMessageBox.information')
def test_generate_variation_api_flow(mock_info, vh, mock_main_handler):
    provider = MagicMock()
    mock_main_handler.ai_lifecycle_manager._prepare_provider.return_value = provider
    mock_main_handler._maybe_edit_prompt.return_value = ("edited_sys", "edited_user")
    mock_main_handler._attach_session_to_task.return_value = False
    
    vh.generate_variation_for_current_string(force=True)
    
    mock_main_handler.ui_handler.start_ai_operation.assert_called_once_with("AI Variation", model_name=ANY, parent=None)
    mock_main_handler._run_ai_task.assert_called_once()
    args, kwargs = mock_main_handler._run_ai_task.call_args
    assert args[0] == provider
    assert args[1]['type'] == 'generate_variation'
    assert args[1]['precomposed_prompt'][0]['content'] == 'edited_sys'


@patch('PyQt6.QtWidgets.QMessageBox.information')
def test_handle_variation_success(mock_info, vh, mock_main_handler):
    response = MagicMock()
    context = {'placeholder_map': {}, 'composer_args': {'source_text': 'source'}}
    
    mock_main_handler.ui_handler.show_variations_dialog.return_value = 'chosen_var'
    
    vh._handle_variation_success(response, context)
    
    assert vh.variations_cache[(0, 0)]['variants'] == ['variant1']
    mock_main_handler.ui_handler.show_variations_dialog.assert_called_once_with(['variant1'], show_refresh=True, parent=None)
    
    mock_main_handler.data_processor.update_edited_data.assert_called_once_with(
        0, 0, 'chosen_var', action_type="TRANSLATE", skip_ui_refresh=True
    )


@patch('PyQt6.QtWidgets.QMessageBox.information')
def test_handle_variation_success_refresh(mock_info, vh, mock_main_handler):
    response = MagicMock()
    context = {'composer_args': {'source_text': 'source'}}
    
    mock_main_handler.ui_handler.show_variations_dialog.return_value = '__REFRESH__'
    vh._schedule_variation_refresh = MagicMock()
    
    vh._handle_variation_success(response, context)
    vh._schedule_variation_refresh.assert_called_once_with(
        0,
        0,
        on_success_callback=None,
        parent=None,
        selected_text=None,
    )


def test_generate_variation_selected_text(vh, mock_main_handler):
    # Setup edited_text_edit Mock
    edited_edit = MagicMock()
    cursor = MagicMock()
    cursor.hasSelection.return_value = True
    cursor.selectedText.return_value = "selected_segment"
    edited_edit.textCursor.return_value = cursor
    edited_edit.toPlainText.return_value = "full current translation with selected_segment"
    
    mock_main_handler.mw.edited_text_edit = edited_edit
    
    # Mock data rules and methods
    mock_main_handler.mw.current_game_rules = MagicMock()
    mock_main_handler.mw.current_game_rules.convert_editor_text_to_data.return_value = "converted_data"
    
    # 1. Test generate_variation_for_current_string with selected text
    provider = MagicMock()
    mock_main_handler.ai_lifecycle_manager._prepare_provider.return_value = provider
    mock_main_handler._maybe_edit_prompt.return_value = ("edited_sys", "edited_user")
    mock_main_handler._attach_session_to_task.return_value = False
    
    vh.generate_variation_for_current_string(force=True)
    
    # Verify selected_text in composer args
    mock_main_handler.prompt_composer.compose_variation_request.assert_called_once()
    args, kwargs = mock_main_handler.prompt_composer.compose_variation_request.call_args
    assert kwargs.get('selected_text') == "selected_segment"
    
    # Verify selected_text in task details
    mock_main_handler._run_ai_task.assert_called_once()
    args, kwargs = mock_main_handler._run_ai_task.call_args
    task_kwargs = args[1]
    assert task_kwargs['selected_text'] == "selected_segment"
    assert task_kwargs['is_inline'] is True

    # 2. Test success with selected text
    response = MagicMock()
    context = {
        'placeholder_map': {},
        'selected_text': 'selected_segment',
        'is_inline': True,
        'block_idx': 0,
        'string_idx': 0
    }
    
    mock_main_handler.ui_handler.show_variations_dialog.return_value = 'chosen_var'
    mock_main_handler.data_processor.update_edited_data.reset_mock()
    
    vh._handle_variation_success(response, context)
    
    # Verify cached with selected text
    assert vh.variations_cache[(0, 0, 'selected_segment')]['variants'] == ['variant1']
    
    # Verify _apply_chosen_variation flow for inline:
    # 1. apply_inline_variation is called with the chosen var
    mock_main_handler.ui_handler.apply_inline_variation.assert_called_once_with('chosen_var')
    # 2. update_edited_data is called with converted database representation
    mock_main_handler.data_processor.update_edited_data.assert_called_once_with(
        0, 0, 'converted_data', action_type="TRANSLATE", skip_ui_refresh=True
    )


def test_generate_variation_explicit_selected_text(vh, mock_main_handler):
    # Setup mock methods without setting edited_text_edit
    mock_main_handler.mw.edited_text_edit = None
    
    provider = MagicMock()
    mock_main_handler.ai_lifecycle_manager._prepare_provider.return_value = provider
    mock_main_handler._maybe_edit_prompt.return_value = ("edited_sys", "edited_user")
    mock_main_handler._attach_session_to_task.return_value = False
    
    vh.generate_variation_for_current_string(force=True, selected_text="explicit_segment")
    
    # Verify selected_text in composer args
    mock_main_handler.prompt_composer.compose_variation_request.assert_called_once()
    args, kwargs = mock_main_handler.prompt_composer.compose_variation_request.call_args
    assert kwargs.get('selected_text') == "explicit_segment"
    
    # Verify selected_text in task details
    mock_main_handler._run_ai_task.assert_called_once()
    args, kwargs = mock_main_handler._run_ai_task.call_args
    task_kwargs = args[1]
    assert task_kwargs['selected_text'] == "explicit_segment"
    assert task_kwargs['is_inline'] is True


