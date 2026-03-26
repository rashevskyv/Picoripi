# components/tree_folder_mixin.py
"""Virtual folder CRUD, tree↔PM synchronisation, expansion-state mixin for CustomTreeWidget."""
import re
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QInputDialog, QTreeWidgetItemIterator

from utils.logging_utils import log_debug


class TreeFolderMixin:
    """Handles folder create/rename/delete, sync_tree_to_project_manager, and expansion state."""

    # ─────────────────────────────────────────────────────────────────────────
    # In-line rename (itemChanged signal)
    # ─────────────────────────────────────────────────────────────────────────

    def _handle_item_changed(self, item, column):
        if getattr(self, '_is_programmatic_expansion', False):
            return

        new_name = item.text(column)
        folder_id = item.data(column, Qt.UserRole + 1)
        if not folder_id:
            return

        main_window = self.window()
        pm = getattr(main_window, 'project_manager', None)
        if not pm:
            return

        folder = pm.find_virtual_folder(folder_id)
        if folder and folder.name != new_name:
            log_debug(f"In-place rename folder {folder.name!r} → {new_name!r}")
            undo_mgr = getattr(main_window, 'undo_manager', None)
            before = undo_mgr.get_project_snapshot() if undo_mgr else None

            folder.name = new_name
            pm.save()

            if undo_mgr and before is not None:
                undo_mgr.record_structural_action(before, 'RENAME_FOLDER', f"Rename folder to {new_name!r}")

            QTimer.singleShot(0, main_window.ui_updater.populate_blocks)

    # ─────────────────────────────────────────────────────────────────────────
    # Create folder
    # ─────────────────────────────────────────────────────────────────────────

    def _create_folder_at_cursor(self):
        main_window = self.window()
        pm = getattr(main_window, 'project_manager', None)
        if not pm or not pm.project:
            return

        current_item = self.currentItem()
        parent_id = None
        if current_item:
            b_idx = current_item.data(0, Qt.UserRole)
            f_id = current_item.data(0, Qt.UserRole + 1)
            if f_id:
                parent_id = f_id
            elif b_idx is not None:
                parent_item = current_item.parent()
                if parent_item:
                    parent_id = parent_item.data(0, Qt.UserRole + 1)

        default_name = self._get_next_unnamed_name(pm)
        undo_mgr = getattr(main_window, 'undo_manager', None)
        before = undo_mgr.get_project_snapshot() if undo_mgr else None

        new_folder = pm.create_virtual_folder(default_name, parent_id=parent_id)
        if not new_folder:
            return

        pm.save()
        if undo_mgr and before is not None:
            undo_mgr.record_structural_action(before, 'ADD_FOLDER', f"Add folder {default_name!r}")

        main_window.ui_updater.populate_blocks()

        # Find the new item in the refreshed tree and start edit mode
        it = QTreeWidgetItemIterator(self)
        while it.value():
            item = it.value()
            if item.data(0, Qt.UserRole + 1) == new_folder.id:
                self.setCurrentItem(item)
                item.setSelected(True)
                self.scrollToItem(item)
                QTimer.singleShot(100, lambda: self.editItem(item, 0))
                break
            it += 1

    # ─────────────────────────────────────────────────────────────────────────
    # Rename folder
    # ─────────────────────────────────────────────────────────────────────────

    def _rename_folder(self, item):
        """Trigger in-place edit (single, non-compacted folder)."""
        self.editItem(item, 0)

    def _rename_folder_by_id(self, folder_id, current_name: str):
        """Open a dialog to rename a folder (used for compacted items)."""
        new_name, ok = QInputDialog.getText(self, "Rename Folder", "Enter new folder name:", text=current_name)
        if not (ok and new_name):
            return

        main_window = self.window()
        undo_mgr = getattr(main_window, 'undo_manager', None)
        before = undo_mgr.get_project_snapshot() if undo_mgr else None

        folder = main_window.project_manager.find_virtual_folder(folder_id)
        if folder:
            folder.name = new_name
            main_window.project_manager.save()
            main_window.ui_updater.populate_blocks()
            if undo_mgr and before is not None:
                undo_mgr.record_structural_action(before, 'RENAME_FOLDER', f"Rename folder to {new_name!r}")

    # ─────────────────────────────────────────────────────────────────────────
    # Delete folder
    # ─────────────────────────────────────────────────────────────────────────

    def _delete_folder(self, item):
        self.setCurrentItem(item)
        main_window = self.window()
        pah = getattr(main_window, 'project_action_handler', None)
        if pah:
            pah.delete_block_action()

    def _delete_folder_by_id(self, item, folder_id):
        """Temporarily swap folder_id so the handler sees the right target folder."""
        old_fid = item.data(0, Qt.UserRole + 1)
        item.setData(0, Qt.UserRole + 1, folder_id)
        self.setCurrentItem(item)

        main_window = self.window()
        pah = getattr(main_window, 'project_action_handler', None)
        if pah:
            pah.delete_block_action()

        # Restore in case handler didn't remove the item
        if item is not self.invisibleRootItem():
            item.setData(0, Qt.UserRole + 1, old_fid)

    # ─────────────────────────────────────────────────────────────────────────
    # Create subfolder
    # ─────────────────────────────────────────────────────────────────────────

    def _create_subfolder(self, item):
        folder_id = item.data(0, Qt.UserRole + 1)
        self._create_subfolder_by_id(folder_id)

    def _create_subfolder_by_id(self, folder_id):
        main_window = self.window()
        pm = main_window.project_manager
        default_name = self._get_next_unnamed_name(pm)
        new_name, ok = QInputDialog.getText(self, "New Subfolder", "Enter subfolder name:", text=default_name)
        if not (ok and new_name):
            return

        undo_mgr = getattr(main_window, 'undo_manager', None)
        before = undo_mgr.get_project_snapshot() if undo_mgr else None
        pm.create_virtual_folder(new_name, parent_id=folder_id)
        pm.save()
        main_window.ui_updater.populate_blocks()
        if undo_mgr and before is not None:
            undo_mgr.record_structural_action(before, 'ADD_FOLDER', f"Create subfolder {new_name!r}")

    # ─────────────────────────────────────────────────────────────────────────
    # Expansion state
    # ─────────────────────────────────────────────────────────────────────────

    def _handle_item_state_changed(self, item):
        """Persist expand/collapse state to ProjectManager and refresh compaction."""
        if getattr(self, '_is_programmatic_expansion', False):
            return

        main_window = self.window()
        pm = getattr(main_window, 'project_manager', None)
        if not pm or not pm.project:
            return

        f_id = item.data(0, Qt.UserRole + 1)
        if not f_id:
            return

        folder = pm.find_virtual_folder(f_id)
        if not folder:
            return

        is_expanded = item.isExpanded()
        if folder.is_expanded == is_expanded:
            return

        merged_ids = item.data(0, Qt.UserRole + 2) or [f_id]
        log_debug(f"Compacted chain {merged_ids} expansion → {is_expanded}. Syncing…")
        for fid in merged_ids:
            f_obj = pm.find_virtual_folder(fid)
            if f_obj:
                f_obj.is_expanded = is_expanded

        pm.save()
        self.setUpdatesEnabled(False)
        try:
            main_window.ui_updater.populate_blocks()
        finally:
            self.setUpdatesEnabled(True)

    # ─────────────────────────────────────────────────────────────────────────
    # Tree → ProjectManager synchronisation
    # ─────────────────────────────────────────────────────────────────────────

    def sync_tree_to_project_manager(self):
        """Rebuild the virtual folder structure in ProjectManager from the current tree layout."""
        main_window = self.window()
        pm = getattr(main_window, 'project_manager', None)
        if not pm or not pm.project:
            return

        project = pm.project

        def rebuild_from_item(tree_item, parent_id=None):
            folder_map = {}
            block_ids = []

            for i in range(tree_item.childCount()):
                child = tree_item.child(i)
                f_id = child.data(0, Qt.UserRole + 1)
                b_idx = child.data(0, Qt.UserRole)
                merged_ids = child.data(0, Qt.UserRole + 2)
                text = child.text(0)

                target_folder = None

                if merged_ids and isinstance(merged_ids, list) and len(merged_ids) > 0:
                    # ── Compacted chain ──────────────────────────────────────
                    parts = text.split(" / ")
                    is_block_item = b_idx is not None
                    folder_names = parts[:-1] if is_block_item else parts

                    curr_p_id = parent_id
                    chain_top = None
                    chain_bottom = None
                    raw_names = child.data(0, Qt.UserRole + 5)

                    for f_idx, folder_id in enumerate(merged_ids):
                        folder_obj = pm.find_virtual_folder(folder_id)
                        new_f_name = None

                        if raw_names and f_idx < len(raw_names):
                            new_f_name = raw_names[f_idx]
                        elif folder_names:
                            name_idx = len(folder_names) - 1 - (len(merged_ids) - 1 - f_idx)
                            if name_idx >= 0:
                                raw_name = folder_names[name_idx].strip()
                                new_f_name = re.sub(r'\s*\[\d+\s*\|\s*\d+\]$', '', raw_name)

                        if not folder_obj:
                            from core.project_models import VirtualFolder
                            folder_obj = VirtualFolder(
                                id=folder_id,
                                name=new_f_name or "Unnamed Folder",
                                parent_id=curr_p_id,
                            )
                        else:
                            if new_f_name:
                                folder_obj.name = new_f_name
                            folder_obj.parent_id = curr_p_id

                        folder_obj.is_expanded = child.isExpanded()
                        folder_obj.children = []
                        folder_obj.block_ids = []

                        if not chain_top:
                            chain_top = folder_obj
                        if chain_bottom:
                            chain_bottom.children = [folder_obj]
                        chain_bottom = folder_obj
                        curr_p_id = folder_id

                    if is_block_item:
                        if b_idx < len(project.blocks):
                            chain_bottom.block_ids = [project.blocks[b_idx].id]
                    else:
                        sub_f, sub_b = rebuild_from_item(child, f_id)
                        chain_bottom.children = sub_f
                        chain_bottom.block_ids = sub_b

                    target_folder = chain_top

                elif f_id:
                    # ── Standard folder ──────────────────────────────────────
                    folder_obj = pm.find_virtual_folder(f_id)
                    if folder_obj:
                        raw_names = child.data(0, Qt.UserRole + 5)
                        if raw_names and len(raw_names) > 0:
                            folder_obj.name = raw_names[0]
                        else:
                            folder_obj.name = re.sub(r'\s*\[\d+\s*\|\s*\d+\]$', '', text)
                        folder_obj.parent_id = parent_id
                        folder_obj.is_expanded = child.isExpanded()
                        folder_obj.children, folder_obj.block_ids = rebuild_from_item(child, f_id)
                        target_folder = folder_obj

                elif b_idx is not None:
                    # ── Standard block ───────────────────────────────────────
                    if b_idx < len(project.blocks):
                        block_ids.append(project.blocks[b_idx].id)

                # Deduplicate folders by name at this level
                if target_folder:
                    if target_folder.name in folder_map:
                        existing = folder_map[target_folder.name]
                        existing.children.extend(target_folder.children)
                        existing.block_ids.extend(target_folder.block_ids)
                    else:
                        folder_map[target_folder.name] = target_folder

            return list(folder_map.values()), block_ids

        project.virtual_folders, root_block_ids = rebuild_from_item(self.invisibleRootItem())
        project.metadata['root_block_ids'] = root_block_ids
        pm.save()
        log_debug("Virtual folders structure updated.")
