# --- START OF FILE handlers/translation_handler.py ---
# handlers/translation/translation_handler.py

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from PyQt5.QtCore import QTimer, Qt, QPoint, QThread, pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QApplication
from .base_handler import BaseHandler
from core.glossary_manager import GlossaryEntry
from core.translation.config import build_default_translation_config
from core.translation.providers import (
    ProviderResponse,
    TranslationProviderError,
    create_translation_provider,
    BaseTranslationProvider,
    GeminiProvider,
)
from core.translation.session_manager import TranslationSessionManager
from .translation.glossary_handler import GlossaryHandler
from .translation.ai_prompt_composer import AIPromptComposer
from .translation.translation_ui_handler import TranslationUIHandler
from .translation.ai_lifecycle_manager import AILifecycleManager
from .translation.ai_worker import AIWorker
from components.prompt_editor_dialog import PromptEditorDialog
from utils.logging_utils import log_debug, log_warning
from utils.utils import convert_spaces_to_dots_for_display


class TranslationHandler(BaseHandler):
    _MAX_LOG_EXCERPT: int = 160

    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any):
        super().__init__(main_window, data_processor, ui_updater)
        self._cached_system_prompt: Optional[str] = None
        self._cached_glossary: Optional[str] = None
        self._session_manager = TranslationSessionManager()
        self._session_mode: str = 'auto'
        self._provider_supports_sessions: bool = False
        self._active_provider_key: Optional[str] = None
        self.thread: Optional[QThread] = None
        self.worker: Optional[AIWorker] = None
        self.is_ai_running = False
        self.translation_progress: Dict[int, Dict[str, Union[set, int]]] = {}
        self.pre_translation_state: Dict[int, List[str]] = {}

        self.glossary_handler = GlossaryHandler(self)
        self.prompt_composer = AIPromptComposer(self)
        self.ui_handler = TranslationUIHandler(self)
        self.ai_lifecycle_manager = AILifecycleManager(self)

        # Register AI success/error handlers
        self.ai_lifecycle_manager.register_handler('translate_preview', self._handle_preview_translation_success)
        self.ai_lifecycle_manager.register_handler('translate_single', self._handle_single_translation_success)
        self.ai_lifecycle_manager.register_handler('generate_variation', self._handle_variation_success)
        self.ai_lifecycle_manager.register_handler('fill_glossary', self.glossary_handler._handle_ai_fill_success)
        self.ai_lifecycle_manager.register_handler('glossary_occurrence_update', self.glossary_handler._handle_glossary_occurrence_update_success)
        self.ai_lifecycle_manager.register_handler('glossary_occurrence_batch_update', self.glossary_handler._handle_glossary_occurrence_batch_success)
        self.ai_lifecycle_manager.register_handler('glossary_notes_variation', self.glossary_handler._handle_glossary_notes_variation_success)
        
        # Block translation has a chunk handler
        self.ai_lifecycle_manager.register_handler('translate_block_chunked', 
                                                   self._handle_block_translation_success,
                                                   chunk_cb=self._handle_chunk_translated)

        self._glossary_manager = self.glossary_handler.glossary_manager
        
        self.start_new_session = True
        log_debug(f"TranslationHandler.__init__: start_new_session initialized to {self.start_new_session}")

        QTimer.singleShot(0, self.glossary_handler.install_menu_actions)
    
    def initialize_glossary_highlighting(self) -> None:
        self.glossary_handler.initialize_glossary_highlighting()

    def show_glossary_dialog(self, initial_term: Optional[str] = None) -> None:
        self.glossary_handler.show_glossary_dialog(initial_term)

    def get_glossary_entry(self, term: str) -> Optional[GlossaryEntry]:
        return self.glossary_handler.glossary_manager.get_entry(term)

    def add_glossary_entry(self, term: str, context: Optional[str] = None, translation: str = "") -> None:
        self.glossary_handler.add_glossary_entry(term, context, translation)

    def edit_glossary_entry(self, term: str, translation: str = "") -> None:
        self.glossary_handler.edit_glossary_entry(term, translation=translation)

    def append_selection_to_glossary(self) -> None:
        preview_edit = self.mw.preview_text_edit
        selected_lines = preview_edit.get_selected_lines()
        if not selected_lines:
            QMessageBox.information(self.mw, "Glossary", "No lines selected in the preview.")
            return

        start_line = min(selected_lines)
        end_line = max(selected_lines)
        
        block_idx = self.mw.data_store.current_block_idx
        if block_idx == -1:
            return

        selected_lines = []
        for i in range(start_line, end_line + 1):
            line_text = self.glossary_handler._get_original_string(block_idx, i)
            if line_text is not None:
                selected_lines.append(line_text)
        
        if not selected_lines:
            return

        term_to_add = "\n".join(selected_lines)
        self.add_glossary_entry(term_to_add)


    def _prepare_provider(self, provider_key_override: Optional[str] = None) -> Optional[BaseTranslationProvider]:
        return self.ai_lifecycle_manager._prepare_provider(provider_key_override)

    def reset_translation_session(self) -> None:
        self._session_manager.reset()
        self._cached_system_prompt = None
        self._cached_glossary = None
        self.start_new_session = True
        log_debug(f"TranslationHandler.reset_translation_session: Manual reset. start_new_session set to {self.start_new_session}")

        config = getattr(self.mw, 'translation_config', None)
        if config and config.get('provider') == 'gemini':
            provider_settings = config.get('providers', {}).get('gemini', {})
            if provider_settings:
                try:
                    provider = GeminiProvider(provider_settings)
                    provider.start_new_chat_session()
                except Exception as e:
                    log_debug(f"Could not start new chat session on reset: {e}")

        if self.mw.statusBar:
            self.mw.statusBar.showMessage("AI session reset.", 4000)

    
    def _maybe_edit_prompt(
        self,
        *,
        title: str,
        system_prompt: str,
        user_prompt: str,
        save_section: Optional[str] = None,
        save_field: str = 'system_prompt',
    ) -> Optional[Tuple[str, str]]:
        is_ctrl_pressed = bool(QApplication.keyboardModifiers() & Qt.ControlModifier)
        enabled = getattr(self.mw, 'prompt_editor_enabled', True)
        if not is_ctrl_pressed and not enabled:
            return system_prompt, user_prompt

        allow_save = bool(save_section and self.glossary_handler._current_prompts_path)
        dialog = PromptEditorDialog(
            parent=self.mw,
            title=title,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            allow_save=allow_save,
        )
        if dialog.exec_() != dialog.Accepted:
            return None

        edited_system, edited_user, save_requested = dialog.get_user_inputs()
        edited_system = edited_system.rstrip()
        edited_user = edited_user.rstrip()

        if save_requested and allow_save and save_section:
            if self.glossary_handler.save_prompt_section(save_section, save_field, edited_system):
                if save_section == 'translation' and save_field == 'system_prompt':
                    self._cached_system_prompt = edited_system
        return edited_system, edited_user


    def _should_use_session(self, task_type: str) -> bool:
        if not self._provider_supports_sessions:
            return False
        return True

    def _prepare_session_for_request(self, *, base_system_prompt: str, full_system_prompt: str, user_prompt: str, task_type: str) -> Optional[dict]:
        log_debug(f"Preparing session, start_new_session is {self.start_new_session}")
        if not self._should_use_session(task_type):
            return None
        state = self._session_manager.ensure_session(
            provider_key=self._active_provider_key or '',
            base_system_prompt=base_system_prompt,
            full_system_prompt=full_system_prompt,
            supports_sessions=self._provider_supports_sessions,
            start_new_session=self.start_new_session,
        )
        if not state:
            return None
        
        self.start_new_session = False
        log_debug(f"Session established. start_new_session set to {self.start_new_session}")
        
        return {
            'state': state,
            'user_message': {'role': 'user', 'content': user_prompt},
        }

    def _attach_session_to_task(self, task_details: dict, *, base_system_prompt: str, full_system_prompt: str, user_prompt: str, task_type: str) -> bool:
        session_info = self._prepare_session_for_request(
            base_system_prompt=base_system_prompt,
            full_system_prompt=full_system_prompt,
            user_prompt=user_prompt,
            task_type=task_type,
        )
        if not session_info:
            return False
        task_details['session'] = session_info
        task_details['session_state'] = session_info['state']
        task_details['session_user_message'] = session_info['user_message']['content']
        return True

    def _set_notes_dialog_busy(self, dialog_obj, busy: bool) -> None:
        if not dialog_obj:
            return
        if hasattr(dialog_obj, 'set_ai_busy'):
            dialog_obj.set_ai_busy(busy)
        elif hasattr(dialog_obj, 'set_notes_variation_busy'):
            dialog_obj.set_notes_variation_busy(busy)

    def _run_ai_task(self, provider: BaseTranslationProvider, task_details: Dict[str, Any]) -> None:
        self.ai_lifecycle_manager.run_ai_task(provider, task_details)

    def _handle_ai_cancel(self, context: Dict[str, Any]) -> None:
        self.ai_lifecycle_manager._handle_ai_cancel(context)

    def prompt_for_revert_after_cancel(self) -> None:
        if not self.worker:
            self.ui_handler.finish_ai_operation()
            return

        block_idx = self.worker.task_details.get('block_idx')
        if block_idx is None or block_idx not in self.pre_translation_state:
            self.ui_handler.finish_ai_operation()
            return

        reply = QMessageBox.question(
            self.mw,
            "Translation Cancelled",
            "Keep the already translated parts?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.No:
            if block_idx in self.pre_translation_state:
                original_texts = self.pre_translation_state[block_idx]
                for i, text in enumerate(original_texts):
                    self.data_processor.update_edited_data(block_idx, i, text)
                
                del self.pre_translation_state[block_idx]

            if block_idx in self.translation_progress:
                del self.translation_progress[block_idx]

            self.ui_updater.populate_strings_for_block(block_idx, getattr(self.mw, 'current_category_name', None))
            self.ui_updater.update_text_views()
        else:
            if block_idx in self.pre_translation_state:
                del self.pre_translation_state[block_idx]
        
        self.ui_handler.finish_ai_operation()
        self.ui_updater.update_block_item_text_with_problem_count(block_idx)


    def _setup_progress_bar(self, total_chunks: int, completed_chunks: int) -> None:
        block_idx = self.worker.task_details.get('block_idx')
        if block_idx is not None and block_idx in self.translation_progress:
            self.translation_progress[block_idx]['total_chunks'] = total_chunks
        
        self.translated_chunks_count = completed_chunks
        self.ui_handler.status_dialog.setup_progress_bar(total_chunks, completed_chunks)

    def translate_current_string(self) -> None:
        if self.is_ai_running:
            QMessageBox.information(self.mw, "AI Busy", "An AI task is already running. Please wait for it to complete.")
            return
        if self.mw.data_store.current_block_idx == -1 or self.mw.data_store.current_string_idx == -1: return
        self._translate_and_apply(
            source_text=str(self.glossary_handler._get_original_string(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)),
            expected_lines=len(str(self.glossary_handler._get_original_string(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)).split("\n")),
            mode_description="current row",
            block_idx=self.mw.data_store.current_block_idx,
            string_idx=self.mw.data_store.current_string_idx
        )

    def translate_preview_selection(self, context_menu_pos: QPoint) -> None:
        if self.is_ai_running:
            QMessageBox.information(self.mw, "AI Busy", "An AI task is already running. Please wait for it to complete.")
            return
        block_idx = self.mw.data_store.current_block_idx
        if block_idx == -1: return

        preview_edit = self.mw.preview_text_edit
        selected_lines = preview_edit.get_selected_lines()
        if selected_lines:
            start_line = min(selected_lines)
            end_line = max(selected_lines)
        else:
            cursor = preview_edit.cursorForPosition(context_menu_pos)
            if cursor.blockNumber() < 0:
                return
            start_line = end_line = cursor.blockNumber()

        if start_line is None: return

        string_indices = list(range(start_line, end_line + 1))
        source_items = [{"id": idx, "text": str(self.glossary_handler._get_original_string(block_idx, idx))} for idx in string_indices]

        provider = self.ai_lifecycle_manager._prepare_provider()
        if not provider: return

        operation_title = f"AI Translation (Lines {start_line + 1}-{end_line + 1})" if start_line != end_line else f"AI Translation (Line {start_line + 1})"
        
        system_prompt, _ = self.glossary_handler.load_prompts()
        if not system_prompt:
            return

        session_state = self._session_manager.get_state()
        composer_args = {
            'system_prompt': system_prompt,
            'source_items': source_items,
            'all_source_items': source_items,
            'block_idx': block_idx,
            'mode_description': f"lines {start_line + 1}-{end_line + 1}",
            'session_state': session_state,
        }
        
        preview_system, preview_user, p_map = self.prompt_composer.compose_batch_request(**composer_args)

        edited = self._maybe_edit_prompt(
            title=operation_title,
            system_prompt=preview_system,
            user_prompt=preview_user,
            save_section='translation'
        )

        if edited is None:
            return
        edited_system, edited_user = edited

        self.ui_handler.start_ai_operation(operation_title, model_name=self.ai_lifecycle_manager._active_model_name)

        task_details = {
            'type': 'translate_preview',
            'provider': provider,
            'source_items': source_items,
            'attempt': 1,
            'max_retries': 4,
            'block_idx': block_idx,
            'mode_description': f"lines {start_line + 1}-{end_line + 1}",
            'timeout_seconds': self._resolve_base_timeout(provider),
            'precomposed_prompt': [
                {"role": "system", "content": edited_system},
                {"role": "user", "content": edited_user}
            ],
            'placeholder_map': p_map,
        }
        self._initiate_batch_translation(task_details)

    def translate_current_block(self, block_idx: Optional[int] = None, category_name: Optional[str] = None) -> None:
        if self.is_ai_running:
            QMessageBox.information(self.mw, "AI Busy", "An AI task is already running. Please wait for it to complete.")
            return
        target_block_idx = self.mw.data_store.current_block_idx if block_idx is None else block_idx
        if target_block_idx is None or target_block_idx == -1:
            QMessageBox.information(self.mw, "AI Translation", "Select a block to translate.")
            return
        
        self.start_new_session = True
        log_debug(f"TranslationHandler.translate_current_block: Block translation initiated. start_new_session set to {self.start_new_session}")

        operation_title = f"AI Translation (Block {target_block_idx + 1})"
        if category_name:
            operation_title = f"AI Translation ({category_name} in Block {target_block_idx + 1})"

        self.ui_handler.start_ai_operation(operation_title, is_chunked=True, model_name=self.ai_lifecycle_manager._active_model_name)
        from components.ai_status_dialog import AIStatusDialog
        self.ui_handler.update_ai_operation_step(0, "Preparing data...", AIStatusDialog.STATUS_IN_PROGRESS)
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()

        data_source = getattr(self.mw, 'data', None)
        if not isinstance(data_source, list) or not (0 <= target_block_idx < len(data_source)):
            self.ui_handler.finish_ai_operation()
            QMessageBox.information(self.mw, "AI Translation", "No block data available to translate.")
            return

        block_strings = self.glossary_handler._get_original_block(target_block_idx)
        if not block_strings:
            self.ui_handler.finish_ai_operation()
            QMessageBox.information(self.mw, "AI Translation", "The selected block is empty.")
            return

        # Determine target indices
        target_indices = range(len(block_strings))
        if category_name and hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
            pm = self.mw.project_manager
            block_map = getattr(self.mw, 'block_to_project_file_map', {})
            proj_b_idx = block_map.get(target_block_idx, target_block_idx)
            if proj_b_idx < len(pm.project.blocks):
                block = pm.project.blocks[proj_b_idx]
                category = next((c for c in block.get_all_categories_flat() if c.name == category_name), None)
                if category:
                    target_indices = category.line_indices
                    log_debug(f"Translating only category '{category_name}' ({len(target_indices)} lines)")

        self.pre_translation_state[target_block_idx] = self.data_processor.get_block_texts(target_block_idx)

        source_items = [
            {"id": idx, "text": str(self.glossary_handler._get_original_string(target_block_idx, idx) or "")}
            for idx in target_indices if idx < len(block_strings)
        ]

        provider = self.ai_lifecycle_manager._prepare_provider()
        if not provider:
            self.ui_handler.finish_ai_operation()
            return

        base_timeout = self._resolve_base_timeout(provider)
        block_timeout = base_timeout * 10
        log_debug(
            f"Starting block AI translation for block {target_block_idx} with timeout {block_timeout}s (base {base_timeout}s); lines={len(source_items)}"
        )

        task_details = {
            'type': 'translate_block_chunked',
            'provider': provider,
            'source_items': source_items,
            'attempt': 1,
            'max_retries': 4,
            'block_idx': target_block_idx,
            'mode_description': f"block {target_block_idx + 1}" if not category_name else f"category '{category_name}' in block {target_block_idx + 1}",
            'provider_settings_override': {'timeout': block_timeout},
            'timeout_seconds': block_timeout,
            'session_reset_attempted': False
        }
        self._initiate_batch_translation(task_details)

    def resume_block_translation(self, block_idx: int) -> None:
        if block_idx not in self.translation_progress:
            QMessageBox.information(self.mw, "Resume Translation", "No active translation session found for this block.")
            return

        progress_entry = self.translation_progress.get(block_idx, {})

        if block_idx not in self.pre_translation_state:
            self.pre_translation_state[block_idx] = self.data_processor.get_block_texts(block_idx)

        target_block_idx = block_idx
        progress_entry = self.translation_progress.get(block_idx, {})
        source_items = progress_entry.get('source_items', [])
        
        if not source_items:
            # Fallback if somehow missing
            block_strings = self.glossary_handler._get_original_block(target_block_idx)
            source_items = [
                {"id": idx, "text": str(self.glossary_handler._get_original_string(target_block_idx, idx) or "")}
                for idx in range(len(block_strings))
            ]

        provider = self.ai_lifecycle_manager._prepare_provider()
        if not provider:
            return

        base_timeout = self._resolve_base_timeout(provider)
        block_timeout = base_timeout * 10

        operation_title = f"Resuming Translation (Block {target_block_idx + 1})"
        self.ui_handler.start_ai_operation(operation_title, is_chunked=True, model_name=self.ai_lifecycle_manager._active_model_name)

        task_details = {
            'type': 'translate_block_chunked',
            'provider': provider,
            'source_items': source_items,
            'attempt': 1,
            'max_retries': 4,
            'block_idx': target_block_idx,
            'mode_description': f"block {target_block_idx + 1}",
            'provider_settings_override': {'timeout': block_timeout},
            'timeout_seconds': block_timeout,
            'is_resume': True,
            'session_reset_attempted': progress_entry.get('session_reset_attempted', False)
        }
        if progress_entry.get('custom_user_header'):
            task_details['custom_user_header'] = progress_entry.get('custom_user_header')
            task_details['custom_user_label'] = progress_entry.get('custom_user_label')
        if progress_entry.get('system_prompt_override'):
            task_details['system_prompt_override'] = progress_entry.get('system_prompt_override')
        self._initiate_batch_translation(task_details)

    def _on_chunk_timer_timeout(self) -> None:
        pass # This method was likely intended to be implemented or removed.

    def _resolve_base_timeout(self, provider: BaseTranslationProvider) -> int:
        try:
            base = int(provider.settings.get('timeout', 120))
        except (TypeError, ValueError):
            base = 120
        return max(base, 30)


    def _initiate_batch_translation(self, context: Dict[str, Any]) -> None:
        self.translated_chunks_count = 0
        provider = context['provider']
        
        block_idx = context.get('block_idx')
        task_type = context.get('type')

        if task_type == 'translate_block_chunked' and block_idx is not None:
            if not context.get('is_resume', False):
                self.reset_translation_session()
                self.translation_progress[block_idx] = {'completed_chunks': set(), 'total_chunks': 0}
            
            context['chunks_to_skip'] = self.translation_progress.get(block_idx, {}).get('completed_chunks', set())

        system_prompt, _ = self.glossary_handler.load_prompts()
        if not system_prompt:
            self.ui_handler.finish_ai_operation()
            return

        if context.get('system_prompt_override'):
            system_prompt = context['system_prompt_override']

        session_state = self._session_manager.get_state()
        composer_args = {
            'system_prompt': system_prompt,
            'source_items': context['source_items'],
            'all_source_items': context['source_items'],
            'block_idx': context['block_idx'],
            'mode_description': context['mode_description'], 'is_retry': (context['attempt'] > 1),
            'retry_reason': context.get('last_error', ''),
            'session_state': session_state,
        }
        context['composer_args'] = composer_args

        if 'precomposed_prompt' not in context:
            force_prompt = bool(QApplication.keyboardModifiers() & Qt.ControlModifier)
            should_edit_prompt = (
                task_type == 'translate_block_chunked'
                and block_idx is not None
                and (force_prompt or not context.get('is_resume', False))
            )
            if should_edit_prompt:
                preview_system, preview_user, _ = self.prompt_composer.compose_batch_request(**composer_args)
                edited = self._maybe_edit_prompt(
                    title="AI Block Translation Prompt",
                    system_prompt=preview_system,
                    user_prompt=preview_user,
                    save_section='translation',
                )
                if edited is None:
                    self.ui_handler.finish_ai_operation()
                    if block_idx is not None and not context.get('is_resume', False):
                        self.translation_progress.pop(block_idx, None)
                        self.pre_translation_state.pop(block_idx, None)
                    return
                edited_system, edited_user = edited
                context['composer_args']['system_prompt'] = edited_system
                header, sep, json_section = edited_user.partition('JSON DATA TO PROCESS:')
                if sep:
                    context['custom_user_header'] = header
                    context['custom_user_label'] = sep
                else:
                    context['custom_user_header'] = edited_user
                    context['custom_user_label'] = 'JSON DATA TO PROCESS:'
                context['system_prompt_override'] = edited_system
                if block_idx is not None:
                    progress_entry = self.translation_progress.setdefault(block_idx, {'completed_chunks': set(), 'total_chunks': 0})
                    progress_entry['custom_user_header'] = context['custom_user_header']
                    progress_entry['custom_user_label'] = context['custom_user_label']
                    progress_entry['system_prompt_override'] = edited_system
        
        final_system_prompt = context['composer_args']['system_prompt']
        context['composer_args']['all_source_items'] = context['source_items']
        final_user_prompt, _, p_map = self.prompt_composer.compose_batch_request(**context['composer_args'])
        context['placeholder_map'] = p_map 

        if not self._attach_session_to_task(
            context,
            base_system_prompt=system_prompt,
            full_system_prompt=final_system_prompt,
            user_prompt=final_user_prompt,
            task_type=task_type,
        ):
             if 'precomposed_prompt' not in context:
                context['precomposed_prompt'] = [
                    {"role": "system", "content": final_system_prompt},
                    {"role": "user", "content": final_user_prompt}
                ]
        
        self._run_ai_task(provider, context)

    def _handle_chunk_translated(self, chunk_index: int, chunk_text: str, context: Dict[str, Any]) -> None:
        log_debug(f"Received translated chunk {chunk_index}. Raw AI response:\n{chunk_text}")
        try:
            block_idx = context['block_idx']
            parsed_json = json.loads(chunk_text)
            translated_strings = parsed_json.get("translated_strings")
            if hasattr(self.mw, 'undo_manager'):
                self.mw.undo_manager.begin_group()

            for item in translated_strings:
                string_idx, translated_text = item["id"], item["translation"]
                final_text = self.ai_lifecycle_manager._trim_trailing_whitespace_from_lines(translated_text)
                self.data_processor.update_edited_data(block_idx, string_idx, final_text, action_type="TRANSLATE")
            
            if hasattr(self.mw, 'undo_manager'):
                self.mw.undo_manager.end_group("TRANSLATE")
            
            if block_idx in self.translation_progress:
                self.translation_progress[block_idx]['completed_chunks'].add(chunk_index)

            self.ui_updater.populate_strings_for_block(block_idx, getattr(self.mw, 'current_category_name', None), force=True)
            self.translated_chunks_count = len(self.translation_progress.get(block_idx, {}).get('completed_chunks', set()))
            self.ui_handler.status_dialog.update_progress(self.translated_chunks_count)
            
            total_chunks = self.translation_progress.get(block_idx, {}).get('total_chunks', -1)
            if total_chunks != -1 and self.translated_chunks_count == total_chunks:
                self.ui_handler.finish_ai_operation()
                self.ui_updater.update_text_views()
                if hasattr(self.mw, 'app_action_handler'):
                    self.mw.issue_scan_handler.rescan_issues_for_single_block(block_idx, show_message_on_completion=False)
                
                if block_idx in self.translation_progress:
                    del self.translation_progress[block_idx]
                if block_idx in self.pre_translation_state:
                    del self.pre_translation_state[block_idx]
                
                # Removed self.reset_translation_session() to allow user to inspect context if needed

        except (json.JSONDecodeError, ValueError) as e:
            self._handle_ai_error(f"Failed to process chunk {chunk_index + 1}: {e}", context)

    def _handle_preview_translation_success(self, response: ProviderResponse, context: Dict[str, Any]) -> None:
        self.ui_handler.update_ai_operation_step(3, self.ui_handler.status_dialog.steps[3], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        cleaned_text = self.ai_lifecycle_manager._clean_model_output(response)
        
        try:
            parsed_json = json.loads(cleaned_text)
            translated_strings = parsed_json.get("translated_strings")
            if not isinstance(translated_strings, list) or len(translated_strings) != len(context['source_items']):
                raise ValueError("Invalid response structure or item count mismatch.")

            if hasattr(self.mw, 'undo_manager'):
                self.mw.undo_manager.begin_group()
                
            self.ui_handler.update_ai_operation_step(4, self.ui_handler.status_dialog.steps[4], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
            for item in translated_strings:
                string_idx, translated_text = item["id"], item["translation"]
                final_text = self.ai_lifecycle_manager._trim_trailing_whitespace_from_lines(translated_text)
                self.data_processor.update_edited_data(context['block_idx'], string_idx, final_text, action_type="TRANSLATE")

            if hasattr(self.mw, 'undo_manager'):
                self.mw.undo_manager.end_group("TRANSLATE")

            self.ai_lifecycle_manager._record_session_exchange(context=context, assistant_content=cleaned_text, response=response)
            self.ui_handler.finish_ai_operation()
            self.ui_updater.populate_strings_for_block(context['block_idx'], getattr(self.mw, 'current_category_name', None), force=True)
            self.ui_updater.update_text_views()
            if hasattr(self.mw, 'app_action_handler'):
                self.mw.issue_scan_handler.rescan_issues_for_single_block(context['block_idx'], show_message_on_completion=False)

        except (json.JSONDecodeError, ValueError) as e:
            self._handle_ai_error(f"Validation failed: {e}", context)

    def _handle_ai_error(self, error_msg: str, context: Dict[str, Any]) -> None:
        self.ai_lifecycle_manager._handle_ai_error(error_msg, context)

    def _handle_single_translation_success(self, response: ProviderResponse, context: Dict[str, Any]) -> None:
        self.ui_handler.update_ai_operation_step(3, self.ui_handler.status_dialog.steps[3], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        cleaned_translation = self.ai_lifecycle_manager._clean_model_output(response)
        trimmed_translation = self.ai_lifecycle_manager._trim_trailing_whitespace_from_lines(cleaned_translation)
        self.ai_lifecycle_manager._record_session_exchange(context=context, assistant_content=cleaned_translation, response=response)
        
        self.ui_handler.update_ai_operation_step(4, self.ui_handler.status_dialog.steps[4], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        self.ui_handler.apply_full_translation(trimmed_translation)
        self.ui_handler.finish_ai_operation()
        self.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx, getattr(self.mw, 'current_category_name', None), force=True)

    def _on_task_finished(self, context: Dict[str, Any]) -> None:
        self.ai_lifecycle_manager.on_task_finished(context)

    def _handle_variation_success(self, response: ProviderResponse, context: Dict[str, Any]) -> None:
        self.ui_handler.update_ai_operation_step(3, self.ui_handler.status_dialog.steps[3], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        cleaned = self.ai_lifecycle_manager._clean_model_output(response)
        self.ai_lifecycle_manager._record_session_exchange(context=context, assistant_content=cleaned, response=response)
        variants_raw = self.ui_handler.parse_variation_payload(cleaned)
        self.ui_handler.finish_ai_operation()

        if not variants_raw:
            QMessageBox.information(self.mw, "AI Variation", "Failed to parse variations from AI response.")
            return
            
        trimmed = [self.ai_lifecycle_manager._trim_trailing_whitespace_from_lines(v) for v in variants_raw]
        
        chosen = self.ui_handler.show_variations_dialog(trimmed)
        if chosen:
            if context.get('is_inline', False):
                self.ui_handler.apply_inline_variation(chosen)
            else:
                self.ui_handler.apply_full_translation(chosen)


    def generate_variation_for_current_string(self) -> None:
        if self.is_ai_running:
            QMessageBox.information(self.mw, "AI Busy", "An AI task is already running. Please wait for it to complete.")
            return
        if self.mw.data_store.current_block_idx == -1 or self.mw.data_store.current_string_idx == -1: return
        original_text = str(self.glossary_handler._get_original_string(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx))
        current_translation, _ = self.data_processor.get_current_string_text(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)
        if not current_translation:
            QMessageBox.information(self.mw, "AI Variation", "There is no current translation to vary.")
            return
        
        provider = self.ai_lifecycle_manager._prepare_provider()
        if not provider: return

        system_prompt, _ = self.glossary_handler.load_prompts()
        if not system_prompt:
            self.ui_handler.finish_ai_operation()
            return
        
        session_state = self._session_manager.get_state()
        composer_args = {
            'system_prompt': system_prompt,
            'source_text': original_text,
            'block_idx': self.mw.data_store.current_block_idx, 'string_idx': self.mw.data_store.current_string_idx,
            'expected_lines': len(original_text.split('\n')), 'current_translation': str(current_translation),
            'request_type': 'variation_list',
            'session_state': session_state,
        }
        combined_system, user_prompt = self.prompt_composer.compose_variation_request(**composer_args)
        edited = self._maybe_edit_prompt(
            title="AI Variation Prompt",
            system_prompt=combined_system,
            user_prompt=user_prompt,
            save_section='translation',
        )
        if edited is None:
            return
        edited_system, edited_user = edited

        self.ui_handler.start_ai_operation("AI Variation", model_name=self.ai_lifecycle_manager._active_model_name)

        precomposed = [
            {"role": "system", "content": edited_system},
            {"role": "user", "content": edited_user},
        ]
        task_details = {
            'type': 'generate_variation',
            'is_inline': False,
            'composer_args': composer_args,
            'provider_settings_override': {'temperature': 0.7},
            'attempt': 1,
            'max_retries': 1,
        }
        if not self._attach_session_to_task(
            task_details,
            base_system_prompt=system_prompt,
            full_system_prompt=edited_system,
            user_prompt=edited_user,
            task_type='generate_variation',
        ):
            task_details['precomposed_prompt'] = precomposed
        
        self._run_ai_task(provider, task_details)

    def _translate_and_apply(self, *, source_text: str, expected_lines: int, mode_description: str, block_idx: int, string_idx: int) -> None:
        provider = self.ai_lifecycle_manager._prepare_provider()
        if not provider: return

        system_prompt, _ = self.glossary_handler.load_prompts()
        if not system_prompt:
            return

        session_state = self._session_manager.get_state()
        composer_args = {
            'system_prompt': system_prompt,
            'source_text': source_text,
            'block_idx': block_idx, 'string_idx': string_idx, 'expected_lines': expected_lines,
            'current_translation': None, 'request_type': 'translation',
            'session_state': session_state,
        }
        combined_system, user_prompt = self.prompt_composer.compose_variation_request(**composer_args)
        edited = self._maybe_edit_prompt(
            title="AI Translation Prompt",
            system_prompt=combined_system,
            user_prompt=user_prompt,
            save_section='translation',
        )
        if edited is None:
            return
        edited_system, edited_user = edited

        precomposed = [
            {"role": "system", "content": edited_system},
            {"role": "user", "content": edited_user},
        ]
        task_details = {
            'type': 'translate_single',
            'composer_args': composer_args,
            'attempt': 1,
            'max_retries': 1,
        }
        if not self._attach_session_to_task(
            task_details,
            base_system_prompt=system_prompt,
            full_system_prompt=edited_system,
            user_prompt=edited_user,
            task_type='translate_single',
        ):
            task_details['precomposed_prompt'] = precomposed
        self.ui_handler.start_ai_operation("AI Translation", model_name=self.ai_lifecycle_manager._active_model_name)
        self._run_ai_task(provider, task_details)
        
    def _handle_block_translation_success(self, response: ProviderResponse, context: dict):
        log_debug(f"Block translation finished for block {context.get('block_idx')}")
        self.ui_handler.finish_ai_operation()

    def translate_selected_lines(self):
        """
        Translates the lines currently selected in the preview editor.
        If no lines are selected, translates the current string.
        """
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit and preview_edit.get_selected_lines():
            # Pass a dummy point; translate_preview_selection prioritizes 
            # explicit selection over the mouse position.
            self.translate_preview_selection(QPoint(0, 0))
        else:
            self.translate_current_string()