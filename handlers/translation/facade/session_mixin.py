"""Provider/session/progress helpers for TranslationHandler."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from PyQt6.QtWidgets import QDialog, QMessageBox

from core.translation.providers import BaseTranslationProvider, GeminiProvider
from components.prompt_editor_dialog import PromptEditorDialog
from handlers.translation.prompt_composer.instructions import strip_engine_rules
from utils.logging_utils import log_debug
from utils.utils import is_control_modifier_pressed
from core.i18n import tr


class SessionMixin:
    """Provider/session/progress/cancel/revert."""

    def save_progress_to_metadata(self, block_idx: int) -> None:
        """Saves translation progress for a single block into the block's project metadata."""
        self.progress_manager.save_progress_to_metadata(block_idx)

    def load_progress_from_metadata(self) -> None:
        """Loads translation progress for all blocks from their project metadata."""
        self.progress_manager.load_progress_from_metadata()

    def _prepare_provider(self, provider_key_override: Optional[str] = None) -> Optional[BaseTranslationProvider]:
        """Internal helper to prepare provider."""
        return self.ai_lifecycle_manager._prepare_provider(provider_key_override)

    def reset_translation_session(self) -> None:
        """Reset translation session."""
        self._session_manager.reset()
        self._cached_system_prompt = None
        self._cached_glossary = None
        self.start_new_session = True
        self.current_session_translations = {}
        self.current_session_previous_translations = {}
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
        is_ctrl_pressed = force_prompt or is_control_modifier_pressed()
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
            # Save the user's prompt only: the rules the engine appended for this
            # kind of request would otherwise be frozen into every future prompt.
            prompt_to_save = strip_engine_rules(edited_system)
            if self.glossary_handler.save_prompt_section(save_section, save_field, prompt_to_save):
                if save_section == 'translation' and save_field == 'system_prompt':
                    self._cached_system_prompt = prompt_to_save
        return edited_system, edited_user

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
            tr('Translation Cancelled'),
            tr('Keep the already translated parts?'),
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
                
                self.ui_updater.populate_current_view(force=True)
                self.ui_updater.update_text_views()
            else:
                if block_idx in self.pre_translation_state:
                    original_texts = self.pre_translation_state[block_idx]
                    for i, text in enumerate(original_texts):
                        self.data_processor.update_edited_data(block_idx, i, text)
                    
                    del self.pre_translation_state[block_idx]

                if block_idx in self.translation_progress:
                    del self.translation_progress[block_idx]

                self.ui_updater.populate_current_view(force=True)
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
        return is_control_modifier_pressed()
