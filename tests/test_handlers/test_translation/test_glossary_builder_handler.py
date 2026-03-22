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
    creds = gbh._resolve_translation_credentials("OpenAI")
    assert creds["api_key"] == "test_key"
    assert creds["base_url"] == "http://api"

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
        "provider": "OpenAI"
    }
    gbh.mw.translation_config = {} # No keys
    
    gbh.build_glossary_for_block(0)
    mock_box.warning.assert_called_once()

@patch('handlers.translation.glossary_builder_handler.GlossaryBuilderHandler._start_async_glossary_task')
@patch('handlers.translation.glossary_builder_handler.get_provider_for_config')
def test_gbh_build_glossary_for_block_success(mock_provider, mock_start, gbh):
    gbh.mw.glossary_ai = {"chunk_size": 100}
    gbh.build_glossary_for_block(0)
    mock_start.assert_called_once()
    assert mock_start.call_args[0][0] == 0 # block_id
    assert mock_start.call_args[0][3] == ["Line 1\nLine 2"] # chunks

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
    
    gbh._start_async_glossary_task(0, mock_provider, {"model": "gpt-3"}, ["chunk1"])
    
    mock_dialog_inst.start.assert_called()
    mock_thread_inst.start.assert_called()
    assert gbh._worker == mock_worker_inst
    assert gbh._thread == mock_thread_inst

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
