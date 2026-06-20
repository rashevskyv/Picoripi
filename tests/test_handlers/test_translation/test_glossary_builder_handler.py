import pytest
from unittest.mock import MagicMock, patch, call
import json

from handlers.translation.glossary_builder_handler import GlossaryBuilderHandler
from core.translation.providers import ProviderResponse
from utils.utils import ALL_TAGS_PATTERN

@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.data_store = mw
    mw.translation_config = {}
    mw.glossary_ai = {}
    mw.data_store.data = [["Line 1", "Line 2"], ["Line 3"]]
    mw.data_store.block_names = {"0": "Block 0"}
    return mw

@pytest.fixture
def gbh(mock_mw):
    with patch('handlers.translation.glossary_builder_handler.GlossaryBuilderHandler._load_prompts', return_value={"system_prompt": "sys", "user_prompt_template": "user"}):
        handler = GlossaryBuilderHandler(mock_mw)
        return handler

def test_gbh_split_text_into_chunks(gbh):
    text = "1234567890"
    chunks = gbh._split_text_into_chunks(text, 3)
    assert chunks == ["123", "456", "789", "0"]

def test_gbh_mask_tags_for_ai(gbh):
    text = "Hello [Player]!"
    masked = gbh._mask_tags_for_ai(text)
    assert masked == "Hello  !"

def test_gbh_clean_json_response(gbh):
    # normal
    assert gbh._clean_json_response("text") == "text"
    # markdown list
    res = "```json\n[{\"test\": 1}]\n```"
    assert gbh._clean_json_response(res) == "[{\"test\": 1}]"
    
    empty_res = "```\n```"
    assert gbh._clean_json_response(empty_res) == ""

def test_gbh_resolve_translation_credentials(gbh):
    gbh.mw.translation_config = {
        "providers": {
            "openai_chat": {"api_key": "test_key", "base_url": "http://api"}
        }
    }
    # Test OpenAI
    creds = gbh._resolve_translation_credentials("OpenAI")
    assert creds["api_key"] == "test_key"
    assert creds["base_url"] == "http://api"
    assert creds["endpoint"] == "http://api"

    # Test OpenAI Compatible
    creds_compat = gbh._resolve_translation_credentials("OpenAI Compatible")
    assert creds_compat["api_key"] == "test_key"
    assert creds_compat["base_url"] == "http://api"
    assert creds_compat["endpoint"] == "http://api"

    # Ollama special logic
    gbh.mw.translation_config = {
        "providers": {
            "ollama_chat": {"base_url": "http://ollama"}
        }
    }
    creds_ollama = gbh._resolve_translation_credentials("Ollama")
    assert creds_ollama["base_url"] == "http://ollama"
    
    creds_none = gbh._resolve_translation_credentials("Unknown")
    assert creds_none == {}

@patch('handlers.translation.glossary_builder_handler.QMessageBox')
def test_gbh_build_glossary_for_block_empty(mock_box, gbh):
    gbh.mw.data_store.data = [[]] # block 0 is empty
    gbh.build_glossary_for_block(0)
    mock_box.information.assert_called_once()

@patch('handlers.translation.glossary_builder_handler.get_provider_for_config')
@patch('handlers.translation.glossary_builder_handler.QMessageBox')
def test_gbh_build_glossary_for_block_no_key(mock_box, mock_provider, gbh):
    gbh.mw.glossary_ai = {
        "use_translation_api_key": True,
        "provider": "OpenAI Compatible"
    }
    gbh.mw.translation_config = {} # No keys
    
    gbh.build_glossary_for_block(0)
    mock_box.warning.assert_called_once()

@patch('handlers.translation.glossary_builder_handler.get_provider_for_config')
@patch('handlers.translation.glossary_builder_handler.QMessageBox')
def test_gbh_build_glossary_for_block_no_key_but_custom_endpoint(mock_box, mock_provider, gbh):
    gbh.mw.glossary_ai = {
        "use_translation_api_key": True,
        "provider": "OpenAI Compatible"
    }
    gbh.mw.translation_config = {
        "providers": {
            "openai": {"endpoint": "http://localhost:1234"}
        }
    }
    with patch.object(gbh, '_start_async_glossary_task') as mock_start:
        gbh.build_glossary_for_block(0)
        mock_box.warning.assert_not_called()
        mock_start.assert_called_once()

@patch('handlers.translation.glossary_builder_handler.GlossaryBuilderHandler._start_async_glossary_task')
@patch('handlers.translation.glossary_builder_handler.get_provider_for_config')
def test_gbh_build_glossary_for_block_success(mock_provider, mock_start, gbh):
    gbh.mw.glossary_ai = {"chunk_size": 100}
    gbh.build_glossary_for_block(0)
    mock_start.assert_called_once()
    assert mock_start.call_args[0][0] == 0 # block_id
    assert mock_start.call_args[0][3] == ["Line 1", "Line 2"] # block_data
    assert mock_start.call_args[0][4] == [0, 1] # target_indices
    assert mock_start.call_args[0][5] == 100 # chunk_size

@patch('handlers.translation.glossary_builder_handler.QApplication.processEvents')
@patch('handlers.translation.glossary_builder_handler.AIWorker')
@patch('handlers.translation.glossary_builder_handler.QThread')
@patch('handlers.translation.glossary_builder_handler.AIStatusDialog')
def test_gbh_start_async_glossary_task(mock_dialog, mock_thread, mock_worker, mock_process_events, gbh):
    mock_provider = MagicMock()
    mock_dialog_inst = mock_dialog.return_value
    mock_thread_inst = mock_thread.return_value
    mock_worker_inst = mock_worker.return_value
    
    gbh.mw.statusBar = MagicMock()
    gbh.mw.glossary_manager = MagicMock()
    
    gbh._start_async_glossary_task(0, mock_provider, {"model": "gpt-3"}, ["Line 1", "Line 2"], [0, 1], 100)
    
    mock_dialog_inst.start.assert_called()
    mock_thread_inst.start.assert_called()
    assert gbh._worker == mock_worker_inst
    assert gbh._thread == mock_thread_inst

def test_ai_worker_build_glossary_background_processing():
    from handlers.translation.ai_worker import AIWorker
    from core.translation.providers import ProviderResponse
    
    mock_provider = MagicMock()
    mock_provider.translate.return_value = ProviderResponse(text="[]", raw_payload=[])
    
    # Under a chunk_size limit clamp of 1000, we need the text length > 1000 to get 2 chunks.
    # Hello {Color:Red}World! repeated 50 times -> 23 * 50 = 1150 chars.
    # Line [PLAYER] 2 repeated 50 times -> 15 * 50 = 750 chars.
    # Total: ~1900 chars. Masked text is 13 * 50 + 1 + 9 * 50 = 1101 chars.
    task_details = {
        'type': 'build_glossary',
        'system_prompt': 'sys',
        'user_prompt_template': '{text_chunk}',
        'block_data': ["Hello {Color:Red}World!" * 50, "Line [PLAYER] 2" * 50],
        'target_indices': [0, 1],
        'chunk_size': 20,  # Clamped to 1000
        'dialog_steps': ["step1", "step2", "step3", "step4"],
        'block_id': 0
    }
    
    worker = AIWorker(mock_provider, None, task_details)
    
    # We call run directly to simulate execution in the worker thread
    worker.run()
    
    assert mock_provider.translate.call_count == 2
    
    call_args_1 = mock_provider.translate.call_args_list[0][0][0]
    call_args_2 = mock_provider.translate.call_args_list[1][0][0]
    
    # Check that system prompt is correct
    assert call_args_1[0] == {"role": "system", "content": "sys"}
    # Check user chunks
    assert call_args_1[1]["role"] == "user"
    
    expected_full = "Hello  World!" * 50 + "\n" + "Line   2" * 50
    assert call_args_1[1]["content"] == expected_full[:1000]
    assert call_args_2[1]["content"] == expected_full[1000:]

def test_ai_worker_build_glossary_boundary_tags():
    from handlers.translation.ai_worker import AIWorker
    from core.translation.providers import ProviderResponse
    
    mock_provider = MagicMock()
    mock_provider.translate.return_value = ProviderResponse(text="[]", raw_payload=[])
    
    # Under a clamp of 1000, we put [PLAYER] at index 995.
    # In the old code (split first), splitting at 1000 breaks [PLAYER] into [PLA and YER], causing leak.
    # In the new code, masking first replaces it with space, resulting in safe chunks.
    task_details = {
        'type': 'build_glossary',
        'system_prompt': 'sys',
        'user_prompt_template': '{text_chunk}',
        'block_data': ["A" * 995 + "[PLAYER]World!"],
        'target_indices': [0],
        'chunk_size': 10,  # Clamped to 1000
        'dialog_steps': ["step1", "step2", "step3", "step4"],
        'block_id': 0
    }
    
    worker = AIWorker(mock_provider, None, task_details)
    worker.run()
    
    assert mock_provider.translate.call_count == 2
    call_args_1 = mock_provider.translate.call_args_list[0][0][0]
    call_args_2 = mock_provider.translate.call_args_list[1][0][0]
    
    # Verify chunks do not contain broken tag fragments
    assert call_args_1[1]["content"] == "A" * 995 + " Worl"
    assert call_args_2[1]["content"] == "d!"

def test_ai_worker_build_glossary_chunk_size_normalization():
    from handlers.translation.ai_worker import AIWorker
    from core.translation.providers import ProviderResponse
    
    mock_provider = MagicMock()
    mock_provider.translate.return_value = ProviderResponse(text="[]", raw_payload=[])
    
    # 1. Invalid values should fallback to default (8000), resulting in 1 chunk for 1500 chars
    for bad_size in ["bad", None, 0, -1]:
        mock_provider.translate.reset_mock()
        task_details = {
            'type': 'build_glossary',
            'block_data': ["A" * 1500],
            'target_indices': [0],
            'chunk_size': bad_size
        }
        worker = AIWorker(mock_provider, None, task_details)
        worker.run()
        assert mock_provider.translate.call_count == 1
        
    # 2. Values smaller than 1000 should be clamped to 1000 -> 2 chunks for 1500 chars
    mock_provider.translate.reset_mock()
    task_details = {
        'type': 'build_glossary',
        'block_data': ["A" * 1500],
        'target_indices': [0],
        'chunk_size': 500  # Clamped to 1000 -> 2 chunks
    }
    worker = AIWorker(mock_provider, None, task_details)
    worker.run()
    assert mock_provider.translate.call_count == 2

    # 3. Values larger than 32000 should be clamped to 32000 -> 2 chunks for 33000 chars
    mock_provider.translate.reset_mock()
    task_details = {
        'type': 'build_glossary',
        'block_data': ["A" * 33000],
        'target_indices': [0],
        'chunk_size': 50000  # Clamped to 32000 -> 2 chunks
    }
    worker = AIWorker(mock_provider, None, task_details)
    worker.run()
    assert mock_provider.translate.call_count == 2



@patch('handlers.translation.glossary_builder_handler.QMessageBox')
def test_gbh_on_glossary_success(mock_box, gbh):
    mock_mgr = MagicMock()
    mock_mgr.get_entries.return_value = []
    
    # Mock add_entry to return true so it thinks it added
    mock_mgr.add_entry.return_value = True
    mock_mgr.normalize_term.side_effect = lambda t: t.lower()
    
    gbh._glossary_manager = mock_mgr

    mock_sb = MagicMock()

    # Raw payload test
    resp = ProviderResponse(raw_payload=[{"term": "Test", "translation": "Тест"}], text="")
    gbh._on_glossary_success(resp, {}, mock_sb)
    
    mock_mgr.add_entry.assert_called_with("Test", "Тест", "")
    mock_mgr.save_to_disk.assert_called()
    mock_box.information.assert_called()
    mock_sb.showMessage.assert_called()

@patch('handlers.translation.glossary_builder_handler.QMessageBox')
def test_gbh_on_glossary_error_cancelled(mock_box, gbh):
    mock_sb = MagicMock()
    gbh._on_glossary_error("Err", mock_sb)
    mock_box.warning.assert_called()
    
    mock_box.reset_mock()
    gbh._on_glossary_cancelled(mock_sb)
    mock_box.information.assert_called()

def test_gbh_cleanup_worker(gbh):
    gbh._worker = MagicMock()
    gbh._status_dialog = MagicMock()
    gbh._thread = MagicMock()
    gbh._thread.isRunning.return_value = True
    
    gbh._cleanup_worker()
    
    assert gbh._worker is None
    assert gbh._status_dialog is None
    assert gbh._thread is None

def test_gbh_prepare_to_close(gbh):
    gbh._cleanup_worker = MagicMock()
    gbh.prepare_to_close()
    gbh._cleanup_worker.assert_called_once()
