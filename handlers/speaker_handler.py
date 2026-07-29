# handlers/speaker_handler.py
from typing import Any, Optional, Tuple
from PyQt6.QtWidgets import QMessageBox, QTreeWidgetItem
from PyQt6.QtCore import Qt, QTimer
from core.data_store import ViewKind, get_view_kind
from core.mempalace.story_timeline import StoryVirtualProjection
from core.story_context_overrides import (
    get_story_context_override,
    update_story_context_override,
)
from .base_handler import BaseHandler

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

        if get_view_kind(self.mw.data_store) != ViewKind.SPEAKER:
            return
        if getattr(self.mw.data_store, 'current_speaker_name', None) != speaker_name:
            return

        mappings = list(getattr(self.mw.data_store, 'chapter_mappings', []))
        if retained_tuple not in mappings:
            return

        mappings.remove(retained_tuple)
        self.mw.data_store.chapter_mappings = mappings
        if hasattr(self.ui_updater, 'populate_strings_for_block'):
            self.ui_updater.populate_current_view()

    def _restore_editor_focus_after_speaker_save(self) -> None:
        """Return focus from the editable speaker combobox to the main editor."""
        editor = getattr(self.mw, 'edited_text_edit', None)
        if not editor or not hasattr(editor, 'setFocus'):
            return

        def focus_editor() -> None:
            try:
                from PyQt6 import sip
                from PyQt6.QtCore import QObject
            except ImportError:
                import sip
                from PyQt6.QtCore import QObject

            def is_qt_deleted(obj: Any) -> bool:
                try:
                    return isinstance(obj, QObject) and sip.isdeleted(obj)
                except (TypeError, RuntimeError):
                    return True

            try:
                if not self.mw or is_qt_deleted(self.mw):
                    return
                if not editor or is_qt_deleted(editor):
                    return
                editor.setFocus(Qt.FocusReason.OtherFocusReason)
            except TypeError:
                try:
                    if editor and not is_qt_deleted(editor):
                        editor.setFocus()
                except Exception:
                    pass
            except RuntimeError:
                pass

        QTimer.singleShot(0, focus_editor)

    def _expand_item_ancestors(self, item: QTreeWidgetItem) -> None:
        """Ensure the selected virtual folder remains visible after a tree rebuild."""
        parent = item.parent()
        while parent:
            parent.setExpanded(True)
            parent = parent.parent()

    @staticmethod
    def _tree_item_locator(item: QTreeWidgetItem | None):
        """Capture one tree item's exact ancestry without retaining deleted Qt objects."""
        if not isinstance(item, QTreeWidgetItem):
            return None
        path = []
        cursor = item
        while isinstance(cursor, QTreeWidgetItem):
            path.append((
                cursor.text(0),
                cursor.data(0, Qt.UserRole),
                cursor.data(0, Qt.UserRole + 1),
                cursor.data(0, Qt.UserRole + 11),
                cursor.data(0, Qt.UserRole + 15),
                cursor.data(0, Qt.UserRole + 16),
                cursor.data(0, Qt.UserRole + 17),
                cursor.data(0, Qt.UserRole + 19),
            ))
            cursor = cursor.parent()
        return tuple(reversed(path))

    def _find_tree_item_by_locator(self, locator):
        """Find the rebuilt item at the same exact tree path."""
        tree = getattr(self.mw, "block_list_widget", None)
        if tree is None or not locator:
            return None
        from PyQt6.QtWidgets import QTreeWidgetItemIterator

        iterator = QTreeWidgetItemIterator(tree)
        while iterator.value():
            item = iterator.value()
            if self._tree_item_locator(item) == locator:
                return item
            iterator += 1
        return None

    def _restore_tree_selection(self, locator):
        """Restore the exact pre-edit tree item without emitting navigation signals."""
        tree = getattr(self.mw, "block_list_widget", None)
        item = self._find_tree_item_by_locator(locator)
        if tree is None or item is None:
            return None
        signals_were_blocked = tree.blockSignals(True)
        try:
            tree.clearSelection()
            self._expand_item_ancestors(item)
            tree.setCurrentItem(item)
            item.setSelected(True)
        finally:
            tree.blockSignals(signals_were_blocked)
        return item

    def _story_client_and_document(self):
        """Return the active normalized-story client and document, if available."""
        translation = getattr(self.mw, "translation_handler", None)
        composer = getattr(translation, "prompt_composer", None)
        client = composer._get_mempalace_client() if composer else None
        block_updater = getattr(getattr(self.mw, "ui_updater", None), "block_list_updater", None)
        projection = getattr(block_updater, "_story_projection_cache", None)
        document_id = (
            projection.document_id
            if isinstance(projection, StoryVirtualProjection) else None
        )
        return client, document_id

    def _selected_physical_rows(self) -> list[tuple[int, int]]:
        """Return the editor selection as unique physical game-string rows."""
        store = getattr(self.mw, "data_store", None)
        selected = getattr(store, "selected_string_indices", None)
        if not isinstance(selected, (list, tuple, set)):
            return []
        physical_block = getattr(store, "physical_block_idx", -1)
        if physical_block is None or physical_block < 0:
            physical_block = getattr(store, "current_block_idx", -1)
        rows = []
        for value in selected:
            if isinstance(value, (tuple, list)) and len(value) == 2:
                row = (int(value[0]), int(value[1]))
            elif physical_block is not None and physical_block >= 0:
                row = (int(physical_block), int(value))
            else:
                continue
            if row not in rows:
                rows.append(row)
        return rows

    def _continuation_row_after_removal(self, source_rows, removed_rows):
        """Choose the next surviving row after a batch leaves the current view."""
        source_rows = list(source_rows or [])
        removed = set(removed_rows or [])
        removed_positions = [
            index for index, row in enumerate(source_rows) if row in removed
        ]
        if not removed_positions:
            return None

        def is_row_non_empty(row):
            try:
                text, _ = self.data_processor.get_current_string_text(row[0], row[1])
                if not text:
                    return False
                from utils.utils import remove_all_tags
                return bool(remove_all_tags(text).strip())
            except Exception:
                return True

        # 1. Search downwards for a non-empty surviving row
        for row in source_rows[max(removed_positions) + 1:]:
            if row not in removed and is_row_non_empty(row):
                return row

        # 2. Search upwards for a non-empty surviving row
        for row in reversed(source_rows[:min(removed_positions)]):
            if row not in removed and is_row_non_empty(row):
                return row

        # 3. Fallback: Search downwards for any surviving row
        for row in source_rows[max(removed_positions) + 1:]:
            if row not in removed:
                return row

        # 4. Fallback: Search upwards for any surviving row
        for row in reversed(source_rows[:min(removed_positions)]):
            if row not in removed:
                return row

        return None


    def _restore_source_view_after_rebuild(self, locator, continuation_row=None):
        """Restore a virtual source folder and its nearest surviving row."""
        item = self._restore_tree_selection(locator)
        if item is None:
            return False
        mappings = [
            tuple(row) for row in (item.data(0, Qt.UserRole + 13) or ())
            if isinstance(row, (tuple, list)) and len(row) == 2
        ]
        if not mappings:
            return True
        self.mw.data_store.chapter_mappings = mappings
        current_row = (
            self.mw.data_store.physical_block_idx,
            self.mw.data_store.current_string_idx,
        )
        row_to_select = (
            current_row if current_row in mappings
            else continuation_row if continuation_row in mappings
            else mappings[0]
        )
        block_idx, string_idx = row_to_select
        self.mw.data_store.current_block_idx = block_idx
        self.mw.data_store.physical_block_idx = block_idx
        self.mw.data_store.current_string_idx = string_idx
        self.mw.data_store.selected_string_indices = [row_to_select]
        preview = getattr(self.mw, "preview_text_edit", None)
        reset = getattr(preview, "reset_selection_state", None)
        if callable(reset):
            reset()
        populate_view = getattr(self.ui_updater, "populate_current_view", None)
        if callable(populate_view):
            populate_view(force=True)
        return True

    def _save_speaker_for_selected_rows(self, char_name: str) -> bool:
        """Apply an entered speaker to every selected row in one project update."""
        rows = self._selected_physical_rows()
        if len(rows) < 2:
            return False
        manager = getattr(self.mw, "project_manager", None)
        if manager is None or getattr(manager, "project", None) is None:
            return False

        tree = getattr(self.mw, "block_list_widget", None)
        selected_tree_locator = self._tree_item_locator(
            tree.currentItem() if tree is not None else None
        )
        source_mappings = list(
            tree.currentItem().data(0, Qt.UserRole + 13) or []
            if tree is not None and tree.currentItem() is not None
            else getattr(self.mw.data_store, "displayed_string_indices", []) or []
        )
        continuation_row = self._continuation_row_after_removal(
            source_mappings, rows
        )

        undo_mgr = getattr(self.mw, "undo_manager", None)
        before = undo_mgr.get_project_snapshot() if undo_mgr else None
        value = char_name if char_name and char_name.casefold() != "none" else "None"
        changed = sum(
            bool(update_story_context_override(
                self.mw, block_idx, string_idx, speaker=value
            ))
            for block_idx, string_idx in rows
        )
        if not changed:
            return False

        manager.save()
        if undo_mgr and before is not None:
            undo_mgr.record_structural_action(
                before,
                "ASSIGN_STORY_CONTEXT",
                f"Change speaker for {changed} string(s): {value}",
            )
        block_updater = getattr(self.ui_updater, "block_list_updater", None)
        if block_updater is not None:
            block_updater.populate_blocks()
            restored_item = self._restore_tree_selection(selected_tree_locator)
            if restored_item is not None:
                mappings = list(restored_item.data(0, Qt.UserRole + 13) or [])
                self.mw.data_store.chapter_mappings = mappings
                current_row = (
                    self.mw.data_store.physical_block_idx,
                    self.mw.data_store.current_string_idx,
                )
                row_to_select = (
                    continuation_row
                    if continuation_row in mappings
                    else current_row if current_row in mappings
                    else mappings[0] if mappings else None
                )
                if row_to_select is not None:
                    block_idx, string_idx = row_to_select
                    self.mw.data_store.current_block_idx = block_idx
                    self.mw.data_store.physical_block_idx = block_idx
                    self.mw.data_store.current_string_idx = string_idx
                    self.mw.data_store.selected_string_indices = [row_to_select]
                    preview = getattr(self.mw, "preview_text_edit", None)
                    reset_selection = getattr(preview, "reset_selection_state", None)
                    if callable(reset_selection):
                        reset_selection()
                if hasattr(self.ui_updater, "populate_current_view"):
                    self.ui_updater.populate_current_view(force=True)
        settings = getattr(self.mw, "string_settings_updater", None)
        if settings is not None:
            settings.clear_story_context_cache()
            settings.update_string_settings_panel()
        self.data_processor.schedule_autosave()
        status_bar = getattr(self.mw, "statusBar", None)
        if callable(status_bar):
            status_bar().showMessage(
                f"Changed speaker for {changed} selected string(s): {value}", 5000
            )
        self._restore_editor_focus_after_speaker_save()
        return True

    def open_current_string_in_markup_studio(self) -> bool:
        """Reveal the source node linked to the currently selected game string."""
        block_idx = getattr(self.mw.data_store, "physical_block_idx", -1)
        string_idx = getattr(self.mw.data_store, "current_string_idx", -1)
        if block_idx < 0 or string_idx < 0:
            return False
        client, document_id = self._story_client_and_document()
        node = (
            client.get_story_navigation_target(str(block_idx), string_idx, document_id)
            if client else None
        )
        if node is None or node.start_line is None:
            QMessageBox.information(
                self.mw,
                "No marked-script link yet",
                "This game string is not linked to a marked script line yet. "
                "Run Story Context matching after saving the current Markup Studio project.",
            )
            return False
        project_path = client.get_story_document_source_path(document_id)
        actions = getattr(self.mw, "actions", None)
        open_studio = getattr(actions, "open_script_markup_studio", None)
        if not project_path or not callable(open_studio):
            return False
        open_studio()
        studio = getattr(self.mw, "script_markup_studio_dialog", None)
        navigate = getattr(studio, "open_hierarchy_project_at_line", None)
        if studio is None or not callable(navigate) or not navigate(project_path, node.start_line):
            QMessageBox.warning(
                self.mw,
                "Could not open marked line",
                "Markup Studio opened, but the linked source line could not be shown.",
            )
            return False
        studio.show()
        studio.raise_()
        studio.activateWindow()
        return True

    def save_speaker_for_current_string(self, char_name: str) -> None:
        """Save speaker assignment for the current string and refresh UI."""
        combo = getattr(self.mw, "speaker_combobox", None)
        if getattr(combo, "_story_role", "speaker") == "item":
            return
        char_name = char_name.strip()

        # Prevent redundant saves and selection changes when the user clicks/opens the combobox
        cb = getattr(self.mw, 'speaker_combobox', None)
        is_undoing_redoing = False
        if hasattr(self.mw, 'undo_manager') and self.mw.undo_manager:
            is_undoing_redoing = self.mw.undo_manager.is_undoing_redoing

        if cb is not None and not is_undoing_redoing:
            last_displayed = getattr(cb, '_last_displayed_char', None)
            if (
                last_displayed is not None
                and char_name == last_displayed
                and len(self._selected_physical_rows()) < 2
            ):
                return

        block_idx = self.mw.data_store.physical_block_idx
        string_idx = self.mw.data_store.current_string_idx

        if block_idx == -1 or string_idx == -1:
            return

        if self._save_speaker_for_selected_rows(char_name):
            return

        tree = getattr(self.mw, "block_list_widget", None)
        selected_tree_locator = self._tree_item_locator(
            tree.currentItem() if tree is not None else None
        )

        client, document_id = self._story_client_and_document()
        if client is not None and document_id is not None:
            manual = get_story_context_override(self.mw, block_idx, string_idx)
            current = client.get_story_speakers_for_game_string(
                str(block_idx), string_idx, document_id
            )
            visible_current = manual.get("speaker") or (current[0] if len(current) == 1 else None)
            if visible_current == char_name:
                return
            node = client.get_story_navigation_target(
                str(block_idx), string_idx, document_id
            )
            if node is None or node.start_line is None:
                speaker = None if not char_name or char_name.casefold() == "none" else char_name
                if not update_story_context_override(
                    self.mw, block_idx, string_idx, speaker=speaker
                ):
                    return
                manager = getattr(self.mw, "project_manager", None)
                if manager:
                    manager.save()
                block_updater = getattr(self.ui_updater, "block_list_updater", None)
                if block_updater is not None:
                    block_updater.populate_blocks()
                    self._restore_tree_selection(selected_tree_locator)
                settings = getattr(self.mw, "string_settings_updater", None)
                if settings is not None:
                    settings.clear_story_context_cache()
                    settings.update_string_settings_panel()
                self.data_processor.schedule_autosave()
                self._restore_editor_focus_after_speaker_save()
                return
            if not char_name or char_name.casefold() == "none":
                QMessageBox.information(
                    self.mw,
                    "Choose a speaker",
                    "A marked dialogue must have an owning speaker. To remove or rebuild "
                    "the speaker block, open this line in Markup Studio.",
                )
                if cb is not None:
                    cb.setCurrentText(", ".join(current) if current else "None")
                return
            project_path = client.get_story_document_source_path(document_id)
            actions = getattr(self.mw, "actions", None)
            open_studio = getattr(actions, "open_script_markup_studio", None)
            if callable(open_studio):
                open_studio()
            studio = getattr(self.mw, "script_markup_studio_dialog", None)
            assign = getattr(studio, "assign_speaker_at_line", None)
            if callable(assign) and assign(project_path, node.start_line, char_name):
                cb._last_displayed_char = char_name
                self._restore_editor_focus_after_speaker_save()
                return
            QMessageBox.warning(
                self.mw,
                "Could not change speaker",
                "The linked Text block or its owning Speaker block could not be updated.",
            )
            if cb is not None:
                cb.setCurrentText(", ".join(current) if current else "None")
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
                active_item = self._find_tree_item_by_locator(selected_tree_locator)
                from PyQt6.QtWidgets import QTreeWidgetItemIterator
                if active_item is None:
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
                    self.mw.data_store.current_block_idx = block_idx
                    self.mw.data_store.set_view_kind(ViewKind.SPEAKER)
                    self.mw.data_store.physical_block_idx = block_idx
                    self.mw.data_store.current_string_idx = string_idx
                    self.mw.data_store.current_speaker_name = current_speaker_name_in_store
                    block_list_widget = getattr(self.mw, 'block_list_widget', None)
                    if block_list_widget:
                        signals_were_blocked = block_list_widget.blockSignals(True)
                        try:
                            block_list_widget.clearSelection()
                            self._expand_item_ancestors(active_item)
                            block_list_widget.setCurrentItem(active_item)
                            active_item.setSelected(True)
                        finally:
                            block_list_widget.blockSignals(signals_were_blocked)
                    self.ui_updater.populate_current_view()
                    self.mw.data_store.current_block_idx = block_idx
                    self.mw.data_store.set_view_kind(ViewKind.SPEAKER)
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
                    self.mw.data_store.current_block_idx = block_idx
                    self.mw.data_store.set_view_kind(ViewKind.SPEAKER)
                    self.mw.data_store.physical_block_idx = block_idx
                    self.mw.data_store.current_string_idx = string_idx
                    self.mw.data_store.current_speaker_name = current_speaker_name_in_store
                    self.ui_updater.populate_current_view()
                    self.ui_updater.update_text_views()
                    if hasattr(self.mw, 'string_settings_updater'):
                        self.mw.string_settings_updater.update_string_settings_panel()
            else:
                self.ui_updater.block_list_updater.populate_blocks(override_folder_id=override_folder_id, override_block_idx=override_block_idx)
                self._restore_tree_selection(selected_tree_locator)
                if hasattr(self.mw, 'string_settings_updater'):
                    self.mw.string_settings_updater.update_string_settings_panel()
        finally:
            self.mw.is_programmatically_changing_text = previous_programmatic_state

        self._restore_editor_focus_after_speaker_save()
        self.data_processor.schedule_autosave()

    def save_chapter_for_current_string(self, structure_id=None) -> None:
        """Persist a manual chapter/scene assignment for the current game row."""
        block_idx = getattr(self.mw.data_store, "physical_block_idx", -1)
        string_idx = getattr(self.mw.data_store, "current_string_idx", -1)
        if block_idx < 0 or string_idx < 0:
            return
        tree = getattr(self.mw, "block_list_widget", None)
        current_item = tree.currentItem() if tree is not None else None
        source_locator = self._tree_item_locator(current_item)
        source_mappings = [
            tuple(row) for row in (current_item.data(0, Qt.UserRole + 13) or ())
            if isinstance(row, (tuple, list)) and len(row) == 2
        ] if current_item is not None else []
        continuation_row = self._continuation_row_after_removal(
            source_mappings, [(block_idx, string_idx)]
        )
        combo = getattr(self.mw, "chapter_combobox", None)
        if structure_id is None and combo is not None:
            structure_id = combo.currentData()
        path = []
        if combo is not None and structure_id is not None:
            if hasattr(combo, "current_story_path"):
                path = list(combo.current_story_path())
            else:
                path = combo.currentText().split(" › ")
        if not update_story_context_override(
            self.mw,
            block_idx,
            string_idx,
            structure_id=structure_id,
            structure_path=path,
        ):
            return
        manager = getattr(self.mw, "project_manager", None)
        if manager:
            manager.save()
        block_updater = getattr(self.ui_updater, "block_list_updater", None)
        if block_updater is not None:
            block_updater.populate_blocks()
            restored = self._restore_source_view_after_rebuild(
                source_locator, continuation_row
            )
            if not restored and getattr(block_updater, "_is_loading_chapters", False):
                when_ready = getattr(block_updater, "when_virtual_blocks_ready", None)
                if callable(when_ready):
                    when_ready(
                        lambda: self._restore_source_view_after_rebuild(
                            source_locator, continuation_row
                        )
                    )
        settings = getattr(self.mw, "string_settings_updater", None)
        if settings is not None:
            settings.clear_story_context_cache()
            settings.update_string_settings_panel()
        self.data_processor.schedule_autosave()

    def save_character_for_current_string(self, char_name: str) -> None:
        """Alias for save_speaker_for_current_string to maintain compatibility."""
        self.save_speaker_for_current_string(char_name)
