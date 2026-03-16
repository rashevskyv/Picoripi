# --- START OF FILE core/data_state_processor.py ---
import json
from pathlib import Path
from PyQt5.QtWidgets import QMessageBox
from .data_manager import load_json_file, save_json_file, save_text_file
from utils.logging_utils import log_debug, log_error

class DataStateProcessor:
    def __init__(self, main_window):
        self.mw = main_window

    def _get_string_from_source(self, block_idx, string_idx, source_data, source_name):
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

    def get_current_string_text(self, block_idx, string_idx):
        edit_key = (block_idx, string_idx)
        if edit_key in self.mw.edited_data:
            return self.mw.edited_data[edit_key], "edited_data (in-memory)"
        
        text_from_file = self._get_string_from_source(block_idx, string_idx, self.mw.edited_file_data, "edited_file_data")
        if text_from_file is not None: 
            return text_from_file, "edited_file_data"
            
        text_from_original = self._get_string_from_source(block_idx, string_idx, self.mw.data, "original_data")
        if text_from_original is not None:
            return text_from_original, "original_data"
            
        log_debug(f"!!! DSP: Error in get_current_string_text - Index ({block_idx}, {string_idx}) out of bounds or data missing after checking all sources.")
        return "[DATA ERROR]", "error" 

    def get_block_texts(self, block_idx: int) -> list[str]:
        if not self.mw.data or not (0 <= block_idx < len(self.mw.data)):
            return []
        
        num_strings = len(self.mw.data[block_idx])
        return [self.get_current_string_text(block_idx, i)[0] for i in range(num_strings)]

    def update_edited_data(self, block_idx, string_idx, new_text, action_type="TEXT_EDIT"):
        edit_key = (block_idx, string_idx)
        
        # Get old text for undo
        old_text, _ = self.get_current_string_text(block_idx, string_idx)

        original_text = self._get_string_from_source(block_idx, string_idx, self.mw.data, "original_data_for_update_check")
        
        text_from_saved_file = self._get_string_from_source(block_idx, string_idx, self.mw.edited_file_data, "edited_file_data")
        if text_from_saved_file is None:
            text_from_saved_file = original_text
            
        old_unsaved_changes = self.mw.unsaved_changes

        if new_text == text_from_saved_file:
            if edit_key in self.mw.edited_data:
                del self.mw.edited_data[edit_key]
        else:
            self.mw.edited_data[edit_key] = new_text

        # Update unsaved block indices for the indicator (asterisk)
        if edit_key in self.mw.edited_data:
            self.mw.unsaved_block_indices.add(block_idx)
        else:
            # Check if any other edits remain in this block
            has_other_edits = any(b == block_idx for b, s in self.mw.edited_data.keys())
            if not has_other_edits:
                self.mw.unsaved_block_indices.discard(block_idx)

        # Record in undo manager if it exists and text actually changed
        if hasattr(self.mw, 'undo_manager') and old_text != new_text:
            self.mw.undo_manager.record_action(action_type, block_idx, string_idx, old_text, new_text)

        self.mw.unsaved_changes = bool(self.mw.edited_data)
        
        unsaved_status_actually_changed = self.mw.unsaved_changes != old_unsaved_changes
        if unsaved_status_actually_changed:
            log_debug(f"DSP.update_edited_data: Unsaved changes status changed to {self.mw.unsaved_changes}")
        
        # Explicitly trigger tree item refresh to show/hide asterisk
        if hasattr(self.mw, 'ui_updater'):
            self.mw.ui_updater.update_block_item_text_with_problem_count(block_idx)

        return unsaved_status_actually_changed

    def revert_strings_to_original(self, block_idx: int, string_indices: list[int]):
        """Reverts multiple strings in a block to their original state (from the loaded file)."""
        if not hasattr(self.mw, 'edited_data'): return
        
        if hasattr(self.mw, 'undo_manager'):
            self.mw.undo_manager.begin_group()
            
        changed = False
        for s_idx in string_indices:
            # We specifically use self.mw.data here because "Original" refers to the source text (left panel)
            original_text = self._get_string_from_source(block_idx, s_idx, self.mw.data, "original_source_data")
            
            if original_text is not None:
                if self.update_edited_data(block_idx, s_idx, original_text, action_type="REVERT"):
                    changed = True
        
        if hasattr(self.mw, 'undo_manager'):
            self.mw.undo_manager.end_group("REVERT")
            
        if hasattr(self.mw, 'ui_updater'):
            self.mw.ui_updater.populate_strings_for_block(block_idx, getattr(self.mw, 'current_category_name', None), force=True)
            self.mw.ui_updater.update_text_views()

    def perform_revert_strings(self, block_idx: int, string_indices: list[int], confirm: bool = True):
        """Unified revert function with optional confirmation and UI updates."""
        if not string_indices or block_idx == -1: return
        
        if confirm:
            num = len(string_indices)
            msg = f"Revert {num} string(s) in this block to original?" if num > 1 else "Revert this string to original?"
            reply = QMessageBox.question(
                self.mw, 'Revert to Original', 
                msg + "\n\nUnsaved changes for these strings will be lost.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No: return
            
        self.revert_strings_to_original(block_idx, string_indices)
        
        if hasattr(self.mw, 'statusBar'):
            if len(string_indices) == 1:
                self.mw.statusBar.showMessage(f"String {string_indices[0] + 1} reverted to original.", 2000)
            else:
                self.mw.statusBar.showMessage(f"{len(string_indices)} strings reverted to original.", 2000)

    def revert_blocks_to_original(self, block_indices: list[int]):
        """Reverts entire blocks to their state from the loaded edited file (or original)."""
        if not hasattr(self.mw, 'data') or not self.mw.data: return
        
        if hasattr(self.mw, 'undo_manager'):
            self.mw.undo_manager.begin_group()
            
        for b_idx in block_indices:
            if 0 <= b_idx < len(self.mw.data):
                num_strings = len(self.mw.data[b_idx])
                # We avoid calling revert_strings_to_original to prevent nested groups
                # instead we call update_edited_data directly for each string
                for s_idx in range(num_strings):
                    # Use self.mw.data to get the actual original source text
                    original_text = self._get_string_from_source(b_idx, s_idx, self.mw.data, "original_source_data")
                    
                    if original_text is not None:
                        self.update_edited_data(b_idx, s_idx, original_text, action_type="REVERT")
        
        if hasattr(self.mw, 'undo_manager'):
            self.mw.undo_manager.end_group("REVERT_BLOCKS")
            
        if hasattr(self.mw, 'ui_updater'):
            if self.mw.current_block_idx in block_indices:
                self.mw.ui_updater.populate_strings_for_block(self.mw.current_block_idx, getattr(self.mw, 'current_category_name', None), force=True)
                self.mw.ui_updater.update_text_views()
            else:
                # Still need to update indicators in tree
                for b_idx in block_indices:
                    self.mw.ui_updater.update_block_item_text_with_problem_count(b_idx)


    def save_current_edits(self, ask_confirmation=True):
        log_debug(f"--> AppActionHandler: save_data_action called. ask_confirmation={ask_confirmation}, current unsaved={self.mw.unsaved_changes}")
        if self.mw.json_path and not self.mw.edited_json_path:
            self.mw.edited_json_path = self.mw.app_action_handler._derive_edited_path(self.mw.json_path) 
        if not self.mw.edited_json_path:
            QMessageBox.warning(self.mw, "Save Error", "Edited file path is not set. Cannot save.")
            return False
        if not self.mw.current_game_rules: 
            QMessageBox.critical(self.mw, "Save Error", "No game plugin active to format the save file.")
            return False
        
        if not self.mw.unsaved_changes:
            log_debug("Save called but no unsaved changes detected. Skipping file write.")
            if ask_confirmation:
                QMessageBox.information(self.mw, "Save", "No changes to save.")
            return True

        if ask_confirmation:
            reply = QMessageBox.question(self.mw, 'Save Changes', f"Save changes to '{Path(self.mw.edited_json_path).name}'?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.No: return False
        
        try:
            if not self.mw.data: QMessageBox.critical(self.mw, "Save Error", "Original data not loaded. Cannot save."); return False
            
            output_data_list = json.loads(json.dumps(self.mw.data)) 
            if self.mw.edited_file_data:
                output_data_list = json.loads(json.dumps(self.mw.edited_file_data))

            if self.mw.edited_data:
                log_debug(f"Applying {len(self.mw.edited_data)} in-memory edits before saving...")
            for (b_idx, s_idx), edited_text_from_memory in self.mw.edited_data.items():
                if 0 <= b_idx < len(output_data_list) and isinstance(output_data_list[b_idx], list) and \
                   0 <= s_idx < len(output_data_list[b_idx]):
                    output_data_list[b_idx][s_idx] = edited_text_from_memory
                else:
                    log_debug(f"Save: Memory edit for key ({b_idx},{s_idx}) is out of bounds for output_data. Ignored.")

            # Check if we are inside a project mode
            is_project_mode = hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project
            
            if is_project_mode:
                log_debug("Saving in Project Mode: Splitting blocks into their corresponding files")
                blocks = self.mw.project_manager.project.blocks
                success_all = True
                
                # Group data_block indices by translation file path
                file_to_data_indices = {}
                # Map translation file path back to one representative block for metadata
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

                for trans_file_rel, data_indices in file_to_data_indices.items():
                    # Check if this specific file has any unsaved edits
                    has_edits = False
                    for d_idx in data_indices:
                        if isinstance(output_data_list[d_idx], list):
                            for s_idx in range(len(output_data_list[d_idx])):
                                if (d_idx, s_idx) in self.mw.edited_data:
                                    has_edits = True
                                    break
                        if has_edits: break
                    
                    if not has_edits:
                        log_debug(f"Skipping save for project file '{trans_file_rel}' as it has no pending edits.")
                        continue

                    block = file_to_block_info[trans_file_rel]
                    trans_path = self.mw.project_manager.get_absolute_path(trans_file_rel, is_translation=True)
                    
                    # Extract sublists and names for this specific file
                    file_data_list = [output_data_list[d_idx] for d_idx in data_indices]
                    file_block_names = {str(i): self.mw.block_names.get(str(d_idx), 'Unknown') for i, d_idx in enumerate(data_indices)}

                    # Override the plugins 'original_keys' array to only include keys for this specific file
                    if global_keys_backup is not None:
                        # Extract the slice of keys corresponding to these data indices
                        sliced_keys = [global_keys_backup[d_idx] for d_idx in data_indices]
                        self.mw.current_game_rules.original_keys = sliced_keys
                    
                    # Call plugin to map data back into its JSON/Txt structure
                    final_obj_to_save = self.mw.current_game_rules.save_data_to_json_obj(file_data_list, file_block_names)
                    
                    # Save to the specific translation path
                    file_extension = Path(trans_path).suffix.lower()
                    if file_extension == '.json':
                        save_file_success = save_json_file(trans_path, final_obj_to_save)
                    elif file_extension == '.txt':
                        if isinstance(final_obj_to_save, str):
                            save_file_success = save_text_file(trans_path, final_obj_to_save)
                        else:
                            log_debug(f"Save Error: Plugin for .txt file {trans_path} did not return a string.")
                            save_file_success = False
                    else:
                        # Fallback for unknown extensions
                        save_file_success = save_text_file(trans_path, str(final_obj_to_save))

                    if not save_file_success:
                        success_all = False
                        break
                
                if success_all:
                    self.mw.unsaved_changes = False
                    self.mw.edited_data = {}
                    if global_keys_backup is not None:
                        self.mw.current_game_rules.original_keys = global_keys_backup
                        
                    # Don't reload entire project to avoid freezing on full issue recalculation
                    self.mw.edited_file_data = output_data_list

                    if ask_confirmation: QMessageBox.information(self.mw, "Project Saved", "All project translation files saved successfully.")
                    return True
                else: 
                    # Try to restore keys on failure
                    if global_keys_backup is not None:
                        self.mw.current_game_rules.original_keys = global_keys_backup
                    return False
                
            else:
                # Normal single-file save mode
                final_obj_to_save = self.mw.current_game_rules.save_data_to_json_obj(output_data_list, self.mw.block_names)
    
                save_file_success = False
                file_extension = Path(self.mw.edited_json_path).suffix.lower()
                
                if file_extension == '.json':
                    save_file_success = save_json_file(self.mw.edited_json_path, final_obj_to_save)
                elif file_extension == '.txt':
                    if isinstance(final_obj_to_save, str):
                        save_file_success = save_text_file(self.mw.edited_json_path, final_obj_to_save)
                    else:
                        log_debug("Save Error: Plugin for .txt file did not return a string for saving.")
                        QMessageBox.critical(self.mw, "Save Error", "Plugin save format error: expected a string for .txt file.")
                        return False
                
                if save_file_success:
                    self.mw.unsaved_changes = False
                    self.mw.edited_data = {} 
                    
                    # Backup and restore keys since we are just re-parsing to update UI data
                    plugin_keys_backup = None
                    if hasattr(self.mw.current_game_rules, 'original_keys'):
                        plugin_keys_backup = list(self.mw.current_game_rules.original_keys)
                        
                    reloaded_edited_data, _ = self.mw.current_game_rules.load_data_from_json_obj(final_obj_to_save)
                    
                    if plugin_keys_backup is not None and hasattr(self.mw.current_game_rules, 'original_keys'):
                        self.mw.current_game_rules.original_keys = plugin_keys_backup
                        
                    self.mw.edited_file_data = reloaded_edited_data
    
                    if ask_confirmation: QMessageBox.information(self.mw, "Saved", f"Changes saved to\n'{Path(self.mw.edited_json_path).name}'.")
                    return True
                else: return False
        except Exception as e:
            log_error(f"Unexpected error during save prep: {e}", exc_info=True)
            QMessageBox.critical(self.mw, "Save Error", f"Unexpected error during save prep:\n{e}"); 
            return False

    def revert_edited_file_to_original(self):
        is_project_mode = hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project

        if not is_project_mode:
            if not self.mw.json_path or not self.mw.edited_json_path: QMessageBox.warning(self.mw, "Revert Error", "Original or Changes file path is not set."); return False
            if not self.mw.data: QMessageBox.warning(self.mw, "Revert Error", "Original data is not loaded."); return False
            if not self.mw.current_game_rules: QMessageBox.critical(self.mw, "Revert Error", "No game plugin active to format the save file."); return False
    
            reply = QMessageBox.question(self.mw, 'Revert Changes File', f"This will overwrite the file:\n{Path(self.mw.edited_json_path).name}\nwith the content from:\n{Path(self.mw.json_path).name}\n\nAll previous edits in the changes file will be lost.\nCurrent unsaved edits in memory will also be discarded.\n\nAre you sure?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No: return False
            try:
                output_data = self.mw.current_game_rules.save_data_to_json_obj(self.mw.data, self.mw.block_names)
    
                save_file_success = False
                file_extension = Path(self.mw.edited_json_path).suffix.lower()
    
                if file_extension == '.json':
                    save_file_success = save_json_file(self.mw.edited_json_path, output_data)
                elif file_extension == '.txt':
                    if isinstance(output_data, str):
                        save_file_success = save_text_file(self.mw.edited_json_path, output_data)
                    else:
                        log_debug("Revert Error: Plugin for .txt file did not return a string for saving.")
                        QMessageBox.critical(self.mw, "Revert Error", "Plugin save format error: expected a string for .txt file.")
                        return False
    
                if save_file_success:
                    self.mw.unsaved_changes = False; self.mw.edited_data = {}; 
                    
                    # Backup and restore keys since we are reading translation data
                    plugin_keys_backup = None
                    if hasattr(self.mw.current_game_rules, 'original_keys'):
                        plugin_keys_backup = list(self.mw.current_game_rules.original_keys)
                        
                    reverted_data_list, _ = self.mw.current_game_rules.load_data_from_json_obj(output_data)
                    
                    if plugin_keys_backup is not None and hasattr(self.mw.current_game_rules, 'original_keys'):
                        self.mw.current_game_rules.original_keys = plugin_keys_backup
                        
                    self.mw.edited_file_data = reverted_data_list
    
                    QMessageBox.information(self.mw, "Reverted", f"Changes file '{Path(self.mw.edited_json_path).name}' has been reverted to match the original.")
                    self.mw.ui_updater.update_title(); 
                    self.mw.ui_updater.populate_strings_for_block(self.mw.current_block_idx) 
                    return True
                else: return False
            except Exception as e:
                log_error(f"Unexpected error during revert: {e}", exc_info=True)
                QMessageBox.critical(self.mw, "Revert Error", f"Unexpected error during revert:\n{e}"); 
                return False
        else:
            # Project mode revert
            reply = QMessageBox.question(self.mw, 'Revert Project Changes', "This will overwrite all active block translation files with original data.\nAll previous edits in the translation files will be lost.\nCurrent unsaved edits in memory will also be discarded.\n\nAre you sure?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No: return False
            
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
                    
                    # Extract original self.mw.data
                    file_data_list = [self.mw.data[d_idx] for d_idx in data_indices]
                    file_block_names = {str(i): self.mw.block_names.get(str(d_idx), 'Unknown') for i, d_idx in enumerate(data_indices)}

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
                    else:
                        save_file_success = save_text_file(trans_path, str(final_obj_to_save))

                    if not save_file_success:
                        success_all = False
                        break
                        
                if success_all:
                    self.mw.unsaved_changes = False
                    self.mw.edited_data = {}
                    if global_keys_backup is not None:
                        self.mw.current_game_rules.original_keys = global_keys_backup
                        
                    # Reload blocks
                    if hasattr(self.mw, 'project_action_handler') and self.mw.project_action_handler:
                        self.mw.project_action_handler._populate_blocks_from_project()

                    QMessageBox.information(self.mw, "Project Reverted", "All project translation files reverted successfully.")
                    return True
                else: 
                    if global_keys_backup is not None:
                        self.mw.current_game_rules.original_keys = global_keys_backup
                    return False

            except Exception as e:
                log_error(f"Unexpected error during project revert: {e}", exc_info=True)
                QMessageBox.critical(self.mw, "Revert Error", f"Unexpected error during project revert:\n{e}"); 
                return False