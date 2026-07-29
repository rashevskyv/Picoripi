# handlers/category_handler.py
from typing import Any
from PyQt6.QtWidgets import QMessageBox, QInputDialog, QTreeWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QTreeWidgetItemIterator
from .base_handler import BaseHandler
from utils.logging_utils import log_debug

class CategoryHandler(BaseHandler):
    """Handles virtual block (Category) operations within projects."""
    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any):
        """Initialize a new instance."""
        super().__init__(main_window, data_processor, ui_updater)

    @staticmethod
    def _next_surviving_row(displayed_rows, selected_rows):
        """Return the row immediately after a removed selection, or nearest prior row."""
        selected = set(selected_rows)
        positions = [
            index for index, row in enumerate(displayed_rows) if row in selected
        ]
        if not positions:
            return None
        after = next(
            (
                row
                for row in displayed_rows[max(positions) + 1:]
                if row not in selected
            ),
            None,
        )
        if after is not None:
            return after
        return next(
            (
                row
                for row in reversed(displayed_rows[:min(positions)])
                if row not in selected
            ),
            None,
        )

    def _restore_category_tree_item(self, block_idx: int, category_name: str) -> None:
        tree = getattr(self.mw, 'block_list_widget', None)
        if not isinstance(tree, QTreeWidget):
            return
        iterator = QTreeWidgetItemIterator(tree)
        while iterator.value():
            item = iterator.value()
            if (
                item.data(0, Qt.ItemDataRole.UserRole) == block_idx
                and item.data(0, Qt.ItemDataRole.UserRole + 10) == category_name
            ):
                tree.setCurrentItem(item)
                item.setSelected(True)
                tree.scrollToItem(item)
                return
            iterator += 1

    def _activate_category_row(
        self,
        block_idx: int,
        category_name: str,
        preferred_row: int,
        old_scroll_value: int,
    ) -> None:
        store = self.mw.data_store
        displayed = list(getattr(store, 'displayed_string_indices', []) or [])
        remaining = [
            row[1] if isinstance(row, (tuple, list)) and len(row) == 2 else row
            for row in displayed
        ]
        if preferred_row not in remaining:
            return

        relative_row = remaining.index(preferred_row)
        store.current_block_idx = block_idx
        store.physical_block_idx = block_idx
        store.current_category_name = category_name
        store.current_string_idx = preferred_row
        store.selected_string_indices = [preferred_row]

        preview = getattr(self.mw, 'preview_text_edit', None)
        if preview is not None:
            reset = getattr(preview, 'reset_selection_state', None)
            if callable(reset):
                reset()
            set_selected = getattr(preview, 'set_selected_lines', None)
            if callable(set_selected):
                set_selected([relative_row])

            document = preview.document()
            block = document.findBlockByNumber(relative_row)
            if block.isValid():
                try:
                    preview.setTextCursor(QTextCursor(block))
                except TypeError:
                    pass
            scrollbar = preview.verticalScrollBar()
            scrollbar.setValue(
                max(scrollbar.minimum(), min(old_scroll_value, scrollbar.maximum()))
            )
            ensure_visible = getattr(preview, 'ensureCursorVisible', None)
            if callable(ensure_visible):
                ensure_visible()

        self.ui_updater.update_text_views()

    def move_selection_to_category(self) -> None:
        """Move selected strings to a virtual block (Category)."""
        selected_indices = list(
            getattr(self.mw.data_store, 'selected_string_indices', []) or []
        )
        if not selected_indices:
            QMessageBox.warning(self.mw, "Move to Virtual Block", "No strings selected in preview.")
            return

        if self.mw.data_store.current_block_idx == -1:
            return

        pm = self.mw.project_manager
        if not pm or not pm.project:
             log_debug("No project loaded, cannot create virtual blocks.")
             return

        physical_block_idx = getattr(
            self.mw.data_store,
            'physical_block_idx',
            self.mw.data_store.current_block_idx,
        )
        if (
            not isinstance(physical_block_idx, int)
            or isinstance(physical_block_idx, bool)
            or physical_block_idx < 0
        ):
            physical_block_idx = self.mw.data_store.current_block_idx
        normalized_indices = []
        for value in selected_indices:
            if isinstance(value, (tuple, list)) and len(value) == 2:
                if int(value[0]) != physical_block_idx:
                    continue
                value = value[1]
            value = int(value)
            if value not in normalized_indices:
                normalized_indices.append(value)
        if not normalized_indices:
            return

        source_category = getattr(
            self.mw.data_store, 'current_category_name', None
        )
        displayed_before = [
            row[1] if isinstance(row, (tuple, list)) and len(row) == 2 else row
            for row in (
                getattr(self.mw.data_store, 'displayed_string_indices', []) or []
            )
        ]
        continuation_row = self._next_surviving_row(
            displayed_before, normalized_indices
        )
        preview = getattr(self.mw, 'preview_text_edit', None)
        old_scroll_value = (
            preview.verticalScrollBar().value() if preview is not None else 0
        )

        # Find the project block index
        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(physical_block_idx, physical_block_idx)
        if proj_b_idx >= len(pm.project.blocks):
            return

        block = pm.project.blocks[proj_b_idx]

        # Simple input dialog for now
        name, ok = QInputDialog.getText(self.mw, "Move to Virtual Block", "Enter Category Name:", text="New Category")
        if not ok or not name.strip():
            return

        target_category = name.strip()
        pm.move_strings_to_category(
            proj_b_idx, normalized_indices, target_category
        )

        # Update UI
        self.ui_updater.populate_blocks()
        if (
            source_category
            and source_category != target_category
            and continuation_row is not None
        ):
            self.mw.data_store.current_block_idx = physical_block_idx
            self.mw.data_store.physical_block_idx = physical_block_idx
            self.mw.data_store.current_category_name = source_category
            self._restore_category_tree_item(physical_block_idx, source_category)
            self.ui_updater.populate_strings_for_block(
                physical_block_idx, source_category, force=True
            )
            self._activate_category_row(
                physical_block_idx,
                source_category,
                continuation_row,
                old_scroll_value,
            )
        else:
            self.ui_updater.populate_current_view()

        log_debug(
            f"Moved {len(normalized_indices)} strings to Category "
            f"'{target_category}' in Block {proj_b_idx}"
        )

    def rename_category(self, block_idx: int, old_name: str) -> None:
        """Rename a virtual block."""
        new_name, ok = QInputDialog.getText(self.mw, "Rename Virtual Block", "Enter new name:", text=old_name)
        if not ok or not new_name.strip() or new_name == old_name:
            return

        pm = self.mw.project_manager
        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(block_idx, block_idx)

        if proj_b_idx < len(pm.project.blocks):
            block = pm.project.blocks[proj_b_idx]
            for cat in block.categories:
                if cat.name == old_name:
                    cat.name = new_name.strip()
                    break
            pm.save()
            self.ui_updater.populate_blocks()

    def delete_category(self, block_idx: int, category_name: str) -> None:
        """Remove a virtual block (the strings remain in the block)."""
        reply = QMessageBox.question(
            self.mw, "Delete Virtual Block",
            f"Are you sure you want to delete virtual block '{category_name}'?\n\n(Strings will not be deleted from the block itself.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        pm = self.mw.project_manager
        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(block_idx, block_idx)

        if proj_b_idx < len(pm.project.blocks):
            block = pm.project.blocks[proj_b_idx]
            block.categories = [c for c in block.categories if c.name != category_name]
            pm.save()
            self.ui_updater.populate_blocks()
