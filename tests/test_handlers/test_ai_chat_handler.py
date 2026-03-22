import pytest
from unittest.mock import MagicMock, patch
from handlers.ai_chat_handler import AIChatHandler
from core.translation.providers import ProviderResponse
from PyQt5.QtCore import QThread

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


