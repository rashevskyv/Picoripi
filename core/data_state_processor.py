from typing import List, Dict, Tuple, Optional, Any, Union, Set
import json
import re
import datetime
from pathlib import Path
from .data_manager import load_json_file, save_json_file, save_text_file
from .state_manager import AppState
from utils.logging_utils import log_debug, log_info, log_warning, log_error
from components.toast import ToastNotification

import pickle
from PyQt6.QtCore import QTimer
from .data_processor.session_manager import SessionManager
from .data_processor.revert_manager import RevertManager
from .data_processor.set_calculator import SetCalculator
from core.tag_utils import strip_tags

class DataStateProcessor:
    """Data state processor implementation."""
    def __init__(self, main_window: Any):
        """Initialize a new instance."""
        self.mw = main_window

        # Decomposed managers
        self.session_manager = SessionManager(self)
        self.revert_manager = RevertManager(self)
        self.set_calculator = SetCalculator(self)

        try:
            self.autosave_timer = QTimer()
            self.autosave_timer.setSingleShot(True)
            self.autosave_timer.setInterval(2000)  # 2 seconds debounce
            self.autosave_timer.timeout.connect(self._autosave_session)

            self.durable_session_timer = QTimer()
            self.durable_session_timer.setInterval(300000)  # 5 minutes
            self.durable_session_timer.timeout.connect(lambda: self._save_durable_session_json(force=False))
            self.durable_session_timer.start()
        except Exception as e:
            log_warning(f"DSP: Failed to initialize QTimer (probably running in non-GUI test environment): {e}")
            self.autosave_timer = None
            self.durable_session_timer = None

    @property
    def _session_dirty(self) -> bool:
        return self.session_manager._session_dirty

    @_session_dirty.setter
    def _session_dirty(self, val: bool) -> None:
        self.session_manager._session_dirty = val

    @property
    def _durable_session_dirty(self) -> bool:
        return self.session_manager._durable_session_dirty

    @_durable_session_dirty.setter
    def _durable_session_dirty(self, val: bool) -> None:
        self.session_manager._durable_session_dirty = val

    def _show_message(self, title: str, text: str, type: str = "info"):
        """Internal helper to show message."""
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
        """Internal helper to ask yes no."""
        if hasattr(self.mw, 'ui_provider') and self.mw.ui_provider:
            return self.mw.ui_provider.ask_yes_no(title, text, default_yes)
        return default_yes

    def _get_string_from_source(self, block_idx: int, string_idx: int, source_data: List[Any], source_name: str) -> Optional[str]:
        """Internal helper to get the string from source."""
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
        """Get the current string text."""
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
        """Get the block texts."""
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
        cleaned_original = strip_tags(original_text).strip()
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
        """Update the edited data."""
        if action_type != "TEXT_EDIT":
            if hasattr(self.mw, 'editor_operation_handler') and self.mw.editor_operation_handler:
                self.mw.editor_operation_handler.stop_and_flush_editor_changes()

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

        # Incremental index updates (A05)
        store = self.mw.data_store
        if hasattr(store, '_index_empty') and block_idx in store._index_empty:
            orig_text = self._get_string_from_source(block_idx, string_idx, store.data, "readonly")
            is_empty = (not orig_text or not orig_text.strip()) and (not new_text or not str(new_text).strip())
            if is_empty:
                store._index_empty[block_idx].add(string_idx)
            else:
                store._index_empty[block_idx].discard(string_idx)

        if hasattr(store, '_index_translated') and block_idx in store._index_translated:
            if self.is_string_translated(block_idx, string_idx):
                store._index_translated[block_idx].add(string_idx)
            else:
                store._index_translated[block_idx].discard(string_idx)

        if hasattr(store, '_index_unsaved') and block_idx in store._index_unsaved:
            if edit_key in store.edited_data:
                store._index_unsaved[block_idx].add(string_idx)
            else:
                store._index_unsaved[block_idx].discard(string_idx)

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

        # Trigger session autosave timer
        self.schedule_autosave()

        return unsaved_status_actually_changed

    def revert_strings_to_original(self, block_idx: int, string_indices: List[int], progress_dialog=None, progress_offset: int = 0) -> int:
        """Reverts multiple strings in a block to their original state (from the loaded file)."""
        return self.revert_manager.revert_strings_to_original(block_idx, string_indices, progress_dialog, progress_offset)

    def perform_revert_strings(self, block_idx: int, string_indices: List[Any], confirm: bool = True) -> None:
        """Unified revert function with optional confirmation and UI updates."""
        self.revert_manager.perform_revert_strings(block_idx, string_indices, confirm)

    def revert_blocks_to_original(self, block_indices: List[int]) -> None:
        """Reverts entire blocks to their state from the loaded edited file (or original)."""
        self.revert_manager.revert_blocks_to_original(block_indices)


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

    def revert_edited_file_to_original(self) -> bool:
        """Revert edited file to original."""
        return self.revert_manager.revert_edited_file_to_original()

    def get_session_file_path(self) -> Optional[Path]:
        """Get the file path for saving/loading session data."""
        return self.session_manager.get_session_file_path()

    def get_durable_session_file_path(self) -> Optional[Path]:
        """Get the file path for saving/loading durable JSON session data."""
        return self.session_manager.get_durable_session_file_path()

    def _serialize_action(self, action: Any) -> dict:
        return self.session_manager._serialize_action(action)

    def _deserialize_action(self, data: dict) -> Any:
        return self.session_manager._deserialize_action(data)

    def serialize_session_to_json(self, snapshot: dict) -> dict:
        """Serialize AppDataStore snapshot to a JSON-compatible dictionary."""
        return self.session_manager.serialize_session_to_json(snapshot)

    def deserialize_session_from_json(self, json_data: dict) -> dict:
        """Deserialize JSON-compatible dictionary to AppDataStore snapshot format."""
        return self.session_manager.deserialize_session_from_json(json_data)

    def schedule_autosave(self) -> None:
        """Schedule session autosave after a short delay (debounce)."""
        self.session_manager.schedule_autosave()

    def _autosave_session(self, force: bool = False) -> None:
        """Autosave entire data_store into a pickle file if dirty or forced."""
        self.session_manager._autosave_session(force)

    def _save_durable_session_json(self, force: bool = False) -> bool:
        """Autosave entire data_store into a JSON file if dirty or forced."""
        return self.session_manager._save_durable_session_json(force)

    def finalize_clean_shutdown_checkpoint(self) -> bool:
        """Finalize the fast Pickle checkpoint for a clean application exit."""
        return self.session_manager.finalize_clean_shutdown_checkpoint()

    def load_session_file(self) -> bool:
        """Load entire project state from a JSON file (preferred) or a pickle file (fallback)."""
        return self.session_manager.load_session_file()

    def clear_session_file(self) -> None:
        """Delete the temporary session file if it exists."""
        self.session_manager.clear_session_file()

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

    # === Fast Filtering Indexes (A05) ===

    def get_empty_set(self, block_idx: int) -> Set[int]:
        """Get or build the set of empty string indices for the given block."""
        return self.set_calculator.get_empty_set(block_idx)

    def get_translated_set(self, block_idx: int) -> Set[int]:
        """Get or build the set of translated string indices for the given block."""
        return self.set_calculator.get_translated_set(block_idx)

    def get_needs_translation_set(self, block_idx: int) -> Set[int]:
        """Get or build the set of strings whose original text needs translation."""
        return self.set_calculator.get_needs_translation_set(block_idx)

    def get_unsaved_set(self, block_idx: int) -> Set[int]:
        """Get or build the set of unsaved string indices for the given block."""
        return self.set_calculator.get_unsaved_set(block_idx)

    def get_overrides_set(self, block_idx: int) -> Set[int]:
        """Get or build the set of override string indices for the given block."""
        return self.set_calculator.get_overrides_set(block_idx)

    def get_categorized_set(self, block_idx: int) -> Set[int]:
        """Get or build the set of categorized string indices for the given block."""
        return self.set_calculator.get_categorized_set(block_idx)

    def ensure_index_warnings(self, block_idx: int):
        """Helper to build warnings index if it is missing."""
        self.set_calculator.ensure_index_warnings(block_idx)

    def get_warnings_matching_set(self, block_idx: int, active_filters: List[str], detection_config: dict) -> Set[int]:
        """Get the set of string indices matching active or enabled warnings."""
        return self.set_calculator.get_warnings_matching_set(block_idx, active_filters, detection_config)
