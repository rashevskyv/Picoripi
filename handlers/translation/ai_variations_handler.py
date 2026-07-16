# handlers/translation/ai_variations_handler.py

from typing import Any, Dict, List, Optional
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QMessageBox, QApplication

from .base_translation_handler import BaseTranslationHandler
from core.translation.providers import ProviderResponse
from utils.logging_utils import log_debug


class AIVariationsHandler(BaseTranslationHandler):
    """Handler for a i variations operations."""
    def __init__(self, main_handler: Any):
        """Initialize a new instance."""
        super().__init__(main_handler)
        self.variations_cache: Dict[tuple, Dict[str, Any]] = {}
        from PyQt6.QtCore import QObject
        timer_parent = self.mw if isinstance(self.mw, QObject) else None
        self._variation_refresh_timer = QTimer(timer_parent)
        self._variation_refresh_timer.setSingleShot(True)
        self._variation_refresh_timer.timeout.connect(self._on_variation_refresh_timer_timeout)
        self._pending_variation_refresh: Optional[Dict[str, Any]] = None

    def _is_qt_deleted(self, obj: Any) -> bool:
        try:
            from PyQt6 import sip
            from PyQt6.QtCore import QObject
            return isinstance(obj, QObject) and sip.isdeleted(obj)
        except (TypeError, RuntimeError):
            return True

    def _schedule_variation_refresh(
        self,
        block_idx: int,
        string_idx: int,
        *,
        on_success_callback: Optional[callable],
        parent: Optional[Any],
        selected_text: Optional[str],
    ) -> None:
        """Schedule a safe delayed variation refresh."""
        self._pending_variation_refresh = {
            'block_idx': block_idx,
            'string_idx': string_idx,
            'on_success_callback': on_success_callback,
            'parent': parent,
            'selected_text': selected_text,
        }
        self._variation_refresh_timer.start(100)

    def _on_variation_refresh_timer_timeout(self) -> None:
        """Run a delayed variation refresh if the owner widgets are still alive."""
        self._variation_refresh_timer.stop()
        pending = self._pending_variation_refresh
        self._pending_variation_refresh = None
        if not pending:
            return
        if not self.mw or self._is_qt_deleted(self.mw):
            return
        parent = pending.get('parent')
        if parent is not None and self._is_qt_deleted(parent):
            parent = None
        self.generate_variation_for_string(
            pending['block_idx'],
            pending['string_idx'],
            force=True,
            on_success_callback=pending.get('on_success_callback'),
            parent=parent,
            selected_text=pending.get('selected_text'),
        )

    def _handle_variation_success(self, response: ProviderResponse, context: Dict[str, Any]) -> None:
        """Internal helper to handle variation success."""
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
            
        # Get target indices from context
        block_idx = context.get('block_idx', self.mw.data_store.current_block_idx)
        string_idx = context.get('string_idx', self.mw.data_store.current_string_idx)
        on_success_callback = context.get('on_success_callback')
        parent_widget = context.get('parent')
        selected_text = context.get('selected_text')
        
        # Cache the variations for the target string
        current_translation, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        cache_key = (block_idx, string_idx, selected_text) if selected_text else (block_idx, string_idx)
        self.variations_cache[cache_key] = {
            'variants': restored_variants,
            'translation': str(current_translation)
        }

        chosen = self.main_handler.ui_handler.show_variations_dialog(restored_variants, show_refresh=True, parent=parent_widget)
        if chosen == "__REFRESH__":
            self._schedule_variation_refresh(
                block_idx,
                string_idx,
                on_success_callback=on_success_callback,
                parent=parent_widget,
                selected_text=selected_text,
            )
            return
        if chosen:
            if on_success_callback:
                on_success_callback(chosen)
            else:
                self._apply_chosen_variation(chosen, bool(selected_text) or context.get('is_inline', False), target_block_idx=block_idx, target_string_idx=string_idx)

    def _apply_chosen_variation(self, chosen: str, is_inline: bool, target_block_idx: int, target_string_idx: int) -> None:
        """Internal helper to apply chosen variation."""
        if is_inline:
            final_text = chosen
        else:
            final_text = self.main_handler._format_and_wrap_translation(chosen, target_block_idx, target_string_idx)
        
        self.mw.undo_manager.begin_group()
        try:
            if is_inline and target_block_idx == self.mw.data_store.current_block_idx and target_string_idx == self.mw.data_store.current_string_idx:
                # 1. Replace the selection in the editor first
                self.main_handler.ui_handler.apply_inline_variation(final_text)
                
                # 2. Get the new complete text from the editor and convert to data format
                edited_edit = getattr(self.mw, 'edited_text_edit', None)
                if edited_edit and self.mw.current_game_rules:
                    editor_text = edited_edit.toPlainText()
                    actual_text = self.mw.current_game_rules.convert_editor_text_to_data(editor_text)
                    from utils.utils import convert_dots_to_spaces_from_editor
                    actual_text_with_spaces = convert_dots_to_spaces_from_editor(actual_text)
                    
                    # 3. Write this complete text to database
                    self.data_processor.update_edited_data(target_block_idx, target_string_idx, actual_text_with_spaces, action_type="TRANSLATE", skip_ui_refresh=True)
                    
                    # 4. Trigger rescan of issues for the entire string
                    if hasattr(self.mw, 'editor_operation_handler') and self.mw.editor_operation_handler:
                        self.mw.editor_operation_handler._rescan_issues_for_current_string(target_block_idx, target_string_idx, actual_text_with_spaces)
            else:
                # Full line replacement (is_inline is False, or not currently active string)
                self.data_processor.update_edited_data(target_block_idx, target_string_idx, final_text, action_type="TRANSLATE", skip_ui_refresh=True)
                if target_block_idx == self.mw.data_store.current_block_idx and target_string_idx == self.mw.data_store.current_string_idx:
                    self.main_handler.ui_handler.apply_full_translation(final_text)
                else:
                    self.ui_updater.populate_current_view(force=True)
        finally:
            self.mw.undo_manager.end_group("TRANSLATE")


    def generate_variation_for_string(self, block_idx: int, string_idx: int, force: bool = False, on_success_callback: Optional[callable] = None, parent: Optional[Any] = None, selected_text: Optional[str] = None) -> None:
        """Generate variation for a specific string."""
        if self.main_handler.is_ai_running:
            QMessageBox.information(self.mw, "AI Busy", "An AI task is already running. Please wait for it to complete.")
            return
        if block_idx == -1 or string_idx == -1: 
            return
            
        original_text = str(self.main_handler.glossary_handler._get_original_string(block_idx, string_idx))
        current_translation, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        if not current_translation:
            QMessageBox.information(self.mw, "AI Variation", "There is no current translation to vary.")
            return

        # Check cache if not forced
        cache_key = (block_idx, string_idx, selected_text) if selected_text else (block_idx, string_idx)
        if not force and cache_key in self.variations_cache:
            cached = self.variations_cache[cache_key]
            restored_variants = cached.get('variants', [])
            chosen = self.main_handler.ui_handler.show_variations_dialog(restored_variants, show_refresh=True, parent=parent)
            if chosen == "__REFRESH__":
                self._schedule_variation_refresh(
                    block_idx,
                    string_idx,
                    on_success_callback=on_success_callback,
                    parent=parent,
                    selected_text=selected_text,
                )
            elif chosen:
                if on_success_callback:
                    on_success_callback(chosen)
                else:
                    self._apply_chosen_variation(chosen, is_inline=bool(selected_text), target_block_idx=block_idx, target_string_idx=string_idx)
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
        
        # If we have selected text, expected lines should be based on selected text, otherwise full string.
        expected_lines = len(selected_text.split('\n')) if selected_text else len(original_text.split('\n'))
        
        composer_args = {
            'system_prompt': system_prompt,
            'source_text': original_text_for_ai,
            'block_idx': block_idx, 
            'string_idx': string_idx,
            'expected_lines': expected_lines, 
            'current_translation': str(current_translation),
            'request_type': 'variation_list',
            'session_state': session_state,
            'selected_text': selected_text,
        }
        combined_system, user_prompt = self.main_handler.prompt_composer.compose_variation_request(**composer_args)
        edited = self.main_handler._maybe_edit_prompt(
            title="AI Variation Prompt",
            system_prompt=combined_system,
            user_prompt=user_prompt,
            save_section='translation',
            force_prompt=self.main_handler._is_control_pressed(),
        )
        if edited is None:
            return
        edited_system, edited_user = edited

        self.main_handler.ui_handler.start_ai_operation(
            "AI Variation", 
            model_name=self.main_handler.ai_lifecycle_manager._active_model_name,
            parent=parent
        )

        precomposed = [
            {"role": "system", "content": edited_system},
            {"role": "user", "content": edited_user},
        ]
        task_details = {
            'type': 'generate_variation',
            'is_inline': bool(selected_text),
            'composer_args': composer_args,
            'provider_settings_override': {'temperature': 0.7},
            'attempt': 1,
            'max_retries': 1,
            'placeholder_map': p_map,
            'block_idx': block_idx,
            'string_idx': string_idx,
            'on_success_callback': on_success_callback,
            'parent': parent,
            'selected_text': selected_text,
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

    def generate_variation_for_current_string(self, force: bool = False, selected_text: Optional[str] = None) -> None:
        """Generate variation for current string."""
        if not selected_text:
            edited_edit = getattr(self.mw, 'edited_text_edit', None)
            has_selection = False
            if edited_edit:
                try:
                    cursor = edited_edit.textCursor()
                    if cursor is not None and hasattr(cursor, 'hasSelection') and callable(cursor.hasSelection):
                        res_val = cursor.hasSelection()
                        if isinstance(res_val, bool):
                            has_selection = res_val
                except Exception:
                    pass
            
            if has_selection:
                selected_text = edited_edit.textCursor().selectedText().replace('\u2029', '\n')
            
        self.generate_variation_for_string(
            self.mw.data_store.current_block_idx,
            self.mw.data_store.current_string_idx,
            force=force,
            selected_text=selected_text
        )

