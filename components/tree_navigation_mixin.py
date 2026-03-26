# components/tree_navigation_mixin.py
"""Navigation and item reordering mixin for CustomTreeWidget."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTreeWidgetItemIterator

from utils.logging_utils import log_debug


class TreeNavigationMixin:
    """Handles keyboard navigation between blocks/folders and toolbar move-up/down."""

    # -------------------------------------------------------------------------
    # Block / folder keyboard navigation
    # -------------------------------------------------------------------------

    def navigate_blocks(self, direction: int):
        log_debug(f"CustomTreeWidget: navigate_blocks direction={direction}")
        current_item = self.currentItem()
        iterator = QTreeWidgetItemIterator(self)
        items = []
        current_idx = -1

        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.UserRole) is not None:  # block item
                items.append(item)
                if current_item and item == current_item:
                    current_idx = len(items) - 1
            iterator += 1

        if not items:
            return

        if current_idx == -1:
            target_idx = 0 if direction > 0 else len(items) - 1
        else:
            target_idx = (current_idx + direction) % len(items)

        target_item = items[target_idx]
        self.setCurrentItem(target_item)
        target_item.setSelected(True)
        self.scrollToItem(target_item)

    def navigate_folders(self, direction: int):
        log_debug(f"CustomTreeWidget: navigate_folders direction={direction}")
        current_item = self.currentItem()
        iterator = QTreeWidgetItemIterator(self)
        items = []
        current_idx = -1

        while iterator.value():
            item = iterator.value()
            # Virtual folder: no block index but has folder id
            if item.data(0, Qt.UserRole) is None and item.data(0, Qt.UserRole + 1) is not None:
                items.append(item)
                if current_item and item == current_item:
                    current_idx = len(items) - 1
            iterator += 1

        if not items:
            return

        if current_idx == -1:
            target_idx = 0 if direction > 0 else len(items) - 1
        else:
            target_idx = (current_idx + direction) % len(items)

        target_item = items[target_idx]
        self.setCurrentItem(target_item)
        target_item.setSelected(True)
        self.scrollToItem(target_item)

    # -------------------------------------------------------------------------
    # Toolbar move up / move down (shared implementation)
    # -------------------------------------------------------------------------

    def move_current_item_up(self):
        self._move_current_item(direction=-1)

    def move_current_item_down(self):
        self._move_current_item(direction=1)

    def _move_current_item(self, direction: int):
        """Move all selected items up (direction=-1) or down (direction=1)."""
        selected_items = self.selectedItems()
        if not selected_items:
            return

        items_with_indices = []
        for item in selected_items:
            parent = item.parent() or self.invisibleRootItem()
            items_with_indices.append((parent, parent.indexOfChild(item), item))

        # Sort ascending for "up", descending for "down" (to avoid index-shift issues)
        items_with_indices.sort(key=lambda x: x[1], reverse=(direction > 0))

        # Check boundary: can the leading item move in the requested direction?
        lead_parent, lead_idx, _ = items_with_indices[0]
        if direction < 0 and lead_idx <= 0:
            return
        if direction > 0 and lead_idx >= lead_parent.childCount() - 1:
            return

        main_window = self.window()
        undo_mgr = getattr(main_window, 'undo_manager', None)
        before = undo_mgr.get_project_snapshot() if undo_mgr else None

        for parent, index, item in items_with_indices:
            parent.takeChild(index)
            parent.insertChild(index + direction, item)

        # Restore selection (Qt may clear it after takeChild)
        for _, _, item in items_with_indices:
            item.setSelected(True)

        if items_with_indices:
            self.setCurrentItem(items_with_indices[0][2])

        self.sync_tree_to_project_manager()  # provided by TreeFolderMixin
        if undo_mgr and before is not None:
            label = f"Move {len(selected_items)} item(s) {'up' if direction < 0 else 'down'}"
            undo_mgr.record_structural_action(before, 'MOVE_BLOCK_BATCH', label)
