from typing import List, Dict, Tuple, Optional, Any, Union
import json
from pathlib import Path
from .data_manager import load_json_file, save_json_file, save_text_file
from utils.logging_utils import log_debug, log_info, log_warning, log_error

class DataStateProcessor:
    def __init__(self, main_window: Any):
        self.mw = main_window

    def _show_message(self, title: str, text: str, type: str = "info"):
        if hasattr(self.mw, 'ui_provider') and self.mw.ui_provider:
            self.mw.ui_provider.show_message(title, text, type)
        else:
            if type == "error":
                log_error(f"{title}: {text}")
            elif type == "warning":
                log_warning(f"{title}: {text}")
            else:
                log_info(f"{title}: {text}")

    def _ask_yes_no(self, title: str, text: str, default_yes: bool = True) -> bool:
        if hasattr(self.mw, 'ui_provider') and self.mw.ui_provider:
            return self.mw.ui_provider.ask_yes_no(title, text, default_yes)
        return default_yes

    def _get_string_from_source(self, block_idx: int, string_idx: int, source_data: List[Any], source_name: str) -> Optional[str]:
        if not source_data:
            return None
        if not (0 <= block_idx < len(source_data)):
            return None
        
        current_block = source_data[block_idx]
        if not isinstance(current_block, list):
            return None
        
        if not (0 <= string_idx < len(current_block)):
            return None
            
        value = current_block[string_idx]
        return value

    def get_current_string_text(self, block_idx: int, string_idx: int) -> Tuple[str, str]:
        edit_key = (block_idx, string_idx)
        if edit_key in self.mw.data_store.edited_data:
            return self.mw.data_store.edited_data[edit_key], "edited_data (in-memory)"
        
        text_from_file = self._get_string_from_source(block_idx, string_idx, self.mw.data_store.edited_file_data, "edited_file_data")
        if text_from_file is not None: 
            return text_from_file, "edited_file_data"
            
        text_from_original = self._get_string_from_source(block_idx, string_idx, self.mw.data_store.data, "original_data")
        if text_from_original is not None:
            return text_from_original, "original_data"
            
        # Boundary / Loading check: avoid sending error if indices are simply not ready yet
        if block_idx < 0 or string_idx < 0:
            return "", "loading"
            
        log_debug(f"!!! DSP: Index ({block_idx}, {string_idx}) not ready or missing (data length: {len(self.mw.data_store.data) if self.mw.data_store.data else 0}).")
        return "", "initial_load" 

    def get_block_texts(self, block_idx: int) -> List[str]:
        if not self.mw.data_store.data or not (0 <= block_idx < len(self.mw.data_store.data)):
            return []
        
        num_strings = len(self.mw.data_store.data[block_idx])
        return [self.get_current_string_text(block_idx, i)[0] for i in range(num_strings)]

    def string_needs_translation(self, block_idx: int, string_idx: int) -> bool:
        """
        Checks whether a string needs manual translation.
        A string does not need translation if its original source text is empty 
        or contains only tags and whitespace.
        """
        if not self.mw.data_store.data or not (0 <= block_idx < len(self.mw.data_store.data)):
            return False
        
        block_original = self.mw.data_store.data[block_idx]
        if not isinstance(block_original, list) or not (0 <= string_idx < len(block_original)):
            return False
            
        original_text = str(block_original[string_idx])
        import re
        cleaned_original = re.sub(r'\{[^}]*\}|\[[^\]]*\]', '', original_text).strip()
        return bool(cleaned_original)

    def is_string_translated(self, block_idx: int, string_idx: int) -> bool:
        """
        Checks whether a string has a valid translation.
        A string is considered translated if its original text needs translation
        and its current edited translation is non-empty and differs from the original source text.
        """
        if not self.string_needs_translation(block_idx, string_idx):
            return False
            
        original_text = str(self.mw.data_store.data[block_idx][string_idx])
        current_text, source = self.get_current_string_text(block_idx, string_idx)
        
        if not current_text or not current_text.strip():
            return False
            
        return current_text.strip() != original_text.strip()

    def update_edited_data(self, block_idx: int, string_idx: int, new_text: str, action_type: str = "TEXT_EDIT", skip_ui_refresh: bool = False) -> bool:
        edit_key = (block_idx, string_idx)
        
        # Get old text for undo
        old_text, _ = self.get_current_string_text(block_idx, string_idx)

        original_text = self._get_string_from_source(block_idx, string_idx, self.mw.data_store.data, "original_data_for_update_check")
        
        text_from_saved_file = self._get_string_from_source(block_idx, string_idx, self.mw.data_store.edited_file_data, "edited_file_data")
        if text_from_saved_file is None:
            text_from_saved_file = original_text
            
        old_unsaved_changes = self.mw.data_store.unsaved_changes

        if new_text == text_from_saved_file:
            if edit_key in self.mw.data_store.edited_data:
                del self.mw.data_store.edited_data[edit_key]
        else:
            self.mw.data_store.edited_data[edit_key] = new_text

        # Update translation metadata in .uiproj Block objects
        if original_text is not None and new_text and new_text.strip() != original_text.strip():
            try:
                if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                    proj_b_idx = getattr(self.mw, 'block_to_project_file_map', {}).get(block_idx, block_idx)
                    if 0 <= proj_b_idx < len(self.mw.project_manager.project.blocks):
                        block = self.mw.project_manager.project.blocks[proj_b_idx]
                        if not isinstance(block.metadata, dict):
                            block.metadata = {}
                        if "translation_status" not in block.metadata:
                            block.metadata["translation_status"] = {}
                        
                        import datetime
                        now_str = datetime.datetime.now().isoformat()
                        
                        model_name = "User Edit"
                        if action_type == "TRANSLATE" and hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
                            model_name = getattr(self.mw.translation_handler.ai_lifecycle_manager, '_active_model_name', 'AI Model')
                            
                        block.metadata["translation_status"][str(string_idx)] = {
                            "ai_model": model_name,
                            "timestamp": now_str,
                            "approved": action_type == "USER_APPROVED"
                        }
            except Exception as e:
                log_debug(f"DSP: Failed to update translation metadata in Block: {e}")

        # Update unsaved block indices for the indicator (asterisk)
        if edit_key in self.mw.data_store.edited_data:
            self.mw.data_store.unsaved_block_indices.add(block_idx)
        else:
            # Check if any other edits remain in this block
            has_other_edits = any(b == block_idx for b, s in self.mw.data_store.edited_data.keys())
            if not has_other_edits:
                self.mw.data_store.unsaved_block_indices.discard(block_idx)

        # Record in undo manager if it exists and text actually changed
        if hasattr(self.mw, 'undo_manager') and old_text != new_text:
            self.mw.undo_manager.record_action(action_type, block_idx, string_idx, old_text, new_text)

        self.mw.data_store.unsaved_changes = bool(self.mw.data_store.edited_data)
        
        unsaved_status_actually_changed = self.mw.data_store.unsaved_changes != old_unsaved_changes
        if unsaved_status_actually_changed:
            log_debug(f"DSP.update_edited_data: Unsaved changes status changed to {self.mw.data_store.unsaved_changes}")
        
        # Explicitly trigger tree item refresh to show/hide asterisk
        if not skip_ui_refresh and hasattr(self.mw, 'ui_updater'):
            self.mw.ui_updater.update_block_item_text_with_problem_count(block_idx)

        return unsaved_status_actually_changed

    def revert_strings_to_original(self, block_idx: int, string_indices: List[int], progress_dialog=None, progress_offset: int = 0) -> int:
        """Reverts multiple strings in a block to their original state (from the loaded file)."""
        if not hasattr(self.mw, 'data_store') or not hasattr(self.mw.data_store, 'edited_data'): return 0
        
        # Auto-save translation before reverting
        if hasattr(self.mw, 'saved_translations_manager') and self.mw.saved_translations_manager:
            to_save = []
            for s_idx in string_indices:
                curr_text, _ = self.get_current_string_text(block_idx, s_idx)
                original_text = self._get_string_from_source(block_idx, s_idx, self.mw.data_store.data, "original_source_data")
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
                
                # We specifically use self.mw.data_store.data here because "Original" refers to the source text (left panel)
                original_text = self._get_string_from_source(block_idx, s_idx, self.mw.data_store.data, "original_source_data")
                
                if original_text is not None:
                    # Recording this as a REVERT action
                    self.update_edited_data(block_idx, s_idx, original_text, action_type="REVERT", skip_ui_refresh=True)
                
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
            
            # Explicitly refresh the tree widget once at the end
            if hasattr(self.mw, 'ui_updater'):
                self.mw.ui_updater.update_block_item_text_with_problem_count(block_idx)
            
        if hasattr(self.mw, 'ui_updater') and getattr(self.mw.data_store, 'current_block_idx', -1) == block_idx:
            preview_edit = getattr(self.mw, 'preview_text_edit', None)
            if preview_edit and self.mw.current_game_rules:
                old_scrollbar_value = preview_edit.verticalScrollBar().value()
                
                # Prevent triggering events during the text updates
                was_programmatically_changing = self.mw.is_programmatically_changing_text
                self.mw.is_programmatically_changing_text = True
                
                try:
                    target_indices = getattr(self.mw.data_store, 'displayed_string_indices', [])
                    if not target_indices:
                        if 0 <= block_idx < len(self.mw.data_store.data) and isinstance(self.mw.data_store.data[block_idx], list):
                            target_indices = list(range(len(self.mw.data_store.data[block_idx])))
                        else:
                            target_indices = []
                    
                    # Generate all preview lines (this is very fast)
                    preview_lines = []
                    for real_idx in target_indices:
                        if isinstance(real_idx, tuple) and len(real_idx) == 2:
                            b, s = real_idx
                        else:
                            b, s = block_idx, real_idx
                            
                        if 0 <= b < len(self.mw.data_store.data) and 0 <= s < len(self.mw.data_store.data[b]):
                            text_for_preview_raw, _ = self.get_current_string_text(b, s)
                            preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
                            preview_lines.append(preview_line_text)

                    preview_full_text = "\n".join(preview_lines)
                    
                    # Update preview editor instantly
                    if preview_edit.toPlainText() != preview_full_text:
                        preview_edit.setPlainText(preview_full_text)
                    
                    # Update local cache to match the new text
                    preview_updater = getattr(self.mw.ui_updater, 'preview_updater', None)
                    if preview_updater and hasattr(preview_updater, '_preview_cache'):
                        cache_key = preview_updater.get_cache_key(block_idx, getattr(self.mw.data_store, 'current_category_name', None))
                        preview_updater._preview_cache[cache_key] = {
                            'lines': preview_lines,
                            'next_index': len(target_indices),
                            'target_indices': target_indices
                        }
                        for s_idx in string_indices:
                            text_for_preview_raw, _ = self.get_current_string_text(block_idx, s_idx)
                            if self.mw.current_game_rules:
                                preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
                            else:
                                preview_line_text = str(text_for_preview_raw)
                            preview_updater.update_cached_string(block_idx, s_idx, preview_line_text)
                    
                    # Refresh highlights
                    if hasattr(preview_edit, 'highlightManager'):
                        preview_edit.highlightManager.clearAllProblemHighlights()
                        self.mw.ui_updater.preview_updater._apply_highlights_for_block(block_idx)
                    
                    # Restore selection
                    if self.mw.data_store.current_string_idx != -1 and self.mw.data_store.current_string_idx in target_indices:
                        preview_idx_to_select = target_indices.index(self.mw.data_store.current_string_idx)
                        if 0 <= preview_idx_to_select < preview_edit.document().blockCount():
                            preview_edit.set_selected_lines([preview_idx_to_select])
                    
                    # Restore scrollbar position perfectly
                    preview_edit.verticalScrollBar().setValue(old_scrollbar_value)
                    if hasattr(preview_edit, 'lineNumberArea'):
                        preview_edit.lineNumberArea.update()
                finally:
                    self.mw.is_programmatically_changing_text = was_programmatically_changing
            
            # Fast update for original and edited text views
            self.mw.ui_updater.update_text_views()
            
        return processed

    def perform_revert_strings(self, block_idx: int, string_indices: List[Any], confirm: bool = True) -> None:
        """Unified revert function with optional confirmation and UI updates."""
        if not string_indices or block_idx == -1: return
        
        is_chapter_revert = False
        if block_idx == -2 or (string_indices and isinstance(string_indices[0], tuple)):
            is_chapter_revert = True

        if confirm:
            num = len(string_indices)
            if is_chapter_revert:
                msg = f"Revert {num} string(s) in this chapter to original?" if num > 1 else "Revert this string to original?"
            else:
                msg = f"Revert {num} string(s) in this block to original?" if num > 1 else "Revert this string to original?"
            
            reply = self._ask_yes_no('Revert to Original', msg + "\n\nUnsaved changes for these strings will be lost.", default_yes=False)
            if not reply: return
            
        if is_chapter_revert:
            # Group strings by block_idx
            grouped = {}
            for item in string_indices:
                if isinstance(item, tuple) and len(item) == 2:
                    b_idx, s_idx = item
                else:
                    b_idx = block_idx
                    s_idx = item
                grouped.setdefault(b_idx, []).append(s_idx)
            
            # Perform revert for each block
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
            
            # Refresh tree items and active preview
            if hasattr(self.mw, 'ui_updater'):
                for b_idx in grouped.keys():
                    self.mw.ui_updater.update_block_item_text_with_problem_count(b_idx)
                # Re-populate preview for the current block/category
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
        if not hasattr(self.mw, 'data_store') or not hasattr(self.mw.data_store, 'data') or not self.mw.data_store.data: return
        
        # Auto-save translation before reverting blocks
        if hasattr(self.mw, 'saved_translations_manager') and self.mw.saved_translations_manager:
            for b_idx in block_indices:
                if 0 <= b_idx < len(self.mw.data_store.data):
                    to_save = []
                    num_strings = len(self.mw.data_store.data[b_idx])
                    for s_idx in range(num_strings):
                        curr_text, _ = self.get_current_string_text(b_idx, s_idx)
                        original_text = self._get_string_from_source(b_idx, s_idx, self.mw.data_store.data, "original_source_data")
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
                        original_text = self._get_string_from_source(b_idx, s_idx, self.mw.data_store.data, "original_source_data")
                        if original_text is not None:
                            self.update_edited_data(b_idx, s_idx, original_text, action_type="REVERT", skip_ui_refresh=True)
                        
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
                self.mw.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx, getattr(self.mw, 'current_category_name', None), force=True)
                self.mw.ui_updater.update_text_views()
            for b_idx in block_indices:
                self.mw.ui_updater.update_block_item_text_with_problem_count(b_idx)


    def _perform_save_impl(self, output_data_list: List[Any], progress_callback=None) -> Tuple[bool, List[Tuple[str, int, int]], List[str]]:
        warnings = []
        errors = []
        
        # Check if we are inside a project mode
        is_project_mode = hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project
        
        try:
            if is_project_mode:
                log_debug("Saving in Project Mode: Splitting blocks into their corresponding files", category="file_ops")
                blocks = self.mw.project_manager.project.blocks
                success_all = True
                
                # Group data_block indices by translation file path
                file_to_data_indices = {}
                file_to_block_info = {}

                for data_b_idx, p_b_idx in self.mw.block_to_project_file_map.items():
                    if p_b_idx >= len(blocks): continue
                    block = blocks[p_b_idx]
                    path = block.translation_file
                    if path not in file_to_data_indices:
                        file_to_data_indices[path] = []
                        file_to_block_info[path] = block
                    file_to_data_indices[path].append(data_b_idx)
                
                # Backup original keys for pokemon plugin logic
                global_keys_backup = None
                if hasattr(self.mw.current_game_rules, 'original_keys'):
                    global_keys_backup = list(self.mw.current_game_rules.original_keys)

                files_saved_in_this_transaction = set()

                # Determine which files have edits
                files_to_save = {}
                for trans_file_rel, data_indices in file_to_data_indices.items():
                    has_edits = False
                    for d_idx in data_indices:
                        if isinstance(output_data_list[d_idx], list):
                            for s_idx in range(len(output_data_list[d_idx])):
                                if (d_idx, s_idx) in self.mw.data_store.edited_data:
                                    has_edits = True
                                    break
                        if has_edits: break
                    if has_edits:
                        files_to_save[trans_file_rel] = data_indices

                # Collect unique modified archives
                modified_archives = set()
                for trans_file_rel, data_indices in files_to_save.items():
                    prefix = ".extracted/translation/"
                    if trans_file_rel.startswith(prefix):
                        sub_path = trans_file_rel[len(prefix):]
                        for _ext in ('.arc', '.rarc', '.ark'):
                            if _ext in sub_path.lower():
                                _idx = sub_path.lower().find(_ext)
                                archive_rel_path = sub_path[:_idx + len(_ext)]
                                modified_archives.add(archive_rel_path)
                                break

                total_steps = len(files_to_save) + len(modified_archives)
                step_idx = 0

                for trans_file_rel, data_indices in files_to_save.items():
                    block = file_to_block_info[trans_file_rel]
                    trans_path = self.mw.project_manager.get_absolute_path(trans_file_rel, is_translation=True)
                    
                    if progress_callback:
                        progress_callback(step_idx, total_steps, f"Saving file: {Path(trans_path).name}")
                    step_idx += 1

                    # Extract sublists and names for this specific file
                    file_data_list = [output_data_list[d_idx] for d_idx in data_indices]
                    file_block_names = {str(i): self.mw.data_store.block_names.get(str(d_idx), 'Unknown') for i, d_idx in enumerate(data_indices)}

                    # Override the plugins 'original_keys' array to only include keys for this specific file
                    if global_keys_backup is not None:
                        sliced_keys = [global_keys_backup[d_idx] for d_idx in data_indices]
                        self.mw.current_game_rules.original_keys = sliced_keys
                    
                    # For Zelda BMG plugin, pre-load the actual BMG file structure
                    if hasattr(self.mw.current_game_rules, 'last_loaded_bmg'):
                        from bmg_tool import BMGFile
                        bmg = None
                        _prefix_trans = '.extracted/translation/'
                        _prefix_source = '.extracted/sources/'
                        _arc_rel = None
                        _inner_file = None

                        if trans_file_rel.startswith(_prefix_trans):
                            _sub = trans_file_rel[len(_prefix_trans):]
                        elif trans_file_rel.startswith(_prefix_source):
                            _sub = trans_file_rel[len(_prefix_source):]
                        else:
                            _sub = None

                        if _sub:
                            for _ext in ('.arc', '.rarc', '.ark'):
                                _ext_with_slash = _ext + '/'
                                if _ext_with_slash in _sub.lower():
                                    _idx = _sub.lower().find(_ext_with_slash)
                                    _arc_rel = _sub[:_idx + len(_ext)]
                                    _inner_file = _sub[_idx + len(_ext) + 1:]
                                    break

                        if _arc_rel and _inner_file:
                            try:
                                container_trans = self.mw.project_manager.get_archive_container(_arc_rel, is_translation=True)
                                bmg_bytes = container_trans.read_file(_inner_file)
                                bmg_temp = BMGFile()
                                bmg_temp.load(bmg_bytes)
                                bmg = bmg_temp
                            except Exception as e_trans:
                                log_warning(f"Cannot pre-load BMG from translation archive {_arc_rel}/{_inner_file}: {e_trans}. Trying source.", category="file_ops")

                            if bmg is None:
                                try:
                                    container_src = self.mw.project_manager.get_archive_container(_arc_rel, is_translation=False)
                                    bmg_bytes = container_src.read_file(_inner_file)
                                    bmg_temp = BMGFile()
                                    bmg_temp.load(bmg_bytes)
                                    bmg = bmg_temp
                                except Exception as e_src:
                                    log_error(f"Failed to pre-load BMG from source archive {_arc_rel}/{_inner_file}: {e_src}", category="file_ops")
                        else:
                            trans_path_bmg = self.mw.project_manager.get_absolute_path(trans_file_rel, is_translation=True)
                            source_path_bmg = self.mw.project_manager.get_absolute_path(trans_file_rel, is_translation=False)
                            for _p in [trans_path_bmg, source_path_bmg]:
                                if Path(_p).exists():
                                    try:
                                        bmg_temp = BMGFile()
                                        bmg_temp.load(Path(_p).read_bytes())
                                        bmg = bmg_temp
                                        break
                                    except Exception:
                                        pass

                        if bmg:
                            self.mw.current_game_rules.last_loaded_bmg = bmg

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
                            p = Path(trans_path)
                            p.parent.mkdir(parents=True, exist_ok=True)
                            with p.open('wb') as f:
                                f.write(final_obj_to_save)
                            save_file_success = True
                        except Exception as e:
                            log_debug(f"Failed to write BMG: {e}", category="file_ops")
                            save_file_success = False
                    else:
                        save_file_success = save_text_file(trans_path, str(final_obj_to_save))

                    if not save_file_success:
                        success_all = False
                        errors.append(f"Failed to save file: {trans_file_rel}")
                        break
                    else:
                        files_saved_in_this_transaction.add(trans_file_rel)
                
                if success_all:
                    if modified_archives:
                        from core.containers import ContainerManager
                        for archive_rel_path in modified_archives:
                            try:
                                if progress_callback:
                                    progress_callback(step_idx, total_steps, f"Packing archive: {archive_rel_path}")
                                step_idx += 1

                                container = self.mw.project_manager.get_archive_container(archive_rel_path, is_translation=True)
                                
                                for trans_file_rel, data_indices in file_to_data_indices.items():
                                    if trans_file_rel not in files_saved_in_this_transaction:
                                        continue
                                    
                                    prefix = ".extracted/translation/"
                                    if not trans_file_rel.startswith(prefix):
                                        continue
                                    
                                    sub_path = trans_file_rel[len(prefix):]
                                    if sub_path.startswith(archive_rel_path + "/"):
                                        inner_path = sub_path[len(archive_rel_path) + 1:]
                                        trans_path = self.mw.project_manager.get_absolute_path(trans_file_rel, is_translation=True)
                                        
                                        if Path(trans_path).exists():
                                            file_bytes = Path(trans_path).read_bytes()
                                            container.write_file(inner_path, file_bytes)

                                packed_bytes = container.pack()

                                try:
                                    orig_archive_path = self.mw.project_manager.get_absolute_path(archive_rel_path, is_translation=False)
                                    if Path(orig_archive_path).exists():
                                        orig_size = Path(orig_archive_path).stat().st_size
                                        new_size = len(packed_bytes)
                                        if isinstance(orig_size, (int, float)) and new_size > orig_size:
                                            warnings.append((archive_rel_path, new_size, orig_size))
                                except Exception as size_err:
                                    log_error(f"Error checking archive size: {size_err}", category="file_ops")

                                dest_archive_path = Path(self.mw.project_manager.get_absolute_path(archive_rel_path, is_translation=True))
                                dest_archive_path.parent.mkdir(parents=True, exist_ok=True)
                                dest_archive_path.write_bytes(packed_bytes)
                                self.mw.project_manager.clear_archive_cache()
                                
                            except Exception as archive_err:
                                log_error(f"Native packing failed for {archive_rel_path}: {archive_err}", exc_info=True, category="file_ops")
                                errors.append(f"{archive_rel_path}: {archive_err}")
                
                if global_keys_backup is not None:
                    self.mw.current_game_rules.original_keys = global_keys_backup

                return success_all and len(errors) == 0, warnings, errors

            else:
                # Normal single-file save mode
                if progress_callback:
                    progress_callback(0, 1, "Saving file...")
                
                final_obj_to_save = self.mw.current_game_rules.save_data_to_json_obj(output_data_list, self.mw.data_store.block_names)
                save_file_success = False
                file_extension = Path(self.mw.data_store.edited_json_path).suffix.lower()
                
                if file_extension == '.json':
                    save_file_success = save_json_file(self.mw.data_store.edited_json_path, final_obj_to_save)
                elif file_extension == '.txt':
                    if isinstance(final_obj_to_save, str):
                        save_file_success = save_text_file(self.mw.data_store.edited_json_path, final_obj_to_save)
                    else:
                        errors.append("Plugin did not return a string for .txt file.")
                        return False, warnings, errors
                elif file_extension == '.bmg':
                    try:
                        p = Path(self.mw.data_store.edited_json_path)
                        p.parent.mkdir(parents=True, exist_ok=True)
                        with p.open('wb') as f:
                            f.write(final_obj_to_save)
                        save_file_success = True
                    except Exception as e:
                        log_debug(f"Failed to write BMG: {e}", category="file_ops")
                        errors.append(f"Failed to save BMG file: {e}")
                        save_file_success = False
                
                if not save_file_success and not errors:
                    errors.append("Failed to write file to disk.")
                
                if save_file_success:
                    # Backup and restore keys since we are just re-parsing to update UI data
                    plugin_keys_backup = None
                    if hasattr(self.mw.current_game_rules, 'original_keys'):
                        plugin_keys_backup = list(self.mw.current_game_rules.original_keys)
                        
                    reloaded_edited_data, _ = self.mw.current_game_rules.load_data_from_json_obj(final_obj_to_save)
                    
                    if plugin_keys_backup is not None and hasattr(self.mw.current_game_rules, 'original_keys'):
                        self.mw.current_game_rules.original_keys = plugin_keys_backup
                        
                    self.mw.data_store.edited_file_data = reloaded_edited_data

                return save_file_success, warnings, errors
                
        except Exception as e:
            log_error(f"Error during save implementation: {e}", exc_info=True)
            errors.append(str(e))
            return False, warnings, errors


    def save_current_edits(self, ask_confirmation: bool = True) -> bool:
        log_debug(f"--> AppActionHandler: save_data_action called. ask_confirmation={ask_confirmation}, current unsaved={self.mw.data_store.unsaved_changes}", category="file_ops")
        if self.mw.data_store.json_path and not self.mw.data_store.edited_json_path:
            self.mw.data_store.edited_json_path = self.mw.app_action_handler._derive_edited_path(self.mw.data_store.json_path) 
        if not self.mw.data_store.edited_json_path:
            self._show_message("Save Error", "Edited file path is not set. Cannot save.", type="warning")
            return False
        if not self.mw.current_game_rules: 
            self._show_message("Save Error", "No game plugin active to format the save file.", type="error")
            return False
        
        if not self.mw.data_store.unsaved_changes:
            log_debug("Save called but no unsaved changes detected. Skipping file write.", category="file_ops")
            if ask_confirmation:
                self._show_message("Save", "No changes to save.", type="info")
            return True

        if ask_confirmation:
            reply = self._ask_yes_no('Save Changes', f"Save changes to '{Path(self.mw.data_store.edited_json_path).name}'?", default_yes=True)
            if not reply: return False
        
        try:
            if not self.mw.data_store.data:
                self._show_message("Save Error", "Original data not loaded. Cannot save.", type="error")
                return False
            
            # Build the merged save snapshot
            source_data = self.mw.data_store.data
            edited_file_data = self.mw.data_store.edited_file_data or []
            edited_memory = self.mw.data_store.edited_data or {}

            edits_by_block = {}
            for (b_idx, s_idx), edited_text in edited_memory.items():
                edits_by_block.setdefault(b_idx, {})[s_idx] = edited_text

            output_data_list = []
            for i in range(len(source_data)):
                if i < len(edited_file_data) and edited_file_data[i]:
                    chosen_block = edited_file_data[i]
                else:
                    chosen_block = source_data[i]

                block_edits = edits_by_block.get(i)
                if block_edits and isinstance(chosen_block, list):
                    materialized = list(chosen_block)
                    for s_idx, edited_text in block_edits.items():
                        if 0 <= s_idx < len(materialized):
                            materialized[s_idx] = edited_text
                    output_data_list.append(materialized)
                else:
                    output_data_list.append(chosen_block)

            # Check if running under pytest to preserve synchronous path
            import sys
            if 'pytest' in sys.modules:
                success, warnings, errors = self._perform_save_impl(output_data_list)
                if not success:
                    if errors:
                        self._show_message("Save Error", "\n".join(errors), type="error")
                    return False
                
                # Post-save state updates
                self.mw.data_store.unsaved_changes = False
                self.mw.data_store.edited_data = {}
                self.mw.data_store.edited_sublines.clear()
                self.mw.data_store.edited_file_data = output_data_list
                
                for archive_rel_path, new_size, orig_size in warnings:
                    if getattr(self.mw, 'show_archive_size_warnings', True):
                        if hasattr(self.mw, 'ui_provider') and self.mw.ui_provider:
                            self.mw.ui_provider.show_archive_size_warning(archive_rel_path, new_size, orig_size)
                            
                if ask_confirmation:
                    self._show_message("Project Saved", "All project translation files saved successfully.", type="info")
                if hasattr(self.mw, 'issue_scan_handler'):
                    self.mw.issue_scan_handler._save_issues_cache()
                return True

            # If running in production mode, delegate the async saving process to AppActionHandler
            if hasattr(self.mw, 'app_action_handler') and self.mw.app_action_handler:
                return self.mw.app_action_handler.perform_async_save_flow(output_data_list, ask_confirmation)
            else:
                # Fallback to sync saving if app_action_handler is not available
                success, warnings, errors = self._perform_save_impl(output_data_list)
                if not success:
                    if errors:
                        self._show_message("Save Error", "\n".join(errors), type="error")
                    return False
                
                self.mw.data_store.unsaved_changes = False
                self.mw.data_store.edited_data = {}
                self.mw.data_store.edited_sublines.clear()
                self.mw.data_store.edited_file_data = output_data_list
                
                for archive_rel_path, new_size, orig_size in warnings:
                    if getattr(self.mw, 'show_archive_size_warnings', True):
                        if hasattr(self.mw, 'ui_provider') and self.mw.ui_provider:
                            self.mw.ui_provider.show_archive_size_warning(archive_rel_path, new_size, orig_size)
                            
                if ask_confirmation:
                    self._show_message("Project Saved", "All project translation files saved successfully.", type="info")
                if hasattr(self.mw, 'issue_scan_handler'):
                    self.mw.issue_scan_handler._save_issues_cache()
                return True

        except Exception as e:
            log_error(f"Unexpected error during save: {e}", exc_info=True)
            self._show_message("Save Error", f"Unexpected error during save:\n{e}", type="error")
            return False

    def revert_edited_file_to_original(self) -> bool:
        is_project_mode = hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project

        if not is_project_mode:
            if not self.mw.data_store.json_path or not self.mw.data_store.edited_json_path:
                self._show_message("Revert Error", "Original or Changes file path is not set.", type="warning")
                return False
            if not self.mw.data_store.data:
                self._show_message("Revert Error", "Original data is not loaded.", type="warning")
                return False
            if not self.mw.current_game_rules:
                self._show_message("Revert Error", "No game plugin active to format the save file.", type="error")
                return False
    
            reply = self._ask_yes_no('Revert Changes File', f"This will overwrite the file:\n{Path(self.mw.data_store.edited_json_path).name}\nwith the content from:\n{Path(self.mw.data_store.json_path).name}\n\nAll previous edits in the changes file will be lost.\nCurrent unsaved edits in memory will also be discarded.\n\nAre you sure?", default_yes=False)
            if not reply: return False
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
                        self._show_message("Revert Error", "Plugin save format error: expected a string for .txt file.", type="error")
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
                    self.mw.data_store.unsaved_changes = False; self.mw.data_store.edited_data = {}; self.mw.data_store.edited_sublines.clear(); 
                    
                    # Backup and restore keys since we are reading translation data
                    plugin_keys_backup = None
                    if hasattr(self.mw.current_game_rules, 'original_keys'):
                        plugin_keys_backup = list(self.mw.current_game_rules.original_keys)
                        
                    reverted_data_list, _ = self.mw.current_game_rules.load_data_from_json_obj(output_data)
                    
                    if plugin_keys_backup is not None and hasattr(self.mw.current_game_rules, 'original_keys'):
                        self.mw.current_game_rules.original_keys = plugin_keys_backup
                        
                    self.mw.data_store.edited_file_data = reverted_data_list
    
                    self._show_message("Reverted", f"Changes file '{Path(self.mw.data_store.edited_json_path).name}' has been reverted to match the original.", type="info")
                    self.mw.ui_updater.update_title(); 
                    self.mw.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx) 
                    return True
                else: return False
            except Exception as e:
                log_error(f"Unexpected error during revert: {e}", exc_info=True)
                self._show_message("Revert Error", f"Unexpected error during revert:\n{e}", type="error")
                return False
        else:
            # Project mode revert
            reply = self._ask_yes_no('Revert Project Changes', "This will overwrite all active block translation files with original data.\nAll previous edits in the translation files will be lost.\nCurrent unsaved edits in memory will also be discarded.\n\nAre you sure?", default_yes=False)
            if not reply: return False
            
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
                    if p_b_idx >= len(blocks): continue
                    
                    block = blocks[p_b_idx]
                    trans_path = self.mw.project_manager.get_absolute_path(block.translation_file, is_translation=True)
                    
                    # Extract original self.mw.data_store.data
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
                        except Exception as e:
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
                        
                    # Reload blocks
                    if hasattr(self.mw, 'project_action_handler') and self.mw.project_action_handler:
                        self.mw.project_action_handler._populate_blocks_from_project()
 
                    self._show_message("Project Reverted", "All project translation files reverted successfully.", type="info")
                    return True
                else: 
                    if global_keys_backup is not None:
                        self.mw.current_game_rules.original_keys = global_keys_backup
                    return False
 
            except Exception as e:
                log_error(f"Unexpected error during project revert: {e}", exc_info=True)
                self._show_message("Revert Error", f"Unexpected error during project revert:\n{e}", type="error")
                return False
