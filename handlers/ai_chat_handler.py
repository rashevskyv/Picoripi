import html
import re
from typing import Dict, Optional, List, Any
from PyQt6.QtCore import QThread, QTimer
from PyQt6.QtGui import QTextCursor
from .base_handler import BaseHandler
from components.ai_chat_dialog import AIChatDialog
from core.translation.session_manager import TranslationSessionManager
from core.translation.providers import ProviderResponse, _extract_timeout
from handlers.translation.ai_worker import AIWorker
from utils.logging_utils import log_debug
import markdown
from core.i18n import tr
from utils.utils import resolve_target_language_prompt


class AIChatHandler(BaseHandler):
    """Handler for a i chat operations."""
    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any):
        """Initialize a new instance."""
        super().__init__(main_window, data_processor, ui_updater)
        self.dialog: Optional[AIChatDialog] = None
        self.sessions: Dict[int, TranslationSessionManager] = {}
        self._worker: Optional[AIWorker] = None
        self._thread: Optional[QThread] = None
        self.system_prompt = (
            "You are a helpful linguistic assistant specializing in video game localization into {target_lang}.\n"
            "When discussing, advising, or proposing translations, adhere to these transcription standards:\n"
            "[IF_TARGET_LANG: Ukrainian]\n"
            "Strictly follow modern Ukrainian Orthography (2019) and Ukrainian game localization standards:\n"
            "- Sound [g] (letter G/g) is ALWAYS transcribed as Ukrainian Ґ/ґ (e.g. Hogwarts -> Гоґвортс, Gandalf -> Ґандальф, Ganon -> Ґанон), NEVER Russian Г or Х.\n"
            "- Sound [h] (letter H/h) is ALWAYS transcribed as Ukrainian Г/г (e.g. Harry -> Гаррі, Hyrule -> Гайрул), NEVER Russian Х.\n"
            "- Root Hy- [haɪ] (Hyrule, Hylia, Hylian): Strictly unified as Гайрул, Гайлія, гайлійці / гайлійський (including all related places, fish, and animals: озеро Гайлія, гайрульський окунь, гайлійський щит). NEVER Russian-style Хайрул, NEVER Гілія/Хілія/гілійці.\n"
            "- Digraph Th is transcribed as Т/т (Arthur -> Артур); W is transcribed as В/в (Wind -> Вінд).\n"
            "- Japanese transcription follows the Ukrainian academic/practical Kovalenko system: shi -> сі (Yoshi -> Йосі), chi -> ті (Hitachi -> Хітаті), ji -> дзі (Fuji -> Фудзі), tsu -> цу, plosive g -> ґ, syllabic n before p/b/m -> м. Strictly avoid Russian Polivanov patterns (no ши, чи, джи).\n"
            "- Zero tolerance for Russianisms: no Хогвартс, no Гарри, no Хайрул, no Гілія/Хілія/гілійці.\n"
            "[/IF_TARGET_LANG]"
        )
        self._stream_buffer: Dict[int, str] = {}
        self._message_queue: List[Dict[str, Any]] = []
        self._last_request_info: Dict[int, Dict[str, Any]] = {}
        self._status_timer: Optional[QTimer] = None
        self._elapsed_seconds = 0
        self._active_tab_index: Optional[int] = None
        self._is_thinking_placeholder_active: Dict[int, bool] = {}
        self._auto_scroll: Dict[int, bool] = {}

    def _get_available_providers(self) -> Dict[str, Dict[str, str]]:
        """Internal helper to get the available providers."""
        providers_data: Dict[str, Dict[str, str]] = {}
        config: Dict[str, Any] = getattr(self.mw, 'translation_config', {}).get('providers', {})
        for key, info in config.items():
            if key != 'disabled':
                display_name: str = key.replace('_', ' ').title()
                if key == 'openai':
                    display_name = 'OpenAI Compatible'
                providers_data[key] = {
                    'display_name': display_name,
                    'model': info.get('model', 'default')
                }
        return providers_data

    def show_chat_window(self, initial_text: str = "") -> None:
        """Show chat window."""
        if self.dialog is None:
            self.dialog = AIChatDialog(self.mw)
            self.dialog.message_sent.connect(self._handle_send_message)
            self.dialog.stop_generation_requested.connect(self._handle_stop_generation)
            self.dialog.cancel_queue_requested.connect(self._handle_cancel_queue)
            self.dialog.reset_context_requested.connect(self._handle_reset_context)
            self.dialog.retry_requested.connect(self._handle_retry_message)
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
                current_tab.input_edit.moveCursor(QTextCursor.MoveOperation.End)
        
        self.dialog.show()
        if self.dialog.isMinimized():
            self.dialog.showNormal()
        self.dialog.raise_()
        self.dialog.activateWindow()
        
        current_tab = self.dialog.tabs.currentWidget()
        if current_tab:
            current_tab.input_edit.setFocus()

    def _add_new_chat_session(self) -> None:
        """Internal helper to add new chat session."""
        if not self.dialog: return

        new_tab = self.dialog.add_new_tab()
        providers = self._get_available_providers()
        new_tab.populate_models(providers)
        
        tab_index = self.dialog.tabs.indexOf(new_tab)
        self.sessions[tab_index] = TranslationSessionManager()

    def _handle_tab_closed(self, index: int) -> None:
        """Internal helper to handle tab closed."""
        if index in self.sessions:
            del self.sessions[index]
            log_debug(f"AI Chat: Session for tab {index} has been removed.")
        if index in self._last_request_info:
            del self._last_request_info[index]
        self.sessions = {k - 1 if k > index else k: v for k, v in self.sessions.items()}
        self._last_request_info = {k - 1 if k > index else k: v for k, v in self._last_request_info.items()}
        self._message_queue = [item for item in self._message_queue if item.get('tab_index') != index]
        if self._active_tab_index == index:
            self._stop_status_timer()
            self._active_tab_index = None

    def _start_status_timer(self, tab_index: int) -> None:
        """Start the diagnostic status update timer for an active request."""
        self._active_tab_index = tab_index
        self._elapsed_seconds = 0
        if self._status_timer is None:
            from PyQt6.QtCore import QObject
            parent = self.dialog if isinstance(self.dialog, QObject) else None
            self._status_timer = QTimer(parent)
            self._status_timer.setInterval(1000)
            self._status_timer.timeout.connect(self._on_status_tick)
        self._status_timer.start()

    def _stop_status_timer(self) -> None:
        """Stop the diagnostic status update timer."""
        if self._status_timer and self._status_timer.isActive():
            self._status_timer.stop()
        self._elapsed_seconds = 0

    def _on_status_tick(self) -> None:
        """Handle 1-second ticks of the diagnostic status timer."""
        self._elapsed_seconds += 1
        if self.dialog and self._active_tab_index is not None:
            tab = self.dialog.tabs.widget(self._active_tab_index)
            if tab and hasattr(tab, 'set_status'):
                if self._is_thinking_placeholder_active.get(self._active_tab_index, False):
                    tab.set_status(f"{tr('Thinking...')} ({self._elapsed_seconds}s)")
                else:
                    chars = len(self._stream_buffer.get(self._active_tab_index, ""))
                    tab.set_status(f"{tr('Receiving response...')} ({self._elapsed_seconds}s, {chars} chars)")

    def _handle_send_message(self, tab_index: int, message: str, provider_key: str, web_search_enabled: bool) -> None:
        """Internal helper to handle send message."""
        if self._thread and self._thread.isRunning():
            # Immediately show user message with Queued badge
            if self.dialog:
                queue_badge = tr("In Queue")
                user_html = f"""
                <table class="message-table user-message">
                  <tr>
                    <td>
                      <div class='chat-prefix chat-prefix-user'>User <span class='chat-queue-badge'>{queue_badge}</span></div>
                      <div class='chat-content user-chat-content'>{html.escape(message)}</div>
                    </td>
                  </tr>
                </table>
                """
                self.dialog.append_to_history(tab_index, user_html)
                self.dialog.scroll_to_bottom(tab_index)

            self._message_queue.append({
                'tab_index': tab_index,
                'message': message,
                'provider_key': provider_key,
                'web_search_enabled': web_search_enabled,
                'user_rendered': True,
            })
            if self.dialog:
                q_count = len([m for m in self._message_queue if m.get('tab_index') == tab_index])
                self.dialog.set_tab_queue_count(tab_index, q_count)
            return

        self._start_chat_request(tab_index, message, provider_key, web_search_enabled, user_rendered=False)

    def _start_chat_request(self, tab_index: int, message: str, provider_key: str, web_search_enabled: bool, user_rendered: bool = False) -> None:
        """Prepare and start an AI chat worker thread."""
        if self.dialog:
            self.dialog.set_tab_generating(tab_index, True)
            if not user_rendered:
                user_html = f"""
                <table class="message-table user-message">
                  <tr>
                    <td>
                      <div class='chat-prefix chat-prefix-user'>User</div>
                      <div class='chat-content user-chat-content'>{html.escape(message)}</div>
                    </td>
                  </tr>
                </table>
                """
                self.dialog.append_to_history(tab_index, user_html)

        provider = self.mw.translation_handler._prepare_provider(provider_key)
        if not provider:
            error_html = f"""
            <table class="message-table ai-message">
              <tr>
                <td>
                  <div class='chat-prefix chat-prefix-ai' style='color:red;'>Error</div>
                  <div class='chat-content' style='color:red;'>{tr("Could not create AI provider '{key}'.").format(key=provider_key)}</div>
                </td>
              </tr>
            </table>
            """
            if self.dialog:
                self.dialog.append_to_history(tab_index, error_html)
                self.dialog.set_tab_generating(tab_index, False)
            self._process_next_queued_message()
            return

        session_manager = self.sessions.get(tab_index)
        if not session_manager:
            session_manager = TranslationSessionManager()
            self.sessions[tab_index] = session_manager
            log_debug(f"AI Chat: Re-created missing session for tab index {tab_index}.")

        use_stream = True
        if provider_key == 'gemini' and getattr(provider, 'settings', {}).get('base_url'):
            use_stream = False
            log_debug("AI Chat: Gemini with base_url detected, disabling streaming.")

        target_lang = getattr(self.mw, 'target_language', 'Ukrainian')
        if not isinstance(target_lang, str):
            target_lang = 'Ukrainian'
        resolved_system = resolve_target_language_prompt(self.system_prompt, target_lang)
        state = session_manager.ensure_session(
            provider_key=provider_key,
            base_system_prompt=resolved_system,
            full_system_prompt=resolved_system,
            supports_sessions=True,
            start_new_session=False,
            target_lang=target_lang,
        )
        
        content_end_pos_before = 0
        if self.dialog:
            if hasattr(self.dialog, 'get_tab_document_end_pos'):
                content_end_pos_before = self.dialog.get_tab_document_end_pos(tab_index)
            else:
                tab = self.dialog.tabs.widget(tab_index)
                if tab and hasattr(tab, 'history_view'):
                    content_end_pos_before = tab.history_view.document().characterCount() - 1

            self._is_thinking_placeholder_active[tab_index] = True
            self._auto_scroll[tab_index] = True
            thinking_text = tr("Searching web & thinking...") if web_search_enabled else tr("Thinking...")
            placeholder_html = f"""
            <table class="message-table ai-message">
              <tr>
                <td>
                  <div class='chat-prefix chat-prefix-ai'>AI</div>
                  <div class='chat-content ai-chat-content'><span class='chat-thinking'>{thinking_text}</span></div>
                </td>
              </tr>
            </table>
            """
            self.dialog.append_to_history(tab_index, placeholder_html)
            self.dialog.scroll_to_bottom(tab_index)

        self._start_status_timer(tab_index)
        if self.dialog:
            init_status = tr("Searching web & connecting...") if web_search_enabled else tr("Connecting to AI...")
            self.dialog.set_tab_status(tab_index, init_status)

        provider_settings = getattr(provider, 'settings', {})
        current_to = _extract_timeout(provider_settings, default=60.0)
        min_to = 180.0 if web_search_enabled else 120.0
        chat_timeout = max(current_to, min_to)

        self._last_request_info[tab_index] = {
            'message': message,
            'provider_key': provider_key,
            'web_search_enabled': web_search_enabled,
            'content_end_pos_before': content_end_pos_before,
        }
        if self.dialog:
            self.dialog.set_tab_can_retry(tab_index, True, last_message=message)

        task_details = {
            'type': 'chat_message_stream' if use_stream else 'chat_message',
            'tab_index': tab_index,
            'session_state': state,
            'session_user_message': message,
            'web_search_enabled': web_search_enabled,
            'content_end_pos_before': content_end_pos_before,
            'settings_override': {
                'timeout': chat_timeout,
            }
        }

        self._thread = QThread()
        self._worker = AIWorker(provider, None, task_details, self.mw)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        if use_stream:
            self._stream_buffer[tab_index] = ""
            self._worker.chunk_received.connect(self._on_ai_chunk_received)
            self._worker.success.connect(self._on_ai_stream_finished)
        else:
            self._worker.success.connect(self._on_ai_chat_success)
        
        self._worker.translation_cancelled.connect(self._on_ai_cancelled)
        self._worker.error.connect(self._on_ai_error)
        self._worker.finished.connect(self._cleanup_worker)

        self._thread.start()
    
    def _process_annotations(self, text: str, annotations: List[Dict[str, Any]]) -> str:
        """Internal helper to process annotations."""
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

            link = f'<a href="{html.escape(url)}" title="{html.escape(title)}">'
            modified_text = modified_text[:end] + '</a>' + modified_text[end:]
            modified_text = modified_text[:start] + link + modified_text[start:]
            
        return modified_text

    def _format_ai_response_for_display(self, text: str, annotations: Optional[List[Dict[str, Any]]]) -> str:
        """Internal helper to format the ai response for display."""
        # Clean multiple trailing newlines
        text = text.rstrip()
        
        # Ensure list items preceded by a text line have a blank line before them
        text = re.sub(r'([^\n])\n([ \t]*[*+-] |\d+\. )', r'\1\n\n\2', text)

        text_with_citations = self._process_annotations(text, annotations) if annotations else text

        html_output = markdown.markdown(text_with_citations, extensions=['nl2br', 'fenced_code', 'tables'])

        return html_output

    def _on_ai_chunk_received(self, context: Dict[str, Any], chunk: str) -> None:
        """Internal helper to handle the ai chunk received event."""
        tab_index = context.get('tab_index')
        if self.dialog and tab_index is not None:
            content_end_pos_before = context.get('content_end_pos_before', 0)
            # Remove thinking placeholder on first chunk arrival
            if self._is_thinking_placeholder_active.get(tab_index, False):
                self._is_thinking_placeholder_active[tab_index] = False
                self.dialog.remove_tab_text_after(tab_index, content_end_pos_before)
                self.dialog.scroll_to_bottom(tab_index)

            # If user manually scrolled up away from bottom, pause auto-scroll
            at_bottom = bool(self.dialog.is_tab_at_bottom(tab_index, threshold=40))
            self._auto_scroll[tab_index] = at_bottom

            auto_scroll = self._auto_scroll.get(tab_index, True)
            self.dialog.insert_tab_stream_chunk(tab_index, chunk, auto_scroll=auto_scroll)

            self._stream_buffer[tab_index] = self._stream_buffer.get(tab_index, "") + chunk

    def _on_ai_stream_finished(self, response: ProviderResponse, context: Dict[str, Any]) -> None:
        """Internal helper to handle the ai stream finished event."""
        self._stop_status_timer()
        tab_index = context.get('tab_index')
        if self.dialog and tab_index is not None:
            self.dialog.set_tab_generating(tab_index, False)
            self.dialog.set_tab_status(tab_index, "")

            full_response = self._stream_buffer.get(tab_index, "") or response.text or ""
            formatted_html = self._format_ai_response_for_display(full_response, response.annotations)
            
            content_end_pos_before = context.get('content_end_pos_before', 0)
            was_at_bottom = bool(self.dialog.is_tab_at_bottom(tab_index, threshold=60))
            self.dialog.remove_tab_text_after(tab_index, content_end_pos_before)

            final_html = f"""
            <table class="message-table ai-message">
              <tr>
                <td>
                  <div class='chat-prefix chat-prefix-ai'>AI</div>
                  <div class='chat-content ai-chat-content'>{formatted_html}</div>
                </td>
              </tr>
            </table>
            """
            self.dialog.append_to_history(tab_index, final_html)
            self._stream_buffer[tab_index] = ""
            self._is_thinking_placeholder_active[tab_index] = False

            if was_at_bottom:
                self.dialog.scroll_to_bottom(tab_index)
            else:
                self.dialog.scroll_to_response(tab_index, content_end_pos_before)

            state = context.get('session_state')
            user_content = context.get('session_user_message')
            if state and user_content:
                state.record_exchange(
                    user_content=user_content, 
                    assistant_content=response.text or full_response, 
                    conversation_id=response.conversation_id
                )

    def _on_ai_chat_success(self, response: ProviderResponse, context: Dict[str, Any]) -> None:
        """Internal helper to handle the ai chat success event."""
        self._stop_status_timer()
        tab_index: Optional[int] = context.get('tab_index')
        if self.dialog and tab_index is not None:
            self.dialog.set_tab_generating(tab_index, False)
            self.dialog.set_tab_status(tab_index, "")
            self.dialog.set_input_enabled(tab_index, True)
            ai_response_text = response.text or "[No response]"
            
            content_end_pos_before = context.get('content_end_pos_before', 0)
            self.dialog.remove_tab_text_after(tab_index, content_end_pos_before)

            formatted_html = self._format_ai_response_for_display(ai_response_text, response.annotations)
            html_msg = f"""
            <table class="message-table ai-message">
              <tr>
                <td>
                  <div class='chat-prefix chat-prefix-ai'>AI</div>
                  <div class='chat-content ai-chat-content'>{formatted_html}</div>
                </td>
              </tr>
            </table>
            """
            self.dialog.append_to_history(tab_index, html_msg)
            self.dialog.scroll_to_response(tab_index, content_end_pos_before)
            self._is_thinking_placeholder_active[tab_index] = False
            
            state = context.get('session_state')
            user_content = context.get('session_user_message')
            if state and user_content:
                state.record_exchange(user_content=user_content, assistant_content=ai_response_text, conversation_id=response.conversation_id)

    def _on_ai_error(self, message: str, context: Dict[str, Any]) -> None:
        """Internal helper to handle the ai error event."""
        self._stop_status_timer()
        tab_index = context.get('tab_index')
        if self.dialog and tab_index is not None:
            self.dialog.set_tab_generating(tab_index, False)
            self.dialog.set_tab_status(tab_index, f"{tr('Error')}: {message[:40]}")
            self.dialog.set_input_enabled(tab_index, True)

            content_end_pos_before = context.get('content_end_pos_before', 0)
            self.dialog.remove_tab_text_after(tab_index, content_end_pos_before)

            streamed_text = self._stream_buffer.get(tab_index, "").strip()
            if streamed_text:
                # Text was already received! Preserve it and show warning notice.
                formatted_html = self._format_ai_response_for_display(streamed_text, None)
                warning_title = tr("Stream Interrupted")
                warning_desc = tr("The response was interrupted ({err}). The partial text received before the interruption is preserved above.").format(err=html.escape(message))
                final_html = f"""
                <table class="message-table ai-message">
                  <tr>
                    <td>
                      <div class='chat-prefix chat-prefix-ai'>AI</div>
                      <div class='chat-content ai-chat-content'>{formatted_html}</div>
                      <div class='chat-interrupted-warning'>
                        <strong>⚠️ {warning_title}:</strong> {warning_desc}
                      </div>
                    </td>
                  </tr>
                </table>
                """
                self.dialog.append_to_history(tab_index, final_html)
                self.dialog.scroll_to_response(tab_index, content_end_pos_before)

                state = context.get('session_state')
                user_content = context.get('session_user_message')
                if state and user_content:
                    state.record_exchange(
                        user_content=user_content,
                        assistant_content=streamed_text,
                        conversation_id=None
                    )
            else:
                # No response text was received at all
                diagnosis = ""
                if "Read timed out" in message or "timeout" in message.lower():
                    diagnosis = f"<br/><small style='color:#888;'>{tr('Diagnosis: The request timed out waiting for the server to reply. If using a local proxy (e.g. localhost:8081), ensure it is running and not overloaded.')}</small>"
                elif "Connection refused" in message or "ConnectTimeout" in message:
                    diagnosis = f"<br/><small style='color:#888;'>{tr('Diagnosis: Could not connect to the server. Check if your AI service/proxy is started.')}</small>"

                retry_hint = f"<div style='margin-top: 8px; font-size: 11px; color: #ea580c; font-weight: bold;'>↻ {tr('Click Retry to try again.')}</div>"
                error_html = f"""
                <table class="message-table ai-message">
                  <tr>
                    <td>
                      <div class='chat-prefix chat-prefix-ai' style='color:red;'>Error</div>
                      <div class='chat-content' style='color:red;'>{html.escape(message)}{diagnosis}{retry_hint}</div>
                    </td>
                  </tr>
                </table>
                """
                self.dialog.append_to_history(tab_index, error_html)
                self.dialog.scroll_to_response(tab_index, content_end_pos_before)

            self._stream_buffer[tab_index] = ""
            self._is_thinking_placeholder_active[tab_index] = False
            if self.dialog:
                last_info = self._last_request_info.get(tab_index, {})
                last_msg = last_info.get('message', '')
                self.dialog.set_tab_can_retry(tab_index, True, last_message=last_msg)

    def _on_ai_cancelled(self) -> None:
        """Internal helper to handle cancellation (Stop generation)."""
        self._stop_status_timer()
        context = self._worker.task_details if self._worker else {}
        tab_index = context.get('tab_index')
        if self.dialog and tab_index is not None:
            self.dialog.set_tab_generating(tab_index, False)
            self.dialog.set_tab_status(tab_index, tr("Stopped"))
            self.dialog.set_input_enabled(tab_index, True)

            content_end_pos_before = context.get('content_end_pos_before', 0)
            self.dialog.remove_tab_text_after(tab_index, content_end_pos_before)

            streamed_text = self._stream_buffer.get(tab_index, "").strip()
            if streamed_text:
                formatted_html = self._format_ai_response_for_display(streamed_text, None)
                stopped_label = tr("Generation stopped by user.")
                final_html = f"""
                <table class="message-table ai-message">
                  <tr>
                    <td>
                      <div class='chat-prefix chat-prefix-ai'>AI</div>
                      <div class='chat-content ai-chat-content'>{formatted_html}</div>
                      <div class='chat-interrupted-warning' style='color:#666; border-left-color:#888; background:rgba(128,128,128,0.1);'>
                        ℹ️ {stopped_label}
                      </div>
                    </td>
                  </tr>
                </table>
                """
                self.dialog.append_to_history(tab_index, final_html)
                self.dialog.scroll_to_response(tab_index, content_end_pos_before)

                state = context.get('session_state')
                user_content = context.get('session_user_message')
                if state and user_content:
                    state.record_exchange(
                        user_content=user_content,
                        assistant_content=streamed_text,
                        conversation_id=None
                    )

            self._stream_buffer[tab_index] = ""
            self._is_thinking_placeholder_active[tab_index] = False

    def _handle_stop_generation(self, tab_index: int) -> None:
        """User clicked Stop button."""
        if self._worker:
            self._worker.cancel()

    def _handle_cancel_queue(self, tab_index: int) -> None:
        """User cancelled queue for this tab."""
        self._message_queue = [m for m in self._message_queue if m.get('tab_index') != tab_index]
        if self.dialog:
            self.dialog.set_tab_queue_count(tab_index, 0)

    def _handle_reset_context(self, tab_index: int) -> None:
        """Reset conversation session context for the specified tab."""
        session_manager = self.sessions.get(tab_index)
        if session_manager:
            session_manager.reset()

        if tab_index in self._last_request_info:
            del self._last_request_info[tab_index]

        if self.dialog:
            self.dialog.set_tab_can_retry(tab_index, False)
            reset_title = tr("Context Reset")
            reset_desc = tr("Previous messages will not be sent to the AI in subsequent requests.")
            reset_html = f"""
            <div class='chat-context-reset' style='margin: 14px 0; text-align: center;'>
              <hr style='border: 0; border-top: 1px dashed #888; margin-bottom: 8px;'/>
              <span style='color: #888; font-size: 11px; font-style: italic;'>
                🔄 <strong>{reset_title}:</strong> {reset_desc}
              </span>
              <hr style='border: 0; border-top: 1px dashed #888; margin-top: 8px;'/>
            </div>
            """
            self.dialog.append_to_history(tab_index, reset_html)
            self.dialog.scroll_to_bottom(tab_index)
            self.dialog.set_tab_status(tab_index, tr("Context reset"))

    def _handle_retry_message(self, tab_index: int) -> None:
        """User clicked Retry button to resend the last message."""
        last_info = self._last_request_info.get(tab_index)
        if not last_info:
            return

        message = last_info.get('message', '')
        if not message:
            return

        # Read current provider and web search selection from tab
        if self.dialog:
            tab = self.dialog.tabs.widget(tab_index)
            if hasattr(tab, 'model_combo') and hasattr(tab, 'web_search_checkbox'):
                provider_key = tab.model_combo.currentData() or last_info.get('provider_key')
                web_search_enabled = tab.web_search_checkbox.isChecked()
            else:
                provider_key = last_info.get('provider_key')
                web_search_enabled = last_info.get('web_search_enabled', False)
        else:
            provider_key = last_info.get('provider_key')
            web_search_enabled = last_info.get('web_search_enabled', False)

        content_end_pos_before = last_info.get('content_end_pos_before', 0)

        # Remove previous AI response or error message from chat view
        if self.dialog and content_end_pos_before > 0:
            self.dialog.remove_tab_text_after(tab_index, content_end_pos_before)

        # Clean session history if the last exchange was already recorded
        session_manager = self.sessions.get(tab_index)
        if session_manager:
            state = session_manager.get_state()
            if state and len(state.history) >= 2:
                last_user = state.history[-2]
                if last_user.get('content') == message:
                    state.history.pop()  # remove assistant
                    state.history.pop()  # remove user

        if self._thread and self._thread.isRunning():
            self._message_queue.append({
                'tab_index': tab_index,
                'message': message,
                'provider_key': provider_key,
                'web_search_enabled': web_search_enabled,
                'user_rendered': True,
            })
            if self.dialog:
                q_count = len([m for m in self._message_queue if m.get('tab_index') == tab_index])
                self.dialog.set_tab_queue_count(tab_index, q_count)
            return

        self._start_chat_request(
            tab_index,
            message,
            provider_key,
            web_search_enabled,
            user_rendered=True,
        )

    def _cleanup_worker(self) -> None:
        """Internal helper to cleanup worker and process next queued message."""
        self._stop_status_timer()
        tab_index = self._worker.task_details.get('tab_index') if self._worker else None
        if self.dialog and tab_index is not None:
            self.dialog.set_tab_generating(tab_index, False)
            self.dialog.set_input_enabled(tab_index, True)
            
        from utils.thread_utils import safe_shutdown_thread
        safe_shutdown_thread(self._thread, self._worker)
        self._thread = None
        self._worker = None
        self._process_next_queued_message()

    def _process_next_queued_message(self) -> None:
        """Start the next message waiting in the queue if no worker is running."""
        if self._thread and self._thread.isRunning():
            return
        if self._message_queue:
            next_task = self._message_queue.pop(0)
            tab_index = next_task['tab_index']
            if self.dialog:
                q_count = len([m for m in self._message_queue if m.get('tab_index') == tab_index])
                self.dialog.set_tab_queue_count(tab_index, q_count)
            self._start_chat_request(
                tab_index,
                next_task['message'],
                next_task['provider_key'],
                next_task['web_search_enabled'],
                user_rendered=next_task.get('user_rendered', False),
            )

    def prepare_to_close(self) -> None:
        """Prepare to close."""
        self._stop_status_timer()
        self._message_queue.clear()
        self._last_request_info.clear()
        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None
        from utils.thread_utils import safe_shutdown_thread
        safe_shutdown_thread(self._thread, self._worker)
        self._thread = None
        self._worker = None