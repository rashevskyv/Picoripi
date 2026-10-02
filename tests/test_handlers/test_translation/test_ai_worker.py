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


def test_AIWorker_cancel_closes_active_provider_stream(worker_deps):
    provider, prompt_composer = worker_deps
    worker = AIWorker(provider, prompt_composer, {})

    worker.cancel()

    provider.cancel_active_stream.assert_called_once()

def test_AIWorkerclean_json_response(worker_deps):
    provider, prompt_composer = worker_deps
    worker = AIWorker(provider, prompt_composer, {})
    
    assert worker._clean_json_response("```json\n{\"a\":1}\n```") == '{"a":1}'
    assert worker._clean_json_response("Some text { \"a\": 1 } more text") == '{ "a": 1 }'
    # No JSON at all is an error, not text handed on for json.loads to trip over.
    for not_json in ("Just text", ""):
        with pytest.raises(json.JSONDecodeError):
            worker._clean_json_response(not_json)

    # Тести для видалення trailing commas
    invalid_json_object = '{"a": 1, "b": "hello",}'
    assert json.loads(worker._clean_json_response(invalid_json_object)) == {"a": 1, "b": "hello"}
    # An unfenced array keeps its brackets.
    assert worker._clean_json_response('[{"a":1},{"b":2}]') == '[{"a":1},{"b":2}]'

    # Тест на ігнорування коми всередині лапок
    json_with_comma_in_string = '{"a": "привіт, }"}'
    assert worker._clean_json_response(json_with_comma_in_string) == '{"a": "привіт, }"}'

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
        'block_data': ['test'],
        'target_indices': [0],
        'chunk_size': 8000,
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

def test_AIWorker_build_glossary_unreadable_chunk_is_an_error_not_a_silent_drop(worker_deps):
    provider, prompt_composer = worker_deps
    worker = AIWorker(provider, prompt_composer, {
        'type': 'build_glossary',
        'block_data': ['test'],
        'target_indices': [0],
        'chunk_size': 8000,
        'dialog_steps': ['1', '2', '3', '4'],
    })
    mock_success = MagicMock()
    mock_error = MagicMock()
    worker.success.connect(mock_success)
    worker.error.connect(mock_error)
    provider.translate.return_value = ProviderResponse(text='{"note": "an object, not the term list"}')

    worker.run()

    mock_error.assert_called_once()
    assert mock_error.call_args[0][1]['error_kind'] == 'parse'
    mock_success.assert_not_called()


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
    
    response = ProviderResponse(text='{"translated_strings": [{"id": 0, "translation": "TransA"}]}')
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

def test_AIWorker_mw_fallback_and_logging(worker_deps):
    provider, _ = worker_deps
    mock_mw = MagicMock()
    mock_mw.log_ai_traffic = True
    
    state_mock = MagicMock()
    state_mock.prepare_request.return_value = ([{"role": "user", "content": "hi"}], None)
    
    task_details = {
        'type': 'chat_message',
        'session_state': state_mock,
        'session_user_message': 'hello'
    }
    
    worker = AIWorker(provider, None, task_details, mw=mock_mw)
    
    assert worker.mw == mock_mw
    
    provider.translate.return_value = ProviderResponse(text="response")
    
    with patch('utils.logging_utils.log_ai_traffic') as mock_log:
        worker.run()
        assert mock_log.called
        assert mock_log.call_args[0][0] == mock_mw


def test_AIWorker_detail_updated_signal(worker_deps):
    provider, prompt_composer = worker_deps
    
    # Mock MemePalaceClient
    mock_client = MagicMock()
    mock_client.get_script_mapping.return_value = {
        "script_line": 123,
        "chapter_num": 4,
        "chapter_title": "Arbitrary Chapter Name"
    }
    prompt_composer._get_mempalace_client.return_value = mock_client
    prompt_composer._get_wing_name.return_value = "Zelda_TP"
    prompt_composer._get_block_label.return_value = "d_mn08"
    
    task_details = {
        'type': 'translate_block_chunked',
        'source_items': [{'id': 10, 'text': 'A'}],
        'composer_args': {}
    }
    worker = AIWorker(provider, prompt_composer, task_details)
    
    mock_detail_updated = MagicMock()
    worker.detail_updated.connect(mock_detail_updated)
    
    response = ProviderResponse(text='{"translated_strings": [{"id": 10, "translation": "TransA"}]}')
    provider.translate.return_value = response
    
    worker.run()
    
    mock_detail_updated.assert_called_once()
    emitted_text = mock_detail_updated.call_args[0][0]
    assert "Chapter 4" in emitted_text
    assert "Arbitrary Chapter Name" in emitted_text
    assert "d_mn08" in emitted_text
    assert "Line: 10" in emitted_text
    assert "Script Line: 123" in emitted_text

def test_AIWorker_retry_adds_reminder(worker_deps):
    provider, prompt_composer = worker_deps
    
    # 1. Test batch block translation attempt > 1
    task_details = {
        'type': 'translate_block_chunked',
        'source_items': ['A'],
        'composer_args': {},
        'attempt': 2
    }
    worker = AIWorker(provider, prompt_composer, task_details)
    
    provider.translate.return_value = ProviderResponse(text='{"translated_strings": ["TransA"]}')
    
    worker.run()
    
    # Verify that translator was called with messages having the retry reminder
    call_messages = provider.translate.call_args[0][0]
    assert isinstance(call_messages, list)
    system_content = next(msg['content'] for msg in call_messages if msg.get('role') == 'system')
    assert "IMPORTANT REMINDER FOR RETRY" in system_content
    assert "trailing commas" in system_content

    # 2. Test other task attempt > 1 (e.g. translate_single)
    task_details_single = {
        'type': 'translate_single',
        'composer_args': {'system_prompt': 'sys', 'user_prompt': 'user'},
        'attempt': 3,
        'dialog_steps': ['1', '2', '3']
    }
    worker_single = AIWorker(provider, prompt_composer, task_details_single)
    worker_single.run()
    
    call_messages_single = provider.translate.call_args[0][0]
    system_content_single = next(msg['content'] for msg in call_messages_single if msg.get('role') == 'system')
    assert "IMPORTANT REMINDER FOR RETRY" in system_content_single


def test_AIWorker_run_glossary_occurrence_batch_update_chunking(worker_deps):
    provider, prompt_composer = worker_deps
    
    # Mock compose_glossary_occurrence_batch_request to return (system, user)
    prompt_composer.compose_glossary_occurrence_batch_request.return_value = ("sys", "user")
    
    # We want to test chunking, so let's provide 15 items (which should split into 2 chunks: 12 and 3)
    batch_items = [{"id": str(i), "text": f"text{i}"} for i in range(15)]
    
    task_details = {
        'type': 'glossary_occurrence_batch_update',
        'composer_args': {
            'system_prompt': 'sys',
            'term': 'sword',
            'old_translation': 'меч',
            'new_translation': 'меч2',
            'batch_items': batch_items
        }
    }
    
    worker = AIWorker(provider, prompt_composer, task_details)
    
    # Mock provider translate to return different chunks.
    # Chunk 1 (12 items): 0-11
    # Chunk 2 (3 items): 12-14
    mock_responses = [
        ProviderResponse(text=json.dumps({"occurrences": [{"id": str(i), "translation": f"trans{i}"} for i in range(12)]})),
        ProviderResponse(text=json.dumps({"occurrences": [{"id": str(i), "translation": f"trans{i}"} for i in range(12, 15)]}))
    ]
    provider.translate.side_effect = mock_responses
    
    mock_success = MagicMock()
    mock_error = MagicMock()
    worker.success.connect(mock_success)
    worker.error.connect(mock_error)
    
    worker.run()
    
    if mock_error.called:
        pytest.fail(f"Worker emitted error: {mock_error.call_args}")
        
    assert provider.translate.call_count == 2
    mock_success.assert_called_once()

    # Verify aggregated payload has all 15 elements
    success_arg = mock_success.call_args[0][0]
    payload = json.loads(success_arg.text)
    occurrences = payload.get("occurrences")
    assert len(occurrences) == 15
    for i in range(15):
        assert occurrences[i]["id"] == str(i)
        assert occurrences[i]["translation"] == f"trans{i}"


def test_AIWorker_run_translate_block_chunked_parallel(worker_deps):
    provider, prompt_composer = worker_deps
    source_items = [{"id": i, "text": f"Line {i}"} for i in range(25)]

    prompt_composer.compose_batch_request.side_effect = lambda **kwargs: (
        "sys",
        json.dumps(kwargs.get("source_items", [])),
        "fmt"
    )

    task_details = {
        'type': 'translate_block_chunked',
        'block_idx': 0,
        'source_items': source_items,
        'workers': 4,
        'composer_args': {
            'system_prompt': 'sys',
            'block_idx': 0,
            'mode_description': 'block 1'
        }
    }

    worker = AIWorker(provider, prompt_composer, task_details)

    def dynamic_translate(messages, session=None, settings_override=None):
        import re
        user_msg = next((m['content'] for m in messages if m.get('role') == 'user'), "")
        ids = re.findall(r'"id":\s*(\d+)', user_msg)
        if ids:
            return ProviderResponse(text=json.dumps({
                "translated_strings": [{"id": int(i), "translation": f"Переклад {i}"} for i in ids]
            }))
        return ProviderResponse(text=json.dumps({
            "translated_strings": [{"translation": "Переклад"}]
        }))

    provider.translate.side_effect = dynamic_translate

    chunk_signals = []
    worker.chunk_translated.connect(lambda idx, text, ctx: chunk_signals.append((idx, text)))
    error_signals = []
    worker.error.connect(lambda msg, ctx: error_signals.append(msg))

    worker.run()

    assert not error_signals, f"Unexpected errors: {error_signals}"
    assert len(chunk_signals) == 3
    assert provider.translate.call_count == 3



def _parallel_worker(worker_deps, item_count, workers):
    provider, prompt_composer = worker_deps
    source_items = [{"id": i, "text": f"Line {i}"} for i in range(item_count)]
    prompt_composer.compose_batch_request.side_effect = lambda **kwargs: (
        "sys", json.dumps(kwargs.get("source_items", [])), "fmt"
    )
    worker = AIWorker(provider, prompt_composer, {
        'type': 'translate_block_chunked',
        'block_idx': 0,
        'source_items': source_items,
        'workers': workers,
        'enable_editor_review': False,
        'composer_args': {'system_prompt': 'sys', 'block_idx': 0, 'mode_description': 'block 1'},
    })
    chunks, errors = [], []
    worker.chunk_translated.connect(lambda idx, text, ctx: chunks.append(idx))
    worker.error.connect(lambda msg, ctx: errors.append((msg, ctx)))
    return provider, worker, chunks, errors


def _ids_in(messages):
    import re
    user_msg = next((m['content'] for m in messages if m.get('role') == 'user'), "")
    return [int(i) for i in re.findall(r'"id":\s*(\d+)', user_msg)]


def test_parallel_one_bad_chunk_keeps_the_other_seven(worker_deps):
    provider, worker, chunks, errors = _parallel_worker(worker_deps, item_count=96, workers=4)

    def translate(messages, session=None, settings_override=None):
        ids = _ids_in(messages)
        if 24 in ids:  # the third chunk of eight
            return ProviderResponse(text="Sorry, I cannot translate this.")
        return ProviderResponse(text=json.dumps(
            {"translated_strings": [{"id": i, "translation": f"T{i}"} for i in ids]}
        ))

    provider.translate.side_effect = translate
    worker.run()

    assert sorted(chunks) == [0, 1, 3, 4, 5, 6, 7]
    assert len(errors) == 1
    message, details = errors[0]
    assert details['failed_chunks'] == [2]
    assert "1 of 8 chunks failed (chunk 3)" in message
    assert details['error_kind'] == 'parse'


def test_parallel_fatal_error_stops_handing_out_chunks(worker_deps):
    from core.translation.transport import ErrorKind, TransportError
    provider, worker, chunks, errors = _parallel_worker(worker_deps, item_count=96, workers=2)
    provider.translate.side_effect = TransportError("401 Client Error: Unauthorized", kind=ErrorKind.AUTH, status=401)

    worker.run()

    assert chunks == []
    assert len(errors) == 1 and "the run was stopped" in errors[0][0]
    # Only what was already in the two-wide window was sent; the other chunks never were.
    assert provider.translate.call_count <= 3


def test_parallel_reordered_ids_are_rejected(worker_deps):
    provider, worker, chunks, errors = _parallel_worker(worker_deps, item_count=24, workers=2)

    def translate(messages, session=None, settings_override=None):
        ids = _ids_in(messages)
        if 0 in ids:
            ids = list(reversed(ids))
        return ProviderResponse(text=json.dumps(
            {"translated_strings": [{"id": i, "translation": f"T{i}"} for i in ids]}
        ))

    provider.translate.side_effect = translate
    worker.run()

    assert chunks == [1]
    assert errors[0][1]['failed_chunks'] == [0]
    assert "do not match the request" in errors[0][0]


def test_parallel_run_logs_matching_request_and_response_ids_and_a_summary(worker_deps):
    import utils.logging_utils as logging_utils
    provider, worker, chunks, errors = _parallel_worker(worker_deps, item_count=36, workers=3)
    worker._mw = MagicMock()
    worker._mw.log_ai_traffic = True
    worker._mw.current_game_rules = None
    details = []
    worker.detail_updated.connect(details.append)

    def translate(messages, session=None, settings_override=None):
        ids = _ids_in(messages)
        if 12 in ids:
            from core.translation.transport import ErrorKind, TransportError
            raise TransportError("502 Server Error: Bad Gateway", kind=ErrorKind.SERVER, status=502)
        return ProviderResponse(text=json.dumps(
            {"translated_strings": [{"id": i, "translation": f"T{i}"} for i in ids]}
        ))

    provider.translate.side_effect = translate
    path = logging_utils.ai_traffic_log_path()
    start = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
    worker.run()

    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()[start:]]
    requests_by_id = {r["request_id"]: r for r in records if r["event"] == "request"}
    answers = [r for r in records if r["event"] in ("response", "error") and r.get("request_id")]
    assert len(requests_by_id) == 3 and len(answers) == 3
    for answer in answers:
        assert answer["chunk"] == requests_by_id[answer["request_id"]]["chunk"]
        assert answer["duration_ms"] >= 0
    assert [(r["chunk"], r["kind"], r["status"]) for r in answers if r["event"] == "error"] == [(1, "server", 502)]
    summary = [r for r in records if r["event"] == "summary"][-1]["summary"]
    assert summary.startswith("3 request(s), p50 ") and "failed: server×1" in summary
    assert details[-1] == summary
