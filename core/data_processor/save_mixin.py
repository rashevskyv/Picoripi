"""Save helpers for DataStateProcessor."""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from components.toast import ToastNotification
from core.data_manager import save_json_file, save_text_file
from core.state_manager import AppState
from utils.logging_utils import log_debug, log_error, log_info, log_warning


class SaveMixin:
    """Disk save implementation and save entrypoints."""

    def _perform_save_impl(self, output_data_list: List[Any], progress_callback=None, edited_data_for_transaction: Optional[Dict[Tuple[int, int], str]] = None) -> Tuple[bool, List[Tuple[str, int, int]], List[str]]:
        """Internal helper to perform save impl."""
        warnings = []
        errors = []

        edited_data = edited_data_for_transaction if edited_data_for_transaction is not None else self.mw.data_store.edited_data

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
                original_keys = getattr(self.mw.current_game_rules, 'original_keys', None)
                if original_keys is not None:
                    try:
                        global_keys_backup = list(original_keys)
                    except TypeError:
                        global_keys_backup = None

                files_saved_in_this_transaction = set()

                # Determine which files have edits
                files_to_save = {}
                for trans_file_rel, data_indices in file_to_data_indices.items():
                    has_edits = False
                    for d_idx in data_indices:
                        if isinstance(output_data_list[d_idx], list):
                            for s_idx in range(len(output_data_list[d_idx])):
                                if (d_idx, s_idx) in edited_data:
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
                        if all(0 <= d_idx < len(global_keys_backup) for d_idx in data_indices):
                            sliced_keys = [global_keys_backup[d_idx] for d_idx in data_indices]
                            self.mw.current_game_rules.original_keys = sliced_keys
                        else:
                            log_warning(
                                "Project save skipped plugin original_keys slicing because the key snapshot is incomplete.",
                                category="file_ops"
                            )

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

    def save_current_edits(self, ask_confirmation: bool = True, on_finished_callback: Optional[Any] = None) -> bool:
        """
        Save current edits.

        Returns:
            bool: In async mode, returns True if the saving process was successfully started
                  (or was not needed/skipped). In sync mode, returns True if saving to disk succeeded.
                  Returns False if saving failed or couldn't be started.
        """
        if hasattr(self.mw, 'state') and self.mw.state and self.mw.state.is_active(AppState.SAVING_DATA):
            log_debug("Save requested but a save operation is already in progress. Ignoring.", category="file_ops")
            if on_finished_callback:
                on_finished_callback(False)
            return False

        log_debug(f"--> AppActionHandler: save_data_action called. ask_confirmation={ask_confirmation}, current unsaved={self.mw.data_store.unsaved_changes}", category="file_ops")
        is_project_mode = hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project
        if not is_project_mode:
            if self.mw.data_store.json_path and not self.mw.data_store.edited_json_path:
                self.mw.data_store.edited_json_path = self.mw.app_action_handler._derive_edited_path(self.mw.data_store.json_path)
            if not self.mw.data_store.edited_json_path:
                self._show_message("Save Error", "Edited file path is not set. Cannot save.", type="warning")
                if on_finished_callback:
                    on_finished_callback(False)
                return False
        if not self.mw.current_game_rules:
            self._show_message("Save Error", "No game plugin active to format the save file.", type="error")
            if on_finished_callback:
                on_finished_callback(False)
            return False

        if not self.mw.data_store.unsaved_changes:
            log_debug("Save called but no unsaved changes detected. Skipping file write.", category="file_ops")
            if ask_confirmation:
                self._show_message("Save", "No changes to save.", type="info")
            if on_finished_callback:
                on_finished_callback(True)
            return True

        if ask_confirmation:
            if is_project_mode:
                msg = "Save changes to all project translation files?"
            else:
                msg = f"Save changes to '{Path(self.mw.data_store.edited_json_path).name}'?"
            reply = self._ask_yes_no('Save Changes', msg, default_yes=True)
            if not reply:
                if on_finished_callback:
                    on_finished_callback(False)
                return False

        try:
            if not self.mw.data_store.data:
                self._show_message("Save Error", "Original data not loaded. Cannot save.", type="error")
                if on_finished_callback:
                    on_finished_callback(False)
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
                    if on_finished_callback:
                        on_finished_callback(False)
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

                ToastNotification.show_toast(self.mw, "All project translation files saved successfully.")
                if hasattr(self.mw, 'issue_scan_handler'):
                    self.mw.issue_scan_handler._save_issues_cache()
                if on_finished_callback:
                    on_finished_callback(True)
                return True

            # If running in production mode, delegate the async saving process to AppActionHandler
            if hasattr(self.mw, 'app_action_handler') and self.mw.app_action_handler:
                def on_save_done(success: bool, warnings: List[Any], errors: List[Any]):
                    if success:
                        self.mw.data_store.unsaved_changes = False
                        self.mw.data_store.edited_data = {}
                        self.mw.data_store.edited_sublines.clear()
                        self.mw.data_store.edited_file_data = output_data_list

                        for archive_rel_path, new_size, orig_size in warnings:
                            if getattr(self.mw, 'show_archive_size_warnings', True):
                                if hasattr(self.mw, 'ui_provider') and self.mw.ui_provider:
                                    self.mw.ui_provider.show_archive_size_warning(archive_rel_path, new_size, orig_size)

                        ToastNotification.show_toast(self.mw, "All project translation files saved successfully.")
                        if hasattr(self.mw, 'issue_scan_handler'):
                            self.mw.issue_scan_handler._save_issues_cache()

                        if hasattr(self, '_autosave_session'):
                            self._autosave_session(force=True)

                    if on_finished_callback:
                        on_finished_callback(success)

                self.mw.app_action_handler.perform_async_save_flow(output_data_list, ask_confirmation, on_finished_callback=on_save_done, edited_data_for_transaction=self.mw.data_store.edited_data.copy())
                return True
            else:
                # Fallback to sync saving if app_action_handler is not available
                success, warnings, errors = self._perform_save_impl(output_data_list)
                if not success:
                    if errors:
                        self._show_message("Save Error", "\n".join(errors), type="error")
                    if on_finished_callback:
                        on_finished_callback(False)
                    return False

                self.mw.data_store.unsaved_changes = False
                self.mw.data_store.edited_data = {}
                self.mw.data_store.edited_sublines.clear()
                self.mw.data_store.edited_file_data = output_data_list

                for archive_rel_path, new_size, orig_size in warnings:
                    if getattr(self.mw, 'show_archive_size_warnings', True):
                        if hasattr(self.mw, 'ui_provider') and self.mw.ui_provider:
                            self.mw.ui_provider.show_archive_size_warning(archive_rel_path, new_size, orig_size)

                ToastNotification.show_toast(self.mw, "All project translation files saved successfully.")
                if hasattr(self.mw, 'issue_scan_handler'):
                    self.mw.issue_scan_handler._save_issues_cache()
                if on_finished_callback:
                    on_finished_callback(True)
                return True

        except Exception as e:
            log_error(f"Unexpected error during save: {e}", exc_info=True)
            self._show_message("Save Error", f"Unexpected error during save:\n{e}", type="error")
            if on_finished_callback:
                on_finished_callback(False)
            return False

    def save_specific_edits(self, strings_to_save: List[Tuple[int, int]], ask_confirmation: bool = True, on_finished_callback: Optional[Any] = None) -> bool:
        """
        Saves only the specified strings to the translation files on disk.
        Other unsaved edits remain in memory as unsaved changes.

        Returns:
            bool: In async mode, returns True if the saving process was successfully started
                  (or was not needed/skipped). In sync mode, returns True if saving to disk succeeded.
                  Returns False if saving failed or couldn't be started.
        """
        if hasattr(self.mw, 'state') and self.mw.state and self.mw.state.is_active(AppState.SAVING_DATA):
            log_debug("Save specific edits requested but a save operation is already in progress. Ignoring.", category="file_ops")
            if on_finished_callback:
                on_finished_callback(False)
            return False

        log_info(f"DSP: save_specific_edits called for {len(strings_to_save)} strings", category="file_ops")
        if not strings_to_save:
            if on_finished_callback:
                on_finished_callback(True)
            return True

        is_project_mode = hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project
        if not is_project_mode:
            if not self.mw.data_store.edited_json_path:
                self._show_message("Save Error", "Edited file path is not set. Cannot save.", type="warning")
                if on_finished_callback:
                    on_finished_callback(False)
                return False
        if not self.mw.current_game_rules:
            self._show_message("Save Error", "No game plugin active to format the save file.", type="error")
            if on_finished_callback:
                on_finished_callback(False)
            return False
        if not self.mw.data_store.data:
            self._show_message("Save Error", "Original data not loaded. Cannot save.", type="error")
            if on_finished_callback:
                on_finished_callback(False)
            return False

        # Filter the edits to save
        original_edited_data = self.mw.data_store.edited_data.copy()
        filtered_edited_data = {k: v for k, v in original_edited_data.items() if k in strings_to_save}

        if not filtered_edited_data:
            if ask_confirmation:
                self._show_message("Save", "No changes to save for the selected items.", type="info")
            if on_finished_callback:
                on_finished_callback(True)
            return True

        if ask_confirmation:
            num = len(filtered_edited_data)
            reply = self._ask_yes_no('Save Changes', f"Save {num} selected change(s) to files?", default_yes=True)
            if not reply:
                if on_finished_callback:
                    on_finished_callback(False)
                return False

        try:
            # Build the merged save snapshot
            source_data = self.mw.data_store.data
            edited_file_data = self.mw.data_store.edited_file_data or []

            output_data_list = []
            for i in range(len(source_data)):
                if i < len(edited_file_data) and edited_file_data[i]:
                    chosen_block = list(edited_file_data[i])
                else:
                    chosen_block = list(source_data[i])

                # Apply only the filtered changes that we want to save in this transaction
                for (b_idx, s_idx), text in filtered_edited_data.items():
                    if b_idx == i:
                        if 0 <= s_idx < len(chosen_block):
                            chosen_block[s_idx] = text
                output_data_list.append(chosen_block)

            # Check if running under pytest to preserve synchronous path
            import sys
            success = False
            if 'pytest' in sys.modules:
                success, warnings, errors = self._perform_save_impl(output_data_list, edited_data_for_transaction=filtered_edited_data)
                if not success:
                    if errors:
                        self._show_message("Save Error", "\n".join(errors), type="error")
                    if on_finished_callback:
                        on_finished_callback(False)
                    return False

                # Restore remaining unsaved changes to memory
                remaining_edits = {k: v for k, v in original_edited_data.items() if k not in filtered_edited_data}
                self.mw.data_store.edited_data = remaining_edits
                self.mw.data_store.unsaved_changes = len(remaining_edits) > 0
                self.mw.data_store.edited_file_data = output_data_list

                if hasattr(self.mw, 'helper'):
                    self.mw.helper.rebuild_unsaved_block_indices()

                if hasattr(self.mw, 'ui_updater'):
                    affected_blocks = {b_idx for (b_idx, s_idx) in filtered_edited_data.keys()}
                    if hasattr(self.mw.ui_updater, 'refresh_block_tree_indicators'):
                        self.mw.ui_updater.refresh_block_tree_indicators()
                    else:
                        for b_idx in affected_blocks:
                            self.mw.ui_updater.update_block_item_text_with_problem_count(b_idx)
                    self.mw.ui_updater.update_title()

                    if self.mw.data_store.current_block_idx in affected_blocks:
                        self.mw.ui_updater.populate_current_view()
                    if getattr(self.mw.data_store, 'show_unsaved_blocks_only', False):
                        self.mw.ui_updater.block_list_updater.populate_blocks()

                self._autosave_session(force=True)
                if on_finished_callback:
                    on_finished_callback(True)
                return True
            else:
                if hasattr(self.mw, 'app_action_handler') and self.mw.app_action_handler:
                    def on_specific_save_done(success: bool, warnings: List[Any], errors: List[Any]):
                        if success:
                            remaining_edits = {k: v for k, v in original_edited_data.items() if k not in filtered_edited_data}
                            self.mw.data_store.edited_data = remaining_edits
                            self.mw.data_store.unsaved_changes = len(remaining_edits) > 0
                            self.mw.data_store.edited_file_data = output_data_list

                            if hasattr(self.mw, 'helper'):
                                self.mw.helper.rebuild_unsaved_block_indices()

                            if hasattr(self.mw, 'ui_updater'):
                                affected_blocks = {b_idx for (b_idx, s_idx) in filtered_edited_data.keys()}
                                if hasattr(self.mw.ui_updater, 'refresh_block_tree_indicators'):
                                    self.mw.ui_updater.refresh_block_tree_indicators()
                                else:
                                    for b_idx in affected_blocks:
                                        self.mw.ui_updater.update_block_item_text_with_problem_count(b_idx)
                                self.mw.ui_updater.update_title()

                                if self.mw.data_store.current_block_idx in affected_blocks:
                                    self.mw.ui_updater.populate_current_view()
                                if getattr(self.mw.data_store, 'show_unsaved_blocks_only', False):
                                    self.mw.ui_updater.block_list_updater.populate_blocks()

                            self._autosave_session(force=True)

                        if on_finished_callback:
                            on_finished_callback(success)

                    self.mw.app_action_handler.perform_async_save_flow(output_data_list, ask_confirmation=False, on_finished_callback=on_specific_save_done, edited_data_for_transaction=filtered_edited_data)
                    return True
                else:
                    success, warnings, errors = self._perform_save_impl(output_data_list, edited_data_for_transaction=filtered_edited_data)
                    if not success:
                        if errors:
                            self._show_message("Save Error", "\n".join(errors), type="error")
                        if on_finished_callback:
                            on_finished_callback(False)
                        return False

                    remaining_edits = {k: v for k, v in original_edited_data.items() if k not in filtered_edited_data}
                    self.mw.data_store.edited_data = remaining_edits
                    self.mw.data_store.unsaved_changes = len(remaining_edits) > 0
                    self.mw.data_store.edited_file_data = output_data_list

                    if hasattr(self.mw, 'helper'):
                        self.mw.helper.rebuild_unsaved_block_indices()

                    if hasattr(self.mw, 'ui_updater'):
                        affected_blocks = {b_idx for (b_idx, s_idx) in filtered_edited_data.keys()}
                        if hasattr(self.mw.ui_updater, 'refresh_block_tree_indicators'):
                            self.mw.ui_updater.refresh_block_tree_indicators()
                        else:
                            for b_idx in affected_blocks:
                                self.mw.ui_updater.update_block_item_text_with_problem_count(b_idx)
                        self.mw.ui_updater.update_title()

                        if self.mw.data_store.current_block_idx in affected_blocks:
                            self.mw.ui_updater.populate_current_view()
                        if getattr(self.mw.data_store, 'show_unsaved_blocks_only', False):
                            self.mw.ui_updater.block_list_updater.populate_blocks()

                    self._autosave_session(force=True)
                    if on_finished_callback:
                        on_finished_callback(True)
                    return True

        except Exception as e:
            self.mw.data_store.edited_data = original_edited_data
            log_error(f"Unexpected error during partial save: {e}", exc_info=True)
            self._show_message("Save Error", f"Unexpected error during save:\n{e}", type="error")
            if on_finished_callback:
                on_finished_callback(False)
            return False
