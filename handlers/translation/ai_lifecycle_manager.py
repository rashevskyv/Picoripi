# handlers/translation/ai_lifecycle_manager.py
from typing import Dict, List, Optional, Tuple, Union, Any, Callable
from PyQt5.QtCore import QThread, QTimer, Qt
from PyQt5.QtWidgets import QMessageBox

from .base_translation_handler import BaseTranslationHandler
from .ai_worker import AIWorker
from core.translation.providers import (
    ProviderResponse,
    TranslationProviderError,
    create_translation_provider,
    BaseTranslationProvider,
    GeminiProvider,
)
from core.translation.config import build_default_translation_config
from utils.logging_utils import log_debug, log_warning, log_info

class AILifecycleManager(BaseTranslationHandler):
    def __init__(self, main_handler):
        super().__init__(main_handler)
        self.thread: Optional[QThread] = None
        self.worker: Optional[AIWorker] = None
        self.is_ai_running = False
        self._active_provider_key: Optional[str] = None
        self._active_model_name: Optional[str] = None
        self._provider_supports_sessions: bool = False
        
        # Callbacks for task types
        self._success_handlers: Dict[str, Callable] = {}
        self._error_handlers: Dict[str, Callable] = {}
        self._chunk_handlers: Dict[str, Callable] = {}
        
        # Retry context
        self._retry_context: Optional[dict] = None
        self._is_waiting_retry_delay = False

    def register_handler(self, task_type: str, success_cb: Callable, error_cb: Optional[Callable] = None, chunk_cb: Optional[Callable] = None):
        self._success_handlers[task_type] = success_cb
        if error_cb:
            self._error_handlers[task_type] = error_cb
        if chunk_cb:
            self._chunk_handlers[task_type] = chunk_cb

    def _prepare_provider(self, provider_key_override: Optional[str] = None):
        config = getattr(self.mw, 'translation_config', None) or build_default_translation_config()
        provider_key = provider_key_override if provider_key_override is not None else config.get('provider', 'disabled')
        
        if not provider_key or provider_key == 'disabled':
            QMessageBox.information(self.mw, "AI Translation", "The AI provider is disabled in the settings.")
            return None
        
        provider_settings = config.get('providers', {}).get(provider_key, {})
        if not provider_settings:
            QMessageBox.warning(self.mw, "AI Translation", f"No configuration found for provider '{provider_key}'.")
            return None

        try:
            provider = create_translation_provider(provider_key, provider_settings)
            
            if provider_key_override is None:
                self._active_provider_key = provider_key
                self._active_model_name = provider_settings.get('model') if isinstance(provider_settings, dict) else None
                self._provider_supports_sessions = bool(getattr(provider, 'supports_sessions', False))
                if not self._provider_supports_sessions:
                    self.main_handler._session_manager.reset()

            return provider
        except TranslationProviderError as exc:
            if provider_key_override is None:
                self._provider_supports_sessions = False
            QMessageBox.critical(self.mw, "AI Translation", str(exc))
            return None

    def run_ai_task(self, provider: BaseTranslationProvider, task_details: dict):
        self.is_ai_running = True
        self.main_handler.is_ai_running = True # Keep hub state in sync for now
        
        self.thread = QThread()
        self.main_handler.thread = self.thread # Keep hub state in sync

        task_details['dialog_steps'] = self.main_handler.ui_handler.status_dialog.steps
        self.worker = AIWorker(provider, self.main_handler.prompt_composer, task_details)
        self.main_handler.worker = self.worker # Keep hub state in sync
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.step_updated.connect(self.main_handler.ui_handler.update_ai_operation_step)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self._on_thread_finished)

        task_type = task_details.get('type')
        
        # Connect signals
        if task_type == 'translate_block_chunked':
            self.worker.total_chunks_calculated.connect(self.main_handler._setup_progress_bar)
            self.worker.chunk_translated.connect(self._on_chunk_translated)
            self.worker.translation_cancelled.connect(self._on_worker_cancelled)
            self.worker.progress_updated.connect(self.main_handler.ui_handler.status_dialog.update_progress)
        else:
            self.worker.success.connect(self._on_success)
            self.worker.translation_cancelled.connect(self._on_worker_cancelled)

        self.worker.error.connect(self._on_error)

        self.thread.start()

    def _on_thread_finished(self):
        log_debug("AILifecycleManager: Worker thread finished. Cleaning up.")
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        if self.thread:
            self.thread.deleteLater()
            self.thread = None
        
        self.is_ai_running = False
        self.main_handler.is_ai_running = False

        if self._retry_context and not self._is_waiting_retry_delay:
            log_debug("AILifecycleManager: A retry context was found. Initiating immediate retry.")
            self._perform_retry()

    def _on_success(self, response: ProviderResponse, context: dict):
        task_type = context.get('type')
        handler = self._success_handlers.get(task_type)
        if handler:
            handler(response, context)
        else:
            log_warning(f"AILifecycleManager: No success handler registered for task type '{task_type}'")

    def _on_chunk_translated(self, chunk_index: int, chunk_text: str, context: dict):
        task_type = context.get('type')
        handler = self._chunk_handlers.get(task_type)
        if handler:
            handler(chunk_index, chunk_text, context)
        else:
            # Fallback to main_handler if registered there (e.g. for block translation)
            if hasattr(self.main_handler, '_handle_chunk_translated'):
                self.main_handler._handle_chunk_translated(chunk_index, chunk_text, context)

    def _on_worker_cancelled(self):
        log_debug("AILifecycleManager: Worker has confirmed cancellation.")
        self.main_handler.reset_translation_session()
        self.main_handler.prompt_for_revert_after_cancel()

    def _on_error(self, error_message: str, context: dict):
        task_type = context.get('type')
        handler = self._error_handlers.get(task_type)
        if handler:
            handler(error_message, context)
        else:
            self._handle_task_error(error_message, context)

    def _handle_task_error(self, error_message: str, context: dict):
        attempt = context.get('attempt', 1)
        max_attempts = context.get('max_retries', 1)
        mode = context.get('mode_description', 'unknown')
        task_type = context.get('type', 'unknown')
        timeout_seconds = context.get('timeout_seconds')

        log_debug(
            f"AI Error (type={task_type}, attempt={attempt}/{max_attempts}, mode={mode}): {error_message}"
        )

        if task_type in ['fill_glossary', 'glossary_occurrence_update', 'glossary_occurrence_batch_update', 'glossary_notes_variation']:
            self.main_handler.ui_handler.finish_ai_operation()
            if task_type == 'fill_glossary':
                self.main_handler.glossary_handler._handle_ai_fill_error(error_message, context)
            elif task_type in ['glossary_occurrence_update', 'glossary_occurrence_batch_update']:
                self.main_handler.glossary_handler._handle_occurrence_ai_error(error_message, context.get('from_batch', False))
            elif task_type == 'glossary_notes_variation':
                self.main_handler.glossary_handler._set_notes_dialog_busy(context.get('dialog'), False)
                message = error_message or "AI request failed."
                QMessageBox.warning(self.mw, "AI Glossary Notes", message)
            return

        is_timeout = 'timed out' in error_message.lower()
        context['last_error'] = error_message
        next_attempt = attempt + 1
        context['attempt'] = next_attempt

        if next_attempt <= max_attempts:
            if task_type == 'translate_block_chunked' and not context.get('session_reset_attempted', False):
                provider = context.get('provider')
                if isinstance(provider, GeminiProvider):
                    log_debug("Block translation failed. Attempting Gemini session reset and retrying.")
                    provider.start_new_chat_session()
                    context['session_reset_attempted'] = True
                    context['attempt'] = 1
                    
                    block_idx = context.get('block_idx')
                    if block_idx is not None and block_idx in self.main_handler.translation_progress:
                        self.main_handler.translation_progress[block_idx]['session_reset_attempted'] = True
                    
                    self._retry_context = context
                    return

            if is_timeout:
                message = f"AI translation timed out after {timeout_seconds or '?'} seconds while processing {mode}.\n\nWould you like to wait longer and retry?"
                user_choice = QMessageBox.question(self.mw, "AI Translation Timeout", message, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if user_choice != QMessageBox.Yes:
                    log_debug("User chose not to retry after timeout.")
                    pass
                else:
                    log_debug("Retrying AI translation after user confirmation post-timeout.")
                    self._retry_context = context
                    self._is_waiting_retry_delay = False
                    QTimer.singleShot(0, self._on_retry_timer_timeout)
                    return
            else:
                log_debug(f"Showing debug retry dialog for AI task. Attempt {attempt}/{max_attempts}")
                
                msg_box = QMessageBox(self.mw)
                msg_box.setWindowTitle("AI Translation Error (Debug)")
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setText(f"An error occurred during AI operation (Attempt {attempt}/{max_attempts}).")
                
                info_text = f"<b>Mode:</b> {mode}<br><b>Error:</b> {error_message}"
                msg_box.setInformativeText(info_text)
                
                # If the error contains raw output (we'll add this to AIWorker later), show it in details
                raw_output = context.get('raw_response_text', "")
                if raw_output:
                    msg_box.setDetailedText(f"Raw AI Response:\n\n{raw_output}")
                
                retry_btn = msg_box.addButton("Retry (Wait 3s)", QMessageBox.AcceptRole)
                cancel_btn = msg_box.addButton("Stop/Cancel AI", QMessageBox.RejectRole)
                msg_box.setDefaultButton(retry_btn)
                
                # If we have a status dialog, make sure we handle window modality
                msg_box.exec_()
                
                if msg_box.clickedButton() == retry_btn:
                    log_debug("User clicked Retry in debug dialog.")
                    self._retry_context = context
                    self._is_waiting_retry_delay = True
                    
                    if hasattr(self.main_handler.ui_handler, 'status_dialog'):
                        dialog = self.main_handler.ui_handler.status_dialog
                        dialog.subtitle_label.setText(f"Waiting 3s before retry ({next_attempt}/{max_attempts})...")
                        dialog.subtitle_label.setStyleSheet("color: #d32f2f;")
                        dialog.subtitle_label.setVisible(True)
                    
                    QTimer.singleShot(3000, self._on_retry_timer_timeout)
                    return
                else:
                    log_debug("User clicked Cancel in debug dialog.")
                    # Fall through to the final failure handling below
                    pass

        self.main_handler.ui_handler.finish_ai_operation()
        failure_message = f"Operation failed after {max_attempts} attempts while processing {mode}.\n\nLast error: {error_message}"
        QMessageBox.critical(self.mw, "AI Operation Failed", failure_message)

    def _record_session_exchange(self, *, context: dict, assistant_content: str, response: Optional[ProviderResponse] = None) -> None:
        state = context.get('session_state') if isinstance(context, dict) else None
        user_content = context.get('session_user_message') if isinstance(context, dict) else None
        if not state or not isinstance(user_content, str):
            return
        conversation_id = response.conversation_id if isinstance(response, ProviderResponse) else None
        state.record_exchange(
            user_content=user_content,
            assistant_content=assistant_content or '',
            conversation_id=conversation_id,
        )

    def _clean_model_output(self, raw_output: Union[str, ProviderResponse]) -> str:
        text = raw_output.text if isinstance(raw_output, ProviderResponse) else str(raw_output or '')
        if not text:
            return ""
            
        # 1. Try to find content inside triple backticks first
        import re
        code_block_match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
        if code_block_match:
            return code_block_match.group(1).strip()
            
        # 2. If no code blocks, look for the first '{' and last '}'
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return text[first_brace:last_brace + 1].strip()
            
        return text.strip()
    def _trim_trailing_whitespace_from_lines(self, text: str) -> str:
        if not text:
            return ""
        lines = text.split("\n")
        return "\n".join(line.rstrip() for line in lines)

    def _on_retry_timer_timeout(self):
        log_debug("AILifecycleManager: Retry delay finished. Carrying out retry.")
        self._is_waiting_retry_delay = False
        
        # If the thread already finished while we were waiting, initiate retry now.
        # If it's somehow still finishing (unlikely), _on_thread_finished will catch it.
        if not self.is_ai_running and self._retry_context:
            self._perform_retry()

    def _perform_retry(self):
        if not self._retry_context:
            return
            
        retry_context = self._retry_context
        self._retry_context = None
        
        task_type = retry_context.get('type')
        log_info(f"AILifecycleManager: Initiating retry for task type '{task_type}'")
        
        # Reset visual error indicator in dialog
        if hasattr(self.main_handler.ui_handler, 'status_dialog'):
            dialog = self.main_handler.ui_handler.status_dialog
            dialog.subtitle_label.setText("") # Will be updated by task start
            dialog.subtitle_label.setStyleSheet("") # Reset to default
            dialog.subtitle_label.setVisible(False)

        if task_type in ['translate_preview', 'translate_block_chunked']:
            # We must use 0-delay timer because we are likely in a callback/signal handler context
            QTimer.singleShot(0, lambda: self.main_handler._initiate_batch_translation(retry_context))
        else:
            log_warning(f"A retry was requested for an unhandled task type: {task_type}")
            self.main_handler.ui_handler.finish_ai_operation()
            QMessageBox.critical(self.mw, "AI Operation Failed", f"Retry logic not implemented for task '{task_type}'.")

