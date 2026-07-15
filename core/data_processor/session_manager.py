import json
import pickle
import time
import os
import base64
import uuid
from pathlib import Path
from typing import Any, Optional
from utils.logging_utils import log_debug, log_info, log_warning, log_error

class SessionManager:
    """Manages session serialization, autosaving, durable JSON checkpoints, and fallbacks."""
    def __init__(self, data_processor: Any):
        """Initialize a new instance."""
        self.dsp = data_processor
        self.mw = data_processor.mw
        self._session_dirty = False
        self._durable_session_dirty = False
        self._last_pickle_checkpoint_id = None
        self._last_pickle_saved_at = 0.0

    def get_session_file_path(self) -> Optional[Path]:
        """Get the file path for saving/loading session data."""
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager:
            p_dir = getattr(self.mw.project_manager, 'project_dir', None)
            if p_dir and isinstance(p_dir, (str, Path)):
                return Path(p_dir) / ".picoripi_session"
        if hasattr(self.mw, 'data_store') and self.mw.data_store:
            ed_path = getattr(self.mw.data_store, 'edited_json_path', None)
            if ed_path and isinstance(ed_path, (str, Path)):
                return Path(ed_path).parent / ".picoripi_session"
        return None

    def get_durable_session_file_path(self) -> Optional[Path]:
        """Get the file path for saving/loading durable JSON session data."""
        p_path = self.get_session_file_path()
        if p_path:
            return p_path.with_name(p_path.name + ".json")
        return None

    def _attach_runtime_session_state(self, snapshot: dict) -> dict:
        """Add runtime-only state that lives outside AppDataStore."""
        game_rules = getattr(self.mw, 'current_game_rules', None)
        original_keys = getattr(game_rules, 'original_keys', None)
        if original_keys is not None:
            try:
                snapshot["plugin_original_keys"] = list(original_keys)
            except TypeError:
                pass
        export_runtime_state = getattr(game_rules, 'export_runtime_session_state', None)
        if callable(export_runtime_state):
            try:
                runtime_state = export_runtime_state()
                if isinstance(runtime_state, dict) and runtime_state:
                    snapshot["plugin_runtime_state"] = runtime_state
            except Exception as e:
                log_warning(f"DSP: Failed to export plugin runtime state: {e}")
        return snapshot

    def _restore_runtime_session_state(self, snapshot: dict) -> None:
        """Restore runtime-only state that is required before project saves."""
        game_rules = getattr(self.mw, 'current_game_rules', None)
        if game_rules is None:
            return
        if "plugin_original_keys" in snapshot and hasattr(game_rules, 'original_keys'):
            plugin_keys = snapshot.get("plugin_original_keys")
            if plugin_keys is not None:
                game_rules.original_keys = list(plugin_keys or [])

        restore_runtime_state = getattr(game_rules, 'restore_runtime_session_state', None)
        runtime_state = snapshot.get("plugin_runtime_state")
        if callable(restore_runtime_state) and isinstance(runtime_state, dict) and runtime_state:
            try:
                restore_runtime_state(runtime_state)
            except Exception as e:
                log_warning(f"DSP: Failed to restore plugin runtime state: {e}")

    def _to_json_safe_value(self, value: Any) -> Any:
        """Convert nested session values to JSON-safe primitives."""
        if isinstance(value, bytes):
            return {
                "__picoripi_type__": "bytes",
                "base64": base64.b64encode(value).decode("ascii")
            }
        if isinstance(value, bytearray):
            return self._to_json_safe_value(bytes(value))
        if isinstance(value, tuple):
            return [self._to_json_safe_value(item) for item in value]
        if isinstance(value, list):
            return [self._to_json_safe_value(item) for item in value]
        if isinstance(value, dict):
            return {str(key): self._to_json_safe_value(val) for key, val in value.items()}
        if isinstance(value, set):
            return [self._to_json_safe_value(item) for item in value]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    def _from_json_safe_value(self, value: Any) -> Any:
        """Restore nested values encoded by _to_json_safe_value."""
        if isinstance(value, list):
            return [self._from_json_safe_value(item) for item in value]
        if isinstance(value, dict):
            if value.get("__picoripi_type__") == "bytes":
                try:
                    return base64.b64decode(value.get("base64", ""))
                except Exception:
                    return b""
            return {key: self._from_json_safe_value(val) for key, val in value.items()}
        return value

    def _serialize_action(self, action: Any) -> dict:
        from core.undo_manager import UndoAction, GroupAction, StructuralAction
        if isinstance(action, UndoAction):
            return {
                "type": "UndoAction",
                "action_type": action.action_type,
                "block_idx": action.block_idx,
                "string_idx": action.string_idx,
                "old_text": action.old_text,
                "new_text": action.new_text,
                "timestamp": action.timestamp,
                "cursor_pos": action.cursor_pos,
                "metadata": action.metadata
            }
        elif isinstance(action, GroupAction):
            return {
                "type": "GroupAction",
                "actions": [self._serialize_action(a) for a in action.actions],
                "action_type": action.action_type,
                "timestamp": action.timestamp
            }
        elif isinstance(action, StructuralAction):
            return {
                "type": "StructuralAction",
                "action_type": action.action_type,
                "before_snapshot": action.before_snapshot,
                "after_snapshot": action.after_snapshot,
                "label": action.label,
                "timestamp": action.timestamp
            }
        return {}

    def _deserialize_action(self, data: dict) -> Any:
        from core.undo_manager import UndoAction, GroupAction, StructuralAction
        if not data:
            return None
        action_type = data.get("type")
        if action_type == "UndoAction":
            return UndoAction(
                action_type=data["action_type"],
                block_idx=data["block_idx"],
                string_idx=data["string_idx"],
                old_text=data["old_text"],
                new_text=data["new_text"],
                timestamp=data["timestamp"],
                cursor_pos=data.get("cursor_pos"),
                metadata=data.get("metadata")
            )
        elif action_type == "GroupAction":
            actions = [self._deserialize_action(a) for a in data["actions"] if a]
            return GroupAction(
                actions=actions,
                action_type=data["action_type"],
                timestamp=data["timestamp"]
            )
        elif action_type == "StructuralAction":
            return StructuralAction(
                action_type=data["action_type"],
                before_snapshot=data["before_snapshot"],
                after_snapshot=data["after_snapshot"],
                label=data["label"],
                timestamp=data["timestamp"]
            )
        return None

    def serialize_session_to_json(self, snapshot: dict) -> dict:
        """Serialize AppDataStore snapshot to a JSON-compatible dictionary."""
        edited_data_serialized = {}
        for (b_idx, s_idx), text in snapshot.get("edited_data", {}).items():
            edited_data_serialized[f"{b_idx},{s_idx}"] = text

        unsaved_blocks = list(snapshot.get("unsaved_block_indices", []))

        problems_serialized = {}
        for key, val in snapshot.get("problems_per_subline", {}).items():
            if isinstance(key, tuple) and len(key) == 3:
                key_str = f"{key[0]},{key[1]},{key[2]}"
                problems_serialized[key_str] = list(val) if isinstance(val, (set, list)) else val

        undo_stack_serialized = [self._serialize_action(a) for a in snapshot.get("undo_stack", [])]
        redo_stack_serialized = [self._serialize_action(a) for a in snapshot.get("redo_stack", [])]

        block_to_file_serialized = {}
        for key, val in snapshot.get("block_to_project_file_map", {}).items():
            block_to_file_serialized[str(key)] = val

        json_snapshot = {
            "version": 1,
            "saved_at": snapshot.get("saved_at", 0.0),
            "checkpoint_id": snapshot.get("checkpoint_id"),
            "json_path": snapshot.get("json_path"),
            "edited_json_path": snapshot.get("edited_json_path"),
            "data": self._to_json_safe_value(snapshot.get("data", [])),
            "edited_file_data": self._to_json_safe_value(snapshot.get("edited_file_data", [])),
            "edited_data": edited_data_serialized,
            "current_block_idx": snapshot.get("current_block_idx", -1),
            "_physical_block_idx": snapshot.get("_physical_block_idx", -1),
            "current_string_idx": snapshot.get("current_string_idx", -1),
            "selected_string_indices": snapshot.get("selected_string_indices", []),
            "current_category_name": snapshot.get("current_category_name"),
            "current_character_name": snapshot.get("current_character_name"),
            "last_selected_block_index": snapshot.get("last_selected_block_index", -1),
            "last_selected_string_index": snapshot.get("last_selected_string_index", -1),
            "highlight_categorized": snapshot.get("highlight_categorized", False),
            "hide_categorized": snapshot.get("hide_categorized", False),
            "hide_translated": snapshot.get("hide_translated", False),
            "hide_original_tags": snapshot.get("hide_original_tags", False),
            "hide_translation_tags": snapshot.get("hide_translation_tags", False),
            "show_overrides_only": snapshot.get("show_overrides_only", False),
            "hide_empty_strings": snapshot.get("hide_empty_strings", False),
            "show_unsaved_only": snapshot.get("show_unsaved_only", False),
            "show_unsaved_blocks_only": snapshot.get("show_unsaved_blocks_only", False),
            "show_warnings_only": snapshot.get("show_warnings_only", False),
            "active_warning_filters": snapshot.get("active_warning_filters", []),
            "undo_stack": undo_stack_serialized,
            "redo_stack": redo_stack_serialized,
            "block_names": snapshot.get("block_names", {}),
            "unsaved_changes": snapshot.get("unsaved_changes", False),
            "unsaved_block_indices": unsaved_blocks,
            "block_to_project_file_map": block_to_file_serialized,
            "problems_per_subline": problems_serialized,
            "plugin_original_keys": snapshot.get("plugin_original_keys"),
            "plugin_runtime_state": self._to_json_safe_value(snapshot.get("plugin_runtime_state")),
        }
        return json_snapshot

    def deserialize_session_from_json(self, json_data: dict) -> dict:
        """Deserialize JSON-compatible dictionary to AppDataStore snapshot format."""
        edited_data_deserialized = {}
        for key_str, text in json_data.get("edited_data", {}).items():
            try:
                parts = key_str.split(',')
                if len(parts) == 2:
                    edited_data_deserialized[(int(parts[0]), int(parts[1]))] = text
            except Exception:
                pass

        unsaved_blocks = set(json_data.get("unsaved_block_indices", []))

        problems_deserialized = {}
        for key_str, val in json_data.get("problems_per_subline", {}).items():
            try:
                parts = key_str.split(',')
                if len(parts) == 3:
                    problems_deserialized[(int(parts[0]), int(parts[1]), int(parts[2]))] = set(val)
            except Exception:
                pass

        block_to_file_deserialized = {}
        for key_str, val in json_data.get("block_to_project_file_map", {}).items():
            try:
                block_to_file_deserialized[int(key_str)] = val
            except Exception:
                block_to_file_deserialized[key_str] = val

        undo_stack_deserialized = [self._deserialize_action(a) for a in json_data.get("undo_stack", []) if a]
        redo_stack_deserialized = [self._deserialize_action(a) for a in json_data.get("redo_stack", []) if a]

        snapshot = {
            "version": 1,
            "saved_at": json_data.get("saved_at", 0.0),
            "checkpoint_id": json_data.get("checkpoint_id"),
            "json_path": json_data.get("json_path"),
            "edited_json_path": json_data.get("edited_json_path"),
            "data": self._from_json_safe_value(json_data.get("data", [])),
            "edited_file_data": self._from_json_safe_value(json_data.get("edited_file_data", [])),
            "edited_data": edited_data_deserialized,
            "current_block_idx": json_data.get("current_block_idx", -1),
            "_physical_block_idx": json_data.get("_physical_block_idx", -1),
            "current_string_idx": json_data.get("current_string_idx", -1),
            "selected_string_indices": json_data.get("selected_string_indices", []),
            "current_category_name": json_data.get("current_category_name"),
            "current_character_name": json_data.get("current_character_name"),
            "last_selected_block_index": json_data.get("last_selected_block_index", -1),
            "last_selected_string_index": json_data.get("last_selected_string_index", -1),
            "highlight_categorized": json_data.get("highlight_categorized", False),
            "hide_categorized": json_data.get("hide_categorized", False),
            "hide_translated": json_data.get("hide_translated", False),
            "hide_original_tags": json_data.get("hide_original_tags", False),
            "hide_translation_tags": json_data.get("hide_translation_tags", False),
            "show_overrides_only": json_data.get("show_overrides_only", False),
            "hide_empty_strings": json_data.get("hide_empty_strings", False),
            "show_unsaved_only": json_data.get("show_unsaved_only", False),
            "show_unsaved_blocks_only": json_data.get("show_unsaved_blocks_only", False),
            "show_warnings_only": json_data.get("show_warnings_only", False),
            "active_warning_filters": json_data.get("active_warning_filters", []),
            "undo_stack": undo_stack_deserialized,
            "redo_stack": redo_stack_deserialized,
            "block_names": json_data.get("block_names", {}),
            "unsaved_changes": json_data.get("unsaved_changes", False),
            "unsaved_block_indices": unsaved_blocks,
            "block_to_project_file_map": block_to_file_deserialized,
            "problems_per_subline": problems_deserialized,
            "plugin_original_keys": json_data.get("plugin_original_keys"),
            "plugin_runtime_state": self._from_json_safe_value(json_data.get("plugin_runtime_state")),
        }
        return snapshot

    def schedule_autosave(self) -> None:
        """Schedule session autosave after a short delay (debounce)."""
        self._session_dirty = True
        self._durable_session_dirty = True
        if getattr(self.dsp, 'autosave_timer', None) is not None:
            self.dsp.autosave_timer.start()

    def _autosave_session(self, force: bool = False) -> None:
        """Autosave entire data_store into a pickle file if dirty or forced."""
        if not force and not self._session_dirty:
            return

        session_path = self.get_session_file_path()
        if not session_path:
            return

        try:
            data_store = getattr(self.mw, 'data_store', None)
            if data_store:
                session_path.parent.mkdir(parents=True, exist_ok=True)
                snapshot = data_store.get_session_snapshot()
                self._attach_runtime_session_state(snapshot)
                snapshot["saved_at"] = time.time()
                snapshot["checkpoint_id"] = uuid.uuid4().hex
                with session_path.open('wb') as f:
                    pickle.dump(snapshot, f)
                self._last_pickle_checkpoint_id = snapshot["checkpoint_id"]
                self._last_pickle_saved_at = snapshot["saved_at"]
                self._session_dirty = False
                log_debug(f"DSP: Session autosaved to {session_path}")
        except Exception as e:
            log_error(f"DSP: Failed to autosave session: {e}", exc_info=True)

    def _save_durable_session_json(self, force: bool = False) -> bool:
        """Autosave entire data_store into a JSON file if dirty or forced."""
        if not force and not self._durable_session_dirty:
            return True

        json_path = self.get_durable_session_file_path()
        if not json_path:
            return False

        tmp_path = None
        try:
            data_store = getattr(self.mw, 'data_store', None)
            if data_store:
                json_path.parent.mkdir(parents=True, exist_ok=True)
                snapshot = data_store.get_session_snapshot()
                self._attach_runtime_session_state(snapshot)
                snapshot["saved_at"] = time.time()
                snapshot["checkpoint_id"] = (
                    self._last_pickle_checkpoint_id
                    if self._last_pickle_checkpoint_id
                    and not self._session_dirty
                    and time.time() - self._last_pickle_saved_at < 10.0
                    else uuid.uuid4().hex
                )
                json_snapshot = self.serialize_session_to_json(snapshot)
                
                tmp_path = json_path.with_suffix(json_path.suffix + ".tmp")
                with tmp_path.open('w', encoding='utf-8') as f:
                    # This checkpoint can contain the complete project data.
                    # Pretty-printing adds several megabytes and noticeably
                    # slows both shutdown writes and the next startup read.
                    json.dump(json_snapshot, f, ensure_ascii=False, separators=(',', ':'))
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except Exception:
                        pass
                
                tmp_path.replace(json_path)
                self._durable_session_dirty = False
                log_debug(f"DSP: Durable JSON session saved to {json_path}")
                return True
            return False
        except Exception as e:
            log_error(f"DSP: Failed to save durable JSON session: {e}", exc_info=True)
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
            return False

    def load_session_file(self) -> bool:
        """Load entire project state from a JSON file (preferred) or a pickle file (fallback)."""
        json_path = self.get_durable_session_file_path()
        session_path = self.get_session_file_path()
        
        json_snapshot = None
        json_saved_at = 0.0
        
        pickle_snapshot = None
        pickle_saved_at = 0.0
        checkpoints_match = False

        # Modern clean-shutdown checkpoints carry the same random ID in both
        # files. Pickle is much faster to deserialize than the large durable
        # JSON, so verify that ID from JSON's small prefix and take the fast
        # path without parsing the full JSON document.
        if json_path and json_path.exists() and session_path and session_path.exists():
            try:
                with session_path.open('rb') as f:
                    candidate = pickle.load(f)
                if isinstance(candidate, dict):
                    pickle_snapshot = candidate
                    pickle_saved_at = candidate.get("saved_at", 0.0)
                checkpoint_id = candidate.get("checkpoint_id") if isinstance(candidate, dict) else None
                if checkpoint_id:
                    with json_path.open('r', encoding='utf-8') as f:
                        json_prefix = f.read(512)
                    compact_marker = f'"checkpoint_id":"{checkpoint_id}"'
                    spaced_marker = f'"checkpoint_id": "{checkpoint_id}"'
                    if compact_marker in json_prefix or spaced_marker in json_prefix:
                        checkpoints_match = True
                        self._last_pickle_checkpoint_id = checkpoint_id
                        self._last_pickle_saved_at = pickle_saved_at
                        log_info("DSP: Loaded matching session checkpoint through Pickle fast path")
            except Exception as e:
                log_debug(f"DSP: Pickle fast-path probe failed; using durable fallback: {e}")

        if not checkpoints_match and json_path and json_path.exists():
            try:
                with json_path.open('r', encoding='utf-8') as f:
                    json_data = json.load(f)
                json_snapshot = self.deserialize_session_from_json(json_data)
                if json_snapshot:
                    json_saved_at = json_snapshot.get("saved_at", 0.0)
            except Exception as e:
                log_warning(f"DSP: Failed to load durable JSON session: {e}")
                json_snapshot = None

        # A normal clean shutdown writes Pickle first and the durable JSON
        # immediately afterwards.  Avoid deserializing both multi-megabyte
        # snapshots when the Pickle file cannot possibly be newer.  We still
        # read it when JSON failed or its filesystem timestamp is newer than
        # JSON's embedded timestamp (crash-recovery path).
        should_read_pickle = (
            not checkpoints_match
            and pickle_snapshot is None
            and bool(session_path and session_path.exists())
        )
        if should_read_pickle and json_snapshot:
            try:
                should_read_pickle = session_path.stat().st_mtime > json_saved_at + 0.01
            except OSError:
                should_read_pickle = True
            if not should_read_pickle:
                log_debug("DSP: Durable JSON is current; skipping redundant Pickle deserialization")

        if should_read_pickle:
            try:
                with session_path.open('rb') as f:
                    pickle_snapshot = pickle.load(f)

                if pickle_snapshot and not isinstance(pickle_snapshot, dict):
                    restored_store = pickle_snapshot
                    pickle_snapshot = {
                        "version": 1,
                        "json_path": restored_store.__dict__.get("json_path"),
                        "edited_json_path": restored_store.__dict__.get("edited_json_path"),
                        "data": restored_store.__dict__.get("_data", restored_store.__dict__.get("data", [])),
                        "edited_file_data": restored_store.__dict__.get("edited_file_data", []),
                        "edited_data": dict(restored_store.__dict__.get("edited_data", {})),
                        "current_block_idx": restored_store.__dict__.get("current_block_idx", -1),
                        "_physical_block_idx": restored_store.__dict__.get("_physical_block_idx", -1),
                        "current_string_idx": restored_store.__dict__.get("current_string_idx", -1),
                        "selected_string_indices": restored_store.__dict__.get("selected_string_indices", []),
                        "current_category_name": restored_store.__dict__.get("current_category_name"),
                        "current_character_name": restored_store.__dict__.get("current_character_name"),
                        "last_selected_block_index": restored_store.__dict__.get("last_selected_block_index", -1),
                        "last_selected_string_index": restored_store.__dict__.get("last_selected_string_index", -1),
                        "highlight_categorized": restored_store.__dict__.get("highlight_categorized", False),
                        "hide_categorized": restored_store.__dict__.get("hide_categorized", False),
                        "hide_translated": restored_store.__dict__.get("hide_translated", False),
                        "hide_original_tags": restored_store.__dict__.get("hide_original_tags", False),
                        "hide_translation_tags": restored_store.__dict__.get("hide_translation_tags", False),
                        "show_overrides_only": restored_store.__dict__.get("show_overrides_only", False),
                        "hide_empty_strings": restored_store.__dict__.get("hide_empty_strings", False),
                        "show_unsaved_only": restored_store.__dict__.get("show_unsaved_only", False),
                        "show_unsaved_blocks_only": restored_store.__dict__.get("show_unsaved_blocks_only", False),
                        "show_warnings_only": restored_store.__dict__.get("show_warnings_only", False),
                        "active_warning_filters": restored_store.__dict__.get("active_warning_filters", []),
                        "undo_stack": restored_store.__dict__.get("undo_stack", []),
                        "redo_stack": restored_store.__dict__.get("redo_stack", []),
                        "block_names": restored_store.__dict__.get("block_names", {}),
                        "unsaved_changes": restored_store.__dict__.get("unsaved_changes", False),
                        "unsaved_block_indices": restored_store.__dict__.get("unsaved_block_indices", set()),
                        "block_to_project_file_map": restored_store.__dict__.get("block_to_project_file_map", {}),
                        "problems_per_subline": dict(restored_store.__dict__.get("problems_per_subline", {})),
                        "plugin_original_keys": restored_store.__dict__.get("plugin_original_keys"),
                    }
                if pickle_snapshot:
                    pickle_saved_at = pickle_snapshot.get("saved_at", 0.0)
            except Exception as e:
                log_error(f"DSP: Failed to load pickle fallback session: {e}", exc_info=True)
                pickle_snapshot = None

        snapshot = None
        needs_durable_sync = False

        if checkpoints_match and pickle_snapshot:
            snapshot = pickle_snapshot
            log_info(f"DSP: Loaded matched Pickle/JSON checkpoint from {session_path}")
        elif json_snapshot and pickle_snapshot:
            if pickle_saved_at > json_saved_at:
                snapshot = pickle_snapshot
                needs_durable_sync = True
                log_info(f"DSP: Pickle session is newer than JSON session ({pickle_saved_at} > {json_saved_at}), using Pickle fallback")
            else:
                snapshot = json_snapshot
                log_info(f"DSP: Loaded session from JSON checkpoint {json_path} ({json_saved_at} >= {pickle_saved_at})")
        elif json_snapshot:
            snapshot = json_snapshot
            log_info(f"DSP: Loaded session from JSON checkpoint {json_path}")
        elif pickle_snapshot:
            snapshot = pickle_snapshot
            needs_durable_sync = True
            log_info(f"DSP: Loaded session from Pickle fallback {session_path}")

        if not snapshot:
            return False

        try:
            if hasattr(self.mw, 'data_store') and self.mw.data_store:
                success = self.mw.data_store.restore_from_snapshot(snapshot)
                if not success:
                    return False

                if hasattr(self.mw.data_store, 'block_to_project_file_map'):
                    self.mw.block_to_project_file_map = self.mw.data_store.block_to_project_file_map

                self._restore_runtime_session_state(snapshot)

                log_info("DSP: Successfully restored entire project state from session")

                if hasattr(self.mw, 'ui_updater') and self.mw.ui_updater:
                    self.mw.ui_updater.sync_filter_checkboxes_with_store()

                if hasattr(self.mw, 'helper') and hasattr(self.mw.helper, 'rebuild_unsaved_block_indices'):
                    self.mw.helper.rebuild_unsaved_block_indices()

                if hasattr(self.mw, 'ui_updater') and self.mw.ui_updater:
                    self.mw.ui_updater.update_title()
                    self.mw.ui_updater.populate_blocks()

                    block_idx = self.mw.data_store.current_block_idx
                    category_name = self.mw.data_store.current_category_name
                    string_idx = self.mw.data_store.current_string_idx

                    if block_idx != -1:
                        tree_widget = getattr(self.mw, 'block_list_widget', None)
                        if tree_widget and hasattr(tree_widget, 'select_block_by_index'):
                            tree_widget.select_block_by_index(block_idx, category_name)

                        self.mw.ui_updater.populate_strings_for_block(block_idx, category_name, force=False)

                        if string_idx != -1:
                            self.mw.ui_updater.update_text_views()

                self._session_dirty = False
                self._durable_session_dirty = False
                if getattr(self.dsp, 'autosave_timer', None) is not None:
                    self.dsp.autosave_timer.stop()
                if getattr(self.dsp, 'durable_session_timer', None) is not None:
                    self.dsp.durable_session_timer.start()

                if needs_durable_sync:
                    self._durable_session_dirty = True
                    self._save_durable_session_json(force=True)

                return True
        except Exception as e:
            log_error(f"DSP: Failed to load session: {e}", exc_info=True)
        return False

    def clear_session_file(self) -> None:
        """Delete the temporary session file if it exists."""
        session_path = self.get_session_file_path()
        if session_path and session_path.exists():
            try:
                session_path.unlink()
                log_info(f"DSP: Cleaned up session file {session_path}")
            except Exception as e:
                log_warning(f"DSP: Could not delete session file {session_path}: {e}")
