"""Translate entry points for TranslationHandler."""
from __future__ import annotations

from typing import List, Optional, Tuple

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QMessageBox

from utils.logging_utils import log_debug
from core.tag_utils import iter_all_strings
from core.i18n import tr


class TranslateMixin:
    """translate_current/specific/preview/block/resume/selected/all chrono."""

    def translate_current_string(self, force_prompt: bool = False) -> None:
        """Translate current string."""
        if not isinstance(force_prompt, bool):
            force_prompt = False
        is_ctrl = force_prompt or self._is_control_pressed()
        log_debug(f"translate_current_string called: is_ai_running={self.is_ai_running}, block={self.mw.data_store.physical_block_idx}, string={self.mw.data_store.current_string_idx}, force_prompt={is_ctrl}")
        if self.is_ai_running:
            QMessageBox.information(self.mw, tr('AI Busy'), tr('An AI task is already running. Please wait for it to complete.'))
            return
        if self.mw.data_store.physical_block_idx == -1 or self.mw.data_store.current_string_idx == -1: return
        source_text = str(self.glossary_handler._get_original_string(
            self.mw.data_store.physical_block_idx,
            self.mw.data_store.current_string_idx,
        ))
        from core.translation.layout_contract import editor_text_for_layout
        source_editor = editor_text_for_layout(
            source_text, getattr(self.mw, 'current_game_rules', None)
        )
        self._translate_and_apply(
            source_text=source_text,
            expected_lines=len(source_editor.split("\n")),
            mode_description="current row",
            block_idx=self.mw.data_store.physical_block_idx,
            string_idx=self.mw.data_store.current_string_idx,
            force_prompt=is_ctrl
        )

    def translate_specific_strings(self, pairs: List[Tuple[int, int]], description: str, force_prompt: bool = False) -> None:
        """Translate a specific list of (block_idx, string_idx) pairs."""
        if not isinstance(force_prompt, bool):
            force_prompt = False
        force_prompt = force_prompt or self._is_control_pressed()

        if self.is_ai_running:
            QMessageBox.information(self.mw, tr('AI Busy'), tr('An AI task is already running. Please wait for it to complete.'))
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
        first_block_idx = pairs[0][0] if pairs else self.mw.data_store.physical_block_idx
        
        system_prompt, _ = self.glossary_handler.load_prompts()
        if not system_prompt:
            return

        # Determine if we should use chunked translation for large selections (> 12 items)
        is_chunked = len(source_items) > 12

        if is_chunked:
            block_timeout = 180
            
            self.ui_handler.start_ai_operation(operation_title, is_chunked=True, model_name=self.ai_lifecycle_manager._active_model_name)
            from components.ai_status_dialog import AIStatusDialog
            self.ui_handler.update_ai_operation_step(0, "Preparing data...", AIStatusDialog.STATUS_IN_PROGRESS)
            
            task_details = {
                'type': 'translate_block_chunked',
                'provider': provider,
                'source_items': source_items,
                'attempt': 1,
                'max_retries': 4,
                'block_idx': first_block_idx,
                'mode_description': description,
                'provider_settings_override': {'timeout': block_timeout},
                'timeout_seconds': block_timeout,
                'session_reset_attempted': False,
                'force_prompt': force_prompt,
                'temp_id_map': temp_id_map,
            }
            self._initiate_batch_translation(task_details)
        else:
            session_state = self._session_manager.get_state()
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
            QMessageBox.information(self.mw, tr('AI Busy'), tr('An AI task is already running. Please wait for it to complete.'))
            return
        block_idx = self.mw.data_store.physical_block_idx
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
            QMessageBox.information(self.mw, tr('AI Busy'), tr('An AI task is already running. Please wait for it to complete.'))
            return
        target_block_idx = self.mw.data_store.current_block_idx if block_idx is None else block_idx
        if target_block_idx is None or target_block_idx == -1:
            QMessageBox.information(self.mw, tr('AI Translation'), tr('Select a block to translate.'))
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

        if target_block_idx == -2:
            if chapter_id is None:
                chapter_id = self.mw.data_store.current_chapter_id
            if chapter_id is None:
                self.ui_handler.finish_ai_operation()
                QMessageBox.information(self.mw, tr('AI Translation'), tr('No chapter ID available.'))
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
                QMessageBox.information(self.mw, tr('AI Translation'), tr('No lines mapped to this chapter.'))
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


            block_timeout = 180
            log_debug(
                f"Starting chapter AI translation with timeout {block_timeout}s; lines={len(source_items)}"
            )
        else:
            data_source = self.mw.data_store.data
            if not isinstance(data_source, list) or not (0 <= target_block_idx < len(data_source)):
                self.ui_handler.finish_ai_operation()
                QMessageBox.information(self.mw, tr('AI Translation'), tr('No block data available to translate.'))
                return

            block_strings = self.glossary_handler._get_original_block(target_block_idx)
            if not block_strings:
                self.ui_handler.finish_ai_operation()
                QMessageBox.information(self.mw, tr('AI Translation'), tr('The selected block is empty.'))
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

            block_timeout = 180
            log_debug(
                f"Starting block AI translation for block {target_block_idx} with timeout {block_timeout}s; lines={len(source_items)}"
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
            QMessageBox.information(self.mw, tr('Resume Translation'), tr('No active translation session found for this block.'))
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

        block_timeout = 180

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
            QMessageBox.information(self.mw, tr('AI Busy'), tr('An AI task is already running. Please wait for it to complete.'))
            return
            
        data_source = self.mw.data_store.data
        if not isinstance(data_source, list) or not data_source:
            QMessageBox.information(self.mw, tr('AI Translation'), tr('No data available to translate.'))
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
                    tr('Resume Chronological Translation'), 
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

            block_timeout = 180

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

        # 1. Gather all dialogue strings across all blocks
        all_project_items = []
        for b_idx, s_idx, original_text in iter_all_strings(data_source):
            all_project_items.append({
                'block_idx': b_idx,
                'string_idx': s_idx,
                'text': str(original_text or "")
            })

        if not all_project_items:
            self.ui_handler.finish_ai_operation()
            QMessageBox.information(self.mw, tr('AI Translation'), tr('No dialogues found to translate.'))
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


        block_timeout = 180

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
