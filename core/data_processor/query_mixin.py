"""Query and edit-state helpers for DataStateProcessor."""
import datetime
from typing import List, Tuple

from core.tag_utils import strip_tags
from utils.logging_utils import log_debug


class QueryMixin:
    """String text queries and edited-data updates."""

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
