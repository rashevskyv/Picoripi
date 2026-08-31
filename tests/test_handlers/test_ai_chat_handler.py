import pytest
from unittest.mock import MagicMock, patch
from handlers.ai_chat_handler import AIChatHandler

@pytest.fixture
def chat_handler(mock_mw):
    return AIChatHandler(mock_mw, MagicMock(), mock_mw.ui_updater)

def test_AIChatHandler_init(chat_handler, mock_mw):
    assert chat_handler.mw == mock_mw
    assert chat_handler.dialog is None
    assert chat_handler.sessions == {}

def test_AIChatHandler_get_available_providers(chat_handler, mock_mw):
    mock_mw.translation_config = {'providers': {'openai': {'model': 'gpt-4'}}}
    providers = chat_handler._get_available_providers()
    assert 'openai' in providers
    assert providers['openai']['model'] == 'gpt-4'
    assert providers['openai']['display_name'] == 'OpenAI Compatible'

@patch('handlers.ai_chat_handler.AIChatDialog')
def test_AIChatHandler_show_chat_window(mock_dialog_class, chat_handler):
    chat_handler.show_chat_window()
    assert chat_handler.dialog is not None
    mock_dialog_class.return_value.show.assert_called_once()
    mock_dialog_class.return_value.raise_.assert_called_once()

def test_AIChatHandler_add_new_chat_session(chat_handler):
    chat_handler.dialog = MagicMock()
    chat_handler._add_new_chat_session()
    chat_handler.dialog.add_new_tab.assert_called_once()
    assert len(chat_handler.sessions) == 1

def test_AIChatHandler_handle_tab_closed(chat_handler):
    chat_handler.sessions = {1: MagicMock()}
    chat_handler._handle_tab_closed(1)
    assert 1 not in chat_handler.sessions

@patch('handlers.ai_chat_handler.AIWorker')
@patch('handlers.ai_chat_handler.QThread')
def test_AIChatHandler_handle_send_message(mock_qthread_class, mock_worker_class, chat_handler, mock_mw):
    chat_handler.dialog = MagicMock()
    mock_provider = MagicMock()
    mock_mw.translation_handler._prepare_provider.return_value = mock_provider
    mock_provider.supports_sessions = True
    
    mock_thread_instance = mock_qthread_class.return_value
    mock_thread_instance.isRunning.return_value = False
    
    chat_handler._handle_send_message(1, "msg", "openai", False)
    
    assert 1 in chat_handler.sessions
    mock_worker_class.assert_called_once()
    mock_thread_instance.start.assert_called_once()
    # Dialog input remains enabled (set_input_enabled(False) is never called)
    chat_handler.dialog.set_input_enabled.assert_not_called()


def test_AIChatHandler_busy_chat_queues_second_message(chat_handler, mock_mw):
    chat_handler.dialog = MagicMock()
    mock_thread = MagicMock()
    mock_thread.isRunning.return_value = True
    chat_handler._thread = mock_thread

    chat_handler._handle_send_message(1, "second message", "openai", False)

    # Dialog history NOT appended before dequeue
    chat_handler.dialog.append_to_history.assert_not_called()
    # Queued in _message_queue
    assert len(chat_handler._message_queue) == 1
    assert chat_handler._message_queue[0]["message"] == "second message"
    assert chat_handler._message_queue[0]["tab_index"] == 1


@patch('handlers.ai_chat_handler.AIWorker')
@patch('handlers.ai_chat_handler.QThread')
def test_AIChatHandler_queued_message_starts_after_worker_completes(mock_qthread, mock_worker, chat_handler, mock_mw):
    chat_handler.dialog = MagicMock()
    mock_provider = MagicMock()
    mock_mw.translation_handler._prepare_provider.return_value = mock_provider
    mock_provider.supports_sessions = True

    # Setup running thread and worker
    mock_thread_inst = MagicMock()
    mock_thread_inst.isRunning.return_value = False
    chat_handler._thread = mock_thread_inst
    worker_mock = MagicMock()
    chat_handler._worker = worker_mock
    worker_mock.task_details = {'tab_index': 1}

    # Queue second message
    chat_handler._message_queue.append({
        'tab_index': 1,
        'message': 'queued message',
        'provider_key': 'openai',
        'web_search_enabled': False,
    })

    chat_handler._cleanup_worker()

    # User bubble appended once upon starting the queued request
    chat_handler.dialog.append_to_history.assert_called_once()
    assert "queued message" in chat_handler.dialog.append_to_history.call_args.args[1]

    # Queue should now be empty and second request started
    assert len(chat_handler._message_queue) == 0
    mock_worker.assert_called_once()
    assert chat_handler._worker is not None


@patch('handlers.ai_chat_handler.AIWorker')
@patch('handlers.ai_chat_handler.QThread')
def test_AIChatHandler_streaming_queue_end_to_end_ordering(mock_qthread, mock_worker, chat_handler, mock_mw):
    chat_handler.dialog = MagicMock()
    mock_provider = MagicMock()
    mock_mw.translation_handler._prepare_provider.return_value = mock_provider
    mock_provider.supports_sessions = True

    mock_thread_inst = MagicMock()
    mock_thread_inst.isRunning.return_value = False
    mock_qthread.return_value = mock_thread_inst

    # Send message 1
    chat_handler._handle_send_message(1, "First prompt", "openai", False)
    assert chat_handler.dialog.append_to_history.call_count == 1
    assert "First prompt" in chat_handler.dialog.append_to_history.call_args.args[1]
    assert len(chat_handler._message_queue) == 0

    # While message 1 is running, send message 2
    mock_thread_inst.isRunning.return_value = True
    chat_handler._handle_send_message(1, "Second prompt", "openai", False)

    # Second user bubble is NOT appended yet
    assert chat_handler.dialog.append_to_history.call_count == 1
    assert len(chat_handler._message_queue) == 1

    # First stream completes and worker cleans up
    mock_thread_inst.isRunning.return_value = False
    response = MagicMock(text="AI response 1", annotations=[], conversation_id="conv-1")
    context = {'tab_index': 1, 'session_state': MagicMock(), 'session_user_message': 'First prompt'}
    chat_handler._on_ai_stream_finished(response, context)
    assert chat_handler.dialog.append_to_history.call_count == 2  # +1 for AI message

    # Worker cleanup triggers next queued message
    chat_handler._cleanup_worker()

    # Second user message is now appended and worker started
    assert chat_handler.dialog.append_to_history.call_count == 3  # +1 for Second user message
    assert "Second prompt" in chat_handler.dialog.append_to_history.call_args.args[1]
    assert len(chat_handler._message_queue) == 0


def test_AIChatHandler_process_annotations(chat_handler):
    assert chat_handler._process_annotations("foo", []) == "foo"
    annotations = [{'start_index': 5, 'end_index': 16, 'url': 'http://test.com', 'title': 'Test'}]
    res = chat_handler._process_annotations("text 【11†source】", annotations)
    assert '<a href="http://test.com"' in res

def test_AIChatHandler_format_ai_response_for_display(chat_handler):
    formatted = chat_handler._format_ai_response_for_display("Hello\n**Bold**", [])
    assert "<p>Hello</p>" in formatted or "<br" in formatted or "Hello" in formatted

def test_AIChatHandler_on_ai_chunk_received(chat_handler):
    chat_handler.dialog = MagicMock()
    chat_handler._on_ai_chunk_received({'tab_index': 1}, "chunk")
    assert chat_handler._stream_buffer[1] == "chunk"

def test_AIChatHandler_on_ai_stream_finished(chat_handler):
    chat_handler.dialog = MagicMock()
    chat_handler._stream_buffer[1] = "Full message"
    
    response = MagicMock()
    response.text = "Full message"
    response.annotations = []
    response.conversation_id = "123"
    
    context = {'tab_index': 1, 'session_state': MagicMock(), 'session_user_message': 'hello'}
    
    chat_handler._on_ai_stream_finished(response, context)
    chat_handler.dialog.append_to_history.assert_called_once()
    assert chat_handler._stream_buffer[1] == ""

def test_AIChatHandler_on_ai_chat_success(chat_handler):
    chat_handler.dialog = MagicMock()
    response = MagicMock()
    response.text = "Response"
    response.annotations = []
    response.conversation_id = "123"
    
    context = {'tab_index': 1, 'session_state': MagicMock(), 'session_user_message': 'hello'}
    
    chat_handler._on_ai_chat_success(response, context)
    chat_handler.dialog.set_input_enabled.assert_called_with(1, True)

def test_AIChatHandler_on_ai_error(chat_handler):
    chat_handler.dialog = MagicMock()
    context = {'tab_index': 1}
    
    chat_handler._on_ai_error("Error details", context)
    chat_handler.dialog.append_to_history.assert_called_once()

def test_AIChatHandler_cleanup_worker(chat_handler):
    mock_thread = MagicMock()
    chat_handler._thread = mock_thread
    mock_thread.isRunning.return_value = True
    
    worker_mock = MagicMock()
    chat_handler._worker = worker_mock
    worker_mock.task_details = {'tab_index': 1}
    
    chat_handler._cleanup_worker()
    
    mock_thread.quit.assert_called_once()
    worker_mock.deleteLater.assert_called_once()
    assert chat_handler._thread is None

@patch('utils.thread_utils.safe_shutdown_thread')
def test_AIChatHandler_prepare_to_close(mock_safe_shutdown, chat_handler):
    mock_thread = MagicMock()
    mock_worker = MagicMock()
    chat_handler._thread = mock_thread
    chat_handler._worker = mock_worker

    chat_handler.prepare_to_close()

    mock_safe_shutdown.assert_called_once_with(mock_thread, mock_worker)
    assert chat_handler._thread is None
    assert chat_handler._worker is None

def test_AIChatHandler_history_limit(chat_handler):
    from core.translation.session_manager import TranslationSessionState
    state = TranslationSessionState(
        provider_key="openai",
        base_system_prompt="system",
        current_system_prompt="system"
    )
    # Record exchange 25 times (limit is 20 pairs = 40 messages)
    for i in range(25):
        state.record_exchange(
            user_content=f"user {i}",
            assistant_content=f"ai {i}",
            conversation_id=None
        )
    # Check that history length is capped at 40 (MAX_HISTORY_MESSAGES * 2)
    assert len(state.history) == 40
    # The oldest messages (0 to 4) should be discarded
    assert state.history[0]["content"] == "user 5"
    assert state.history[-1]["content"] == "ai 24"



