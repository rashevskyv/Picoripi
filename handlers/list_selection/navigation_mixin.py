"""Tree navigation helpers for list selection."""
from __future__ import annotations

from PyQt6.QtWidgets import QTreeWidgetItemIterator
from PyQt6.QtCore import Qt, QSignalBlocker


class NavigationMixin:
    """Tree navigation helpers for list selection."""

    def navigate_between_blocks(self, forward: bool) -> None:
        """Handle global Alt+Shift+Up/Down to jump to next/prev block in the tree."""
        self.virtual_folder_handler.navigate_between_blocks(forward)

    def navigate_between_folders(self, forward: bool) -> None:
        """Handle global Alt+Shift+Left/Right to jump to next/prev folder in the tree."""
        self.virtual_folder_handler.navigate_between_folders(forward)

    def _select_virtual_tree_item(self, role_offset: int, value, kind: int | None = None) -> bool:
        if value is None:
            return False
        target = (
            self.mw.data_store.physical_block_idx,
            self.mw.data_store.current_string_idx,
        )
        iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.UserRole + role_offset) == value and (
                kind is None or item.data(0, Qt.UserRole) == kind
            ):
                mappings = item.data(0, Qt.UserRole + 13) or []
                if target not in mappings:
                    iterator += 1
                    continue
                self._target_block_idx, self._target_string_idx = target
                parent = item.parent()
                while parent is not None:
                    parent.setExpanded(True)
                    parent = parent.parent()
                previous = self.mw.block_list_widget.currentItem()
                # Invoke the selection route explicitly. Tree signals may be
                # temporarily blocked while a large project tree is refreshed;
                # navigation must still switch to the virtual block reliably.
                blocker = QSignalBlocker(self.mw.block_list_widget)
                self.mw.block_list_widget.setCurrentItem(item)
                del blocker
                self.block_selected(item, previous)
                self.mw.block_list_widget.scrollToItem(item)
                return (
                    self.mw.data_store.view_block_token == kind
                    and self.mw.data_store.current_string_idx == target[1]
                    and self.mw.data_store.physical_block_idx == target[0]
                )
            iterator += 1
        return False

    def navigate_to_current_story_structure(self) -> bool:
        label = getattr(self.mw, "chapter_value_label", None)
        structure_id = getattr(label, "story_structure_id", None)
        return bool(label is not None and self._select_virtual_tree_item(11, structure_id, -2))

    def navigate_to_current_story_role(self) -> bool:
        combo = getattr(self.mw, "speaker_combobox", None)
        name = combo.currentText().strip() if combo is not None else ""
        role = getattr(combo, "_story_role", "speaker") if combo is not None else "speaker"
        offset, kind = (16, -4) if role == "item" else (15, -3)
        return self._select_virtual_tree_item(offset, name, kind) if name and name != "None" else False

    def navigate_to_current_physical_block(self) -> bool:
        return self.navigate_to_physical_string(
            self.mw.data_store.physical_block_idx,
            self.mw.data_store.current_string_idx,
        )

    def navigate_to_physical_string(self, block_idx: int, string_idx: int) -> bool:
        """Select one concrete project row, regardless of the current virtual folder."""
        self._target_block_idx = int(block_idx)
        self._target_string_idx = int(string_idx)
        iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.UserRole) == int(block_idx):
                previous = self.mw.block_list_widget.currentItem()
                blocker = QSignalBlocker(self.mw.block_list_widget)
                self.mw.block_list_widget.setCurrentItem(item)
                del blocker
                self.block_selected(item, previous)
                self.mw.block_list_widget.scrollToItem(item)
                self.select_string_by_absolute_index(int(string_idx))
                preview_edit = getattr(self.mw, 'preview_text_edit', None)
                if preview_edit and hasattr(preview_edit, 'set_selected_lines'):
                    rel_idx = self._get_relative_index(int(string_idx))
                    if rel_idx != -1:
                        preview_edit.set_selected_lines([rel_idx], force=True)
                self._target_block_idx = None
                self._target_string_idx = None
                return True
            iterator += 1
        self._target_block_idx = None
        self._target_string_idx = None
        return False
