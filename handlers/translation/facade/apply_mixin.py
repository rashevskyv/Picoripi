"""Apply/format/batch helpers for TranslationHandler."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.translation.providers import BaseTranslationProvider, ProviderResponse
from utils.logging_utils import log_debug


class ApplyMixin:
    """Chunk timer, format/wrap, batch initiate, success/error, variation, _translate_and_apply."""

    def _on_chunk_timer_timeout(self) -> None:
        """Internal helper to handle the chunk timer timeout event."""
        pass # This method was likely intended to be implemented or removed.

    def _resolve_base_timeout(self, provider: BaseTranslationProvider) -> int:
        """Internal helper to resolve base timeout."""
        return self.batch_translator._resolve_base_timeout(provider)

    def _filter_already_saved_translations(
        self, source_items: List[Dict[str, Any]], temp_id_map: Dict[Any, Tuple[int, int]], force_prompt: bool = False
    ) -> Tuple[List[Dict[str, Any]], Dict[Any, Tuple[int, int]]]:
        """
        Filters out items that already have a saved translation in SavedTranslationsManager.
        Applies those saved translations immediately to the database and refreshes the UI.
        Returns the remaining source items and their corresponding temp_id_map.
        """
        return self.batch_translator.filter_already_saved_translations(source_items, temp_id_map, force_prompt)

    def _format_and_wrap_translation(self, text: str, block_idx: int, string_idx: int) -> str:
        """
        Cleans the incoming translation, wraps lines to balance between line_width_warning_threshold_pixels 
        and game_dialog_max_width_pixels, and splits sentences into pages according to lines_per_page.
        """
        return self.text_formatter.format_and_wrap_translation(text, block_idx, string_idx)

    def _convert_translation_preserving_layout(self, text: str) -> str:
        return self.text_formatter.convert_translation_preserving_layout(text)

    def _initiate_batch_translation(self, context: Dict[str, Any]) -> None:
        """Internal helper to initiate batch translation."""
        self.batch_translator.initiate_batch_translation(context)

    def _handle_chunk_translated(self, chunk_index: int, chunk_text: str, context: Dict[str, Any]) -> None:
        """Proxy helper to handle chunk translated."""
        self.batch_translator.handle_chunk_translated(chunk_index, chunk_text, context)

    def _handle_preview_translation_success(self, response: ProviderResponse, context: Dict[str, Any]) -> None:
        """Proxy helper to handle preview translation success."""
        self.batch_translator.handle_preview_translation_success(response, context)

    def _handle_ai_error(self, error_msg: str, context: Dict[str, Any]) -> None:
        """Internal helper to handle ai error."""
        self.ai_lifecycle_manager._handle_task_error(error_msg, context)

    def _handle_single_translation_success(self, response: ProviderResponse, context: Dict[str, Any]) -> None:
        """Internal helper to handle single translation success."""
        self.batch_translator.handle_single_translation_success(response, context)

    def _on_task_finished(self, context: Dict[str, Any]) -> None:
        """Internal helper to handle the task finished event."""
        self.ai_lifecycle_manager.on_task_finished(context)

    def generate_variation_for_current_string(self, force: bool = False, selected_text: Optional[str] = None) -> None:
        """Generate variation for current string."""
        self.variations_handler.generate_variation_for_current_string(force, selected_text)

    def _translate_and_apply(self, *, source_text: str, expected_lines: int, mode_description: str, block_idx: int, string_idx: int, force_prompt: bool = False) -> None:
        """Internal helper to translate and apply."""
        log_debug(f"_translate_and_apply: block={block_idx}, string={string_idx}, source_text_len={len(source_text)}, force_prompt={force_prompt}")
        
        saved_mgr = getattr(self.mw, 'saved_translations_manager', None)
        if not force_prompt and saved_mgr:
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
