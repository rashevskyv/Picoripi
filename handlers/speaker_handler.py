# handlers/speaker_handler.py
from typing import Any, Optional, Tuple
from PyQt6.QtWidgets import QTreeWidgetItem
from PyQt6.QtCore import Qt, QTimer
from .base_handler import BaseHandler
from utils.logging_utils import log_debug, log_info

class SpeakerHandler(BaseHandler):
    """Handles virtual speaker folder navigation, persistence, and pending row retention."""
    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any):
        """Initialize a new instance."""
        super().__init__(main_window, data_processor, ui_updater)
        self._pending_speaker_retention: Optional[Tuple[str, Tuple[int, int], int]] = None

    def _clear_pending_speaker_retention(self, next_tuple: Optional[Tuple[int, int]] = None) -> None:
        """Drop a temporarily retained speaker row once the user navigates away from it."""
        pending = self._pending_speaker_retention
        if not pending:
            return

        speaker_name, retained_tuple, _ = pending
        if next_tuple == retained_tuple:
            return

        self._pending_speaker_retention = None

        if getattr(self.mw.data_store, 'current_block_idx', None) != -3:
            return
        if getattr(self.mw.data_store, 'current_speaker_name', None) != speaker_name:
            return

        mappings = list(getattr(self.mw.data_store, 'chapter_mappings', []))
        if retained_tuple not in mappings:
            return

        mappings.remove(retained_tuple)
        self.mw.data_store.chapter_mappings = mappings
        if hasattr(self.ui_updater, 'populate_strings_for_block'):
            self.ui_updater.populate_strings_for_block(-3)

    def _restore_editor_focus_after_speaker_save(self) -> None:
        """Return focus from the editable speaker combobox to the main editor."""
        editor = getattr(self.mw, 'edited_text_edit', None)
        if not editor or not hasattr(editor, 'setFocus'):
            return

        def focus_editor() -> None:
            try:
                editor.setFocus(Qt.FocusReason.OtherFocusReason)
            except TypeError:
                editor.setFocus()

        QTimer.singleShot(0, focus_editor)

    def _expand_item_ancestors(self, item: QTreeWidgetItem) -> None:
        """Ensure the selected virtual folder remains visible after a tree rebuild."""
        parent = item.parent()
        while parent:
            parent.setExpanded(True)
            parent = parent.parent()

    def save_speaker_for_current_string(self, char_name: str) -> None:
        """Save speaker assignment for the current string and refresh UI."""
        char_name = char_name.strip()

        # Prevent redundant saves and selection changes when the user clicks/opens the combobox
        cb = getattr(self.mw, 'speaker_combobox', None)
        is_undoing_redoing = False
        if hasattr(self.mw, 'undo_manager') and self.mw.undo_manager:
            is_undoing_redoing = self.mw.undo_manager.is_undoing_redoing

        if cb is not None and not is_undoing_redoing:
            last_displayed = getattr(cb, '_last_displayed_char', None)
            if last_displayed is not None and char_name == last_displayed:
                return

        block_idx = self.mw.data_store.physical_block_idx
        string_idx = self.mw.data_store.current_string_idx

        if block_idx == -1 or string_idx == -1:
            return

        pm = getattr(self.mw, 'project_manager', None)
        if not pm or not pm.project:
            return

        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(block_idx, block_idx)
        if proj_b_idx >= len(pm.project.blocks):
            return

        block = pm.project.blocks[proj_b_idx]
        assignments = block.metadata.setdefault("character_assignments", {})

        old_char = assignments.get(str(string_idx))

        # Normalize none/empty values to avoid false triggers upon dropdown focus/activation
        is_none_or_empty_new = (not char_name or char_name.lower() == "none")
        is_none_or_empty_old = (not old_char or old_char.lower() == "none")

        if old_char == char_name or (is_none_or_empty_new and is_none_or_empty_old):
            return

        # Record undo action
        if hasattr(self.mw, 'undo_manager') and self.mw.undo_manager and not is_undoing_redoing:
            self.mw.undo_manager.record_action(
                action_type='CHANGE_SPEAKER',
                block_idx=block_idx,
                string_idx=string_idx,
                old_text=old_char or "",
                new_text=char_name or ""
            )

        if is_none_or_empty_new:
            assignments.pop(str(string_idx), None)
        else:
            assignments[str(string_idx)] = char_name

        pm.save()

        current_item = self.mw.block_list_widget.currentItem()
        override_block_idx = None
        override_folder_id = None
        if current_item:
            override_block_idx = current_item.data(0, Qt.ItemDataRole.UserRole)
            override_folder_id = current_item.data(0, Qt.ItemDataRole.UserRole + 1)

        # Ensure we stay in virtual mode if we are editing inside virtual speakers/chapters directories
        current_speaker_name_in_store = getattr(self.mw.data_store, 'current_speaker_name', None)
        current_chapter_id_in_store = getattr(self.mw.data_store, 'current_chapter_id', None)
        if current_speaker_name_in_store is not None:
            override_block_idx = -3
            override_folder_id = current_speaker_name_in_store
            if hasattr(self.mw, 'list_selection_handler'):
                self.mw.list_selection_handler._target_block_idx = block_idx
                self.mw.list_selection_handler._target_string_idx = string_idx
            retained_tuple = (block_idx, string_idx)
            current_mappings = list(getattr(self.mw.data_store, 'chapter_mappings', []))
            retention_index = current_mappings.index(retained_tuple) if retained_tuple in current_mappings else len(current_mappings)
            self._pending_speaker_retention = (current_speaker_name_in_store, retained_tuple, retention_index)
        elif current_chapter_id_in_store is not None:
            override_block_idx = -2
            if hasattr(self.mw, 'list_selection_handler'):
                self.mw.list_selection_handler._target_block_idx = block_idx
                self.mw.list_selection_handler._target_string_idx = string_idx
        else:
            if hasattr(self.mw, 'list_selection_handler'):
                self.mw.list_selection_handler._target_block_idx = block_idx
                self.mw.list_selection_handler._target_string_idx = string_idx

        previous_programmatic_state = self.mw.is_programmatically_changing_text
        self.mw.is_programmatically_changing_text = True
        try:
            if override_block_idx == -3 and current_speaker_name_in_store:
                # Rebuild tree so items have updated mappings lists
                self.ui_updater.block_list_updater.populate_blocks(override_folder_id=override_folder_id, override_block_idx=override_block_idx)

                # Find the active speaker item in the block tree to get its updated mappings
                active_item = None
                from PyQt6.QtWidgets import QTreeWidgetItemIterator
                iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
                while iterator.value():
                    item = iterator.value()
                    if item.data(0, Qt.UserRole) == -3 and item.data(0, Qt.UserRole + 15) == current_speaker_name_in_store:
                        active_item = item
                        break
                    iterator += 1

                if active_item:
                    # Update chapter_mappings from the freshly-rebuilt item, then refresh
                    # the preview WITHOUT treating emitted selection signals as navigation.
                    new_mappings = active_item.data(0, Qt.UserRole + 13) or []
                    retained_tuple = (block_idx, string_idx)
                    pending_retention = self._pending_speaker_retention
                    retention_index = 0
                    is_retained_by_pending = (
                        pending_retention is not None
                        and pending_retention[0] == current_speaker_name_in_store
                        and pending_retention[1] == retained_tuple
                    )
                    if is_retained_by_pending:
                        retention_index = pending_retention[2]

                    if retained_tuple not in new_mappings:
                        new_mappings = list(new_mappings)
                        new_mappings.insert(min(max(retention_index, 0), len(new_mappings)), retained_tuple)
                        active_item.setData(0, Qt.UserRole + 13, new_mappings)
                        self._pending_speaker_retention = (current_speaker_name_in_store, retained_tuple, retention_index)
                    elif is_retained_by_pending:
                        self._pending_speaker_retention = (current_speaker_name_in_store, retained_tuple, retention_index)
                    else:
                        self._pending_speaker_retention = None
                    self.mw.data_store.chapter_mappings = new_mappings
                    self.mw.data_store.current_block_idx = -3
                    self.mw.data_store.physical_block_idx = block_idx
                    self.mw.data_store.current_string_idx = string_idx
                    self.mw.data_store.current_speaker_name = current_speaker_name_in_store
                    block_list_widget = getattr(self.mw, 'block_list_widget', None)
                    if block_list_widget:
                        signals_were_blocked = block_list_widget.blockSignals(True)
                        try:
                            self._expand_item_ancestors(active_item)
                            block_list_widget.setCurrentItem(active_item)
                            active_item.setSelected(True)
                        finally:
                            block_list_widget.blockSignals(signals_were_blocked)
                    self.ui_updater.populate_strings_for_block(-3)
                    self.mw.data_store.current_block_idx = -3
                    self.mw.data_store.physical_block_idx = block_idx
                    self.mw.data_store.current_string_idx = string_idx
                    self.mw.data_store.current_speaker_name = current_speaker_name_in_store
                    if hasattr(self.mw, 'list_selection_handler'):
                        self.mw.list_selection_handler._target_block_idx = None
                        self.mw.list_selection_handler._target_string_idx = None
                    self.ui_updater.update_text_views()
                    if hasattr(self.mw, 'string_settings_updater'):
                        self.mw.string_settings_updater.update_string_settings_panel()
                    self.ui_updater.update_statusbar_paths()
                else:
                    self.mw.data_store.chapter_mappings = []
                    self.mw.data_store.current_block_idx = -3
                    self.mw.data_store.physical_block_idx = block_idx
                    self.mw.data_store.current_string_idx = string_idx
                    self.mw.data_store.current_speaker_name = current_speaker_name_in_store
                    self.ui_updater.populate_strings_for_block(-3)
                    self.ui_updater.update_text_views()
                    if hasattr(self.mw, 'string_settings_updater'):
                        self.mw.string_settings_updater.update_string_settings_panel()
            else:
                self.ui_updater.block_list_updater.populate_blocks(override_folder_id=override_folder_id, override_block_idx=override_block_idx)
                if hasattr(self.mw, 'string_settings_updater'):
                    self.mw.string_settings_updater.update_string_settings_panel()
        finally:
            self.mw.is_programmatically_changing_text = previous_programmatic_state

        self._restore_editor_focus_after_speaker_save()
        self.data_processor.schedule_autosave()

    def save_character_for_current_string(self, char_name: str) -> None:
        """Alias for save_speaker_for_current_string to maintain compatibility."""
        self.save_speaker_for_current_string(char_name)
