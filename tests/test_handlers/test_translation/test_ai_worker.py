import pytest
from unittest.mock import MagicMock, patch
import json
from handlers.translation.ai_worker import AIWorker
from core.translation.providers import ProviderResponse

@pytest.fixture
def worker_deps():
    provider = MagicMock()
    prompt_composer = MagicMock()
    # Mock compose_variation_request to return (system, user)
    prompt_composer.compose_variation_request.return_value = ("sys", "user")
    # Mock compose_batch_request to return (system, user, format)
    prompt_composer.compose_batch_request.return_value = ("sys", "user", "fmt")
    return provider, prompt_composer

def test_AIWorker_init(worker_deps):
    provider, prompt_composer = worker_deps
    worker = AIWorker(provider, prompt_composer, {"type": "test"})
    assert worker.provider == provider
    assert worker.prompt_composer == prompt_composer
    assert worker.task_details == {"type": "test"}
    assert worker.is_cancelled is False

def test_AIWorker_cancel(worker_deps):
    provider, prompt_composer = worker_deps
    worker = AIWorker(provider, prompt_composer, {})
    worker.cancel()
    assert worker.is_cancelled is True

def test_AIWorkerclean_json_response(worker_deps):
    provider, prompt_composer = worker_deps
    worker = AIWorker(provider, prompt_composer, {})
    
    assert worker._clean_json_response("```json\n{\"a\":1}\n```") == '{"a":1}'
    assert worker._clean_json_response("Some text { \"a\": 1 } more text") == '{ "a": 1 }'
    assert worker._clean_json_response("Just text") == "Just text"
    assert worker._clean_json_response("") == ""

def test_AIWorker_run_chat_message(worker_deps):
    provider, prompt_composer = worker_deps
    
    state_mock = MagicMock()
    state_mock.prepare_request.return_value = ([{"role": "user"}], None)
    
    task_details = {
        'type': 'chat_message',
        'session_state': state_mock,
        'session_user_message': 'hello'
    }
    worker = AIWorker(provider, prompt_composer, task_details)
    
    mock_success = MagicMock()
    mock_error = MagicMock()
    mock_finished = MagicMock()
    worker.success.connect(mock_success)
    worker.error.connect(mock_error)
    worker.finished.connect(mock_finished)
    
    response = ProviderResponse(text="response")
    provider.translate.return_value = response
    
    worker.run()
    
    if mock_error.called:
        pytest.fail(f"Worker emitted error: {mock_error.call_args}")
    mock_success.assert_called_once_with(response, task_details)
    mock_finished.assert_called_once()

def test_AIWorker_run_build_glossary(worker_deps):
    provider, prompt_composer = worker_deps
    
    task_details = {
        'type': 'build_glossary',
        'chunks': ['chunk1'],
        'dialog_steps': ['1', '2', '3', '4']
    }
    worker = AIWorker(provider, prompt_composer, task_details)
    
    mock_success = MagicMock()
    mock_error = MagicMock()
    worker.success.connect(mock_success)
    worker.error.connect(mock_error)
    
    response = ProviderResponse(text='```json\n[{"term": "test"}]\n```')
    provider.translate.return_value = response
    
    worker.run()
    
    if mock_error.called:
        pytest.fail(f"Worker emitted error: {mock_error.call_args}")
    mock_success.assert_called()
    emitted_response = mock_success.call_args[0][0]
    assert "test" in emitted_response.text

def test_AIWorker_run_translate_block_chunked(worker_deps):
    provider, prompt_composer = worker_deps
    task_details = {
        'type': 'translate_block_chunked',
        'source_items': ['A'],
        'composer_args': {}
    }
    worker = AIWorker(provider, prompt_composer, task_details)
    
    mock_chunk_translated = MagicMock()
    mock_error = MagicMock()
    worker.chunk_translated.connect(mock_chunk_translated)
    worker.error.connect(mock_error)
    
    response = ProviderResponse(text='{"translated_strings": ["TransA"]}')
    provider.translate.return_value = response
    
    worker.run()
    
    if mock_error.called:
        pytest.fail(f"Worker emitted error: {mock_error.call_args}")
    mock_chunk_translated.assert_called_once()
    assert "TransA" in mock_chunk_translated.call_args[0][1]

def test_AIWorker_run_cancelled(worker_deps):
    """Test that cancel() sets is_cancelled flag and worker stops early."""
    provider, prompt_composer = worker_deps
    worker = AIWorker(provider, prompt_composer, {
        'type': 'translate_block_chunked',
        'source_items': ['A', 'B', 'C'],
        'composer_args': {}
    })
    worker.cancel()
    
    assert worker.is_cancelled is True
    
    mock_cancel = MagicMock()
    mock_error = MagicMock()
    worker.translation_cancelled.connect(mock_cancel)
    worker.error.connect(mock_error)
    
    worker.run()
    
    if mock_error.called:
        pytest.fail(f"Worker emitted error: {mock_error.call_args}")
    # is_cancelled=True перед запуском - iteration відразу emits cancelled
    mock_cancel.assert_called()

def test_AIWorker_run_chat_message_stream(worker_deps):
    provider, prompt_composer = worker_deps
    
    state_mock = MagicMock()
    state_mock.prepare_request.return_value = ([{"role": "user", "content": "hi"}], None)
    
    task_details = {
        'type': 'chat_message_stream',
        'session_state': state_mock,
        'session_user_message': 'hello'
    }
    worker = AIWorker(provider, prompt_composer, task_details)
    
    mock_chunk = MagicMock()
    mock_success = MagicMock()
    worker.chunk_received.connect(mock_chunk)
    worker.success.connect(mock_success)
    
    provider.translate_stream.return_value = ["res", "ponse"]
    
    worker.run()
    
    assert mock_chunk.call_count == 2
    mock_chunk.assert_any_call(task_details, "res")
    mock_chunk.assert_any_call(task_details, "ponse")
    
    assert mock_success.called
    emitted_response = mock_success.call_args[0][0]
    assert emitted_response.text == "response"


