from pathlib import Path
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QDialog
from PyQt6.QtCore import Qt
from utils.logging_utils import log_info, log_warning
from core.i18n import tr


class BlocksMixin:
    def import_block_action(self) -> None:
        """Import block action."""
        from components.project_dialogs import ImportBlockDialog
        log_info("Import Block action triggered.")

        if not self.mw.project_manager or not self.mw.project_manager.project:
            QMessageBox.warning(self.mw, tr('No Project'), tr('Please open or create a project first.'))
            return

        dialog = ImportBlockDialog(self.mw, project_manager=self.mw.project_manager)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            log_info("Import block dialog cancelled.")
            return

        info = dialog.get_block_info()
        if not info:
            return

        # Import block using ProjectManager
        block = self.mw.project_manager.add_block(
            name=info['name'],
            source_file_path=info['source_file'],
            translation_file_path=info.get('translation_file'),
            description=info['description']
        )

        if block:
            log_info(f"Block '{info['name']}' imported successfully.")
            # Update UI
            def on_imported(state_restored):
                QMessageBox.information(self.mw, tr('Block Imported'), f"Block '{info['name']}' has been imported.")
            self._populate_blocks_from_project(on_completed=on_imported)
        else:
            QMessageBox.critical(self.mw, tr('Import Failed'), tr('Failed to import block.'))

    def import_directory_action(self) -> None:
        """Import directory action."""
        log_info("Import Directory action triggered.")

        if not self.mw.project_manager or not self.mw.project_manager.project:
            QMessageBox.warning(self.mw, tr('No Project'), tr('Please open or create a project first.'))
            return

        start_dir = str(Path.home())
        directory_path = QFileDialog.getExistingDirectory(
            self.mw,
            "Select Directory to Import",
            start_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )

        if not directory_path:
            log_info("Import directory cancelled.")
            return

        # Import directory using ProjectManager
        blocks = self.mw.project_manager.import_directory(directory_path)

        if blocks:
            log_info(f"{len(blocks)} blocks imported successfully from '{directory_path}'.")
            def on_dir_imported(state_restored):
                QMessageBox.information(self.mw, tr('Directory Imported'), f"{len(blocks)} blocks have been imported.")
            self._populate_blocks_from_project(on_completed=on_dir_imported)
        else:
            QMessageBox.information(self.mw, tr('Import Result'), tr('No supported files found or failed to import.'))

    def delete_block_action(self) -> None:
        """Remove block action."""
        log_info("Delete Item action triggered.")

        if not self.mw.project_manager or not self.mw.project_manager.project:
            return

        current_item = self.mw.block_list_widget.currentItem()
        if not current_item:
            return

        block_idx = current_item.data(0, Qt.UserRole)
        folder_id = current_item.data(0, Qt.UserRole + 1)
        pm = self.mw.project_manager

        # Determine what we are deleting
        if block_idx is not None:
            # IT IS A BLOCK
            block = pm.project.blocks[block_idx]
            block_name = block.name

            reply = QMessageBox.question(
                self.mw,
                tr('Delete Block'),
                f"Are you sure you want to remove block '{block_name}' from the project?\n\n"
                "This will NOT delete the physical files, only the reference in the project.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            undo_mgr = getattr(self.mw, 'undo_manager', None)
            before = undo_mgr.get_project_snapshot() if undo_mgr else None

            # PREPARE SELECTION RECOVERY
            parent_item = current_item.parent() or self.mw.block_list_widget.invisibleRootItem()
            idx = parent_item.indexOfChild(current_item)
            neighbor = None
            if parent_item.childCount() > 1:
                if idx < parent_item.childCount() - 1: neighbor = parent_item.child(idx + 1)
                else: neighbor = parent_item.child(idx - 1)
            else:
                neighbor = parent_item if parent_item != self.mw.block_list_widget.invisibleRootItem() else None

            success = pm.project.remove_block(block.id)
            if success:
                pm.save()
                if undo_mgr and before is not None:
                    undo_mgr.record_structural_action(before, 'DELETE_BLOCK', f"Delete block '{block_name}'")
                log_info(f"Block '{block_name}' removed from project.")

                if neighbor:
                    self.mw.block_list_widget.setCurrentItem(neighbor)

                self._populate_blocks_from_project()
            else:
                QMessageBox.critical(self.mw, tr('Delete Error'), tr('Failed to remove block.'))

        elif folder_id is not None:
            self.mw.virtual_folder_handler.delete_folder_action(folder_id, current_item)

    def move_block_action(self, direction: int) -> None:
        """direction: -1 for up, +1 for down."""
        log_info(f"Move Block {'Up' if direction < 0 else 'Down'} action triggered.")
        if hasattr(self.mw, 'block_list_widget'):
            self.mw.block_list_widget.move_current_item(direction)

    def add_folder_action(self) -> None:
        """Add folder action."""
        self.mw.virtual_folder_handler.add_folder_action()

    def add_items_to_folder_action(self) -> None:
        """Add items to folder action."""
        self.mw.virtual_folder_handler.add_items_to_folder_action()

    def _ensure_project_compat_paths(self) -> None:
        """Populate legacy source/translation paths from the first project block."""
        project_manager = getattr(self.mw, 'project_manager', None)
        project = getattr(project_manager, 'project', None)
        blocks = getattr(project, 'blocks', None)
        if not project_manager or not blocks:
            return

        try:
            first_block = blocks[0]
            self.mw.data_store.json_path = project_manager.get_absolute_path(first_block.source_file)
            self.mw.data_store.edited_json_path = project_manager.get_absolute_path(
                first_block.translation_file,
                is_translation=True
            )
        except Exception as e:
            log_warning(f"Could not set project compatibility paths: {e}", category="file_ops")

