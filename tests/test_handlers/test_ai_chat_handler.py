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

    # Dialog history IS appended immediately with In Queue badge
    chat_handler.dialog.append_to_history.assert_called_once()
    appended_html = chat_handler.dialog.append_to_history.call_args.args[1]
    assert "second message" in appended_html
    assert "In Queue" in appended_html or "chat-queue-badge" in appended_html
    chat_handler.dialog.set_tab_queue_count.assert_called_with(1, 1)

    # Queued in _message_queue with user_rendered=True
    assert len(chat_handler._message_queue) == 1
    assert chat_handler._message_queue[0]["message"] == "second message"
    assert chat_handler._message_queue[0]["tab_index"] == 1
    assert chat_handler._message_queue[0]["user_rendered"] is True


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

    # Queue second message that was already rendered as queued
    chat_handler._message_queue.append({
        'tab_index': 1,
        'message': 'queued message',
        'provider_key': 'openai',
        'web_search_enabled': False,
        'user_rendered': True,
    })

    chat_handler._cleanup_worker()

    # User bubble was already shown; only AI placeholder is appended on start
    chat_handler.dialog.append_to_history.assert_called_once()
    assert "chat-thinking" in chat_handler.dialog.append_to_history.call_args.args[1]

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

    # Send message 1 -> appends User message (1) and AI thinking placeholder (2)
    chat_handler._handle_send_message(1, "First prompt", "openai", False)
    assert chat_handler.dialog.append_to_history.call_count == 2
    assert "First prompt" in chat_handler.dialog.append_to_history.call_args_list[0].args[1]
    assert "chat-thinking" in chat_handler.dialog.append_to_history.call_args_list[1].args[1]
    assert len(chat_handler._message_queue) == 0

    # While message 1 is running, send message 2 -> immediately appended as queued (3)
    mock_thread_inst.isRunning.return_value = True
    chat_handler._handle_send_message(1, "Second prompt", "openai", False)
    assert chat_handler.dialog.append_to_history.call_count == 3
    assert "Second prompt" in chat_handler.dialog.append_to_history.call_args_list[2].args[1]
    assert "chat-queue-badge" in chat_handler.dialog.append_to_history.call_args_list[2].args[1]
    assert len(chat_handler._message_queue) == 1

    # First stream completes and replaces raw stream with final AI response (4)
    mock_thread_inst.isRunning.return_value = False
    response = MagicMock(text="AI response 1", annotations=[], conversation_id="conv-1")
    context = {'tab_index': 1, 'session_state': MagicMock(), 'session_user_message': 'First prompt'}
    chat_handler._on_ai_stream_finished(response, context)
    assert chat_handler.dialog.append_to_history.call_count == 4

    # Worker cleanup triggers next queued message -> starts message 2, appends AI thinking placeholder (5)
    chat_handler._cleanup_worker()
    assert chat_handler.dialog.append_to_history.call_count == 5
    assert "chat-thinking" in chat_handler.dialog.append_to_history.call_args_list[4].args[1]
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
    
    # When stream buffer is empty, displays error with diagnosis
    chat_handler._stream_buffer[1] = ""
    chat_handler._on_ai_error("Read timed out", context)
    chat_handler.dialog.append_to_history.assert_called_once()
    assert "Read timed out" in chat_handler.dialog.append_to_history.call_args.args[1]

    # When stream buffer has partial response, preserves text and shows warning banner
    chat_handler.dialog.append_to_history.reset_mock()
    chat_handler._stream_buffer[1] = "Partial streamed answer about **Hraesvelgr**"
    mock_state = MagicMock()
    context_with_state = {'tab_index': 1, 'session_state': mock_state, 'session_user_message': 'prompt'}
    chat_handler._on_ai_error("API stream request failed: Read timed out", context_with_state)
    chat_handler.dialog.append_to_history.assert_called_once()
    err_html = chat_handler.dialog.append_to_history.call_args.args[1]
    assert "Hraesvelgr" in err_html
    assert "chat-interrupted-warning" in err_html
    assert "Stream Interrupted" in err_html or "Стрім перервано" in err_html
    # Records exchange in session state
    mock_state.record_exchange.assert_called_once()
    assert mock_state.record_exchange.call_args.kwargs['assistant_content'] == "Partial streamed answer about **Hraesvelgr**"


def test_AIChatHandler_on_ai_cancelled(chat_handler):
    chat_handler.dialog = MagicMock()
    worker_mock = MagicMock()
    mock_state = MagicMock()
    worker_mock.task_details = {'tab_index': 1, 'session_state': mock_state, 'session_user_message': 'question'}
    chat_handler._worker = worker_mock
    chat_handler._stream_buffer[1] = "Cancelled response text"

    chat_handler._on_ai_cancelled()
    chat_handler.dialog.append_to_history.assert_called_once()
    cancelled_html = chat_handler.dialog.append_to_history.call_args.args[1]
    assert "Cancelled response text" in cancelled_html
    assert "Generation stopped" in cancelled_html or "зупинено" in cancelled_html
    mock_state.record_exchange.assert_called_once()


def test_AIChatHandler_on_ai_chunk_received_no_html_escaping(chat_handler):
    # Ensure apostrophes and quotes are NOT corrupted to &#x27; or &quot;
    chat_handler.dialog = MagicMock()

    chat_handler._stream_buffer[1] = ""
    chat_handler._is_thinking_placeholder_active[1] = False
    context = {'tab_index': 1, 'content_end_pos_before': 0}

    chat_handler._on_ai_chunk_received(context, "ім'я «бос»")
    chat_handler.dialog.insert_tab_stream_chunk.assert_called_with(1, "ім'я «бос»", auto_scroll=True)
    assert "&#x27;" not in chat_handler.dialog.insert_tab_stream_chunk.call_args.args[1]
    assert chat_handler._stream_buffer[1] == "ім'я «бос»"

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
    mock_dialog = MagicMock()
    chat_handler._thread = mock_thread
    chat_handler._worker = mock_worker
    chat_handler.dialog = mock_dialog

    chat_handler.prepare_to_close()

    mock_safe_shutdown.assert_called_once_with(mock_thread, mock_worker)
    mock_dialog.close.assert_called_once()
    assert chat_handler.dialog is None
    assert chat_handler._thread is None
    assert chat_handler._worker is None


def test_AIChatHandler_show_chat_window_unminimizes(chat_handler):
    mock_dialog = MagicMock()
    mock_dialog.isMinimized.return_value = True
    mock_tab = MagicMock()
    mock_dialog.tabs.currentWidget.return_value = mock_tab
    chat_handler.dialog = mock_dialog

    chat_handler.show_chat_window()

    mock_dialog.show.assert_called_once()
    mock_dialog.showNormal.assert_called_once()
    mock_dialog.raise_.assert_called_once()
    mock_dialog.activateWindow.assert_called_once()
    mock_tab.input_edit.setFocus.assert_called_once()


def test_session_state_prepare_request_preserves_system_prompt_and_history():
    from core.translation.session_manager import TranslationSessionState
    state = TranslationSessionState(
        provider_key="gemini",
        base_system_prompt="Base system instruction",
        current_system_prompt="Full system instruction",
    )

    # Turn 1
    msgs, payload = state.prepare_request({"role": "user", "content": "Hello"})
    assert payload is None
    assert len(msgs) == 2
    assert msgs[0] == {"role": "system", "content": "Full system instruction"}
    assert msgs[1] == {"role": "user", "content": "Hello"}

    # Assistant replies with conversation_id
    state.record_exchange(
        user_content="Hello",
        assistant_content="Hi there!",
        conversation_id="conv-12345",
    )
    assert state.conversation_id == "conv-12345"

    # Turn 2: verify system prompt and history are preserved despite conversation_id
    msgs2, payload2 = state.prepare_request({"role": "user", "content": "Tell me more"})
    assert payload2 == {"conversation_id": "conv-12345"}
    assert len(msgs2) == 4
    assert msgs2[0] == {"role": "system", "content": "Full system instruction"}
    assert msgs2[1] == {"role": "user", "content": "Hello"}
    assert msgs2[2] == {"role": "assistant", "content": "Hi there!"}
    assert msgs2[3] == {"role": "user", "content": "Tell me more"}

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


def test_AIChatHandler_reset_context(chat_handler):
    from core.translation.session_manager import TranslationSessionManager
    chat_handler.dialog = MagicMock()
    session_mgr = TranslationSessionManager()
    state = session_mgr.ensure_session(
        provider_key="gemini",
        base_system_prompt="base",
        full_system_prompt="full",
        supports_sessions=True,
    )
    state.record_exchange(user_content="u1", assistant_content="a1", conversation_id="conv1")
    assert state.conversation_id == "conv1"
    assert len(state.history) == 2

    chat_handler.sessions[0] = session_mgr
    chat_handler._last_request_info[0] = {'message': 'u1'}
    chat_handler._handle_reset_context(0)

    assert session_mgr.get_state() is None
    assert 0 not in chat_handler._last_request_info
    chat_handler.dialog.set_tab_can_retry.assert_called_with(0, False)
    chat_handler.dialog.append_to_history.assert_called_once()
    assert "chat-context-reset" in chat_handler.dialog.append_to_history.call_args.args[1]
    chat_handler.dialog.scroll_to_bottom.assert_called_with(0)


def test_AIChatHandler_retry_message_starts_request(chat_handler):
    mock_dialog = MagicMock()
    mock_tab = MagicMock()
    mock_tab.model_combo.currentData.return_value = 'gemini'
    mock_tab.web_search_checkbox.isChecked.return_value = True
    mock_dialog.tabs.widget.return_value = mock_tab
    chat_handler.dialog = mock_dialog

    chat_handler._last_request_info[0] = {
        'message': 'Test prompt to retry',
        'provider_key': 'openai',
        'web_search_enabled': False,
        'content_end_pos_before': 42,
    }

    with patch.object(chat_handler, '_start_chat_request') as mock_start:
        chat_handler._handle_retry_message(0)

        mock_dialog.remove_tab_text_after.assert_called_once_with(0, 42)
        mock_start.assert_called_once_with(
            0,
            'Test prompt to retry',
            'gemini',
            True,
            user_rendered=True,
        )


def test_AIChatHandler_retry_while_busy_queues_message(chat_handler):
    mock_dialog = MagicMock()
    mock_tab = MagicMock()
    mock_tab.model_combo.currentData.return_value = 'openai'
    mock_tab.web_search_checkbox.isChecked.return_value = False
    mock_dialog.tabs.widget.return_value = mock_tab
    chat_handler.dialog = mock_dialog

    mock_thread = MagicMock()
    mock_thread.isRunning.return_value = True
    chat_handler._thread = mock_thread

    chat_handler._last_request_info[1] = {
        'message': 'Queued retry prompt',
        'provider_key': 'openai',
        'web_search_enabled': False,
        'content_end_pos_before': 15,
    }

    chat_handler._handle_retry_message(1)

    mock_dialog.remove_tab_text_after.assert_called_once_with(1, 15)
    assert len(chat_handler._message_queue) == 1
    assert chat_handler._message_queue[0]['message'] == 'Queued retry prompt'
    assert chat_handler._message_queue[0]['user_rendered'] is True
    mock_dialog.set_tab_queue_count.assert_called_once_with(1, 1)


def test_AIChatHandler_retry_pops_matching_history_from_session(chat_handler):
    from core.translation.session_manager import TranslationSessionManager
    mock_dialog = MagicMock()
    mock_tab = MagicMock()
    mock_tab.model_combo.currentData.return_value = 'openai'
    mock_tab.web_search_checkbox.isChecked.return_value = False
    mock_dialog.tabs.widget.return_value = mock_tab
    chat_handler.dialog = mock_dialog

    session_mgr = TranslationSessionManager()
    state = session_mgr.ensure_session(
        provider_key="openai",
        base_system_prompt="base",
        full_system_prompt="full",
        supports_sessions=True,
    )
    state.record_exchange(user_content="Previous question", assistant_content="Previous answer", conversation_id=None)
    assert len(state.history) == 2

    chat_handler.sessions[0] = session_mgr
    chat_handler._last_request_info[0] = {
        'message': 'Previous question',
        'provider_key': 'openai',
        'web_search_enabled': False,
        'content_end_pos_before': 20,
    }

    with patch.object(chat_handler, '_start_chat_request'):
        chat_handler._handle_retry_message(0)

    # The matching user/assistant pair was popped to avoid duplication
    assert len(state.history) == 0
