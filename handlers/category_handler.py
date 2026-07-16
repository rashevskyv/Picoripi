# handlers/category_handler.py
from typing import Any
from PyQt6.QtWidgets import QMessageBox, QInputDialog
from PyQt6.QtCore import Qt
from .base_handler import BaseHandler
from utils.logging_utils import log_debug, log_info

class CategoryHandler(BaseHandler):
    """Handles virtual block (Category) operations within projects."""
    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any):
        """Initialize a new instance."""
        super().__init__(main_window, data_processor, ui_updater)

    def move_selection_to_category(self) -> None:
        """Move selected strings to a virtual block (Category)."""
        selected_indices = getattr(self.mw.data_store, 'selected_string_indices', [])
        if not selected_indices:
            QMessageBox.warning(self.mw, "Move to Virtual Block", "No strings selected in preview.")
            return

        if self.mw.data_store.current_block_idx == -1:
            return

        pm = self.mw.project_manager
        if not pm or not pm.project:
             log_debug("No project loaded, cannot create virtual blocks.")
             return

        # Find the project block index
        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(self.mw.data_store.current_block_idx, self.mw.data_store.current_block_idx)
        if proj_b_idx >= len(pm.project.blocks):
            return

        block = pm.project.blocks[proj_b_idx]

        # Simple input dialog for now
        name, ok = QInputDialog.getText(self.mw, "Move to Virtual Block", "Enter Category Name:", text="New Category")
        if not ok or not name.strip():
            return

        pm.move_strings_to_category(proj_b_idx, selected_indices, name.strip())

        # Update UI
        self.ui_updater.populate_blocks()
        self.ui_updater.populate_current_view()

        log_debug(f"Moved {len(selected_indices)} strings to Category '{name}' in Block {proj_b_idx}")

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
