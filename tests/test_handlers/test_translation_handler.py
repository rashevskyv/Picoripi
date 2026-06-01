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
    mw.data_store = mw
    mw.translation_config = {}
    mw.string_metadata = {}
    mw.data_store.current_block_idx = 1
    mw.data_store.current_string_idx = 2
    mw.preview_text_edit = MagicMock()
    mw.project_manager = None
    dp = MagicMock()
    ui = MagicMock()
    return mw, dp, ui

@pytest.fixture
def th(mock_deps):
    mw, dp, ui = mock_deps
    mw.current_game_rules.convert_editor_text_to_data.side_effect = lambda x: x
    mw.current_game_rules.get_shift_enter_char.return_value = "\n"
    
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
        handler.prompt_composer.restore_placeholders.side_effect = lambda text, *args, **kwargs: text
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
    th.glossary_handler.add_glossary_entry.assert_called_with("term", "ctx", "")
    
    th.edit_glossary_entry("term")
    th.glossary_handler.edit_glossary_entry.assert_called_with("term", translation="")

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
    
    th.glossary_handler.add_glossary_entry.assert_called_with("line 0\nline 1", None, "")

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
    assert th._prepare_session_for_request(base_system_prompt="", full_system_prompt="", user_prompt="", task_type="translate_block_chunked") is None
    
    th._provider_supports_sessions = True
    th._session_manager.ensure_session.return_value = "state"
    
    # Non-session task type should return None
    assert th._prepare_session_for_request(base_system_prompt="bs", full_system_prompt="fs", user_prompt="u", task_type="translate_single") is None
    
    # Session-supported task type should return valid session info
    res = th._prepare_session_for_request(base_system_prompt="bs", full_system_prompt="fs", user_prompt="u", task_type="translate_block_chunked")
    assert res is not None
    assert res['state'] == "state"
    assert res['user_message']['content'] == "u"
    assert th.start_new_session is False
    
    task_details = {}
    assert th._attach_session_to_task(task_details, base_system_prompt="bs", full_system_prompt="fs", user_prompt="u", task_type="translate_block_chunked") is True
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
    th.ui_updater.populate_strings_for_block.assert_called_with(1, ANY, force=True)
    
    # No revert chosen (which is QMessageBox.Yes)
    th.ui_handler.reset_mock()
    th.pre_translation_state = {1: ["orig"]}
    mock_box.question.return_value = mock_box.Yes
    th.prompt_for_revert_after_cancel()
    assert 1 not in th.pre_translation_state
    th.ui_handler.finish_ai_operation.assert_called_once()

@patch('handlers.translation_handler.QMessageBox')
def test_th_prompt_for_revert_after_cancel_chapter(mock_box, th):
    th.ui_handler.reset_mock()
    th.worker = MagicMock()
    th.worker.task_details = {
        'block_idx': -2,
        'temp_id_map': {0: (0, 0), 1: (0, 1)}
    }
    th.pre_translation_state = {
        0: ["orig0_0", "orig0_1"],
        -2: True
    }
    
    # Revert chosen (QMessageBox.No)
    mock_box.question.return_value = mock_box.No
    th.prompt_for_revert_after_cancel()
    
    th.data_processor.update_edited_data.assert_any_call(0, 0, "orig0_0")
    th.data_processor.update_edited_data.assert_any_call(0, 1, "orig0_1")
    assert 0 not in th.pre_translation_state
    assert -2 not in th.pre_translation_state
    th.ui_updater.populate_strings_for_block.assert_called_with(-2, force=True)


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
    th.mw.data_store.data = [["s1", "s2"], ["s3"]]
    th.glossary_handler._get_original_block.return_value = ["s1", "s2"]
    
    provider = MagicMock()
    th.ai_lifecycle_manager._prepare_provider.return_value = provider
    
    with patch.object(th, '_initiate_batch_translation') as mock_init:
        th.translate_current_block(0)
        assert 0 in th.pre_translation_state
        mock_init.assert_called_once()

@patch('handlers.translation_handler.QMessageBox')
def test_th_translate_current_block_chapter(mock_box, th):
    th.is_ai_running = False
    th.mw.data_store.data = [["s1", "s2"], ["s3"]]
    
    provider = MagicMock()
    th.ai_lifecycle_manager._prepare_provider.return_value = provider
    
    # Mock mempalace client and mappings
    mock_client = MagicMock()
    th.prompt_composer._get_mempalace_client.return_value = mock_client
    th.prompt_composer._get_wing_name.return_value = "Zelda_TP"
    
    mock_client.get_chapter_mappings.return_value = [
        {"bmg_id": "block_0_Str_0"},
        {"bmg_id": "block_0_Str_1"}
    ]
    th.mw.list_selection_handler.resolve_bmg_id_to_indices.side_effect = lambda bmg_id: (0, 0) if "_Str_0" in bmg_id else (0, 1)
    
    th.glossary_handler._get_original_string.side_effect = lambda b, s: f"orig_{b}_{s}"
    
    with patch.object(th, '_initiate_batch_translation') as mock_init:
        th.translate_current_block(-2, chapter_id=12)
        assert 0 in th.pre_translation_state
        assert -2 in th.pre_translation_state
        mock_init.assert_called_once()
        
        task_details = mock_init.call_args[0][0]
        assert task_details['type'] == 'translate_block_chunked'
        assert task_details['block_idx'] == -2
        assert task_details['mode_description'] == 'chapter'
        assert task_details['source_items'] == [
            {"id": 0, "text": "orig_0_0"},
            {"id": 1, "text": "orig_0_1"}
        ]
        assert task_details['temp_id_map'] == {
            0: (0, 0),
            1: (0, 1)
        }


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
    th.data_processor.update_edited_data.assert_called_with(1, 0, "t", action_type="TRANSLATE", skip_ui_refresh=True)
    th.ui_handler.finish_ai_operation.assert_called_once()
    assert 1 not in th.translation_progress

def test_th_handle_chunk_translated_chapter(th):
    ctx = {
        'block_idx': -2,
        'temp_id_map': {0: (0, 0)}
    }
    th.translation_progress = {-2: {'completed_chunks': set(), 'total_chunks': 1}}
    th.mw.data_store.current_chapter_id = 12
    th.mw.data_store.current_block_idx = 0
    
    chunk_text = '{"translated_strings": [{"id": 0, "translation": "t"}]}'
    th.ai_lifecycle_manager._trim_trailing_whitespace_from_lines.return_value = "t"
    
    th._handle_chunk_translated(0, chunk_text, ctx)
    
    # Verify that populate_strings_for_block is called with -2, not current_block_idx (0)
    th.ui_updater.populate_strings_for_block.assert_called_with(-2, ANY, force=True)


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
    th.data_processor.update_edited_data.assert_called_once()
    th.ui_handler.apply_full_translation.assert_called_with("trans")
    th.ui_handler.finish_ai_operation.assert_called_once()

@patch('handlers.translation_handler.QMessageBox')
def test_th_handle_variation_success(mock_box, th):
    ctx = {'is_inline': True}
    th.ai_lifecycle_manager._clean_model_output.return_value = "vars"
    th.ui_handler.parse_variation_payload.return_value = ["v1", "v2"]
    th.ui_handler.show_variations_dialog.return_value = "v1"
    
    th._handle_variation_success(ProviderResponse(), ctx)
    th.data_processor.update_edited_data.assert_called_once()
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


def test_translate_all_blocks_chronologically(th):
    th.mw.data_store.data = [["s1", "s2"], ["s3"]]
    th.glossary_handler._get_original_block.side_effect = lambda idx: ["s1", "s2"] if idx == 0 else ["s3"]
    th.glossary_handler._get_original_string.side_effect = lambda b, s: f"str_{b}_{s}"
    
    th.prompt_composer._get_wing_name.return_value = "Zelda_TP"
    mock_client = MagicMock()
    th.prompt_composer._get_mempalace_client.return_value = mock_client
    th.prompt_composer._get_block_label.side_effect = lambda idx: f"block_{idx}"
    
    # Mock MemePalace mappings: block_1 has script_line 5, block_0 has script_line 10
    mock_client.get_script_mapping.side_effect = lambda wing, bmg_id: {"script_line": 10} if "block_0" in bmg_id else {"script_line": 5}
    mock_client.get_cached_context.return_value = {"room": "dungeon"}
    mock_client.get_room_visual_context.return_value = "Dark room description"
    
    provider = MagicMock()
    th.ai_lifecycle_manager._prepare_provider.return_value = provider
    
    with patch.object(th, '_initiate_batch_translation') as mock_init:
        th.translate_all_blocks_chronologically()
        mock_init.assert_called_once()
        
        task_details = mock_init.call_args[0][0]
        assert task_details['type'] == 'translate_block_chunked'
        assert task_details['block_idx'] == 999999
        
        # Verify chronological sorting order: block 1 (script_line 5) comes before block 0 (script_line 10)
        source_items = task_details['source_items']
        assert len(source_items) == 3
        # temp_id_map should map temp_id -> (real_block_idx, real_string_idx)
        # block 1 has 1 item: (1, 0)
        # block 0 has 2 items: (0, 0), (0, 1)
        assert task_details['temp_id_map'][0] == (1, 0)
        assert task_details['temp_id_map'][1] == (0, 0)
        assert task_details['temp_id_map'][2] == (0, 1)


@patch('handlers.translation_handler.QMessageBox')
def test_translate_all_blocks_chronologically_resume_yes(mock_box, th):
    th.mw.data_store.data = [["s1"]]
    th.translation_progress = {
        999999: {
            'completed_chunks': {0, 1},
            'total_chunks': 5,
            'source_items': [{'id': 0, 'text': 's'}],
            'temp_id_map': {0: (0, 0)}
        }
    }
    
    mock_box.question.return_value = mock_box.Yes
    provider = MagicMock()
    th.ai_lifecycle_manager._prepare_provider.return_value = provider
    
    with patch.object(th, '_initiate_batch_translation') as mock_init:
        th.translate_all_blocks_chronologically()
        
        mock_init.assert_called_once()
        task_details = mock_init.call_args[0][0]
        assert task_details['is_resume'] is True
        assert task_details['block_idx'] == 999999
        assert task_details['source_items'] == [{'id': 0, 'text': 's'}]
        assert task_details['temp_id_map'] == {0: (0, 0)}


@patch('handlers.translation_handler.QMessageBox')
def test_translate_all_blocks_chronologically_resume_no(mock_box, th):
    th.mw.data_store.data = [["s1"]]
    th.translation_progress = {
        999999: {
            'completed_chunks': {0, 1},
            'total_chunks': 5,
            'source_items': [{'id': 0, 'text': 's'}],
            'temp_id_map': {0: (0, 0)}
        }
    }
    
    mock_box.question.return_value = mock_box.No
    provider = MagicMock()
    th.ai_lifecycle_manager._prepare_provider.return_value = provider
    th.glossary_handler._get_original_block.return_value = ["s1"]
    th.glossary_handler._get_original_string.return_value = "s1"
    
    with patch.object(th, '_initiate_batch_translation') as mock_init:
        th.translate_all_blocks_chronologically()
        
        mock_init.assert_called_once()
        task_details = mock_init.call_args[0][0]
        # Should NOT be resume because user clicked NO (Start Over)
        assert task_details.get('is_resume') is not True
        assert 999999 not in th.translation_progress  # Re-initialized session will not be created because _initiate_batch_translation is mocked

def test_th_handle_chunk_translated_updates_title(th):
    # Setup context and progress
    th.translation_progress = {
        0: {
            'completed_chunks': set(),
            'total_chunks': 1,
            'source_items': [{'id': 0, 'text': 's'}],
            'temp_id_map': {0: (0, 0)}
        }
    }
    context = {
        'block_idx': 0,
        'temp_id_map': {0: (0, 0)},
        'calculated_chunks': [[{'id': 0, 'text': 's'}]]
    }
    chunk_text = json.dumps({
        'translated_strings': [{'id': 0, 'translation': 'trans'}]
    })
    
    th._handle_chunk_translated(0, chunk_text, context)
    
    # Check that update_title was called to show asterisk
    th.ui_updater.update_title.assert_called_once()

def test_th_handle_preview_translation_success_updates_title(th):
    context = {
        'block_idx': 0,
        'source_items': [{'id': 0, 'text': 's'}],
        'temp_id_map': {0: (0, 0)}
    }
    response = ProviderResponse(
        text=json.dumps({
            'translated_strings': [{'id': 0, 'translation': 'trans'}]
        })
    )
    th.ai_lifecycle_manager._clean_model_output.return_value = response.text
    
    th._handle_preview_translation_success(response, context)
    
    # Check that update_title was called to show asterisk
    th.ui_updater.update_title.assert_called_once()


def test_save_and_load_progress_metadata(th):
    # Setup mock project and blocks
    mock_block = MagicMock()
    mock_block.metadata = {}
    
    th.mw.project_manager = MagicMock()
    th.mw.project_manager.project = MagicMock()
    th.mw.project_manager.project.blocks = [mock_block]
    
    th.mw.block_to_project_file_map = {0: 0}
    
    # 1. Save progress
    th.translation_progress = {
        0: {
            'completed_chunks': {0, 1},
            'total_chunks': 3,
            'source_items': [{'id': 0, 'text': 'src'}],
            'temp_id_map': {0: (0, 0)},
            'custom_user_header': 'Header',
            'custom_user_label': 'Label',
            'system_prompt_override': 'Prompt',
            'session_reset_attempted': False
        }
    }
    
    th.save_progress_to_metadata(0)
    
    # Assert it was saved into mock_block.metadata
    assert 'translation_progress' in mock_block.metadata
    saved = mock_block.metadata['translation_progress']
    assert saved['total_chunks'] == 3
    assert saved['completed_chunks'] == [0, 1]  # converted to list
    assert saved['custom_user_header'] == 'Header'
    th.mw.project_manager.save.assert_called()
    
    # 2. Load progress
    th.translation_progress.clear()
    th.load_progress_from_metadata()
    
    assert 0 in th.translation_progress
    loaded = th.translation_progress[0]
    assert loaded['total_chunks'] == 3
    assert loaded['completed_chunks'] == {0, 1}  # converted back to set
    assert loaded['temp_id_map'] == {0: (0, 0)}  # keys converted to int
    assert loaded['custom_user_header'] == 'Header'


def test_format_and_wrap_translation_balanced_and_page_building(th):
    # Setup mock settings on th.mw
    th.mw.game_dialog_max_width_pixels = 460
    th.mw.line_width_warning_threshold_pixels = 410
    th.mw.lines_per_page = 2
    
    # We will mock calculate_string_width to simplify testing.
    # Let's say: each character has a width of 10.
    # Warning threshold (410px) = 41 chars
    # Max width (460px) = 46 chars
    with patch('handlers.translation_handler.calculate_string_width') as mock_width, \
         patch('handlers.translation_handler.remove_all_tags') as mock_remove_tags:
        
        mock_width.side_effect = lambda text, *args, **kwargs: len(text) * 10
        mock_remove_tags.side_effect = lambda text: text
        
        # Mock current game rules with shift enter and editor translation
        mock_rules = MagicMock()
        mock_rules.get_shift_enter_char.return_value = "[P]\n"
        # Mock convert_editor_text_to_data: just replace [P]\n with \p
        mock_rules.convert_editor_text_to_data.side_effect = lambda text: text.replace("[P]\n", "\\p")
        th.mw.current_game_rules = mock_rules
        
        # Test Case 1: Balanced wrapping of a sentence
        # ShortWord (90px) + NextWord (80px) = 170px.
        # Adding AnotherWord (110px) -> 290px <= 410px.
        # Let's construct long words.
        # Word 1: 20 chars (200px)
        # Word 2: 22 chars (220px)
        # Word 1 + space + Word 2 -> 20 + 1 + 22 = 43 chars (430px).
        # 430px > 410px (warning threshold) but <= 460px (max width).
        # So they must stay on the same line!
        # Word 3: 15 chars (150px)
        # Adding Word 3 would make 430px + 10px (space) + 150px = 590px > 460px.
        # So Word 3 must wrap to line 2.
        w1 = "a" * 20
        w2 = "b" * 22
        w3 = "c" * 15
        text_to_wrap = f"{w1} {w2} {w3}"
        res = th._format_and_wrap_translation(text_to_wrap, 0, 0)
        assert res == f"{w1} {w2}\n{w3}"
        
        # Test Case 2: Page building / sentence integrity
        # Sentence 1: "SentenceA." -> 10 chars (1 line)
        # Sentence 2: WordOne + space + WordTwo + space + WordThree.
        # Let's make WordOne = 23 chars, WordTwo = 23 chars.
        # WordOne (230px). Adding WordTwo (230px) -> 230 + 10 + 230 = 470px > 460px.
        # So WordTwo wraps to line 2.
        # Sentence 2 has 2 lines: "WordOne", "WordTwo WordThree."
        # lines_per_page = 2.
        # Sentence 1 (1 line) + Sentence 2 (2 lines) = 3 lines total.
        # Sentence 2 cannot fit on page 1, so it must start on page 2.
        # Page 1: "SentenceA."
        # Page 2: "WordOne\nWordTwo WordThree."
        # joined by shift_enter_char [P]\n, then converted (replace [P]\n with \p)
        text_integrity = "SentenceA. 12345678901234567890123 12345678901234567890123 WordThree."
        res = th._format_and_wrap_translation(text_integrity, 0, 0)
        assert res == "SentenceA.\\p12345678901234567890123\n12345678901234567890123 WordThree."




