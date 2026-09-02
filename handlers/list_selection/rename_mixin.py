"""Inline rename for blocks and folders."""
from __future__ import annotations

from PyQt6.QtWidgets import QTreeWidgetItem
from PyQt6.QtCore import Qt
from utils.logging_utils import log_debug, log_info


class RenameMixin:
    """Inline rename for blocks and folders."""

    def rename_block(self, item: QTreeWidgetItem) -> None:
        """Rename block."""
        if not item: return
        self.mw.block_list_widget.editItem(item, 0)

    def handle_block_item_text_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle inline renaming of block or folder."""
        if self.mw.is_loading_data or self.mw.is_programmatically_changing_text:
            return

        new_text = item.text(column).strip()
        if not new_text:
            # Revert if empty
            self.ui_updater.populate_blocks()
            return

        # Check if it's a virtual folder or a block
        folder_id = item.data(0, Qt.UserRole + 1)
        block_index_from_data = item.data(0, Qt.UserRole)
        merged_ids = item.data(0, Qt.UserRole + 2)

        undo_mgr = getattr(self.mw, 'undo_manager', None)
        before = undo_mgr.get_project_snapshot() if undo_mgr else None

        # Check if it's a virtual block (category). Virtual blocks have BOTH block_index AND category_name set.
        # We must check category_name FIRST because virtual block items also have a block_index.
        category_name = item.data(0, Qt.UserRole + 10)

        self.mw.is_programmatically_changing_text = True
        try:
            if category_name is not None and block_index_from_data is not None:
                # Rename Virtual Block (Category) — delegate to the proper method
                log_debug(f"Virtual block '{category_name}' renamed to '{new_text}' (via inline edit)")
                pm = getattr(self.mw, 'project_manager', None)
                block_map = getattr(self.mw, 'block_to_project_file_map', {})
                proj_b_idx = block_map.get(block_index_from_data, block_index_from_data)
                if pm and proj_b_idx < len(pm.project.blocks):
                    block = pm.project.blocks[proj_b_idx]
                    for cat in block.categories:
                        if cat.name == category_name:
                            cat.name = new_text.strip()
                            break
                    pm.save()
                    item.setData(0, Qt.UserRole + 10, new_text.strip())
                    item.setData(0, Qt.UserRole + 4, new_text.strip())
                    item.setData(0, Qt.EditRole, new_text.strip())
                    self.ui_updater.update_block_item_text_with_problem_count(block_index_from_data)
            elif block_index_from_data is not None:
                # Rename Block
                block_index_str = str(block_index_from_data)

                # If there are merged IDs (compact folders), handle multi-part rename
                if merged_ids and " / " in new_text:
                    parts = new_text.split(" / ")
                    actual_block_name = parts[-1].strip()
                    self.mw.data_store.block_names[block_index_str] = actual_block_name

                    # Also update ProjectManager if applicable
                    if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                        block_map = getattr(self.mw, 'block_to_project_file_map', {})
                        proj_idx = block_map.get(block_index_from_data)
                        if proj_idx is not None and proj_idx < len(self.mw.project_manager.project.blocks):
                            self.mw.project_manager.project.blocks[proj_idx].name = actual_block_name

                    # Rename parent folders in the chain
                    folder_names = parts[:-1]
                    for f_idx, f_id in enumerate(merged_ids):
                        folder_obj = self.mw.project_manager.find_virtual_folder(f_id)
                        if folder_obj and folder_names:
                            name_idx = len(folder_names) - 1 - (len(merged_ids) - 1 - f_idx)
                            if name_idx >= 0:
                                import re
                                raw_name = folder_names[name_idx].strip()
                                # Strip the display count [f / b]
                                new_name = re.sub(r'\s*\[\d+\s*/\s*\d+\]$', '', raw_name)
                                # Check for collision with siblings of this folder in the chain
                                siblings = []
                                if folder_obj.parent_id:
                                    p = self.mw.project_manager.find_virtual_folder(folder_obj.parent_id)
                                    if p: siblings = p.children
                                else:
                                    siblings = self.mw.project_manager.project.virtual_folders

                                collision = None
                                for s in siblings:
                                    if s.id != folder_obj.id and s.name == new_name:
                                        collision = s
                                        break

                                if collision:
                                    self.mw.project_manager.merge_folders(folder_obj.id, collision.id)
                                else:
                                    folder_obj.name = new_name
                else:
                    self.mw.data_store.block_names[block_index_str] = new_text

                    # Also update ProjectManager if applicable
                    if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                        block_map = getattr(self.mw, 'block_to_project_file_map', {})
                        proj_idx = block_map.get(block_index_from_data)
                        if proj_idx is not None and proj_idx < len(self.mw.project_manager.project.blocks):
                            self.mw.project_manager.project.blocks[proj_idx].name = new_text
                            self.mw.project_manager.save()

                item.setData(0, Qt.UserRole + 4, new_text)
                item.setData(0, Qt.EditRole, new_text)
                self.mw.settings_manager.save_block_names()
                log_debug(f"Block {block_index_from_data} renamed to '{new_text}'")

                # Repopulate to fix any visual issues
                self.ui_updater.update_block_item_text_with_problem_count(block_index_from_data)
            elif folder_id:
                # Rename Folder
                folder = self.mw.project_manager.find_virtual_folder(folder_id)
                if folder:
                    if merged_ids and " / " in new_text:
                        parts = new_text.split(" / ")
                        for f_idx, f_id in enumerate(merged_ids):
                            f_obj = self.mw.project_manager.find_virtual_folder(f_id)
                            if f_obj:
                                name_idx = len(parts) - 1 - (len(merged_ids) - 1 - f_idx)
                                if name_idx >= 0:
                                    import re
                                    raw_name = parts[name_idx].strip()
                                    # Strip the display count [f / b]
                                    new_name = re.sub(r'\s*\[\d+\s*/\s*\d+\]$', '', raw_name)
                                    # Merge if collision
                                    siblings = []
                                    if f_obj.parent_id:
                                        p = self.mw.project_manager.find_virtual_folder(f_obj.parent_id)
                                        if p: siblings = p.children
                                    else:
                                        siblings = self.mw.project_manager.project.virtual_folders

                                    collision = None
                                    for s in siblings:
                                        if s.id != f_obj.id and s.name == new_name:
                                            collision = s
                                            break
                                    if collision:
                                        self.mw.project_manager.merge_folders(f_obj.id, collision.id)
                                    else:
                                        f_obj.name = new_name
                    else:
                        import re
                        raw_input = new_text.strip()
                        new_name = re.sub(r'\s*\[\d+\s*/\s*\d+\]$', '', raw_input)
                        # Check for collision at same level
                        siblings = []
                        if folder.parent_id:
                            p_obj = self.mw.project_manager.find_virtual_folder(folder.parent_id)
                            if p_obj: siblings = p_obj.children
                        else:
                            siblings = self.mw.project_manager.project.virtual_folders

                        target_collision = None
                        for s in siblings:
                            if s.id != folder.id and s.name == new_name:
                                target_collision = s
                                break

                        if target_collision:
                            # MERGE CASE: Rename to existing folder name
                            log_info(f"Renaming '{folder.name}' to existing '{new_name}' -> merging {folder.id} into {target_collision.id}")
                            self.mw.project_manager.merge_folders(folder.id, target_collision.id)
                        else:
                            folder.name = new_name

                    self.mw.project_manager.save()
                    log_debug(f"Folder {folder_id} rename/merge handled.")

            # Repopulate to fix any visual issues
            self.ui_updater.populate_blocks()
        finally:
            self.mw.is_programmatically_changing_text = False

        if undo_mgr and before is not None:
            action_label = f"Rename block to '{new_text}'" if block_index_from_data is not None else f"Rename folder to '{new_text}'"
            action_type = 'RENAME_BLOCK' if block_index_from_data is not None else 'RENAME_FOLDER'
            undo_mgr.record_structural_action(before, action_type, action_label)
