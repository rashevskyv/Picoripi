# handlers/virtual_folder_handler.py

from typing import Any, List, Dict, Optional
from PyQt6.QtWidgets import QMessageBox, QTreeWidgetItem
from PyQt6.QtCore import Qt
from .base_handler import BaseHandler
from utils.logging_utils import log_info
from components.folder_delete_dialog import FolderDeleteDialog


class VirtualFolderHandler(BaseHandler):
    """
    Handles virtual folder management operations within projects,
    such as folder creation, deletion, moving items, and managing expansion state.
    """
    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any):
        """Initialize a new instance."""
        super().__init__(main_window, data_processor, ui_updater)

    def add_folder_action(self) -> None:
        """Add folder action."""
        log_info("Add Folder action triggered.")
        if hasattr(self.mw, 'block_list_widget'):
            self.mw.block_list_widget._create_folder_at_cursor()

    def add_items_to_folder_action(self) -> None:
        """Move multiple selected items into a folder."""
        if not self.mw.project_manager or not self.mw.project_manager.project:
            return

        selected_items = self.mw.block_list_widget.selectedItems()
        if not selected_items:
            return

        pm = self.mw.project_manager

        # 1. Use MoveToFolderDialog
        from components.project_dialogs import MoveToFolderDialog

        # Try to find current parent folder ID if items are in a folder
        current_parent_id: Optional[str] = None
        if selected_items[0].parent():
            current_parent_id = selected_items[0].parent().data(0, Qt.UserRole + 1)

        from PyQt6.QtWidgets import QDialog
        dialog = MoveToFolderDialog(self.mw, pm, current_folder_id=current_parent_id)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        target_folder_id = dialog.get_selected_folder_id()

        # 2. Perform the Move
        undo_mgr = getattr(self.mw, 'undo_manager', None)
        before = undo_mgr.get_project_snapshot() if undo_mgr else None

        block_map: Dict[int, int] = getattr(self.mw, 'block_to_project_file_map', {})
        moved_count = 0

        for item in selected_items:
            b_idx = item.data(0, Qt.UserRole)
            f_id = item.data(0, Qt.UserRole + 1)

            if b_idx is not None:
                proj_idx = block_map.get(b_idx, b_idx)
                if proj_idx < len(pm.project.blocks):
                    pm.move_block_to_folder(pm.project.blocks[proj_idx].id, target_folder_id)
                    moved_count += 1
            elif f_id:
                if pm.move_folder_to_folder(f_id, target_folder_id):
                    moved_count += 1

        if moved_count > 0:
            pm.save()
            if undo_mgr and before is not None:
                undo_mgr.record_structural_action(before, 'MOVE_BATCH', f"Move {moved_count} items to folder")

            # Keep focus at the source parent so the view doesn't jump
            source_parent_item = selected_items[0].parent() if selected_items else None
            if source_parent_item:
                self.mw.block_list_widget.setCurrentItem(source_parent_item)

            self.ui_updater.populate_blocks(override_folder_id=target_folder_id)
            log_info(f"Batch move completed: {moved_count} items moved.")

    def delete_folder_action(self, folder_id: str, current_item: QTreeWidgetItem) -> None:
        """Deletes a virtual folder from the project tree, optionally preserving or removing its content."""
        pm = self.mw.project_manager
        folder = pm.find_virtual_folder(folder_id)
        if not folder:
            return

        # If folder is empty, don't show the complex dialog
        is_empty = not folder.block_ids and not folder.children
        action = 0

        if is_empty:
            reply = QMessageBox.question(
                self.mw, 'Delete Folder',
                f"Are you sure you want to delete the empty folder '{folder.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                action = 2  # Delete all (which is none)
        else:
            dialog = FolderDeleteDialog(folder.name, self.mw)
            dialog.exec()
            action = dialog.result_action

        if action == 0:
            return  # Cancel

        # PREPARE SELECTION RECOVERY
        # Find a neighbor to select after deletion so we don't jump to the bottom
        new_selection_block_idx = None
        new_selection_folder_id = None

        parent_item = current_item.parent() or self.mw.block_list_widget.invisibleRootItem()
        idx = parent_item.indexOfChild(current_item)
        neighbor = None
        if parent_item.childCount() > 1:
            if idx < parent_item.childCount() - 1:
                neighbor = parent_item.child(idx + 1)
            else:
                neighbor = parent_item.child(idx - 1)
        else:
            neighbor = parent_item if parent_item != self.mw.block_list_widget.invisibleRootItem() else None

        if neighbor:
            new_selection_block_idx = neighbor.data(0, Qt.UserRole)
            new_selection_folder_id = neighbor.data(0, Qt.UserRole + 1)

        undo_mgr = getattr(self.mw, 'undo_manager', None)
        before = undo_mgr.get_project_snapshot() if undo_mgr else None

        if action == 1:
            # 1. DELETE FOLDER ONLY (Keep contents)
            children_folders = list(folder.children)
            children_blocks = list(folder.block_ids)
            parent_id = folder.parent_id

            pm._remove_folder_from_anywhere(folder_id)

            # Move everything up
            if parent_id:
                parent_folder = pm.find_virtual_folder(parent_id)
                if parent_folder:
                    for child_f in children_folders:
                        child_f.parent_id = parent_id
                        parent_folder.children.append(child_f)
                    parent_folder.block_ids.extend(children_blocks)
            else:  # Move to root
                for child_f in children_folders:
                    child_f.parent_id = None
                    pm.project.virtual_folders.append(child_f)

                if 'root_block_ids' not in pm.project.metadata:
                    pm.project.metadata['root_block_ids'] = []
                pm.project.metadata['root_block_ids'].extend(children_blocks)

            pm.save()
            if undo_mgr and before is not None:
                undo_mgr.record_structural_action(before, 'DELETE_FOLDER_ONLY', f"Delete folder '{folder.name}' (keep contents)")

            # Apply suggested selection
            if new_selection_block_idx is not None or new_selection_folder_id is not None:
                self.mw.block_list_widget.setCurrentItem(neighbor)

            self.ui_updater.populate_blocks()

        elif action == 2:
            # 2. DELETE FOLDER AND CONTENTS
            # Recursively delete all items in folder
            all_block_ids: List[str] = []
            def collect_blocks(f: Any) -> None:
                all_block_ids.extend(f.block_ids)
                for child in f.children:
                    collect_blocks(child)

            collect_blocks(folder)

            pm._remove_folder_from_anywhere(folder_id)
            for bid in all_block_ids:
                pm.project.remove_block(bid)

            pm.save()
            if undo_mgr and before is not None:
                undo_mgr.record_structural_action(before, 'DELETE_FOLDER_ALL', f"Delete folder '{folder.name}' AND its contents")

            if neighbor:
                self.mw.block_list_widget.setCurrentItem(neighbor)

            if all_block_ids:
                # Reload project blocks list entirely
                if hasattr(self.mw.project_action_handler, '_populate_blocks_from_project'):
                    self.mw.project_action_handler._populate_blocks_from_project()
            else:
                self.ui_updater.populate_blocks()

    def update_all_folder_expansion_state(self, expanded: bool, persist: bool = True) -> None:
        """Recursively update the is_expanded state for all virtual folders."""
        if not self.mw.project_manager or not self.mw.project_manager.project:
            return

        def update_folder(f: Any) -> None:
            """Update the folder."""
            f.is_expanded = expanded
            for child in f.children:
                update_folder(child)

        for folder in self.mw.project_manager.project.virtual_folders:
            update_folder(folder)
        if persist:
            self.mw.project_manager.save()

    def navigate_between_blocks(self, forward: bool) -> None:
        """Handle global Alt+Shift+Up/Down to jump to next/prev block in the tree."""
        if not hasattr(self.mw, 'block_list_widget'): return
        direction: int = 1 if forward else -1
        self.mw.block_list_widget.navigate_blocks(direction)

    def navigate_between_folders(self, forward: bool) -> None:
        """Handle global Alt+Shift+Left/Right to jump to next/prev folder in the tree."""
        from utils.logging_utils import log_debug
        log_debug(f"VirtualFolderHandler: navigate_between_folders forward={forward}")
        if not hasattr(self.mw, 'block_list_widget'): return
        direction: int = 1 if forward else -1
        self.mw.block_list_widget.navigate_folders(direction)
