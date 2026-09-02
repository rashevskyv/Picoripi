"""Block revert / restore / properties context-menu helpers."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from core.i18n import tr


class BlockActionsMixin:
    """Block-level context-menu action helpers."""

    def _revert_selected_to_original(self):
        """Internal helper to revert selected to original."""
        main_window = self.window()
        if not hasattr(main_window, 'data_processor'):
            return
            
        selected_strings = self._get_selected_strings_by_block()
        if not selected_strings:
            return
            
        total_strings = sum(len(s_indices) for s_indices in selected_strings.values())
        
        reply = QMessageBox.question(
            self,
            tr('Revert to Original'),
            f"Are you sure you want to revert {total_strings} string(s) to their original state?\n\n"
            "All unsaved changes for these strings will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return
            
        flat_list = []
        for b_idx, s_indices in selected_strings.items():
            for s_idx in s_indices:
                flat_list.append((b_idx, s_idx))
                
        main_window.data_processor.perform_revert_strings(-2, flat_list, confirm=False)

    def _show_block_properties(self, block_idx: int):
        """Internal helper to show block properties."""
        from .block_properties_dialog import BlockPropertiesDialog
        dialog = BlockPropertiesDialog(self.window(), block_idx)
        dialog.exec()

    def _get_selected_strings_by_block(self) -> dict:
        """Internal helper to get the selected strings by block."""
        main_window = self.window()
        selected_strings = {}
        
        for item in self.selectedItems():
            block_idx = item.data(0, Qt.UserRole)
            category_name = item.data(0, Qt.UserRole + 10)
            ch_id = item.data(0, Qt.UserRole + 11)
            
            if block_idx == -2:
                # Chapter
                composer = getattr(main_window, "translation_handler", None)
                if composer and hasattr(composer, "prompt_composer"):
                    client = composer.prompt_composer._get_mempalace_client()
                    if client:
                        wing_name = composer.prompt_composer._get_wing_name()
                        mappings = client.get_chapter_mappings(wing_name, ch_id)
                        for m in mappings:
                            bmg_id = m.get("bmg_id")
                            indices = main_window.list_selection_handler.resolve_bmg_id_to_indices(bmg_id)
                            if indices:
                                b_idx, s_idx = indices
                                selected_strings.setdefault(b_idx, []).append(s_idx)
            elif category_name:
                # Virtual block/category
                if block_idx >= 0 and main_window.project_manager and main_window.project_manager.project:
                    pm = main_window.project_manager
                    block_map = getattr(main_window, 'block_to_project_file_map', {})
                    proj_b_idx = block_map.get(block_idx, block_idx)
                    if proj_b_idx < len(pm.project.blocks):
                        block = pm.project.blocks[proj_b_idx]
                        category = next((c for c in block.categories if c.name == category_name), None)
                        if category:
                            for s_idx in category.line_indices:
                                selected_strings.setdefault(block_idx, []).append(s_idx)
            elif block_idx is not None and block_idx >= 0:
                # Standard Block
                if main_window.data_store and main_window.data_store.data and block_idx < len(main_window.data_store.data):
                    num_strings = len(main_window.data_store.data[block_idx])
                    selected_strings[block_idx] = list(range(num_strings))
                    
        return selected_strings

    def _restore_selected_translations(self):
        """Internal helper to restore selected translations."""
        main_window = self.window()
        if not hasattr(main_window, 'saved_translations_manager'):
            return
            
        selected_strings = self._get_selected_strings_by_block()
        if not selected_strings:
            return
            
        to_restore_count = 0
        for b_idx, s_indices in selected_strings.items():
            for s_idx in s_indices:
                if main_window.saved_translations_manager.has_saved_translation(b_idx, s_idx):
                    to_restore_count += 1
                    
        if to_restore_count == 0:
            QMessageBox.information(self, tr('Restore Translation'), tr('No saved translations found for the selection.'))
            return
            
        reply = QMessageBox.question(
            self,
            tr('Restore Translations'),
            f"Are you sure you want to restore saved translations for {to_restore_count} string(s)?\n\n"
            "This will overwrite current edits in memory.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return
            
        has_undo = hasattr(main_window, 'undo_manager')
        if has_undo:
            main_window.undo_manager.begin_group()
            
        try:
            for b_idx, s_indices in selected_strings.items():
                saved_s_indices = [s_idx for s_idx in s_indices if main_window.saved_translations_manager.has_saved_translation(b_idx, s_idx)]
                if saved_s_indices:
                    main_window.saved_translations_handler.restore_translations_for_strings(b_idx, saved_s_indices)
        finally:
            if has_undo:
                main_window.undo_manager.end_group("RESTORE_STRINGS")

    def _revert_all_blocks_to_original(self):
        """Internal helper to revert all blocks to original."""
        main_window = self.window()
        if not hasattr(main_window, 'data_processor') or not main_window.data_store.data:
            return
            
        num_blocks = len(main_window.data_store.data)
        total_strings = sum(len(main_window.data_store.data[b_idx]) for b_idx in range(num_blocks))
        
        reply = QMessageBox.question(
            self,
            tr('Revert All Blocks'),
            f"Are you sure you want to revert all {total_strings} string(s) across {num_blocks} block(s) to their original state?\n\n"
            "All unsaved changes in the entire project will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return
            
        flat_list = []
        for b_idx in range(num_blocks):
            num_strings = len(main_window.data_store.data[b_idx])
            for s_idx in range(num_strings):
                flat_list.append((b_idx, s_idx))
                
        main_window.data_processor.perform_revert_strings(-2, flat_list, confirm=False)

