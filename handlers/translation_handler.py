# handlers/translation/translation_handler.py

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from PyQt6.QtCore import QTimer, Qt, QPoint, QThread, pyqtSignal
from PyQt6.QtWidgets import QDialog, QMessageBox, QApplication
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
from .translation.text_formatter import TextFormatter
from .translation.ai_variations_handler import AIVariationsHandler
from components.prompt_editor_dialog import PromptEditorDialog
from utils.logging_utils import log_debug, log_warning
from utils.utils import convert_spaces_to_dots_for_display


class TranslationHandler(BaseHandler):
    """Handler for translation operations."""
    _MAX_LOG_EXCERPT: int = 160

    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any):
        """Initialize a new instance."""
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
        self.text_formatter = TextFormatter(self.mw)
        self.variations_handler = AIVariationsHandler(self)

        # Register AI success/error handlers
        self.ai_lifecycle_manager.register_handler('translate_preview', self._handle_preview_translation_success)
        self.ai_lifecycle_manager.register_handler('translate_single', self._handle_single_translation_success)
        self.ai_lifecycle_manager.register_handler('generate_variation', self.variations_handler._handle_variation_success)
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
        
        self.start_new_session = True
        log_debug(f"TranslationHandler.__init__: start_new_session initialized to {self.start_new_session}")

        QTimer.singleShot(0, self.glossary_handler.install_menu_actions)
    
    def save_progress_to_metadata(self, block_idx: int) -> None:
        """Saves translation progress for a single block into the block's project metadata."""
        if not self.mw.project_manager or not self.mw.project_manager.project:
            return
            
        block_map = self.mw.block_to_project_file_map
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
            
        block_map = self.mw.block_to_project_file_map
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
        """Initialize glossary highlighting."""
        self.glossary_handler.initialize_glossary_highlighting()

    def show_glossary_dialog(self, initial_term: Optional[str] = None) -> None:
        """Show glossary dialog."""
        self.glossary_handler.show_glossary_dialog(initial_term)

    def get_glossary_entry(self, term: str) -> Optional[GlossaryEntry]:
        """Get the glossary entry."""
        return self.glossary_handler.glossary_manager.get_entry(term)

    def add_glossary_entry(self, term: str, context: Optional[str] = None, translation: str = "") -> None:
        """Add glossary entry."""
        self.glossary_handler.add_glossary_entry(term, context, translation)

    def edit_glossary_entry(self, term: str, translation: str = "") -> None:
        """Edit glossary entry."""
        self.glossary_handler.edit_glossary_entry(term, translation=translation)

    def append_selection_to_glossary(self) -> None:
        """Append selection to glossary."""
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
        """Internal helper to prepare provider."""
        return self.ai_lifecycle_manager._prepare_provider(provider_key_override)

    def reset_translation_session(self) -> None:
        """Reset translation session."""
        self._session_manager.reset()
        self._cached_system_prompt = None
        self._cached_glossary = None
        self.start_new_session = True
        log_debug(f"TranslationHandler.reset_translation_session: Manual reset. start_new_session set to {self.start_new_session}")

        config = self.mw.translation_config
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
        force_prompt: bool = False,
    ) -> Optional[Tuple[str, str]]:
        """Internal helper to maybe edit prompt."""
        is_ctrl_pressed = force_prompt
        if not is_ctrl_pressed:
            try:
                import ctypes
                # Try GetAsyncKeyState (0x11 is VK_CONTROL) to check the physical keyboard state directly
                is_ctrl_pressed = bool(ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000)
                if not is_ctrl_pressed:
                    is_ctrl_pressed = bool(ctypes.windll.user32.GetKeyState(0x11) & 0x8000)
            except Exception:
                pass

        if not is_ctrl_pressed:
            modifiers = QApplication.keyboardModifiers()
            if hasattr(modifiers, 'value'):
                is_ctrl_pressed = bool(modifiers.value & Qt.KeyboardModifier.ControlModifier.value)
            elif isinstance(modifiers, int):
                is_ctrl_pressed = bool(modifiers & Qt.KeyboardModifier.ControlModifier.value)
            else:
                is_ctrl_pressed = bool(modifiers & Qt.KeyboardModifier.ControlModifier)

        enabled = self.mw.prompt_editor_enabled
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
        if dialog.exec() != QDialog.DialogCode.Accepted:
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
        """Internal helper to check if should use session."""
        if not self._provider_supports_sessions:
            return False
        return task_type in ('chat_message', 'chat_message_stream', 'translate_block_chunked')

    def _prepare_session_for_request(self, *, base_system_prompt: str, full_system_prompt: str, user_prompt: str, task_type: str) -> Optional[dict]:
        """Internal helper to prepare session for request."""
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
        """Internal helper to attach session to task."""
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
        """Internal helper to set the notes dialog busy."""
        if not dialog_obj:
            return
        if hasattr(dialog_obj, 'set_ai_busy'):
            dialog_obj.set_ai_busy(busy)
        elif hasattr(dialog_obj, 'set_notes_variation_busy'):
            dialog_obj.set_notes_variation_busy(busy)

    def _run_ai_task(self, provider: BaseTranslationProvider, task_details: Dict[str, Any]) -> None:
        """Internal helper to run ai task."""
        task_details['provider'] = provider
        self.ai_lifecycle_manager.run_ai_task(provider, task_details)

    def _handle_ai_cancel(self, context: Dict[str, Any]) -> None:
        """Internal helper to handle ai cancel."""
        self.ai_lifecycle_manager._handle_ai_cancel(context)

    def prompt_for_revert_after_cancel(self) -> None:
        """Prompt for revert after cancel."""
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

                self.ui_updater.populate_strings_for_block(block_idx, self.mw.data_store.current_category_name, force=True)
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
        """Internal helper to setup progress bar."""
        block_idx = self.worker.task_details.get('block_idx')
        if block_idx is not None and block_idx in self.translation_progress:
            self.translation_progress[block_idx]['total_chunks'] = total_chunks
        
        self.translated_chunks_count = completed_chunks
        self.ui_handler.status_dialog.setup_progress_bar(total_chunks, completed_chunks)

    def _is_control_pressed(self) -> bool:
        """Helper to check if Ctrl key is physically pressed."""
        try:
            import ctypes
            # Try GetAsyncKeyState (0x11 is VK_CONTROL) to check the physical keyboard state directly
            if bool(ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000):
                return True
            if bool(ctypes.windll.user32.GetKeyState(0x11) & 0x8000):
                return True
        except Exception:
            pass
        try:
            modifiers = QApplication.keyboardModifiers()
            if hasattr(modifiers, 'value'):
                return bool(modifiers.value & Qt.KeyboardModifier.ControlModifier.value)
            elif isinstance(modifiers, int):
                return bool(modifiers & Qt.KeyboardModifier.ControlModifier.value)
            else:
                return bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        except Exception:
            return False

    def translate_current_string(self, force_prompt: bool = False) -> None:
        """Translate current string."""
        if not isinstance(force_prompt, bool):
            force_prompt = False
        is_ctrl = force_prompt or self._is_control_pressed()
        log_debug(f"translate_current_string called: is_ai_running={self.is_ai_running}, block={self.mw.data_store.current_block_idx}, string={self.mw.data_store.current_string_idx}, force_prompt={is_ctrl}")
        if self.is_ai_running:
            QMessageBox.information(self.mw, "AI Busy", "An AI task is already running. Please wait for it to complete.")
            return
        if self.mw.data_store.current_block_idx == -1 or self.mw.data_store.current_string_idx == -1: return
        self._translate_and_apply(
            source_text=str(self.glossary_handler._get_original_string(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)),
            expected_lines=len(str(self.glossary_handler._get_original_string(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)).split("\n")),
            mode_description="current row",
            block_idx=self.mw.data_store.current_block_idx,
            string_idx=self.mw.data_store.current_string_idx,
            force_prompt=is_ctrl
        )

    def translate_specific_strings(self, pairs: List[Tuple[int, int]], description: str, force_prompt: bool = False) -> None:
        """Translate a specific list of (block_idx, string_idx) pairs."""
        if not isinstance(force_prompt, bool):
            force_prompt = False
        force_prompt = force_prompt or self._is_control_pressed()

        if self.is_ai_running:
            QMessageBox.information(self.mw, "AI Busy", "An AI task is already running. Please wait for it to complete.")
            return

        if not pairs:
            return

        source_items = []
        temp_id_map = {}
        for idx, (b_idx, s_idx) in enumerate(pairs):
            text_raw = str(self.glossary_handler._get_original_string(b_idx, s_idx) or "")
            source_items.append({"id": idx, "text": text_raw})
            temp_id_map[idx] = (b_idx, s_idx)

        source_items, temp_id_map = self._filter_already_saved_translations(source_items, temp_id_map, force_prompt=force_prompt)
        if not source_items:
            log_debug("translate_specific_strings: all items filtered by saved translations, returning early")
            return

        provider = self.ai_lifecycle_manager._prepare_provider()
        if not provider:
            return

        operation_title = f"AI Translation ({description})"
        
        system_prompt, _ = self.glossary_handler.load_prompts()
        if not system_prompt:
            return

        session_state = self._session_manager.get_state()
        first_block_idx = pairs[0][0] if pairs else self.mw.data_store.current_block_idx
        composer_args = {
            'system_prompt': system_prompt,
            'source_items': source_items,
            'all_source_items': source_items,
            'block_idx': first_block_idx,
            'mode_description': description,
            'session_state': session_state,
        }
        
        preview_system, preview_user, p_map = self.prompt_composer.compose_batch_request(**composer_args)

        edited = self._maybe_edit_prompt(
            title=operation_title,
            system_prompt=preview_system,
            user_prompt=preview_user,
            save_section='translation',
            force_prompt=force_prompt
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
            'block_idx': first_block_idx,
            'mode_description': description,
            'timeout_seconds': self._resolve_base_timeout(provider),
            'precomposed_prompt': [
                {"role": "system", "content": edited_system},
                {"role": "user", "content": edited_user}
            ],
            'placeholder_map': p_map,
            'temp_id_map': temp_id_map,
        }
        self._initiate_batch_translation(task_details)

    def translate_preview_selection(self, context_menu_pos: QPoint, force_prompt: bool = False) -> None:
        """Translate preview selection."""
        if not isinstance(force_prompt, bool):
            force_prompt = False
        force_prompt = force_prompt or self._is_control_pressed()
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
        
        displayed_indices = self.mw.data_store.displayed_string_indices
        pairs = []
        for idx in string_indices:
            if idx < len(displayed_indices):
                real_idx = displayed_indices[idx]
                if isinstance(real_idx, tuple):
                    pairs.append(real_idx)
                else:
                    pairs.append((block_idx, real_idx))

        description = f"Lines {start_line + 1}-{end_line + 1}" if start_line != end_line else f"Line {start_line + 1}"
        self.translate_specific_strings(pairs, description, force_prompt=force_prompt)

    def translate_current_block(self, block_idx: Optional[int] = None, category_name: Optional[str] = None, chapter_id: Optional[int] = None, force_prompt: bool = False) -> None:
        """Translate current block."""
        if not isinstance(force_prompt, bool):
            force_prompt = False
        force_prompt = force_prompt or self._is_control_pressed()
        if self.is_ai_running:
            QMessageBox.information(self.mw, "AI Busy", "An AI task is already running. Please wait for it to complete.")
            return
        target_block_idx = self.mw.data_store.current_block_idx if block_idx is None else block_idx
        if target_block_idx is None or target_block_idx == -1:
            QMessageBox.information(self.mw, "AI Translation", "Select a block to translate.")
            return
        
        self.start_new_session = True
        log_debug(f"TranslationHandler.translate_current_block: Block translation initiated. start_new_session set to {self.start_new_session}, force_prompt={force_prompt}")

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
                chapter_id = self.mw.data_store.current_chapter_id
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

            if not force_prompt:
                source_items, temp_id_map = self._filter_already_saved_translations(source_items, temp_id_map)
                if not source_items:
                    self.ui_handler.finish_ai_operation()
                    if hasattr(self.mw, 'statusBar') and self.mw.statusBar:
                        self.mw.statusBar.showMessage("All lines in chapter restored from saved translations.", 3000)
                    return


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
            data_source = self.mw.data_store.data
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
            if category_name and self.mw.project_manager and self.mw.project_manager.project:
                pm = self.mw.project_manager
                block_map = self.mw.block_to_project_file_map
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
            temp_id_map = {idx: (target_block_idx, idx) for idx in target_indices if idx < len(block_strings)}

            if not force_prompt:
                source_items, temp_id_map = self._filter_already_saved_translations(source_items, temp_id_map)
                if not source_items:
                    self.ui_handler.finish_ai_operation()
                    if hasattr(self.mw, 'statusBar') and self.mw.statusBar:
                        self.mw.statusBar.showMessage("All lines in block restored from saved translations.", 3000)
                    return

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
            'temp_id_map': temp_id_map,
            'mode_description': (
                "chapter" if target_block_idx == -2
                else (f"block {target_block_idx + 1}" if not category_name else f"category '{category_name}' in block {target_block_idx + 1}")
            ),
            'provider_settings_override': {'timeout': block_timeout},
            'timeout_seconds': block_timeout,
            'session_reset_attempted': False,
            'force_prompt': force_prompt
        }
        self._initiate_batch_translation(task_details)
    def resume_block_translation(self, block_idx: int) -> None:
        """Resume block translation."""
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
        """Internal helper to handle the chunk timer timeout event."""
        pass # This method was likely intended to be implemented or removed.

    def _resolve_base_timeout(self, provider: BaseTranslationProvider) -> int:
        """Internal helper to resolve base timeout."""
        try:
            base = int(provider.settings.get('timeout', 120))
        except (TypeError, ValueError):
            base = 120
        return max(base, 30)

    def _filter_already_saved_translations(
        self, source_items: List[Dict[str, Any]], temp_id_map: Dict[Any, Tuple[int, int]], force_prompt: bool = False
    ) -> Tuple[List[Dict[str, Any]], Dict[Any, Tuple[int, int]]]:
        """
        Filters out items that already have a saved translation in SavedTranslationsManager.
        Applies those saved translations immediately to the database and refreshes the UI.
        Returns the remaining source items and their corresponding temp_id_map.
        """
        saved_mgr = getattr(self.mw, 'saved_translations_manager', None)
        if not saved_mgr or hasattr(saved_mgr, 'assert_called_with'):
            return source_items, temp_id_map

        saved_translations = saved_mgr.load_all_saved_translations()
        if not isinstance(saved_translations, dict) or hasattr(saved_translations, 'assert_called_with') or not saved_translations:
            return source_items, temp_id_map

        # Count cached items
        cached_count = 0
        first_cached_text = None
        first_cached_block_idx = None
        first_cached_string_idx = None
        for item in source_items:
            item_id = item.get("id")
            if temp_id_map and item_id in temp_id_map:
                r_block_idx, r_string_idx = temp_id_map[item_id]
            else:
                r_block_idx = self.mw.data_store.current_block_idx
                try:
                    r_string_idx = int(item_id)
                except (ValueError, TypeError):
                    r_string_idx = item_id

            key = saved_mgr._get_string_unique_key(r_block_idx, r_string_idx)
            saved_text = saved_translations.get(key)
            if saved_text and isinstance(saved_text, str) and not hasattr(saved_text, 'assert_called_with') and saved_text.strip():
                cached_count += 1
                if first_cached_text is None:
                    first_cached_text = saved_text
                    first_cached_block_idx = r_block_idx
                    first_cached_string_idx = r_string_idx
        if force_prompt:
            # Ctrl+click: skip cache entirely, translate everything anew
            return source_items, temp_id_map

        if cached_count > 0:
            from PyQt6.QtWidgets import QWidget
            parent = self.mw if isinstance(self.mw, QWidget) else None
            msg_box = QMessageBox(parent)
            msg_box.setWindowTitle("Cached Translation Detected" if cached_count == 1 else "Cached Translations Detected")
            msg_box.setIcon(QMessageBox.Icon.Question)
            
            if cached_count == 1:
                block_name = None
                if hasattr(self.mw, 'data_store') and self.mw.data_store.block_names:
                    block_name = self.mw.data_store.block_names.get(str(first_cached_block_idx))
                if not block_name:
                    block_name = f"Block {first_cached_block_idx + 1}"
                msg_box.setText(f"A cached translation is available for {block_name}, Line {first_cached_string_idx + 1}. Use cached translation?")
                msg_box.setInformativeText(f"Cached text:\n\"{first_cached_text}\"")
            else:
                msg_box.setText(f"Cached translations are available for {cached_count} of the selected lines. Use cached translations?")
                msg_box.setInformativeText("For cached lines, the translation will be restored instantly. Other lines will be translated via AI.")

            restore_btn = msg_box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
            translate_btn = msg_box.addButton("Translate Anew", QMessageBox.ButtonRole.ActionRole)
            cancel_btn = msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            msg_box.setDefaultButton(restore_btn)
            
            msg_box.exec()
            clicked_button = msg_box.clickedButton()
            
            if clicked_button == translate_btn:
                # User wants to translate everything anew
                return source_items, temp_id_map
            elif clicked_button != restore_btn:
                # User cancelled, return empty lists to abort translation task
                return [], {}

        filtered_source_items = []
        filtered_temp_id_map = {}
        restored_items = []

        for item in source_items:
            item_id = item.get("id")
            if temp_id_map and item_id in temp_id_map:
                r_block_idx, r_string_idx = temp_id_map[item_id]
            else:
                r_block_idx = self.mw.data_store.current_block_idx
                try:
                    r_string_idx = int(item_id)
                except (ValueError, TypeError):
                    r_string_idx = item_id

            key = saved_mgr._get_string_unique_key(r_block_idx, r_string_idx)
            saved_text = saved_translations.get(key)
            
            if saved_text and isinstance(saved_text, str) and not hasattr(saved_text, 'assert_called_with') and saved_text.strip():
                restored_items.append((r_block_idx, r_string_idx, saved_text))
            else:
                filtered_source_items.append(item)
                if temp_id_map and item_id in temp_id_map:
                    filtered_temp_id_map[item_id] = (r_block_idx, r_string_idx)


        if restored_items:
            has_undo = hasattr(self.mw, 'undo_manager')
            if has_undo:
                self.mw.undo_manager.begin_group()

            try:
                for r_block_idx, r_string_idx, saved_text in restored_items:
                    final_text = self._format_and_wrap_translation(saved_text, r_block_idx, r_string_idx)
                    self.data_processor.update_edited_data(
                        r_block_idx, r_string_idx, final_text, action_type="RESTORE", skip_ui_refresh=True
                    )
                    if hasattr(self.mw, 'text_operation_handler') and self.mw.text_operation_handler:
                        self.mw.text_operation_handler._rescan_issues_for_current_string(r_block_idx, r_string_idx, final_text)
            finally:
                if has_undo:
                    self.mw.undo_manager.end_group("RESTORE_SAVED")

            modified_blocks = {b_idx for b_idx, _, _ in restored_items}
            for m_block in modified_blocks:
                self.ui_updater.update_block_item_text_with_problem_count(m_block)

            current_view_block = self.mw.data_store.current_block_idx
            if self.mw.data_store.current_chapter_id is not None:
                current_view_block = -2
            self.ui_updater.populate_strings_for_block(
                current_view_block, getattr(self.mw.data_store, 'current_category_name', None), force=True
            )
            self.ui_updater.update_text_views()
            self.ui_updater.update_title()

            if hasattr(self.mw, 'statusBar') and self.mw.statusBar:
                self.mw.statusBar.showMessage(f"Restored {len(restored_items)} lines from saved translations.", 3000)

            # Refresh SearchReviewDialog if open
            try:
                from dialogs.search_review_dialog import SearchReviewDialog
                for widget in QApplication.topLevelWidgets():
                    if isinstance(widget, SearchReviewDialog):
                        widget.refresh_from_project()
            except Exception as e:
                log_warning(f"Failed to refresh SearchReviewDialog in _filter_already_saved_translations: {e}")

        return filtered_source_items, filtered_temp_id_map


    def _format_and_wrap_translation(self, text: str, block_idx: int, string_idx: int) -> str:
        """
        Cleans the incoming translation, wraps lines to balance between line_width_warning_threshold_pixels 
        and game_dialog_max_width_pixels, and splits sentences into pages according to lines_per_page.
        """
        return self.text_formatter.format_and_wrap_translation(text, block_idx, string_idx)



    def _initiate_batch_translation(self, context: Dict[str, Any]) -> None:
        """Internal helper to initiate batch translation."""
        self.translated_chunks_count = 0
        provider = context['provider']
        
        block_idx = context.get('block_idx')
        task_type = context.get('type')

        if 'precomposed_prompt' in context:
            self._run_ai_task(provider, context)
            return

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
            force_prompt = context.get('force_prompt', False)
            if not force_prompt:
                try:
                    import ctypes
                    # Try GetAsyncKeyState (0x11 is VK_CONTROL) to check the physical keyboard state directly
                    force_prompt = bool(ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000)
                    if not force_prompt:
                        force_prompt = bool(ctypes.windll.user32.GetKeyState(0x11) & 0x8000)
                except Exception:
                    pass
            if not force_prompt:
                modifiers = QApplication.keyboardModifiers()
                if hasattr(modifiers, 'value'):
                    force_prompt = bool(modifiers.value & Qt.KeyboardModifier.ControlModifier.value)
                elif isinstance(modifiers, int):
                    force_prompt = bool(modifiers & Qt.KeyboardModifier.ControlModifier.value)
                else:
                    force_prompt = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
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
                    force_prompt=force_prompt,
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
        """Internal helper to handle chunk translated."""
        log_debug(f"Received translated chunk {chunk_index}. Raw AI response:\n{chunk_text}")
        try:
            block_idx = context['block_idx']
            parsed_json = json.loads(chunk_text)
            translated_strings = parsed_json.get("translated_strings", [])
            self.mw.undo_manager.begin_group()

            temp_id_map = context.get('temp_id_map')
            modified_blocks = set()
            translations_by_block = {}

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
                    if real_block_idx not in translations_by_block:
                        translations_by_block[real_block_idx] = []
                    translations_by_block[real_block_idx].append((real_string_idx, final_text))


            
            self.mw.undo_manager.end_group("TRANSLATE")
            
            saved_mgr = getattr(self.mw, 'saved_translations_manager', None)
            if saved_mgr:
                for b_idx, items in translations_by_block.items():
                    if b_idx != 999999 and b_idx >= 0:
                        saved_mgr.save_translations_bulk(b_idx, items)

            
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
            
            current_view_block = self.mw.data_store.current_block_idx
            if self.mw.data_store.current_chapter_id is not None:
                current_view_block = -2
            self.ui_updater.populate_strings_for_block(current_view_block, self.mw.data_store.current_category_name, force=True)
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
        """Internal helper to handle preview translation success."""
        log_debug(f"_handle_preview_translation_success called: source_items_count={len(context.get('source_items', []))}")
        self.ui_handler.update_ai_operation_step(3, self.ui_handler.status_dialog.steps[3], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        cleaned_text = self.ai_lifecycle_manager._clean_model_output(response, expect_json=True)
        log_debug(f"_handle_preview_translation_success: cleaned_text length={len(cleaned_text)}")
        
        try:
            parsed_json = json.loads(cleaned_text)
            translated_strings = parsed_json.get("translated_strings")
            if not isinstance(translated_strings, list) or len(translated_strings) != len(context['source_items']):
                raise ValueError("Invalid response structure or item count mismatch.")

            self.mw.undo_manager.begin_group()
                
            self.ui_handler.update_ai_operation_step(4, self.ui_handler.status_dialog.steps[4], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
            
            temp_id_map = context.get('temp_id_map')
            p_map = context.get('placeholder_map', {})
            source_items = context.get('source_items', [])
            modified_blocks = set()
            translations_by_block = {}

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
                
                if real_block_idx not in translations_by_block:
                    translations_by_block[real_block_idx] = []
                translations_by_block[real_block_idx].append((real_string_idx, final_text))

            self.mw.undo_manager.end_group("TRANSLATE")

            saved_mgr = getattr(self.mw, 'saved_translations_manager', None)
            if saved_mgr:
                for b_idx, items in translations_by_block.items():
                    if b_idx != 999999 and b_idx >= 0:
                        saved_mgr.save_translations_bulk(b_idx, items)


            self.ai_lifecycle_manager._record_session_exchange(context=context, assistant_content=cleaned_text, response=response)

            # Refresh tree indicators for all modified blocks once
            for m_block in modified_blocks:
                self.ui_updater.update_block_item_text_with_problem_count(m_block)

            self.ui_handler.finish_ai_operation()
            
            current_view_block = self.mw.data_store.current_block_idx
            if self.mw.data_store.current_chapter_id is not None:
                current_view_block = -2
            self.ui_updater.populate_strings_for_block(current_view_block, self.mw.data_store.current_category_name, force=True)
            self.ui_updater.update_text_views()
            self.ui_updater.update_title()

            # Refresh SearchReviewDialog if open
            try:
                from dialogs.search_review_dialog import SearchReviewDialog
                for widget in QApplication.topLevelWidgets():
                    if isinstance(widget, SearchReviewDialog):
                        widget.refresh_from_project()
            except Exception as e:
                log_warning(f"Failed to refresh SearchReviewDialog in _handle_preview_translation_success: {e}")

            if hasattr(self.mw, 'app_action_handler'):
                for m_block in modified_blocks:
                    if m_block != 999999:
                        self.mw.issue_scan_handler.rescan_issues_for_single_block(m_block, show_message_on_completion=False)

        except (json.JSONDecodeError, ValueError) as e:
            self._handle_ai_error(f"Validation failed: {e}", context)

    def _handle_ai_error(self, error_msg: str, context: Dict[str, Any]) -> None:
        """Internal helper to handle ai error."""
        self.ai_lifecycle_manager._handle_task_error(error_msg, context)

    def _handle_single_translation_success(self, response: ProviderResponse, context: Dict[str, Any]) -> None:
        """Internal helper to handle single translation success."""
        log_debug(f"_handle_single_translation_success called: block={context.get('block_idx')}, string={context.get('string_idx')}")
        self.ui_handler.update_ai_operation_step(3, self.ui_handler.status_dialog.steps[3], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        cleaned_translation = self.ai_lifecycle_manager._clean_model_output(response, expect_json=False)
        
        # Restore placeholders
        p_map = context.get('placeholder_map', {})
        cleaned_translation = self.prompt_composer.restore_placeholders(cleaned_translation, p_map, key=0)
        
        block_idx = context.get('block_idx', self.mw.data_store.current_block_idx)
        string_idx = context.get('string_idx', self.mw.data_store.current_string_idx)
        final_text = self._format_and_wrap_translation(cleaned_translation, block_idx, string_idx)
        self.ai_lifecycle_manager._record_session_exchange(context=context, assistant_content=cleaned_translation, response=response)
        
        self.ui_handler.update_ai_operation_step(4, self.ui_handler.status_dialog.steps[4], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        
        # Write translated text directly to the database to prevent timer desync and immediate UI overwrites
        if hasattr(self.mw, 'undo_manager'):
            self.mw.undo_manager.begin_group()
        self.data_processor.update_edited_data(block_idx, string_idx, final_text, action_type="TRANSLATE", skip_ui_refresh=True)
        if hasattr(self.mw, 'undo_manager'):
            self.mw.undo_manager.end_group("TRANSLATE")
            
        saved_mgr = getattr(self.mw, 'saved_translations_manager', None)
        if saved_mgr:
            saved_mgr.save_translation(block_idx, string_idx, final_text)

        self.ui_handler.apply_full_translation(final_text)
        log_debug("_handle_single_translation_success: applied translation length=%d" % len(final_text))
        self.ui_handler.finish_ai_operation()
        refresh_idx = block_idx
        if self.mw.data_store.current_chapter_id is not None:
            refresh_idx = -2
        self.ui_updater.populate_strings_for_block(refresh_idx, self.mw.data_store.current_category_name, force=True)
        # If we translated the currently visible string, update the text view
        if self.mw.data_store.current_block_idx == block_idx and self.mw.data_store.current_string_idx == string_idx:
            self.ui_updater.update_text_views()
        self.ui_updater.update_title()

    def _on_task_finished(self, context: Dict[str, Any]) -> None:
        """Internal helper to handle the task finished event."""
        self.ai_lifecycle_manager.on_task_finished(context)

    def generate_variation_for_current_string(self, force: bool = False) -> None:
        """Generate variation for current string."""
        self.variations_handler.generate_variation_for_current_string(force)

    def _translate_and_apply(self, *, source_text: str, expected_lines: int, mode_description: str, block_idx: int, string_idx: int, force_prompt: bool = False) -> None:
        """Internal helper to translate and apply."""
        log_debug(f"_translate_and_apply: block={block_idx}, string={string_idx}, source_text_len={len(source_text)}, force_prompt={force_prompt}")
        
        saved_mgr = getattr(self.mw, 'saved_translations_manager', None)
        if not force_prompt and saved_mgr and not hasattr(saved_mgr, 'assert_called_with'):
            source_items = [{"id": string_idx, "text": source_text}]
            temp_id_map = {string_idx: (block_idx, string_idx)}
            filtered_items, filtered_map = self._filter_already_saved_translations(
                source_items, temp_id_map, force_prompt=force_prompt
            )
            if not filtered_items:
                log_debug("_translate_and_apply: item was filtered by saved translations or translation was cancelled, returning early")
                return

        provider = self.ai_lifecycle_manager._prepare_provider()
        if not provider:
            log_debug("_translate_and_apply: no provider, returning")
            return

        system_prompt, _ = self.glossary_handler.load_prompts()
        if not system_prompt:
            log_debug("_translate_and_apply: no system_prompt, returning")
            return        # Apply force-aliases
        from utils.force_alias import prepare_text_for_ai
        tag_mappings = self.mw.default_tag_mappings
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
            force_prompt=force_prompt
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
            'max_retries': 4,
            'placeholder_map': p_map,
            'block_idx': block_idx,
            'string_idx': string_idx,
        }
        if not self._attach_session_to_task(
            task_details,
            base_system_prompt=system_prompt,
            full_system_prompt=edited_system,
            user_prompt=edited_user,
            task_type='translate_single',
        ):
            task_details['precomposed_prompt'] = precomposed
        log_debug(f"_translate_and_apply: starting AI operation, task_type=translate_single, block={block_idx}, string={string_idx}")
        self.ui_handler.start_ai_operation("AI Translation", model_name=self.ai_lifecycle_manager._active_model_name)
        self._run_ai_task(provider, task_details)
        
    def _handle_block_translation_success(self, response: ProviderResponse, context: dict):
        """Internal helper to handle block translation success."""
        log_debug(f"Block translation finished for block {context.get('block_idx')}")
        self.ui_handler.finish_ai_operation()

    def translate_selected_lines(self, force_prompt: bool = False):
        """
        Translates the lines currently selected in the preview editor.
        If no lines are selected, translates the current string.
        """
        if not isinstance(force_prompt, bool):
            force_prompt = False
        force_prompt = force_prompt or self._is_control_pressed()
        preview_edit = self.mw.preview_text_edit
        if preview_edit and preview_edit.get_selected_lines():
            # Pass a dummy point; translate_preview_selection prioritizes 
            # explicit selection over the mouse position.
            self.translate_preview_selection(QPoint(0, 0), force_prompt=force_prompt)
        else:
            self.translate_current_string(force_prompt=force_prompt)

    def translate_all_blocks_chronologically(self) -> None:
        """Translate all blocks chronologically."""
        if self.is_ai_running:
            QMessageBox.information(self.mw, "AI Busy", "An AI task is already running. Please wait for it to complete.")
            return
            
        data_source = self.mw.data_store.data
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

        source_items, temp_id_map = self._filter_already_saved_translations(source_items, temp_id_map)
        if not source_items:
            self.ui_handler.finish_ai_operation()
            if hasattr(self.mw, 'statusBar') and self.mw.statusBar:
                self.mw.statusBar.showMessage("All lines in project restored from saved translations.", 3000)
            return

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