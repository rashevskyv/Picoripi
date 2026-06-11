# handlers/translation/ai_variations_handler.py

from typing import Any, Dict, List, Optional
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QMessageBox, QApplication

from .base_translation_handler import BaseTranslationHandler
from core.translation.providers import ProviderResponse
from utils.logging_utils import log_debug


class AIVariationsHandler(BaseTranslationHandler):
    def __init__(self, main_handler: Any):
        super().__init__(main_handler)
        self.variations_cache: Dict[tuple, Dict[str, Any]] = {}

    def _handle_variation_success(self, response: ProviderResponse, context: Dict[str, Any]) -> None:
        self.main_handler.ui_handler.update_ai_operation_step(
            3, 
            self.main_handler.ui_handler.status_dialog.steps[3], 
            self.main_handler.ui_handler.status_dialog.STATUS_IN_PROGRESS
        )
        cleaned = self.main_handler.ai_lifecycle_manager._clean_model_output(response, expect_json=True)
        self.main_handler.ai_lifecycle_manager._record_session_exchange(context=context, assistant_content=cleaned, response=response)
        variants_raw = self.main_handler.ui_handler.parse_variation_payload(cleaned)
        self.main_handler.ui_handler.finish_ai_operation(show_popup=False)

        if not variants_raw:
            QMessageBox.information(self.mw, "AI Variation", "Failed to parse variations from AI response.")
            return
            
        trimmed = [self.main_handler.ai_lifecycle_manager._trim_trailing_whitespace_from_lines(v) for v in variants_raw]
        
        # Restore placeholders
        p_map = context.get('placeholder_map', {})
        restored_variants = []
        for v in trimmed:
            restored_v = self.main_handler.prompt_composer.restore_placeholders(v, p_map, key=0)
            restored_variants.append(restored_v)
            
        # Cache the variations for the current string
        block_idx = self.mw.data_store.current_block_idx
        string_idx = self.mw.data_store.current_string_idx
        current_translation, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        self.variations_cache[(block_idx, string_idx)] = {
            'variants': restored_variants,
            'translation': str(current_translation)
        }

        chosen = self.main_handler.ui_handler.show_variations_dialog(restored_variants, show_refresh=True)
        if chosen == "__REFRESH__":
            QTimer.singleShot(100, lambda: self.generate_variation_for_current_string(force=True))
            return
        if chosen:
            self._apply_chosen_variation(chosen, context.get('is_inline', False), target_block_idx=block_idx, target_string_idx=string_idx)

    def _apply_chosen_variation(self, chosen: str, is_inline: bool, target_block_idx: int, target_string_idx: int) -> None:
        final_text = self.main_handler._format_and_wrap_translation(chosen, target_block_idx, target_string_idx)
        
        # Write chosen variation directly to the database to prevent timer desync and immediate UI overwrites
        self.mw.undo_manager.begin_group()
        self.data_processor.update_edited_data(target_block_idx, target_string_idx, final_text, action_type="TRANSLATE", skip_ui_refresh=True)
        self.mw.undo_manager.end_group("TRANSLATE")
            
        if target_block_idx == self.mw.data_store.current_block_idx and target_string_idx == self.mw.data_store.current_string_idx:
            if is_inline:
                self.main_handler.ui_handler.apply_inline_variation(final_text)
            else:
                self.main_handler.ui_handler.apply_full_translation(final_text)
        else:
            self.ui_updater.populate_strings_for_block(target_block_idx, self.mw.data_store.current_category_name, force=True)

    def generate_variation_for_current_string(self, force: bool = False) -> None:
        if self.main_handler.is_ai_running:
            QMessageBox.information(self.mw, "AI Busy", "An AI task is already running. Please wait for it to complete.")
            return
        if self.mw.data_store.current_block_idx == -1 or self.mw.data_store.current_string_idx == -1: 
            return
            
        original_text = str(self.main_handler.glossary_handler._get_original_string(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx))
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
            chosen = self.main_handler.ui_handler.show_variations_dialog(restored_variants, show_refresh=True)
            if chosen == "__REFRESH__":
                QTimer.singleShot(100, lambda: self.generate_variation_for_current_string(force=True))
            elif chosen:
                self._apply_chosen_variation(chosen, is_inline=False, target_block_idx=block_idx, target_string_idx=string_idx)
            return
        
        provider = self.main_handler.ai_lifecycle_manager._prepare_provider()
        if not provider: 
            return

        system_prompt, _ = self.main_handler.glossary_handler.load_prompts()
        if not system_prompt:
            self.main_handler.ui_handler.finish_ai_operation()
            return
        
        # Apply force-aliases
        from utils.force_alias import prepare_text_for_ai
        tag_mappings = self.mw.default_tag_mappings
        original_text_for_ai, force_maps = prepare_text_for_ai(original_text, tag_mappings)
        p_map = {0: force_maps} if force_maps else {}

        session_state = self.main_handler._session_manager.get_state()
        composer_args = {
            'system_prompt': system_prompt,
            'source_text': original_text_for_ai,
            'block_idx': self.mw.data_store.current_block_idx, 
            'string_idx': self.mw.data_store.current_string_idx,
            'expected_lines': len(original_text.split('\n')), 
            'current_translation': str(current_translation),
            'request_type': 'variation_list',
            'session_state': session_state,
        }
        combined_system, user_prompt = self.main_handler.prompt_composer.compose_variation_request(**composer_args)
        edited = self.main_handler._maybe_edit_prompt(
            title="AI Variation Prompt",
            system_prompt=combined_system,
            user_prompt=user_prompt,
            save_section='translation',
        )
        if edited is None:
            return
        edited_system, edited_user = edited

        self.main_handler.ui_handler.start_ai_operation("AI Variation", model_name=self.main_handler.ai_lifecycle_manager._active_model_name)

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
        if not self.main_handler._attach_session_to_task(
            task_details,
            base_system_prompt=system_prompt,
            full_system_prompt=edited_system,
            user_prompt=edited_user,
            task_type='generate_variation',
        ):
            task_details['precomposed_prompt'] = precomposed
        
        self.main_handler._run_ai_task(provider, task_details)
