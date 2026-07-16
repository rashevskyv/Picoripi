from pathlib import Path
from typing import List, Any, Optional
from utils.logging_utils import log_debug, log_error, log_info
from .session_manager import SessionManager

class RevertManager:
    """Manages reverting strings, blocks, and files to their original states."""
    def __init__(self, data_processor: Any):
        """Initialize a new instance."""
        self.dsp = data_processor
        self.mw = data_processor.mw

    def revert_strings_to_original(self, block_idx: int, string_indices: List[int], progress_dialog=None, progress_offset: int = 0) -> int:
        """Reverts multiple strings in a block to their original state (from the loaded file)."""
        if not hasattr(self.mw, 'data_store') or not hasattr(self.mw.data_store, 'edited_data'): 
            return 0

        # Auto-save translation before reverting
        if hasattr(self.mw, 'saved_translations_manager') and self.mw.saved_translations_manager:
            to_save = []
            for s_idx in string_indices:
                curr_text, _ = self.dsp.get_current_string_text(block_idx, s_idx)
                original_text = self.dsp._get_string_from_source(block_idx, s_idx, self.mw.data_store.data, "original_source_data")
                if curr_text and curr_text != original_text:
                    to_save.append((s_idx, curr_text))
            if to_save:
                self.mw.saved_translations_manager.save_translations_bulk(block_idx, to_save)

        has_undo = hasattr(self.mw, 'undo_manager')
        if has_undo:
            self.mw.undo_manager.begin_group()

        show_progress = len(string_indices) > 20 and hasattr(self.mw, 'ui_updater') and progress_dialog is None
        progress = progress_dialog
        if show_progress and hasattr(self.mw, 'ui_provider') and self.mw.ui_provider:
            progress = self.mw.ui_provider.create_progress_tracker("Revert Strings", "Reverting strings to original...", len(string_indices))

        processed = 0
        try:
            for i, s_idx in enumerate(string_indices):
                if progress and progress.was_canceled():
                    break

                original_text = self.dsp._get_string_from_source(block_idx, s_idx, self.mw.data_store.data, "original_source_data")

                if original_text is not None:
                    self.dsp.update_edited_data(block_idx, s_idx, original_text, action_type="REVERT", skip_ui_refresh=True)

                processed += 1
                if progress:
                    if progress_dialog is not None:
                        progress.set_value(progress_offset + processed)
                    else:
                        progress.set_value(processed)
        finally:
            if show_progress and progress:
                progress.set_value(len(string_indices))
            if has_undo:
                self.mw.undo_manager.end_group("REVERT")

            if hasattr(self.mw, 'ui_updater'):
                self.mw.ui_updater.update_block_item_text_with_problem_count(block_idx)

        if hasattr(self.mw, 'ui_updater') and getattr(self.mw.data_store, 'current_block_idx', -1) == block_idx:
            preview_edit = getattr(self.mw, 'preview_text_edit', None)
            if preview_edit and self.mw.current_game_rules:
                old_scrollbar_value = preview_edit.verticalScrollBar().value()

                was_programmatically_changing = self.mw.is_programmatically_changing_text
                self.mw.is_programmatically_changing_text = True

                try:
                    target_indices = getattr(self.mw.data_store, 'displayed_string_indices', [])
                    if not target_indices:
                        if 0 <= block_idx < len(self.mw.data_store.data) and isinstance(self.mw.data_store.data[block_idx], list):
                            target_indices = list(range(len(self.mw.data_store.data[block_idx])))
                        else:
                            target_indices = []

                    preview_lines = []
                    preview_updater = getattr(self.mw.ui_updater, 'preview_updater', None)
                    for line_idx, real_idx in enumerate(target_indices):
                        if isinstance(real_idx, tuple) and len(real_idx) == 2:
                            b, s = real_idx
                        else:
                            b, s = block_idx, real_idx

                        if real_idx == -1:
                            preview_line_text = getattr(preview_updater, '_placeholder_texts', {}).get(line_idx, "[Empty Lines]") if preview_updater else "[Empty Lines]"
                        elif 0 <= b < len(self.mw.data_store.data) and 0 <= s < len(self.mw.data_store.data[b]):
                            text_for_preview_raw, _ = self.dsp.get_current_string_text(b, s)
                            preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
                        else:
                            preview_line_text = ""
                        preview_lines.append(preview_line_text)

                    preview_full_text = "\n".join(preview_lines)

                    if preview_edit.toPlainText() != preview_full_text:
                        preview_edit.setPlainText(preview_full_text)

                    preview_updater = getattr(self.mw.ui_updater, 'preview_updater', None)
                    if preview_updater and hasattr(preview_updater, '_preview_cache'):
                        cache_key = preview_updater.get_cache_key(block_idx, getattr(self.mw.data_store, 'current_category_name', None))
                        preview_updater._preview_cache[cache_key] = {
                            'lines': preview_lines,
                            'next_index': len(target_indices),
                            'target_indices': target_indices
                        }
                        for s_idx in string_indices:
                            text_for_preview_raw, _ = self.dsp.get_current_string_text(block_idx, s_idx)
                            if self.mw.current_game_rules:
                                preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
                            else:
                                preview_line_text = str(text_for_preview_raw)
                            preview_updater.update_cached_string(block_idx, s_idx, preview_line_text)

                    if hasattr(preview_edit, 'highlightManager'):
                        preview_edit.highlightManager.clearAllProblemHighlights()
                        self.mw.ui_updater.preview_updater._apply_highlights_for_block(block_idx)

                    if self.mw.data_store.current_string_idx != -1 and self.mw.data_store.current_string_idx in target_indices:
                        preview_idx_to_select = target_indices.index(self.mw.data_store.current_string_idx)
                        if 0 <= preview_idx_to_select < preview_edit.document().blockCount():
                            preview_edit.set_selected_lines([preview_idx_to_select])

                    preview_edit.verticalScrollBar().setValue(old_scrollbar_value)
                    if hasattr(preview_edit, 'lineNumberArea'):
                        preview_edit.lineNumberArea.update()
                finally:
                    self.mw.is_programmatically_changing_text = was_programmatically_changing

            self.mw.ui_updater.update_text_views()

        return processed

    def perform_revert_strings(self, block_idx: int, string_indices: List[Any], confirm: bool = True) -> None:
        """Unified revert function with optional confirmation and UI updates."""
        if not string_indices or block_idx == -1: 
            return

        is_chapter_revert = False
        if block_idx == -2 or (string_indices and isinstance(string_indices[0], tuple)):
            is_chapter_revert = True

        if confirm:
            num = len(string_indices)
            if is_chapter_revert:
                msg = f"Revert {num} string(s) in this chapter to original?" if num > 1 else "Revert this string to original?"
            else:
                msg = f"Revert {num} string(s) in this block to original?" if num > 1 else "Revert this string to original?"

            reply = self.dsp._ask_yes_no('Revert to Original', msg + "\n\nUnsaved changes for these strings will be lost.", default_yes=False)
            if not reply: 
                return

        if is_chapter_revert:
            grouped = {}
            for item in string_indices:
                if isinstance(item, tuple) and len(item) == 2:
                    b_idx, s_idx = item
                else:
                    b_idx = block_idx
                    s_idx = item
                grouped.setdefault(b_idx, []).append(s_idx)

            has_undo = hasattr(self.mw, 'undo_manager')
            if has_undo:
                self.mw.undo_manager.begin_group()

            total_strings = len(string_indices)
            show_progress = total_strings > 20 and hasattr(self.mw, 'ui_updater')
            progress = None
            if show_progress and hasattr(self.mw, 'ui_provider') and self.mw.ui_provider:
                progress = self.mw.ui_provider.create_progress_tracker(
                    "Revert Strings", "Reverting strings to original...", total_strings
                )

            processed = 0
            try:
                for b_idx, s_indices in grouped.items():
                    if progress and progress.was_canceled():
                        break
                    p_count = self.revert_strings_to_original(b_idx, s_indices, progress_dialog=progress, progress_offset=processed)
                    processed += p_count
            finally:
                if show_progress and progress:
                    progress.set_value(total_strings)
                if has_undo:
                    self.mw.undo_manager.end_group("REVERT")

            if hasattr(self.mw, 'ui_updater'):
                for b_idx in grouped.keys():
                    self.mw.ui_updater.update_block_item_text_with_problem_count(b_idx)
                curr_block = getattr(self.mw.data_store, 'current_block_idx', -1)
                curr_cat = getattr(self.mw.data_store, 'current_category_name', None)
                self.mw.ui_updater.populate_strings_for_block(curr_block, curr_cat, force=True)
                self.mw.ui_updater.update_text_views()
        else:
            self.revert_strings_to_original(block_idx, string_indices)

        if hasattr(self.mw, 'statusBar'):
            if len(string_indices) == 1:
                if is_chapter_revert:
                    self.mw.statusBar.showMessage("String reverted to original.", 2000)
                else:
                    self.mw.statusBar.showMessage(f"String {string_indices[0] + 1} reverted to original.", 2000)
            else:
                self.mw.statusBar.showMessage(f"{len(string_indices)} strings reverted to original.", 2000)

    def revert_blocks_to_original(self, block_indices: List[int]) -> None:
        """Reverts entire blocks to their state from the loaded edited file (or original)."""
        if not hasattr(self.mw, 'data_store') or not hasattr(self.mw.data_store, 'data') or not self.mw.data_store.data: 
            return

        # Auto-save translation before reverting blocks
        if hasattr(self.mw, 'saved_translations_manager') and self.mw.saved_translations_manager:
            for b_idx in block_indices:
                if 0 <= b_idx < len(self.mw.data_store.data):
                    to_save = []
                    num_strings = len(self.mw.data_store.data[b_idx])
                    for s_idx in range(num_strings):
                        curr_text, _ = self.dsp.get_current_string_text(b_idx, s_idx)
                        original_text = self.dsp._get_string_from_source(b_idx, s_idx, self.mw.data_store.data, "original_source_data")
                        if curr_text and curr_text != original_text:
                            to_save.append((s_idx, curr_text))
                    if to_save:
                        self.mw.saved_translations_manager.save_translations_bulk(b_idx, to_save)

        has_undo = hasattr(self.mw, 'undo_manager')
        if has_undo:
            self.mw.undo_manager.begin_group()

        total_strings = 0
        for b_idx in block_indices:
            if 0 <= b_idx < len(self.mw.data_store.data):
                total_strings += len(self.mw.data_store.data[b_idx])

        show_progress = total_strings > 20 and hasattr(self.mw, 'ui_updater')
        progress = None
        if show_progress and hasattr(self.mw, 'ui_provider') and self.mw.ui_provider:
            progress = self.mw.ui_provider.create_progress_tracker(
                "Revert Blocks", "Reverting blocks to original...", total_strings
            )

        processed = 0
        try:
            for b_idx in block_indices:
                if progress and progress.was_canceled():
                    break
                if 0 <= b_idx < len(self.mw.data_store.data):
                    num_strings = len(self.mw.data_store.data[b_idx])
                    for s_idx in range(num_strings):
                        if progress and progress.was_canceled():
                            break
                        original_text = self.dsp._get_string_from_source(b_idx, s_idx, self.mw.data_store.data, "original_source_data")
                        if original_text is not None:
                            self.dsp.update_edited_data(b_idx, s_idx, original_text, action_type="REVERT", skip_ui_refresh=True)

                        processed += 1
                        if progress:
                            progress.set_value(processed)
        finally:
            if progress:
                progress.set_value(total_strings)
            if has_undo:
                self.mw.undo_manager.end_group("REVERT_BLOCKS")

        if hasattr(self.mw, 'ui_updater'):
            if self.mw.data_store.current_block_idx in block_indices:
                self.mw.ui_updater.populate_current_view(force=True)
                self.mw.ui_updater.update_text_views()
            for b_idx in block_indices:
                self.mw.ui_updater.update_block_item_text_with_problem_count(b_idx)

    def revert_edited_file_to_original(self) -> bool:
        """Revert edited file to original."""
        from ..data_manager import save_json_file, save_text_file
        is_project_mode = hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project

        if not is_project_mode:
            if not self.mw.data_store.json_path or not self.mw.data_store.edited_json_path:
                self.dsp._show_message("Revert Error", "Original or Changes file path is not set.", type="warning")
                return False
            if not self.mw.data_store.data:
                self.dsp._show_message("Revert Error", "Original data is not loaded.", type="warning")
                return False
            if not self.mw.current_game_rules:
                self.dsp._show_message("Revert Error", "No game plugin active to format the save file.", type="error")
                return False

            reply = self.dsp._ask_yes_no('Revert Changes File', f"This will overwrite the file:\n{Path(self.mw.data_store.edited_json_path).name}\nwith the content from:\n{Path(self.mw.data_store.json_path).name}\n\nAll previous edits in the changes file will be lost.\nCurrent unsaved edits in memory will also be discarded.\n\nAre you sure?", default_yes=False)
            if not reply: 
                return False
            try:
                output_data = self.mw.current_game_rules.save_data_to_json_obj(self.mw.data_store.data, self.mw.data_store.block_names)

                save_file_success = False
                file_extension = Path(self.mw.data_store.edited_json_path).suffix.lower()

                if file_extension == '.json':
                    save_file_success = save_json_file(self.mw.data_store.edited_json_path, output_data)
                elif file_extension == '.txt':
                    if isinstance(output_data, str):
                        save_file_success = save_text_file(self.mw.data_store.edited_json_path, output_data)
                    else:
                        log_debug("Revert Error: Plugin for .txt file did not return a string for saving.")
                        self.dsp._show_message("Revert Error", "Plugin save format error: expected a string for .txt file.", type="error")
                        return False
                elif file_extension == '.bmg':
                    try:
                        with Path(self.mw.data_store.edited_json_path).open('wb') as f:
                            f.write(output_data)
                        save_file_success = True
                    except Exception as e:
                        log_debug(f"Failed to write BMG: {e}")
                        save_file_success = False

                if save_file_success:
                    self.mw.data_store.unsaved_changes = False
                    self.mw.data_store.edited_data = {}
                    self.mw.data_store.edited_sublines.clear()

                    plugin_keys_backup = None
                    if hasattr(self.mw.current_game_rules, 'original_keys'):
                        plugin_keys_backup = list(self.mw.current_game_rules.original_keys)

                    reverted_data_list, _ = self.mw.current_game_rules.load_data_from_json_obj(output_data)

                    if plugin_keys_backup is not None and hasattr(self.mw.current_game_rules, 'original_keys'):
                        self.mw.current_game_rules.original_keys = plugin_keys_backup

                    self.mw.data_store.edited_file_data = reverted_data_list

                    self.dsp._show_message("Reverted", f"Changes file '{Path(self.mw.data_store.edited_json_path).name}' has been reverted to match the original.", type="info")
                    self.mw.ui_updater.update_title()
                    self.mw.ui_updater.populate_current_view()
                    return True
                else: 
                    return False
            except Exception as e:
                log_error(f"Unexpected error during revert: {e}", exc_info=True)
                self.dsp._show_message("Revert Error", f"Unexpected error during revert:\n{e}", type="error")
                return False
        else:
            # Project mode revert
            reply = self.dsp._ask_yes_no('Revert Project Changes', "This will overwrite all active block translation files with original data.\nAll previous edits in the translation files will be lost.\nCurrent unsaved edits in memory will also be discarded.\n\nAre you sure?", default_yes=False)
            if not reply: 
                return False

            try:
                log_debug("Reverting in Project Mode: Splitting blocks back to their original state")
                blocks = self.mw.project_manager.project.blocks
                success_all = True

                project_block_to_data_blocks = {}
                for data_b_idx, p_b_idx in self.mw.block_to_project_file_map.items():
                    if p_b_idx not in project_block_to_data_blocks:
                        project_block_to_data_blocks[p_b_idx] = []
                    project_block_to_data_blocks[p_b_idx].append(data_b_idx)

                global_keys_backup = None
                if hasattr(self.mw.current_game_rules, 'original_keys'):
                    global_keys_backup = list(self.mw.current_game_rules.original_keys)

                for p_b_idx, data_indices in project_block_to_data_blocks.items():
                    if p_b_idx >= len(blocks): 
                        continue

                    block = blocks[p_b_idx]
                    trans_path = self.mw.project_manager.get_absolute_path(block.translation_file, is_translation=True)

                    file_data_list = [self.mw.data_store.data[d_idx] for d_idx in data_indices]
                    file_block_names = {str(i): self.mw.data_store.block_names.get(str(d_idx), 'Unknown') for i, d_idx in enumerate(data_indices)}

                    if global_keys_backup is not None:
                        sliced_keys = [global_keys_backup[d_idx] for d_idx in data_indices]
                        self.mw.current_game_rules.original_keys = sliced_keys

                    final_obj_to_save = self.mw.current_game_rules.save_data_to_json_obj(file_data_list, file_block_names)

                    file_extension = Path(trans_path).suffix.lower()
                    if file_extension == '.json':
                        save_file_success = save_json_file(trans_path, final_obj_to_save)
                    elif file_extension == '.txt':
                        if isinstance(final_obj_to_save, str):
                            save_file_success = save_text_file(trans_path, final_obj_to_save)
                        else:
                            save_file_success = False
                    elif file_extension == '.bmg':
                        try:
                            with Path(trans_path).open('wb') as f:
                                f.write(final_obj_to_save)
                            save_file_success = True
                        except Exception:
                            save_file_success = False
                    else:
                        save_file_success = save_text_file(trans_path, str(final_obj_to_save))

                    if not save_file_success:
                        success_all = False
                        break

                if success_all:
                    self.mw.data_store.unsaved_changes = False
                    self.mw.data_store.edited_data = {}
                    if global_keys_backup is not None:
                        self.mw.current_game_rules.original_keys = global_keys_backup

                    if hasattr(self.mw, 'project_action_handler') and self.mw.project_action_handler:
                        self.mw.project_action_handler._populate_blocks_from_project()

                    self.dsp._show_message("Project Reverted", "All project translation files reverted successfully.", type="info")
                    return True
                else:
                    if global_keys_backup is not None:
                        self.mw.current_game_rules.original_keys = global_keys_backup
                    return False

            except Exception as e:
                log_error(f"Unexpected error during project revert: {e}", exc_info=True)
                self.dsp._show_message("Revert Error", f"Unexpected error during project revert:\n{e}", type="error")
                return False
