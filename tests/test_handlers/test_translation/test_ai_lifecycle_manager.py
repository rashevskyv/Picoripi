import pytest
from unittest.mock import MagicMock, patch, call
from PyQt5.QtWidgets import QMessageBox

from handlers.translation.ai_lifecycle_manager import AILifecycleManager
from core.translation.providers import ProviderResponse, TranslationProviderError

@pytest.fixture
def mock_main_handler():
    mh = MagicMock()
    mh.mw = MagicMock()
    mh.mw.translation_config = {}
    mh.ui_handler = MagicMock()
    mh._session_manager = MagicMock()
    mh.prompt_composer = MagicMock()
    return mh

@pytest.fixture
def ailm(mock_main_handler):
    return AILifecycleManager(mock_main_handler)

def test_ailm_register_handler(ailm):
    cb1 = MagicMock()
    cb2 = MagicMock()
    cb3 = MagicMock()
    ailm.register_handler('task1', cb1, cb2, cb3)
    assert ailm._success_handlers['task1'] == cb1
    assert ailm._error_handlers['task1'] == cb2
    assert ailm._chunk_handlers['task1'] == cb3

@patch('handlers.translation.ai_lifecycle_manager.QMessageBox')
@patch('handlers.translation.ai_lifecycle_manager.create_translation_provider')
def test_ailm_prepare_provider(mock_create, mock_box, ailm):
    # Disabled provider
    ailm.mw.translation_config = {'provider': 'disabled'}
    assert ailm._prepare_provider() is None
    mock_box.information.assert_called_once()
    mock_box.reset_mock()
    
    # Missing provider settings
    ailm.mw.translation_config = {'provider': 'openai', 'providers': {}}
    assert ailm._prepare_provider() is None
    mock_box.warning.assert_called_once()
    mock_box.reset_mock()
    
    # Provider error
    ailm.mw.translation_config = {'provider': 'openai', 'providers': {'openai': {'model': 'gpt'}}}
    mock_create.side_effect = TranslationProviderError("Err")
    assert ailm._prepare_provider() is None
    mock_box.critical.assert_called_once()
    mock_box.reset_mock()
    
    # Success
    mock_create.side_effect = None
    mock_provider = MagicMock()
    mock_provider.supports_sessions = True
    mock_create.return_value = mock_provider
    p = ailm._prepare_provider()
    
    assert p == mock_provider
    assert ailm._active_provider_key == 'openai'
    assert ailm._provider_supports_sessions is True

@patch('handlers.translation.ai_lifecycle_manager.AIWorker')
@patch('handlers.translation.ai_lifecycle_manager.QThread')
def test_ailm_run_ai_task(mock_thread, mock_worker, ailm):
    mock_thread_inst = mock_thread.return_value
    mock_worker_inst = mock_worker.return_value
    
    mock_provider = MagicMock()
    ailm.run_ai_task(mock_provider, {'type': 'translate_preview'})
    
    assert ailm.is_ai_running is True
    assert ailm.main_handler.is_ai_running is True
    assert ailm.thread == mock_thread_inst
    assert ailm.worker == mock_worker_inst
    
    mock_worker_inst.moveToThread.assert_called_with(mock_thread_inst)
    mock_thread_inst.start.assert_called_once()
    
    # Chunked task check
    ailm.run_ai_task(mock_provider, {'type': 'translate_block_chunked'})
    # Worker signals connected differently
    # Using side effects isn't strictly necessary as we're just checking branch execution
    mock_worker_inst.total_chunks_calculated.connect.assert_called()

def test_ailm_on_thread_finished(ailm):
    ailm.worker = MagicMock()
    ailm.thread = MagicMock()
    
    ailm._on_thread_finished()
    
    assert ailm.worker is None
    assert ailm.thread is None
    assert ailm.is_ai_running is False
    
    # Test retry context triggers _perform_retry
    ailm._retry_context = {'type': 'test'}
    ailm._perform_retry = MagicMock()
    ailm._is_waiting_retry_delay = False
    
    ailm._on_thread_finished()
    ailm._perform_retry.assert_called_once()

def test_ailm_callbacks(ailm):
    cb1 = MagicMock()
    cb2 = MagicMock()
    cb3 = MagicMock()
    ailm.register_handler('test', cb1, cb2, cb3)
    
    resp = ProviderResponse()
    
    ailm._on_success(resp, {'type': 'test'})
    cb1.assert_called_with(resp, {'type': 'test'})
    
    ailm._on_success(resp, {'type': 'unknown'}) # No crash, logs warning
    
    ailm._on_chunk_translated(0, "chunk", {'type': 'test'})
    cb3.assert_called_with(0, "chunk", {'type': 'test'})
    
    ailm._on_error("Err", {'type': 'test'})
    cb2.assert_called_with("Err", {'type': 'test'})
    
    ailm._on_worker_cancelled()
    ailm.main_handler.reset_translation_session.assert_called_once()
    ailm.main_handler.prompt_for_revert_after_cancel.assert_called_once()

@patch('handlers.translation.ai_lifecycle_manager.QMessageBox')
def test_ailm_handle_task_error(mock_box, ailm):
    # Glossary task
    ailm._handle_task_error("Err", {'type': 'fill_glossary'})
    ailm.main_handler.ui_handler.finish_ai_operation.assert_called_once()
    ailm.main_handler.glossary_handler._handle_ai_fill_error.assert_called_with("Err", {'type': 'fill_glossary'})
    
    # Glossary notes task
    mock_box.reset_mock()
    ailm._handle_task_error("Err", {'type': 'glossary_notes_variation', 'dialog': 'd'})
    mock_box.warning.assert_called_once()
    
    # Timeout
    mock_box.reset_mock()
    mock_box.question.return_value = mock_box.Yes
    ctx = {'type': 'translate_preview', 'attempt': 1, 'max_retries': 3}
    
    with patch('handlers.translation.ai_lifecycle_manager.QTimer') as mock_timer:
        ailm._handle_task_error("Read timed out", ctx)
        mock_box.question.assert_called_once()
        assert ailm._retry_context == ctx
        mock_timer.singleShot.assert_called_once()
        
    # Non-timeout error max attempts reached
    mock_box.reset_mock()
    ailm._handle_task_error("Fatal", {'type': 'translate_preview', 'attempt': 3, 'max_retries': 3})
    mock_box.critical.assert_called_once()

def test_ailm_clean_model_output(ailm):
    text = "```json\n{ \"a\": 1 }\n```"
    assert ailm._clean_model_output(ProviderResponse(text=text)) == '{ "a": 1 }'
    
    text2 = "Some random { \"b\": 2 } text"
    assert ailm._clean_model_output(text2) == '{ "b": 2 }'
    
    text3 = "No braces here"
    assert ailm._clean_model_output(text3) == "No braces here"
    
    assert ailm._trim_trailing_whitespace_from_lines("test  \nb  \n") == "test\nb\n"

def test_ailm_perform_retry(ailm):
    ailm._retry_context = {'type': 'translate_preview'}
    
    with patch('handlers.translation.ai_lifecycle_manager.QTimer') as mock_timer:
        ailm._perform_retry()
        # Ensure label reset
        assert ailm._retry_context is None
        mock_timer.singleShot.assert_called_once()
        
    # Unhandled task type
    ailm._retry_context = {'type': 'unknown'}
    with patch('handlers.translation.ai_lifecycle_manager.QMessageBox') as mock_box:
        ailm._perform_retry()
        mock_box.critical.assert_called_once()
