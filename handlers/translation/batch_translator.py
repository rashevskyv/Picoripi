# handlers/translation/batch_translator.py

import json
from typing import Any, Dict, List, Tuple

from PyQt6.QtWidgets import QApplication

from .base_translation_handler import BaseTranslationHandler
from core.translation.providers import BaseTranslationProvider, ProviderResponse, GeminiProvider
from dialogs.cached_translation_dialog import CachedTranslationDialog
from utils.logging_utils import log_debug, log_warning
from utils.utils import is_control_modifier_pressed
from core.translation.layout_contract import (
    editor_text_for_layout,
    resolve_lines_per_window,
    validate_translation_layout,
)


class AIBatchTranslator(BaseTranslationHandler):
    """Handler for batch and chunked translation operations."""

    @staticmethod
    def _translation_value(item: Dict[str, Any]) -> str:
        for key in ("translation", "text", "translated_text"):
            if key in item and item[key] is not None:
                return str(item[key])
        return ""

    def _validate_batch_layouts(
        self,
        translated_strings,
        source_items,
        placeholder_map,
        temp_id_map=None,
        block_idx=None,
    ):
        if not isinstance(translated_strings, list) or len(translated_strings) != len(source_items):
            raise ValueError("Invalid response structure or item count mismatch.")
        validated = []
        rules = getattr(self.mw, "current_game_rules", None)
        for index, (result, source_item) in enumerate(zip(translated_strings, source_items)):
            if not isinstance(result, dict):
                raise ValueError(f"Translation result #{index} is not an object.")
            source_id = source_item.get("id") if isinstance(source_item, dict) else index
            source_text = source_item.get("text", "") if isinstance(source_item, dict) else str(source_item)
            translated = self._translation_value(result)
            translated = self.main_handler.prompt_composer.restore_placeholders(
                translated, placeholder_map, key=source_id
            )
            source_editor_text = editor_text_for_layout(source_text, rules)
            real_block_idx, real_string_idx = block_idx, source_id
            if temp_id_map and source_id in temp_id_map:
                real_block_idx, real_string_idx = temp_id_map[source_id]
            elif temp_id_map and str(source_id) in temp_id_map:
                real_block_idx, real_string_idx = temp_id_map[str(source_id)]
            validated.append(validate_translation_layout(
                source_editor_text,
                translated,
                resolve_lines_per_window(
                    self.mw, real_block_idx, real_string_idx
                ),
                allow_line_expansion=True,
            ))
        return validated

    def _cached_translation_matches_layout(
        self,
        source_item: Dict[str, Any],
        saved_text: str,
        block_idx: int,
        string_idx: int,
    ) -> bool:
        rules = getattr(self.mw, "current_game_rules", None)
        source_editor = editor_text_for_layout(source_item.get("text", ""), rules)
        saved_editor = editor_text_for_layout(saved_text, rules)
        lines_per_window = resolve_lines_per_window(
            self.mw, block_idx, string_idx
        )
        try:
            validate_translation_layout(
                source_editor,
                saved_editor,
                lines_per_window,
                allow_line_expansion=True,
            )
        except ValueError:
            return False
        return True

    def _extract_single_translation(self, response: ProviderResponse) -> str:
        cleaned = self.main_handler.ai_lifecycle_manager._clean_model_output(
            response, expect_json=True
        )
        try:
            payload = json.loads(cleaned)
            if isinstance(payload, dict) and isinstance(payload.get("translation"), str):
                return payload["translation"]
        except (json.JSONDecodeError, TypeError):
            pass
        # Backward compatibility with cached/older plain-text responses.
        return self.main_handler.ai_lifecycle_manager._clean_model_output(
            response, expect_json=False
        )

    def _resolve_base_timeout(self, provider: BaseTranslationProvider) -> int:
        """Resolve base timeout based on the active provider."""
        settings = getattr(provider, 'settings', None)
        if isinstance(settings, dict) and 'timeout' in settings:
            try:
                return max(int(settings['timeout']), 30)
            except (ValueError, TypeError):
                pass

        # For Gemini, default to a much higher timeout (180s) to avoid client-side timeouts during heavy block requests.
        base = 180 if isinstance(provider, GeminiProvider) else 90
        config = getattr(self.mw, 'translation_config', None)
        if config and isinstance(config, dict):
            provider_key = config.get('provider')
            if provider_key:
                provider_settings = config.get('providers', {}).get(provider_key, {})
                if isinstance(provider_settings, dict) and 'timeout' in provider_settings:
                    try:
                        return max(int(provider_settings['timeout']), 30)
                    except (ValueError, TypeError):
                        pass
        return max(base, 30)

    def filter_already_saved_translations(
        self, source_items: List[Dict[str, Any]], temp_id_map: Dict[Any, Tuple[int, int]], force_prompt: bool = False
    ) -> Tuple[List[Dict[str, Any]], Dict[Any, Tuple[int, int]]]:
        """
        Filters out items that already have a saved translation in SavedTranslationsManager.
        Applies those saved translations immediately to the database and refreshes the UI.
        Returns the remaining source items and their corresponding temp_id_map.
        """
        saved_mgr = getattr(self.mw, 'saved_translations_manager', None)
        if not saved_mgr:
            return source_items, temp_id_map

        saved_translations = saved_mgr.load_all_saved_translations()
        if not isinstance(saved_translations, dict) or not saved_translations:
            return source_items, temp_id_map

        # Collect cached items info
        cached_items_info = []
        for item in source_items:
            item_id = item.get("id")
            if temp_id_map and item_id in temp_id_map:
                r_block_idx, r_string_idx = temp_id_map[item_id]
            else:
                r_block_idx = self.mw.data_store.physical_block_idx
                try:
                    r_string_idx = int(item_id)
                except (ValueError, TypeError):
                    r_string_idx = item_id

            key = saved_mgr._get_string_unique_key(r_block_idx, r_string_idx)
            saved_text = saved_translations.get(key)
            if (
                saved_text
                and isinstance(saved_text, str)
                and saved_text.strip()
                and self._cached_translation_matches_layout(
                    item, saved_text, r_block_idx, r_string_idx
                )
            ):
                block_name = None
                if hasattr(self.mw, 'data_store') and self.mw.data_store.block_names:
                    block_name = self.mw.data_store.block_names.get(str(r_block_idx))
                if not block_name:
                    block_name = f"Block {r_block_idx + 1}"
                cached_items_info.append({
                    'block_idx': r_block_idx,
                    'block_name': block_name,
                    'string_idx': r_string_idx,
                    'text': saved_text
                })

        if force_prompt:
            # Ctrl+click: skip cache entirely, translate everything anew
            return source_items, temp_id_map

        if cached_items_info:
            dialog = CachedTranslationDialog(self.mw, cached_items_info)
            res = dialog.exec()
            
            if res == 2:
                # User wants to translate everything anew (Translate Anew)
                return source_items, temp_id_map
            elif res != 1:
                # User cancelled or closed the dialog (Cancel)
                return [], {}

        filtered_source_items = []
        filtered_temp_id_map = {}
        restored_items = []

        for item in source_items:
            item_id = item.get("id")
            if temp_id_map and item_id in temp_id_map:
                r_block_idx, r_string_idx = temp_id_map[item_id]
            else:
                r_block_idx = self.mw.data_store.physical_block_idx
                try:
                    r_string_idx = int(item_id)
                except (ValueError, TypeError):
                    r_string_idx = item_id

            key = saved_mgr._get_string_unique_key(r_block_idx, r_string_idx)
            saved_text = saved_translations.get(key)
            
            if (
                saved_text
                and isinstance(saved_text, str)
                and saved_text.strip()
                and self._cached_translation_matches_layout(
                    item, saved_text, r_block_idx, r_string_idx
                )
            ):
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
                    final_text = self.main_handler._convert_translation_preserving_layout(saved_text)
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

            self.ui_updater.populate_current_view(force=True)
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
                log_warning(f"Failed to refresh SearchReviewDialog in filter_already_saved_translations: {e}")

        return filtered_source_items, filtered_temp_id_map

    def initiate_batch_translation(self, context: Dict[str, Any]) -> None:
        """Internal helper to initiate batch translation."""
        self.main_handler.translated_chunks_count = 0
        provider = context['provider']
        
        block_idx = context.get('block_idx')
        task_type = context.get('type')
        if 'workers' not in context:
            cfg = getattr(self.mw, 'translation_config', {}) or {}
            context['workers'] = int(cfg.get('workers', 6) or 6)

        if 'precomposed_prompt' in context:
            self.main_handler._run_ai_task(provider, context)
            return

        if task_type == 'translate_block_chunked' and block_idx is not None:
            if not context.get('is_resume', False):
                self.main_handler.reset_translation_session()
                self.main_handler.translation_progress[block_idx] = {
                    'completed_chunks': set(),
                    'total_chunks': 0,
                    'source_items': context.get('source_items', []),
                    'temp_id_map': context.get('temp_id_map', {})
                }
            
            context['chunks_to_skip'] = self.main_handler.translation_progress.get(block_idx, {}).get('completed_chunks', set())

        system_prompt, _ = self.main_handler.glossary_handler.load_prompts()
        if not system_prompt:
            self.main_handler.ui_handler.finish_ai_operation()
            return

        if context.get('system_prompt_override'):
            system_prompt = context['system_prompt_override']

        session_state = self.main_handler._session_manager.get_state()
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
            force_prompt = context.get('force_prompt', False) or is_control_modifier_pressed()
            should_edit_prompt = (
                task_type == 'translate_block_chunked'
                and block_idx is not None
                and (force_prompt or not context.get('is_resume', False))
            )
            if should_edit_prompt:
                preview_system, preview_user, _ = self.main_handler.prompt_composer.compose_batch_request(**composer_args)
                title = "AI Block Translation Prompt"
                if context.get('mode_description'):
                    desc = context['mode_description']
                    if "block" not in desc.lower() and "chapter" not in desc.lower():
                        title = f"AI Translation Prompt ({desc})"
                    elif "chapter" in desc.lower():
                        title = "AI Chapter Translation Prompt"

                edited = self.main_handler._maybe_edit_prompt(
                    title=title,
                    system_prompt=preview_system,
                    user_prompt=preview_user,
                    save_section='translation',
                    force_prompt=force_prompt,
                )
                if edited is None:
                    self.main_handler.ui_handler.finish_ai_operation()
                    if block_idx is not None and not context.get('is_resume', False):
                        self.main_handler.translation_progress.pop(block_idx, None)
                        self.main_handler.pre_translation_state.pop(block_idx, None)
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
                    progress_entry = self.main_handler.translation_progress.setdefault(block_idx, {'completed_chunks': set(), 'total_chunks': 0})
                    progress_entry['custom_user_header'] = context['custom_user_header']
                    progress_entry['custom_user_label'] = context['custom_user_label']
                    progress_entry['system_prompt_override'] = edited_system
        
        if task_type == 'translate_block_chunked' and block_idx is not None:
            self.main_handler.save_progress_to_metadata(block_idx)

        final_system_prompt = context['composer_args']['system_prompt']
        context['composer_args']['all_source_items'] = context['source_items']
        final_user_prompt, _, p_map = self.main_handler.prompt_composer.compose_batch_request(**context['composer_args'])
        context['placeholder_map'] = p_map 

        if not self.main_handler._attach_session_to_task(
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
        
        self.main_handler._run_ai_task(provider, context)

    def handle_chunk_translated(self, chunk_index: int, chunk_text: str, context: Dict[str, Any]) -> None:
        """Internal helper to handle chunk translated."""
        log_debug(f"Received translated chunk {chunk_index}. Raw AI response:\n{chunk_text}")
        try:
            block_idx = context['block_idx']
            parsed_json = json.loads(chunk_text)
            translated_strings = parsed_json.get("translated_strings", [])
            chunks = context.get('calculated_chunks')
            current_chunk = chunks[chunk_index] if (chunks and chunk_index < len(chunks)) else None
            source_items_for_chunk = current_chunk or context.get('source_items', [])
            validated_translations = self._validate_batch_layouts(
                translated_strings,
                source_items_for_chunk,
                context.get('placeholder_map', {}),
                context.get('temp_id_map'),
                block_idx,
            )
            self.mw.undo_manager.begin_group()

            temp_id_map = context.get('temp_id_map')
            modified_blocks = set()
            translations_by_block = {}

            # Retrieve calculated chunks for robust sequential mapping in case AI returns sequential/reordered IDs
            for idx_in_response, item in enumerate(translated_strings):
                temp_id = item.get("id")
                translated_text = validated_translations[idx_in_response]
                
                # 1. First, try to resolve real block/string indices using sequential order inside the chunk
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
                            real_block_idx = block_idx
                            real_string_idx = int(temp_id)
                            resolved = True
                        except (ValueError, TypeError):
                            pass

                if resolved:
                    modified_blocks.add(real_block_idx)
                    final_text = self.main_handler._convert_translation_preserving_layout(translated_text)
                    
                    # Track previous translation if it was already translated
                    if self.data_processor.is_string_translated(real_block_idx, real_string_idx):
                        res = self.data_processor.get_current_string_text(real_block_idx, real_string_idx)
                        if isinstance(res, tuple) and len(res) == 2:
                            old_val, _ = res
                            if not hasattr(self.main_handler, 'current_session_previous_translations') or self.main_handler.current_session_previous_translations is None:
                                self.main_handler.current_session_previous_translations = {}
                            if real_block_idx not in self.main_handler.current_session_previous_translations:
                                self.main_handler.current_session_previous_translations[real_block_idx] = []
                            self.main_handler.current_session_previous_translations[real_block_idx].append((real_string_idx, old_val))
                    else:
                        self.data_processor.update_edited_data(real_block_idx, real_string_idx, final_text, action_type="TRANSLATE", skip_ui_refresh=True)
                        if real_block_idx not in translations_by_block:
                            translations_by_block[real_block_idx] = []
                        translations_by_block[real_block_idx].append((real_string_idx, final_text))
                    
                    if not hasattr(self.main_handler, 'current_session_translations') or self.main_handler.current_session_translations is None:
                        self.main_handler.current_session_translations = {}
                    if real_block_idx not in self.main_handler.current_session_translations:
                        self.main_handler.current_session_translations[real_block_idx] = []
                    self.main_handler.current_session_translations[real_block_idx].append((real_string_idx, final_text))

            self.mw.undo_manager.end_group("TRANSLATE")
            
            saved_mgr = getattr(self.mw, 'saved_translations_manager', None)
            if saved_mgr:
                for b_idx, items in translations_by_block.items():
                    if b_idx != 999999 and b_idx >= 0:
                        saved_mgr.save_translations_bulk(b_idx, items)

            if block_idx == -2:
                modified_blocks.add(-2)

            if block_idx in self.main_handler.translation_progress:
                self.main_handler.translation_progress[block_idx]['completed_chunks'].add(chunk_index)
                self.main_handler.save_progress_to_metadata(block_idx)

            # Refresh tree indicators for all modified blocks once
            for m_block in modified_blocks:
                self.ui_updater.update_block_item_text_with_problem_count(m_block)

            self.ui_updater.update_title()
            
            self.main_handler.ai_lifecycle_manager._record_session_exchange(context=context, assistant_content=chunk_text)
            
            self.ui_updater.populate_current_view(force=True)
            self.main_handler.translated_chunks_count = len(self.main_handler.translation_progress.get(block_idx, {}).get('completed_chunks', set()))
            self.main_handler.ui_handler.status_dialog.update_progress(self.main_handler.translated_chunks_count)
            
            total_chunks = self.main_handler.translation_progress.get(block_idx, {}).get('total_chunks', -1)
            if total_chunks != -1 and self.main_handler.translated_chunks_count == total_chunks:
                previous_details = getattr(self.main_handler, 'current_session_previous_translations', None)
                self.main_handler.ui_handler.finish_ai_operation(
                    translation_details=self.main_handler.current_session_translations,
                    previous_translations=previous_details
                )
                self.ui_updater.update_text_views()
                if hasattr(self.mw, 'app_action_handler'):
                    for m_block in modified_blocks:
                        if m_block != 999999 and m_block >= 0:
                            self.mw.issue_scan_handler.rescan_issues_for_single_block(m_block, show_message_on_completion=False)
                
                if block_idx == -2:
                    if -2 in self.main_handler.translation_progress:
                        del self.main_handler.translation_progress[-2]
                    temp_id_map = context.get('temp_id_map', {})
                    modified_blocks_for_cleanup = {b_idx for b_idx, _ in temp_id_map.values()}
                    for b_idx in modified_blocks_for_cleanup:
                        if b_idx in self.main_handler.pre_translation_state:
                            del self.main_handler.pre_translation_state[b_idx]
                    if -2 in self.main_handler.pre_translation_state:
                        del self.main_handler.pre_translation_state[-2]
                else:
                    if block_idx in self.main_handler.translation_progress:
                        del self.main_handler.translation_progress[block_idx]
                        self.main_handler.save_progress_to_metadata(block_idx)
                    if block_idx in self.main_handler.pre_translation_state:
                        del self.main_handler.pre_translation_state[block_idx]
                
        except (json.JSONDecodeError, ValueError) as e:
            self.main_handler._handle_ai_error(f"Failed to process chunk {chunk_index + 1}: {e}", context)

    def handle_preview_translation_success(self, response: ProviderResponse, context: Dict[str, Any]) -> None:
        """Internal helper to handle preview translation success."""
        log_debug(f"handle_preview_translation_success called: source_items_count={len(context.get('source_items', []))}")
        self.main_handler.ui_handler.update_ai_operation_step(3, self.main_handler.ui_handler.status_dialog.steps[3], self.main_handler.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        cleaned_text = self.main_handler.ai_lifecycle_manager._clean_model_output(response, expect_json=True)
        log_debug(f"handle_preview_translation_success: cleaned_text length={len(cleaned_text)}")
        
        try:
            parsed_json = json.loads(cleaned_text)
            translated_strings = parsed_json.get("translated_strings")
            source_items = context.get('source_items', [])
            validated_translations = self._validate_batch_layouts(
                translated_strings,
                source_items,
                context.get('placeholder_map', {}),
                context.get('temp_id_map'),
                context.get('block_idx'),
            )

            self.mw.undo_manager.begin_group()
                
            self.main_handler.ui_handler.update_ai_operation_step(4, self.main_handler.ui_handler.status_dialog.steps[4], self.main_handler.ui_handler.status_dialog.STATUS_IN_PROGRESS)
            
            temp_id_map = context.get('temp_id_map')
            modified_blocks = set()
            translations_by_block = {}

            for idx_in_response, item in enumerate(translated_strings):
                temp_id = item.get("id")
                translated_text = validated_translations[idx_in_response]
                
                resolved_orig_id = None
                if idx_in_response < len(source_items):
                    orig_item = source_items[idx_in_response]
                    if isinstance(orig_item, dict):
                        resolved_orig_id = orig_item.get('id')
                
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
                final_text = self.main_handler._convert_translation_preserving_layout(translated_text)
                
                if not hasattr(self.main_handler, 'current_session_translations') or self.main_handler.current_session_translations is None:
                    self.main_handler.current_session_translations = {}
                if real_block_idx not in self.main_handler.current_session_translations:
                    self.main_handler.current_session_translations[real_block_idx] = []
                self.main_handler.current_session_translations[real_block_idx].append((real_string_idx, final_text))

                # Track previous translation if it was already translated
                if self.data_processor.is_string_translated(real_block_idx, real_string_idx):
                    res = self.data_processor.get_current_string_text(real_block_idx, real_string_idx)
                    if isinstance(res, tuple) and len(res) == 2:
                        old_val, _ = res
                        if not hasattr(self.main_handler, 'current_session_previous_translations') or self.main_handler.current_session_previous_translations is None:
                            self.main_handler.current_session_previous_translations = {}
                        if real_block_idx not in self.main_handler.current_session_previous_translations:
                            self.main_handler.current_session_previous_translations[real_block_idx] = []
                        self.main_handler.current_session_previous_translations[real_block_idx].append((real_string_idx, old_val))
                else:
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

            self.main_handler.ai_lifecycle_manager._record_session_exchange(context=context, assistant_content=cleaned_text, response=response)

            # Refresh tree indicators for all modified blocks once
            for m_block in modified_blocks:
                self.ui_updater.update_block_item_text_with_problem_count(m_block)

            previous_details = getattr(self.main_handler, 'current_session_previous_translations', None)
            self.main_handler.ui_handler.finish_ai_operation(
                translation_details=self.main_handler.current_session_translations,
                previous_translations=previous_details
            )
            
            self.ui_updater.populate_current_view(force=True)
            self.ui_updater.update_text_views()
            self.ui_updater.update_title()

            # Refresh SearchReviewDialog if open
            try:
                from dialogs.search_review_dialog import SearchReviewDialog
                for widget in QApplication.topLevelWidgets():
                    if isinstance(widget, SearchReviewDialog):
                        widget.refresh_from_project()
            except Exception as e:
                log_warning(f"Failed to refresh SearchReviewDialog in handle_preview_translation_success: {e}")

            if hasattr(self.mw, 'app_action_handler'):
                for m_block in modified_blocks:
                    if m_block != 999999:
                        self.mw.issue_scan_handler.rescan_issues_for_single_block(m_block, show_message_on_completion=False)

        except (json.JSONDecodeError, ValueError) as e:
            self.main_handler._handle_ai_error(f"Validation failed: {e}", context)

    def handle_single_translation_success(self, response: ProviderResponse, context: Dict[str, Any]) -> None:
        """Internal helper to handle single translation success."""
        log_debug(f"handle_single_translation_success called: block={context.get('block_idx')}, string={context.get('string_idx')}")
        self.main_handler.ui_handler.update_ai_operation_step(3, self.main_handler.ui_handler.status_dialog.steps[3], self.main_handler.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        cleaned_translation = self._extract_single_translation(response)
        
        # Restore placeholders
        p_map = context.get('placeholder_map', {})
        cleaned_translation = self.main_handler.prompt_composer.restore_placeholders(cleaned_translation, p_map, key=0)
        
        block_idx = context.get('block_idx', self.mw.data_store.physical_block_idx)
        string_idx = context.get('string_idx', self.mw.data_store.current_string_idx)
        source_text = (context.get('composer_args') or {}).get('source_text')
        if isinstance(source_text, str):
            try:
                source_editor = editor_text_for_layout(
                    source_text, getattr(self.mw, 'current_game_rules', None)
                )
                cleaned_translation = validate_translation_layout(
                    source_editor,
                    cleaned_translation,
                    resolve_lines_per_window(self.mw, block_idx, string_idx),
                    allow_line_expansion=True,
                )
            except ValueError as exc:
                self.main_handler._handle_ai_error(f"Validation failed: {exc}", context)
                return
        final_text = self.main_handler._convert_translation_preserving_layout(cleaned_translation)
        self.main_handler.ai_lifecycle_manager._record_session_exchange(context=context, assistant_content=cleaned_translation, response=response)
        
        self.main_handler.ui_handler.update_ai_operation_step(4, self.main_handler.ui_handler.status_dialog.steps[4], self.main_handler.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        
        if hasattr(self.mw, 'undo_manager'):
            self.mw.undo_manager.begin_group()
        self.data_processor.update_edited_data(block_idx, string_idx, final_text, action_type="TRANSLATE", skip_ui_refresh=True)
        if hasattr(self.mw, 'undo_manager'):
            self.mw.undo_manager.end_group("TRANSLATE")
            
        saved_mgr = getattr(self.mw, 'saved_translations_manager', None)
        if saved_mgr:
            saved_mgr.save_translation(block_idx, string_idx, final_text)

        self.main_handler.ui_handler.apply_full_translation(final_text)
        log_debug("handle_single_translation_success: applied translation length=%d" % len(final_text))
        self.main_handler.current_session_translations = {block_idx: [(string_idx, final_text)]}
        self.main_handler.ui_handler.finish_ai_operation(translation_details=self.main_handler.current_session_translations)
        self.ui_updater.populate_current_view(force=True)
        # If we translated the currently visible string, update the text view
        if self.mw.data_store.physical_block_idx == block_idx and self.mw.data_store.current_string_idx == string_idx:
            self.ui_updater.update_text_views()
        self.ui_updater.update_title()

    def handle_block_translation_success(self, response: ProviderResponse, context: dict) -> None:
        """Internal helper to handle block translation success."""
        log_debug(f"Block translation finished for block {context.get('block_idx')}")
        self.main_handler.ui_handler.finish_ai_operation()
