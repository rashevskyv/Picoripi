# --- START OF FILE handlers/ai_chat_handler.py ---
from typing import Dict, Optional, List, Any
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QThread
from PyQt5.QtGui import QTextCursor
from .base_handler import BaseHandler
from components.ai_chat_dialog import AIChatDialog
from core.translation.session_manager import TranslationSessionManager
from core.translation.providers import ProviderResponse
from handlers.translation.ai_worker import AIWorker
from utils.logging_utils import log_debug, log_warning
from html import escape
import re
import markdown

class AIChatHandler(BaseHandler):
    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any):
        super().__init__(main_window, data_processor, ui_updater)
        self.dialog: Optional[AIChatDialog] = None
        self.sessions: Dict[int, TranslationSessionManager] = {}
        self._worker: Optional[AIWorker] = None
        self._thread: Optional[QThread] = None
        self.system_prompt = "You are a helpful linguistic assistant specializing in video game localization."
        self._stream_buffer: Dict[int, str] = {}

    def _get_available_providers(self) -> Dict[str, Dict[str, str]]:
        providers_data: Dict[str, Dict[str, str]] = {}
        config: Dict[str, Any] = getattr(self.mw, 'translation_config', {}).get('providers', {})
        for key, info in config.items():
            if key != 'disabled':
                display_name: str = key.replace('_', ' ').title()
                providers_data[key] = {
                    'display_name': display_name,
                    'model': info.get('model', 'default')
                }
        return providers_data

    def show_chat_window(self, initial_text: str = "") -> None:
        if self.dialog is None:
            self.dialog = AIChatDialog(self.mw)
            self.dialog.message_sent.connect(self._handle_send_message)
            self.dialog.tabs.tabCloseRequested.connect(self._handle_tab_closed)
            self.dialog.add_tab_button.clicked.connect(self._add_new_chat_session)
            
            self._add_new_chat_session()

        if initial_text:
            current_tab = self.dialog.tabs.currentWidget()
            if current_tab:
                current_content = current_tab.input_edit.toPlainText()
                separator = "\n\n" if current_content.strip() else ""
                context_block = f"--- Context ---\n{initial_text.strip()}\n---"
                current_tab.input_edit.setPlainText(current_content + separator + context_block)
                current_tab.input_edit.moveCursor(QTextCursor.End)
        
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
        
        current_tab = self.dialog.tabs.currentWidget()
        if current_tab:
            current_tab.input_edit.setFocus()

    def _add_new_chat_session(self) -> None:
        if not self.dialog: return

        new_tab = self.dialog.add_new_tab()
        providers = self._get_available_providers()
        new_tab.populate_models(providers)
        
        tab_index = self.dialog.tabs.indexOf(new_tab)
        self.sessions[tab_index] = TranslationSessionManager()

    def _handle_tab_closed(self, index: int) -> None:
        if index in self.sessions:
            del self.sessions[index]
            log_debug(f"AI Chat: Session for tab {index} has been removed.")
        else:
            if index in self.sessions:
                del self.sessions[index]
                log_debug(f"AI Chat: Session for tab index {index} has been removed.")

    def _handle_send_message(self, tab_index: int, message: str, provider_key: str, web_search_enabled: bool) -> None:
        if self.dialog:
            html = f"""
            <table class="message-table user-message">
              <tr>
                <td>
                  <div class='chat-prefix chat-prefix-user'>User</div>
                  <div class='chat-content'>{escape(message)}</div>
                </td>
              </tr>
            </table>
            """
            self.dialog.append_to_history(tab_index, html)
            self.dialog.set_input_enabled(tab_index, False)

        provider = self.mw.translation_handler._prepare_provider(provider_key)
        if not provider:
            error_html = f"""
            <table class="message-table ai-message">
              <tr>
                <td>
                  <div class='chat-prefix chat-prefix-ai' style='color:red;'>Error</div>
                  <div class='chat-content' style='color:red;'>Could not create AI provider '{provider_key}'.</div>
                </td>
              </tr>
            </table>
            """
            self.dialog.append_to_history(tab_index, error_html)
            self.dialog.set_input_enabled(tab_index, True)
            return

        session_manager = self.sessions.get(tab_index)
        if not session_manager:
            session_manager = TranslationSessionManager()
            self.sessions[tab_index] = session_manager
            log_debug(f"AI Chat: Re-created missing session for tab index {tab_index}.")

        use_stream = True
        if provider_key == 'gemini' and provider.settings.get('base_url'):
            use_stream = False
            log_debug("AI Chat: Gemini with base_url detected, disabling streaming.")

        state = session_manager.ensure_session(
            provider_key=provider_key,
            base_system_prompt=self.system_prompt,
            full_system_prompt=self.system_prompt,
            supports_sessions=provider.supports_sessions,
            start_new_session=False
        )

        messages, session_payload = state.prepare_request({"role": "user", "content": message})
        
        content_end_pos_before = 0
        if use_stream and self.dialog:
            tab = self.dialog.tabs.widget(tab_index)
            if tab:
                cursor = tab.history_view.textCursor()
                cursor.movePosition(QTextCursor.End)
                content_end_pos_before = cursor.position()

        task_details = {
            'type': 'chat_message_stream' if use_stream else 'chat_message',
            'tab_index': tab_index,
            'session_state': state,
            'session_user_message': message,
            'web_search_enabled': web_search_enabled,
            'content_end_pos_before': content_end_pos_before
        }

        if self._thread and self._thread.isRunning():
            log_warning("AI Chat: An AI task is already running. Please wait.")
            self.dialog.set_input_enabled(tab_index, True)
            return

        self._thread = QThread()
        self._worker = AIWorker(provider, None, task_details)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        if use_stream:
            self._stream_buffer[tab_index] = ""
            self._worker.chunk_received.connect(self._on_ai_chunk_received)
            self._worker.success.connect(self._on_ai_stream_finished)
        else:
            self._worker.success.connect(self._on_ai_chat_success)
        
        self._worker.error.connect(self._on_ai_error)
        self._worker.finished.connect(self._cleanup_worker)

        self._thread.start()
    
    def _process_annotations(self, text: str, annotations: List[Dict[str, Any]]) -> str:
        if not annotations:
            return text
        
        modified_text = text
        for ann in sorted(annotations, key=lambda x: x['start_index'], reverse=True):
            start = ann.get('start_index')
            end = ann.get('end_index')
            url = ann.get('url')
            title = ann.get('title', url)
            
            if start is None or end is None or not url:
                continue

            link = f'<a href="{escape(url)}" title="{escape(title)}">'
            modified_text = modified_text[:end] + '</a>' + modified_text[end:]
            modified_text = modified_text[:start] + link + modified_text[start:]
            
        return modified_text

    def _format_ai_response_for_display(self, text: str, annotations: Optional[List[Dict[str, Any]]]) -> str:
        text_with_citations = self._process_annotations(text, annotations) if annotations else text
        
        html_output = markdown.markdown(text_with_citations, extensions=['nl2br', 'fenced_code'])
        
        return html_output

    def _on_ai_chunk_received(self, context: Dict[str, Any], chunk: str) -> None:
        tab_index = context.get('tab_index')
        if self.dialog and tab_index is not None:
            tab = self.dialog.tabs.widget(tab_index)
            if tab:
                cursor = tab.history_view.textCursor()
                cursor.movePosition(QTextCursor.End)
                cursor.insertText(escape(chunk))
                tab.history_view.ensureCursorVisible()
                self._stream_buffer[tab_index] = self._stream_buffer.get(tab_index, "") + chunk
    
    def _on_ai_stream_finished(self, response: ProviderResponse, context: Dict[str, Any]) -> None:
        tab_index = context.get('tab_index')
        if self.dialog and tab_index is not None:
            full_response = self._stream_buffer.get(tab_index, "")
            formatted_html = self._format_ai_response_for_display(full_response, response.annotations)
            
            tab = self.dialog.tabs.widget(tab_index)
            if tab:
                content_end_pos_before = context.get('content_end_pos_before', 0)
                cursor = tab.history_view.textCursor()
                cursor.setPosition(content_end_pos_before)
                cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()

            final_html = f"""
            <table class="message-table ai-message">
              <tr>
                <td>
                  <div class='chat-prefix chat-prefix-ai'>AI</div>
                  <div class='chat-content'>{formatted_html}</div>
                </td>
              </tr>
            </table>
            """
            self.dialog.append_to_history(tab_index, final_html)
            self._stream_buffer[tab_index] = ""
            
            state = context.get('session_state')
            user_content = context.get('session_user_message')
            if state and user_content:
                state.record_exchange(
                    user_content=user_content, 
                    assistant_content=response.text or full_response, 
                    conversation_id=response.conversation_id
                )

    def _on_ai_chat_success(self, response: ProviderResponse, context: Dict[str, Any]) -> None:
        tab_index: Optional[int] = context.get('tab_index')
        if self.dialog and tab_index is not None:
            self.dialog.set_input_enabled(tab_index, True)
            ai_response_text = response.text or "[No response]"
            
            formatted_html = self._format_ai_response_for_display(ai_response_text, response.annotations)
            html = f"""
            <table class="message-table ai-message">
              <tr>
                <td>
                  <div class='chat-prefix chat-prefix-ai'>AI</div>
                  <div class='chat-content'>{formatted_html}</div>
                </td>
              </tr>
            </table>
            """
            self.dialog.append_to_history(tab_index, html)
            
            state = context.get('session_state')
            user_content = context.get('session_user_message')
            if state and user_content:
                state.record_exchange(user_content=user_content, assistant_content=ai_response_text, conversation_id=response.conversation_id)

    def _on_ai_error(self, message: str, context: Dict[str, Any]) -> None:
        tab_index = context.get('tab_index')
        if self.dialog and tab_index is not None:
            content_end_pos_before = context.get('content_end_pos_before', 0)
            if content_end_pos_before > 0:
                tab = self.dialog.tabs.widget(tab_index)
                if tab:
                    cursor = tab.history_view.textCursor()
                    cursor.setPosition(content_end_pos_before)
                    cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
                    cursor.removeSelectedText()

            self.dialog.set_input_enabled(tab_index, True)
            html = f"""
            <table class="message-table ai-message">
              <tr>
                <td>
                  <div class='chat-prefix chat-prefix-ai' style='color:red;'>Error</div>
                  <div class='chat-content' style='color:red;'>{escape(message)}</div>
                </td>
              </tr>
            </table>
            """
            self.dialog.append_to_history(tab_index, html)

    def _cleanup_worker(self) -> None:
        tab_index = self._worker.task_details.get('tab_index') if self._worker else None
        if self.dialog and tab_index is not None:
            self.dialog.set_input_enabled(tab_index, True)
            
        if self._thread:
            if self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(1000)
            self._thread.deleteLater()
            self._thread = None
        if self._worker:
            self._worker.deleteLater()
            self._worker = None