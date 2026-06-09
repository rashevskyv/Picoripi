# handlers/translation/translation_handler.py

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from PyQt6.QtCore import QTimer, Qt, QPoint, QThread, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QApplication
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
from utils.utils import convert_spaces_to_dots_for_display, calculate_string_width, remove_all_tags


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
        self.ai_lifecycle_manager.register_handler('classify_suggest_types', self.glossary_handler._handle_classify_suggest_success, self.glossary_handler._handle_classify_error)
        self.ai_lifecycle_manager.register_handler('classify_apply', self.glossary_handler._handle_classify_apply_success, self.glossary_handler._handle_classify_error)
        
        # Block translation has a chunk handler
        self.ai_lifecycle_manager.register_handler('translate_block_chunked', 
                                                   self._handle_block_translation_success,
                                                   chunk_cb=self._handle_chunk_translated)

        self._glossary_manager = self.glossary_handler.glossary_manager
        self.variations_cache = {}
        
        self.start_new_session = True
        log_debug(f"TranslationHandler.__init__: start_new_session initialized to {self.start_new_session}")

        QTimer.singleShot(0, self.glossary_handler.install_menu_actions)
    
    def save_progress_to_metadata(self, block_idx: int) -> None:
        """Saves translation progress for a single block into the block's project metadata."""
        if not self.mw.project_manager or not self.mw.project_manager.project:
            return
            
        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        if not isinstance(block_map, dict):
            block_map = {}
            
        proj_block_idx = block_map.get(block_idx, block_idx)
            
        if proj_block_idx < 0 or proj_block_idx >= len(self.mw.project_manager.project.blocks):
            return
            
        block = self.mw.project_manager.project.blocks[proj_block_idx]
        
        if block_idx in self.translation_progress:
            prog = self.translation_progress[block_idx]
            # Convert set to list for JSON serialization
            serialized_prog = {
                'completed_chunks': list(prog.get('completed_chunks', [])),
                'total_chunks': prog.get('total_chunks', 0),
                'source_items': prog.get('source_items', []),
                'temp_id_map': prog.get('temp_id_map', {}),
                'custom_user_header': prog.get('custom_user_header'),
                'custom_user_label': prog.get('custom_user_label'),
                'system_prompt_override': prog.get('system_prompt_override'),
                'session_reset_attempted': prog.get('session_reset_attempted', False)
            }
            block.metadata['translation_progress'] = serialized_prog
        else:
            if 'translation_progress' in block.metadata:
                del block.metadata['translation_progress']
                
        # Persist project changes
        self.mw.project_manager.save()

    def load_progress_from_metadata(self) -> None:
        """Loads translation progress for all blocks from their project metadata."""
        self.translation_progress.clear()
        if not self.mw.project_manager or not self.mw.project_manager.project:
            return
            
        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        # Create a reverse map to go from project block index back to data block index
        rev_block_map = {proj_idx: data_idx for data_idx, proj_idx in block_map.items()}
        
        for proj_idx, block in enumerate(self.mw.project_manager.project.blocks):
            serialized_prog = block.metadata.get('translation_progress')
            if serialized_prog and isinstance(serialized_prog, dict):
                # Resolve the correct data block index
                data_block_idx = rev_block_map.get(proj_idx, proj_idx)
                
                # Reconstruct completed_chunks as a set
                completed_chunks = set(serialized_prog.get('completed_chunks', []))
                
                # Reconstruct temp_id_map, converting keys back to integers where possible
                raw_temp_map = serialized_prog.get('temp_id_map', {})
                temp_id_map = {}
                for k, v in raw_temp_map.items():
                    # Handle tuple conversion (in JSON, list was saved)
                    if isinstance(v, list) and len(v) == 2:
                        val = (v[0], v[1])
                    else:
                        val = v
                        
                    try:
                        temp_id_map[int(k)] = val
                    except (ValueError, TypeError):
                        temp_id_map[k] = val
                
                self.translation_progress[data_block_idx] = {
                    'completed_chunks': completed_chunks,
                    'total_chunks': serialized_prog.get('total_chunks', 0),
                    'source_items': serialized_prog.get('source_items', []),
                    'temp_id_map': temp_id_map,
                    'custom_user_header': serialized_prog.get('custom_user_header'),
                    'custom_user_label': serialized_prog.get('custom_user_label'),
                    'system_prompt_override': serialized_prog.get('system_prompt_override'),
                    'session_reset_attempted': serialized_prog.get('session_reset_attempted', False)
                }
        log_debug(f"Loaded translation progress for {len(self.translation_progress)} blocks from project metadata.")

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
        modifiers = QApplication.keyboardModifiers()
        is_ctrl_pressed = False
        if hasattr(modifiers, 'value'):
            is_ctrl_pressed = bool(modifiers.value & Qt.KeyboardModifier.ControlModifier.value)
        elif isinstance(modifiers, int):
            is_ctrl_pressed = bool(modifiers & Qt.KeyboardModifier.ControlModifier.value)
        else:
            is_ctrl_pressed = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
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
        if dialog.exec() != dialog.Accepted:
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
        return task_type in ('chat_message', 'chat_message_stream', 'translate_block_chunked')

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
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.No:
            if block_idx == -2:
                # Revert all individual blocks that were modified in the chapter
                temp_id_map = self.worker.task_details.get('temp_id_map', {})
                modified_blocks = {b_idx for b_idx, _ in temp_id_map.values()}
                for b_idx in modified_blocks:
                    if b_idx in self.pre_translation_state:
                        original_texts = self.pre_translation_state[b_idx]
                        for i, text in enumerate(original_texts):
                            self.data_processor.update_edited_data(b_idx, i, text)
                        del self.pre_translation_state[b_idx]
                
                if -2 in self.translation_progress:
                    del self.translation_progress[-2]
                if -2 in self.pre_translation_state:
                    del self.pre_translation_state[-2]
                
                self.ui_updater.populate_strings_for_block(-2, force=True)
                self.ui_updater.update_text_views()
            else:
                if block_idx in self.pre_translation_state:
                    original_texts = self.pre_translation_state[block_idx]
                    for i, text in enumerate(original_texts):
                        self.data_processor.update_edited_data(block_idx, i, text)
                    
                    del self.pre_translation_state[block_idx]

                if block_idx in self.translation_progress:
                    del self.translation_progress[block_idx]

                self.ui_updater.populate_strings_for_block(block_idx, getattr(self.mw, 'current_category_name', None), force=True)
                self.ui_updater.update_text_views()
        else:
            if block_idx == -2:
                temp_id_map = self.worker.task_details.get('temp_id_map', {})
                modified_blocks = {b_idx for b_idx, _ in temp_id_map.values()}
                for b_idx in modified_blocks:
                    if b_idx in self.pre_translation_state:
                        del self.pre_translation_state[b_idx]
                if -2 in self.pre_translation_state:
                    del self.pre_translation_state[-2]
            else:
                if block_idx in self.pre_translation_state:
                    del self.pre_translation_state[block_idx]
        
        self.ui_handler.finish_ai_operation()
        if block_idx == -2:
            self.ui_updater.update_block_item_text_with_problem_count(-2)
            temp_id_map = self.worker.task_details.get('temp_id_map', {}) if self.worker else {}
            modified_blocks = {b_idx for b_idx, _ in temp_id_map.values()}
            for b_idx in modified_blocks:
                self.ui_updater.update_block_item_text_with_problem_count(b_idx)
        else:
            self.ui_updater.update_block_item_text_with_problem_count(block_idx)
            self.save_progress_to_metadata(block_idx)


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
        
        displayed_indices = getattr(self.mw.data_store, 'displayed_string_indices', [])
        source_items = []
        temp_id_map = {}
        for idx in string_indices:
            if idx < len(displayed_indices):
                real_idx = displayed_indices[idx]
                if isinstance(real_idx, tuple):
                    r_block_idx, r_string_idx = real_idx
                else:
                    r_block_idx = block_idx
                    r_string_idx = real_idx
                
                text_raw = str(self.glossary_handler._get_original_string(r_block_idx, r_string_idx) or "")
                source_items.append({"id": idx, "text": text_raw})
                temp_id_map[idx] = (r_block_idx, r_string_idx)

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
            'temp_id_map': temp_id_map,
        }
        self._initiate_batch_translation(task_details)

    def translate_current_block(self, block_idx: Optional[int] = None, category_name: Optional[str] = None, chapter_id: Optional[int] = None) -> None:
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
        elif target_block_idx == -2:
            operation_title = "AI Translation (Chapter)"
            if hasattr(self.mw.block_list_widget, 'currentItem') and self.mw.block_list_widget.currentItem():
                ch_name = self.mw.block_list_widget.currentItem().text(0)
                if isinstance(ch_name, str):
                    import re
                    ch_name = re.sub(r'\s*\(\d+\)$', '', ch_name)
                    operation_title = f"AI: Translate Chapter '{ch_name}'"

        self.ui_handler.start_ai_operation(operation_title, is_chunked=True, model_name=self.ai_lifecycle_manager._active_model_name)
        from components.ai_status_dialog import AIStatusDialog
        self.ui_handler.update_ai_operation_step(0, "Preparing data...", AIStatusDialog.STATUS_IN_PROGRESS)
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        if target_block_idx == -2:
            if chapter_id is None:
                chapter_id = getattr(self.mw.data_store, 'current_chapter_id', None)
            if chapter_id is None:
                self.ui_handler.finish_ai_operation()
                QMessageBox.information(self.mw, "AI Translation", "No chapter ID available.")
                return

            chapter_mappings = []
            client = self.prompt_composer._get_mempalace_client()
            if client:
                wing_name = self.prompt_composer._get_wing_name()
                mappings = client.get_chapter_mappings(wing_name, chapter_id)
                for m in mappings:
                    bmg_id = m.get("bmg_id")
                    indices = self.mw.list_selection_handler.resolve_bmg_id_to_indices(bmg_id)
                    if indices:
                        chapter_mappings.append(indices)

            if not chapter_mappings:
                self.ui_handler.finish_ai_operation()
                QMessageBox.information(self.mw, "AI Translation", "No lines mapped to this chapter.")
                return

            # Keep backup of pre-translation state for each block in the chapter
            chapter_blocks = {b_idx for b_idx, _ in chapter_mappings}
            for b_idx in chapter_blocks:
                if b_idx not in self.pre_translation_state:
                    self.pre_translation_state[b_idx] = self.data_processor.get_block_texts(b_idx)
            self.pre_translation_state[-2] = True

            source_items = []
            temp_id_map = {}
            for temp_id, (b_idx, s_idx) in enumerate(chapter_mappings):
                text = str(self.glossary_handler._get_original_string(b_idx, s_idx) or "")
                source_items.append({"id": temp_id, "text": text})
                temp_id_map[temp_id] = (b_idx, s_idx)

            provider = self.ai_lifecycle_manager._prepare_provider()
            if not provider:
                self.ui_handler.finish_ai_operation()
                return

            base_timeout = self._resolve_base_timeout(provider)
            block_timeout = base_timeout * 10
            log_debug(
                f"Starting chapter AI translation with timeout {block_timeout}s (base {base_timeout}s); lines={len(source_items)}"
            )
        else:
            data_source = getattr(self.mw.data_store, 'data', None) if hasattr(self.mw, 'data_store') else getattr(self.mw, 'data', None)
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

            # Always build temp_id_map to prevent index shifting bugs during segment reordering
            temp_id_map = {idx: (target_block_idx, idx) for idx in target_indices if idx < len(block_strings)}

        task_details = {
            'type': 'translate_block_chunked',
            'provider': provider,
            'source_items': source_items,
            'attempt': 1,
            'max_retries': 4,
            'block_idx': target_block_idx,
            'temp_id_map': temp_id_map,
            'mode_description': (
                "chapter" if target_block_idx == -2
                else (f"block {target_block_idx + 1}" if not category_name else f"category '{category_name}' in block {target_block_idx + 1}")
            ),
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
        # Recover or rebuild temp_id_map for safe segment mapping during resume
        temp_id_map = progress_entry.get('temp_id_map', {})
        if not temp_id_map:
            temp_id_map = {item['id']: (target_block_idx, item['id']) for item in source_items if isinstance(item, dict) and 'id' in item}

        task_details = {
            'type': 'translate_block_chunked',
            'provider': provider,
            'source_items': source_items,
            'attempt': 1,
            'max_retries': 4,
            'block_idx': target_block_idx,
            'temp_id_map': temp_id_map,
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

    def _format_and_wrap_translation(self, text: str, block_idx: int, string_idx: int) -> str:
        """
        Cleans the incoming translation, wraps lines to balance between line_width_warning_threshold_pixels 
        and game_dialog_max_width_pixels, and splits sentences into pages according to lines_per_page.
        """
        if not text:
            return ""

        if not isinstance(text, str):
            text = str(text)

        # 1. Clean incoming translation: replace all newlines with spaces
        cleaned_text = text.replace('\n', ' ')
        # Normalize double/multiple spaces to single space
        cleaned_text = re.sub(r' +', ' ', cleaned_text).strip()
        # Remove spaces immediately following leading tags
        cleaned_text = re.sub(r'^((?:\{[^}]*\}|\[[^\]]*\])*)\s+', r'\1', cleaned_text)
        # Remove spaces between tags and punctuation marks (e.g. "{tag} ," -> "{tag},")
        cleaned_text = re.sub(r'(\{[^}]*\}|\[[^\]]*\])\s+([,\.!?;:…])', r'\1\2', cleaned_text)

        # Get font map
        font_map = None
        if hasattr(self.mw, "current_font_map") and self.mw.current_font_map:
            font_map = self.mw.current_font_map
        elif hasattr(self.mw, "font_map") and self.mw.font_map:
            font_map = self.mw.font_map

        # Retrieve thresholds
        string_meta = getattr(self.mw, 'string_metadata', {}).get((block_idx, string_idx), {})
        
        # Max allowed width (hard threshold, e.g. 460px)
        max_width_raw = string_meta.get("width", getattr(self.mw, 'game_dialog_max_width_pixels', 200))
        try:
            max_width = int(max_width_raw)
        except (TypeError, ValueError):
            max_width = 200

        # Warning threshold (desired soft threshold, e.g. 410px)
        warning_threshold_raw = getattr(self.mw, 'line_width_warning_threshold_pixels', 200)
        try:
            warning_threshold = int(warning_threshold_raw)
        except (TypeError, ValueError):
            warning_threshold = 200
            
        # Ensure warning threshold is <= max_width
        if warning_threshold > max_width:
            warning_threshold = max_width

        # Lines per page
        lines_per_page = getattr(self.mw, 'lines_per_page', 4)
        try:
            lines_per_page = int(lines_per_page)
        except (TypeError, ValueError):
            lines_per_page = 4

        # 2. Split text into sentences (tag-aware).
        # We split by (. ! ? …) followed by spaces, but ignoring punctuation inside {...} or [...] tags.
        def split_sentences_tag_aware(txt: str) -> List[str]:
            sentences_list = []
            current_sentence = []
            in_curly = False
            in_square = False
            
            i = 0
            n = len(txt)
            while i < n:
                c = txt[i]
                if c == '{':
                    in_curly = True
                elif c == '}':
                    in_curly = False
                elif c == '[':
                    in_square = True
                elif c == ']':
                    in_square = False
                    
                current_sentence.append(c)
                
                # Split condition: punctuation not in tags, followed by space or end of string
                if not in_curly and not in_square and c in ('.', '!', '?', '…'):
                    j = i + 1
                    while j < n and txt[j].isspace():
                        j += 1
                    if j > i + 1:
                        # Append the spaces to current sentence
                        current_sentence.extend(txt[i+1:j])
                        sentences_list.append("".join(current_sentence).strip())
                        current_sentence = []
                        i = j - 1
                i += 1
                
            if current_sentence:
                sent_str = "".join(current_sentence).strip()
                if sent_str:
                    sentences_list.append(sent_str)
            return sentences_list

        sentences = split_sentences_tag_aware(cleaned_text)
        if not sentences:
            return ""

        # Helper to wrap a single sentence/text into lines based on warning_threshold and max_width
        def wrap_text_segment(segment_text: str) -> List[str]:
            parts = re.findall(r'(\{[^}]*\}|\[[^\]]*\]|\S+|\s+)', segment_text)
            segment_lines = []
            current_line = ""
            current_w = 0
            needs_space_flag = False

            for part in parts:
                part_no_tags = remove_all_tags(part)
                part_width = calculate_string_width(part_no_tags, font_map)

                # Calculate width including space if needed
                is_punctuation = part in (',', '.', '!', '?', ';', ':', '…')
                current_needs_space = (needs_space_flag and not part.isspace() and 
                                      not is_punctuation and current_line and 
                                      not current_line.endswith(" "))
                
                space_w = calculate_string_width(" ", font_map) if current_needs_space else 0
                new_width_if_added = current_w + space_w + part_width

                # Fit condition:
                # 1. Line is empty
                # 2. Or part is punctuation
                # 3. Or the new width is <= warning_threshold
                # 4. Or the current width is <= warning_threshold AND the new width is <= max_width (single word crosses the threshold)
                if (not current_line or 
                    is_punctuation or 
                    new_width_if_added <= warning_threshold or 
                    (current_w <= warning_threshold and new_width_if_added <= max_width)):
                    
                    if current_needs_space:
                        current_line += " "
                    current_line += part
                    current_w = calculate_string_width(remove_all_tags(current_line), font_map)
                    needs_space_flag = not part.isspace()
                else:
                    # Part does not fit, start a new line
                    if current_line:
                        segment_lines.append(current_line.rstrip())
                    current_line = part.strip()
                    current_w = calculate_string_width(remove_all_tags(current_line), font_map)
                    needs_space_flag = not part.isspace()

            if current_line:
                segment_lines.append(current_line.rstrip())
            return segment_lines

        # Wrap each sentence individually
        wrapped_sentences = []
        for s in sentences:
            s_lines = wrap_text_segment(s)
            if s_lines:
                wrapped_sentences.append(s_lines)

        # 3. Build pages using lines_per_page
        pages = []
        current_page_lines = []

        for s_lines in wrapped_sentences:
            num_s_lines = len(s_lines)

            # If a single sentence exceeds the page limit, we have to split it across pages
            if num_s_lines > lines_per_page:
                if current_page_lines:
                    pages.append(current_page_lines)
                    current_page_lines = []
                
                for i in range(0, num_s_lines, lines_per_page):
                    chunk = s_lines[i:i + lines_per_page]
                    if len(chunk) < lines_per_page and i + lines_per_page >= num_s_lines:
                        current_page_lines = chunk
                    else:
                        pages.append(chunk)
            else:
                # If adding this sentence to the current page would exceed lines_per_page,
                # we close the current page and start a new one with this sentence.
                if len(current_page_lines) + num_s_lines > lines_per_page:
                    pages.append(current_page_lines)
                    current_page_lines = list(s_lines)
                else:
                    current_page_lines.extend(s_lines)

        if current_page_lines:
            pages.append(current_page_lines)

        # 4. Join pages with page breaks (shift-enter char) and lines with newlines
        shift_enter_char = "\n"
        if hasattr(self.mw, "current_game_rules") and self.mw.current_game_rules:
            shift_enter_char = self.mw.current_game_rules.get_shift_enter_char()

        page_strings = []
        for page_lines in pages:
            page_strings.append("\n".join(page_lines))

        formatted_editor_text = shift_enter_char.join(page_strings)

        # Clean each line: remove leading spaces and double spaces, treating regular tags
        # {tag}/[tag] as zero-width (ignored for spacing purposes) but forced aliases
        # {f:...}/{F:...} as actual text.
        _token_re = re.compile(
            r'(\{[fF]:[^}]*\})'           # group 1: forced alias → counts as text
            r'|(\{(?![fF]:)[^}]*\}|\[[^\]]*\])'  # group 2: regular tag → zero-width
            r'|( +)'                        # group 3: spaces
            r'|([^ \{\[\]]+)'              # group 4: regular text
        )
        clean_lines = []
        for raw_line in formatted_editor_text.split('\n'):
            tokens = _token_re.findall(raw_line)
            result = []
            last_is_space = True   # True = no visible text seen yet (leading position)
            for forced_alias, reg_tag, spaces, text in tokens:
                if forced_alias or text:
                    result.append(forced_alias if forced_alias else text)
                    last_is_space = False
                elif reg_tag:
                    # Zero-width: keep in output but don't affect space state
                    result.append(reg_tag)
                elif spaces:
                    if not last_is_space:
                        # Not leading/consecutive → keep exactly one space
                        result.append(' ')
                        last_is_space = True
                    # else: leading or double space after invisible tags → skip
            clean_lines.append(''.join(result).rstrip())
        formatted_editor_text = '\n'.join(clean_lines)

        # Convert to data format expected by update_edited_data
        final_data_text = formatted_editor_text
        if hasattr(self.mw, "current_game_rules") and self.mw.current_game_rules:
            final_data_text = self.mw.current_game_rules.convert_editor_text_to_data(formatted_editor_text)

        return final_data_text

    def _initiate_batch_translation(self, context: Dict[str, Any]) -> None:
        self.translated_chunks_count = 0
        provider = context['provider']
        
        block_idx = context.get('block_idx')
        task_type = context.get('type')

        if task_type == 'translate_block_chunked' and block_idx is not None:
            if not context.get('is_resume', False):
                self.reset_translation_session()
                self.translation_progress[block_idx] = {
                    'completed_chunks': set(),
                    'total_chunks': 0,
                    'source_items': context.get('source_items', []),
                    'temp_id_map': context.get('temp_id_map', {})
                }
            
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
            'temp_id_map': context.get('temp_id_map'),
        }
        context['composer_args'] = composer_args

        if 'precomposed_prompt' not in context:
            force_prompt = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier)
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
        
        if task_type == 'translate_block_chunked' and block_idx is not None:
            self.save_progress_to_metadata(block_idx)

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
            translated_strings = parsed_json.get("translated_strings", [])
            if hasattr(self.mw, 'undo_manager'):
                self.mw.undo_manager.begin_group()

            temp_id_map = context.get('temp_id_map')
            modified_blocks = set()

            # Retrieve calculated chunks for robust sequential mapping in case AI returns sequential/reordered IDs
            chunks = context.get('calculated_chunks')
            current_chunk = chunks[chunk_index] if (chunks and chunk_index < len(chunks)) else None

            for idx_in_response, item in enumerate(translated_strings):
                temp_id, translated_text = item["id"], item["translation"]
                
                p_map = context.get('placeholder_map', {})
                if p_map:
                    translated_text = self.prompt_composer.restore_placeholders(translated_text, p_map, key=temp_id)
                
                # 1. First, try to resolve real block/string indices using sequential order inside the chunk
                # (Highly robust against LLMs completely changing ID format or returning sequential indices 0, 1, 2...)
                resolved = False
                if current_chunk and idx_in_response < len(current_chunk):
                    orig_item = current_chunk[idx_in_response]
                    orig_id = orig_item.get('id') if isinstance(orig_item, dict) else None
                    if orig_id is not None:
                        if temp_id_map and orig_id in temp_id_map:
                            real_block_idx, real_string_idx = temp_id_map[orig_id]
                            resolved = True
                        elif not temp_id_map:
                            real_block_idx = block_idx
                            real_string_idx = orig_id
                            resolved = True
                
                # 2. Fallback to mapping by ID in temp_id_map (with type-safe conversions)
                if not resolved:
                    if temp_id_map:
                        # Try integer conversion
                        try:
                            int_id = int(temp_id)
                            if int_id in temp_id_map:
                                real_block_idx, real_string_idx = temp_id_map[int_id]
                                resolved = True
                        except (ValueError, TypeError):
                            pass
                        
                        # Try string key fallback
                        if not resolved:
                            str_id = str(temp_id)
                            if str_id in temp_id_map:
                                real_block_idx, real_string_idx = temp_id_map[str_id]
                                resolved = True
                    else:
                        try:
                            real_block_idx = block_idx
                            real_string_idx = int(temp_id)
                            resolved = True
                        except (ValueError, TypeError):
                            pass

                if resolved:
                    modified_blocks.add(real_block_idx)
                    final_text = self._format_and_wrap_translation(translated_text, real_block_idx, real_string_idx)
                    self.data_processor.update_edited_data(real_block_idx, real_string_idx, final_text, action_type="TRANSLATE", skip_ui_refresh=True)
            
            if hasattr(self.mw, 'undo_manager'):
                self.mw.undo_manager.end_group("TRANSLATE")
            
            if block_idx == -2:
                modified_blocks.add(-2)

            if block_idx in self.translation_progress:
                self.translation_progress[block_idx]['completed_chunks'].add(chunk_index)
                self.save_progress_to_metadata(block_idx)

            # Refresh tree indicators for all modified blocks once
            for m_block in modified_blocks:
                self.ui_updater.update_block_item_text_with_problem_count(m_block)

            self.ui_updater.update_title()
            
            self.ai_lifecycle_manager._record_session_exchange(context=context, assistant_content=chunk_text)
            
            current_view_block = self.mw.data_store.current_block_idx if hasattr(self.mw, 'data_store') else 0
            if hasattr(self.mw, 'data_store') and getattr(self.mw.data_store, 'current_chapter_id', None) is not None:
                current_view_block = -2
            self.ui_updater.populate_strings_for_block(current_view_block, getattr(self.mw, 'current_category_name', None), force=True)
            self.translated_chunks_count = len(self.translation_progress.get(block_idx, {}).get('completed_chunks', set()))
            self.ui_handler.status_dialog.update_progress(self.translated_chunks_count)
            
            total_chunks = self.translation_progress.get(block_idx, {}).get('total_chunks', -1)
            if total_chunks != -1 and self.translated_chunks_count == total_chunks:
                self.ui_handler.finish_ai_operation()
                self.ui_updater.update_text_views()
                if hasattr(self.mw, 'app_action_handler'):
                    for m_block in modified_blocks:
                        if m_block != 999999 and m_block >= 0:
                            self.mw.issue_scan_handler.rescan_issues_for_single_block(m_block, show_message_on_completion=False)
                
                if block_idx == -2:
                    if -2 in self.translation_progress:
                        del self.translation_progress[-2]
                    temp_id_map = context.get('temp_id_map', {})
                    modified_blocks_for_cleanup = {b_idx for b_idx, _ in temp_id_map.values()}
                    for b_idx in modified_blocks_for_cleanup:
                        if b_idx in self.pre_translation_state:
                            del self.pre_translation_state[b_idx]
                    if -2 in self.pre_translation_state:
                        del self.pre_translation_state[-2]
                else:
                    if block_idx in self.translation_progress:
                        del self.translation_progress[block_idx]
                        self.save_progress_to_metadata(block_idx)
                    if block_idx in self.pre_translation_state:
                        del self.pre_translation_state[block_idx]
                
                # Removed self.reset_translation_session() to allow user to inspect context if needed

        except (json.JSONDecodeError, ValueError) as e:
            self._handle_ai_error(f"Failed to process chunk {chunk_index + 1}: {e}", context)

    def _handle_preview_translation_success(self, response: ProviderResponse, context: Dict[str, Any]) -> None:
        self.ui_handler.update_ai_operation_step(3, self.ui_handler.status_dialog.steps[3], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        cleaned_text = self.ai_lifecycle_manager._clean_model_output(response, expect_json=True)
        
        try:
            parsed_json = json.loads(cleaned_text)
            translated_strings = parsed_json.get("translated_strings")
            if not isinstance(translated_strings, list) or len(translated_strings) != len(context['source_items']):
                raise ValueError("Invalid response structure or item count mismatch.")

            if hasattr(self.mw, 'undo_manager'):
                self.mw.undo_manager.begin_group()
                
            self.ui_handler.update_ai_operation_step(4, self.ui_handler.status_dialog.steps[4], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
            
            temp_id_map = context.get('temp_id_map')
            p_map = context.get('placeholder_map', {})
            source_items = context.get('source_items', [])
            modified_blocks = set()

            for idx_in_response, item in enumerate(translated_strings):
                temp_id, translated_text = item["id"], item["translation"]
                
                resolved_orig_id = None
                if idx_in_response < len(source_items):
                    orig_item = source_items[idx_in_response]
                    if isinstance(orig_item, dict):
                        resolved_orig_id = orig_item.get('id')
                
                # Restore placeholders using sequential mapping key first, fallback to temp_id
                restore_key = resolved_orig_id if resolved_orig_id is not None else temp_id
                if p_map:
                    translated_text = self.prompt_composer.restore_placeholders(translated_text, p_map, key=restore_key)
                else:
                    translated_text = self.prompt_composer.restore_placeholders(translated_text, None, key=None)

                # 1. Try sequential order inside source_items first
                resolved = False
                if resolved_orig_id is not None:
                    if temp_id_map and resolved_orig_id in temp_id_map:
                        real_block_idx, real_string_idx = temp_id_map[resolved_orig_id]
                        resolved = True
                    elif not temp_id_map:
                        real_block_idx = context['block_idx']
                        real_string_idx = resolved_orig_id
                        resolved = True

                # 2. Fallback to mapping by ID in temp_id_map (with type-safe conversions)
                if not resolved:
                    if temp_id_map:
                        try:
                            int_id = int(temp_id)
                            if int_id in temp_id_map:
                                real_block_idx, real_string_idx = temp_id_map[int_id]
                                resolved = True
                        except (ValueError, TypeError):
                            pass
                        
                        if not resolved:
                            str_id = str(temp_id)
                            if str_id in temp_id_map:
                                real_block_idx, real_string_idx = temp_id_map[str_id]
                                resolved = True
                    else:
                        try:
                            real_block_idx = context['block_idx']
                            real_string_idx = int(temp_id)
                            resolved = True
                        except (ValueError, TypeError):
                            pass
                
                if not resolved:
                    real_block_idx = context['block_idx']
                    try:
                        real_string_idx = int(temp_id)
                    except (ValueError, TypeError):
                        real_string_idx = temp_id

                modified_blocks.add(real_block_idx)
                final_text = self._format_and_wrap_translation(translated_text, real_block_idx, real_string_idx)
                self.data_processor.update_edited_data(real_block_idx, real_string_idx, final_text, action_type="TRANSLATE")

            if hasattr(self.mw, 'undo_manager'):
                self.mw.undo_manager.end_group("TRANSLATE")

            self.ai_lifecycle_manager._record_session_exchange(context=context, assistant_content=cleaned_text, response=response)

            # Refresh tree indicators for all modified blocks once
            for m_block in modified_blocks:
                self.ui_updater.update_block_item_text_with_problem_count(m_block)

            self.ui_handler.finish_ai_operation()
            
            current_view_block = self.mw.data_store.current_block_idx if hasattr(self.mw, 'data_store') else 0
            if hasattr(self.mw, 'data_store') and getattr(self.mw.data_store, 'current_chapter_id', None) is not None:
                current_view_block = -2
            self.ui_updater.populate_strings_for_block(current_view_block, getattr(self.mw, 'current_category_name', None), force=True)
            self.ui_updater.update_text_views()
            self.ui_updater.update_title()
            if hasattr(self.mw, 'app_action_handler'):
                for m_block in modified_blocks:
                    if m_block != 999999:
                        self.mw.issue_scan_handler.rescan_issues_for_single_block(m_block, show_message_on_completion=False)

        except (json.JSONDecodeError, ValueError) as e:
            self._handle_ai_error(f"Validation failed: {e}", context)

    def _handle_ai_error(self, error_msg: str, context: Dict[str, Any]) -> None:
        self.ai_lifecycle_manager._handle_task_error(error_msg, context)

    def _handle_single_translation_success(self, response: ProviderResponse, context: Dict[str, Any]) -> None:
        self.ui_handler.update_ai_operation_step(3, self.ui_handler.status_dialog.steps[3], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        cleaned_translation = self.ai_lifecycle_manager._clean_model_output(response, expect_json=False)
        
        # Restore placeholders
        p_map = context.get('placeholder_map', {})
        cleaned_translation = self.prompt_composer.restore_placeholders(cleaned_translation, p_map, key=0)
        
        block_idx = self.mw.data_store.current_block_idx
        string_idx = self.mw.data_store.current_string_idx
        final_text = self._format_and_wrap_translation(cleaned_translation, block_idx, string_idx)
        self.ai_lifecycle_manager._record_session_exchange(context=context, assistant_content=cleaned_translation, response=response)
        
        self.ui_handler.update_ai_operation_step(4, self.ui_handler.status_dialog.steps[4], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        
        # Write translated text directly to the database to prevent timer desync and immediate UI overwrites
        if hasattr(self.mw, 'undo_manager'):
            self.mw.undo_manager.begin_group()
        self.data_processor.update_edited_data(block_idx, string_idx, final_text, action_type="TRANSLATE", skip_ui_refresh=True)
        if hasattr(self.mw, 'undo_manager'):
            self.mw.undo_manager.end_group("TRANSLATE")
            
        self.ui_handler.apply_full_translation(final_text)
        self.ui_handler.finish_ai_operation()
        refresh_idx = block_idx
        if getattr(self.mw.data_store, 'current_chapter_id', None) is not None:
            refresh_idx = -2
        self.ui_updater.populate_strings_for_block(refresh_idx, getattr(self.mw, 'current_category_name', None), force=True)

    def _on_task_finished(self, context: Dict[str, Any]) -> None:
        self.ai_lifecycle_manager.on_task_finished(context)

    def _handle_variation_success(self, response: ProviderResponse, context: Dict[str, Any]) -> None:
        self.ui_handler.update_ai_operation_step(3, self.ui_handler.status_dialog.steps[3], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        cleaned = self.ai_lifecycle_manager._clean_model_output(response, expect_json=True)
        self.ai_lifecycle_manager._record_session_exchange(context=context, assistant_content=cleaned, response=response)
        variants_raw = self.ui_handler.parse_variation_payload(cleaned)
        self.ui_handler.finish_ai_operation(show_popup=False)

        if not variants_raw:
            QMessageBox.information(self.mw, "AI Variation", "Failed to parse variations from AI response.")
            return
            
        trimmed = [self.ai_lifecycle_manager._trim_trailing_whitespace_from_lines(v) for v in variants_raw]
        
        # Restore placeholders
        p_map = context.get('placeholder_map', {})
        restored_variants = []
        for v in trimmed:
            restored_v = self.prompt_composer.restore_placeholders(v, p_map, key=0)
            restored_variants.append(restored_v)
            
        # Cache the variations for the current string
        block_idx = self.mw.data_store.current_block_idx
        string_idx = self.mw.data_store.current_string_idx
        current_translation, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        self.variations_cache[(block_idx, string_idx)] = {
            'variants': restored_variants,
            'translation': str(current_translation)
        }

        chosen = self.ui_handler.show_variations_dialog(restored_variants, show_refresh=True)
        if chosen == "__REFRESH__":
            QTimer.singleShot(100, lambda: self.generate_variation_for_current_string(force=True))
            return
        if chosen:
            self._apply_chosen_variation(chosen, context.get('is_inline', False))

    def _apply_chosen_variation(self, chosen: str, is_inline: bool) -> None:
        block_idx = self.mw.data_store.current_block_idx
        string_idx = self.mw.data_store.current_string_idx
        final_text = self._format_and_wrap_translation(chosen, block_idx, string_idx)
        
        # Write chosen variation directly to the database to prevent timer desync and immediate UI overwrites
        if hasattr(self.mw, 'undo_manager'):
            self.mw.undo_manager.begin_group()
        self.data_processor.update_edited_data(block_idx, string_idx, final_text, action_type="TRANSLATE", skip_ui_refresh=True)
        if hasattr(self.mw, 'undo_manager'):
            self.mw.undo_manager.end_group("TRANSLATE")
            
        if is_inline:
            self.ui_handler.apply_inline_variation(final_text)
        else:
            self.ui_handler.apply_full_translation(final_text)


    def generate_variation_for_current_string(self, force: bool = False) -> None:
        if self.is_ai_running:
            QMessageBox.information(self.mw, "AI Busy", "An AI task is already running. Please wait for it to complete.")
            return
        if self.mw.data_store.current_block_idx == -1 or self.mw.data_store.current_string_idx == -1: return
        original_text = str(self.glossary_handler._get_original_string(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx))
        current_translation, _ = self.data_processor.get_current_string_text(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)
        if not current_translation:
            QMessageBox.information(self.mw, "AI Variation", "There is no current translation to vary.")
            return

        # Check cache if not forced
        block_idx = self.mw.data_store.current_block_idx
        string_idx = self.mw.data_store.current_string_idx
        cache_key = (block_idx, string_idx)
        if not force and cache_key in self.variations_cache:
            cached = self.variations_cache[cache_key]
            restored_variants = cached.get('variants', [])
            chosen = self.ui_handler.show_variations_dialog(restored_variants, show_refresh=True)
            if chosen == "__REFRESH__":
                QTimer.singleShot(100, lambda: self.generate_variation_for_current_string(force=True))
            elif chosen:
                self._apply_chosen_variation(chosen, is_inline=False)
            return
        
        provider = self.ai_lifecycle_manager._prepare_provider()
        if not provider: return

        system_prompt, _ = self.glossary_handler.load_prompts()
        if not system_prompt:
            self.ui_handler.finish_ai_operation()
            return
        
        # Apply force-aliases
        from utils.force_alias import prepare_text_for_ai
        tag_mappings = getattr(self.mw, 'default_tag_mappings', {})
        original_text_for_ai, force_maps = prepare_text_for_ai(original_text, tag_mappings)
        p_map = {0: force_maps} if force_maps else {}

        session_state = self._session_manager.get_state()
        composer_args = {
            'system_prompt': system_prompt,
            'source_text': original_text_for_ai,
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
            'placeholder_map': p_map,
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
            return        # Apply force-aliases
        from utils.force_alias import prepare_text_for_ai
        tag_mappings = getattr(self.mw, 'default_tag_mappings', {})
        source_text_for_ai, force_maps = prepare_text_for_ai(source_text, tag_mappings)
        p_map = {0: force_maps} if force_maps else {}

        session_state = self._session_manager.get_state()
        composer_args = {
            'system_prompt': system_prompt,
            'source_text': source_text_for_ai,
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
            'placeholder_map': p_map,
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

    def translate_all_blocks_chronologically(self) -> None:
        if self.is_ai_running:
            QMessageBox.information(self.mw, "AI Busy", "An AI task is already running. Please wait for it to complete.")
            return
            
        data_source = getattr(self.mw.data_store, 'data', None) if hasattr(self.mw, 'data_store') else getattr(self.mw, 'data', None)
        if not isinstance(data_source, list) or not data_source:
            QMessageBox.information(self.mw, "AI Translation", "No data available to translate.")
            return

        target_block_idx = 999999
        is_resume = False
        progress_entry = self.translation_progress.get(target_block_idx)
        if progress_entry and progress_entry.get('completed_chunks') and progress_entry.get('source_items'):
            completed = len(progress_entry['completed_chunks'])
            total = progress_entry.get('total_chunks', 0)
            if total > 0 and completed < total:
                msg = f"An interrupted chronological translation session was found ({completed}/{total} chunks completed).\n\nWould you like to resume it?"
                choice = QMessageBox.question(
                    self.mw, 
                    "Resume Chronological Translation", 
                    msg, 
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                    QMessageBox.StandardButton.Yes
                )
                if choice == QMessageBox.StandardButton.Yes:
                    is_resume = True
                else:
                    self.translation_progress.pop(target_block_idx, None)
                    self.pre_translation_state.pop(target_block_idx, None)

        if is_resume:
            source_items = progress_entry.get('source_items', [])
            temp_id_map = progress_entry.get('temp_id_map', {})
            
            operation_title = "Resuming AI Translation (All Blocks Chronological)"
            self.ui_handler.start_ai_operation(operation_title, is_chunked=True, model_name=self.ai_lifecycle_manager._active_model_name)
            
            provider = self.ai_lifecycle_manager._prepare_provider()
            if not provider:
                self.ui_handler.finish_ai_operation()
                return

            base_timeout = self._resolve_base_timeout(provider)
            block_timeout = base_timeout * 10

            task_details = {
                'type': 'translate_block_chunked',
                'provider': provider,
                'source_items': source_items,
                'attempt': 1,
                'max_retries': 4,
                'block_idx': target_block_idx,
                'temp_id_map': temp_id_map,
                'mode_description': "all blocks chronologically",
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
            return

        self.start_new_session = True
        operation_title = "AI Translation (All Blocks Chronological)"
        
        self.ui_handler.start_ai_operation(operation_title, is_chunked=True, model_name=self.ai_lifecycle_manager._active_model_name)
        from components.ai_status_dialog import AIStatusDialog
        self.ui_handler.update_ai_operation_step(0, "Preparing chronological data...", AIStatusDialog.STATUS_IN_PROGRESS)
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        # 1. Gather all dialogue strings across all blocks
        all_project_items = []
        for b_idx in range(len(data_source)):
            block_strings = self.glossary_handler._get_original_block(b_idx)
            if not block_strings:
                continue
            for s_idx in range(len(block_strings)):
                original_text = str(self.glossary_handler._get_original_string(b_idx, s_idx) or "")
                all_project_items.append({
                    'block_idx': b_idx,
                    'string_idx': s_idx,
                    'text': original_text
                })

        if not all_project_items:
            self.ui_handler.finish_ai_operation()
            QMessageBox.information(self.mw, "AI Translation", "No dialogues found to translate.")
            return

        # 2. Sort chronologically using MemePalace mappings
        wing_name = self.prompt_composer._get_wing_name()
        client = self.prompt_composer._get_mempalace_client()
        block_names_map = {b_idx: self.prompt_composer._get_block_label(b_idx) for b_idx in range(len(data_source))}
        
        scored_items = []
        for item in all_project_items:
            b_idx = item['block_idx']
            s_idx = item['string_idx']
            block_label = block_names_map[b_idx]
            bmg_id = f"{block_label}_Str_{s_idx}"
            
            script_line = 999999
            if client:
                mapping = client.get_script_mapping(wing_name, bmg_id)
                if mapping and mapping.get("script_line"):
                    script_line = mapping["script_line"]
            scored_items.append((item, script_line))
            
        scored_items.sort(key=lambda x: x[1])
        sorted_items = [x[0] for x in scored_items]

        # Save pre-translation state for backup/revert
        for b_idx in range(len(data_source)):
            self.pre_translation_state[b_idx] = self.data_processor.get_block_texts(b_idx)

        # 3. Build source items and temp ID mappings
        source_items = []
        temp_id_map = {}
        for temp_id, item in enumerate(sorted_items):
            scene_context = ""
            if client:
                b_idx = item['block_idx']
                s_idx = item['string_idx']
                block_label = block_names_map[b_idx]
                bmg_id = f"{block_label}_Str_{s_idx}"
                cached = client.get_cached_context(bmg_id, item['text'])
                if cached and cached.get("room"):
                    room = cached.get("room")
                    visual = client.get_room_visual_context(wing_name, room)
                    if visual:
                        scene_context = f"Scene: {room.replace('_', ' ')}\n{visual}"
                    else:
                        scene_context = f"Scene: {room.replace('_', ' ')}"
            
            source_item = {
                'id': temp_id,
                'text': item['text']
            }
            if scene_context:
                source_item['scene_context'] = scene_context
                
            source_items.append(source_item)
            temp_id_map[temp_id] = (item['block_idx'], item['string_idx'])

        provider = self.ai_lifecycle_manager._prepare_provider()
        if not provider:
            self.ui_handler.finish_ai_operation()
            return

        base_timeout = self._resolve_base_timeout(provider)
        block_timeout = base_timeout * 10

        target_block_idx = 999999
        task_details = {
            'type': 'translate_block_chunked',
            'provider': provider,
            'source_items': source_items,
            'attempt': 1,
            'max_retries': 4,
            'block_idx': target_block_idx,
            'temp_id_map': temp_id_map,
            'mode_description': "all blocks chronologically",
            'provider_settings_override': {'timeout': block_timeout},
            'timeout_seconds': block_timeout,
            'session_reset_attempted': False
        }
        self._initiate_batch_translation(task_details)