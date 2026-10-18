"""Save and restore per-string translations; export and import project text as JSON."""
# handlers/saved_translations_handler.py
from utils.atomic_io import atomic_write_json
import copy
import json
import datetime
from collections.abc import Mapping
from pathlib import Path
from typing import List, Tuple
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QProgressDialog

from handlers.base_handler import BaseHandler
from handlers.memory_context_worker import MemoryContextWorker
from core.i18n import tr
from core.translation import memory_context

class SavedTranslationsHandler(BaseHandler):
    """Handler for saved translations operations."""
    def _get_project_name_for_export(self) -> str:
        project_manager = getattr(self.ctx, 'project_manager', None)
        project = getattr(project_manager, 'project', None) if project_manager else None
        return getattr(project, 'name', 'Single File') if project else 'Single File'

    def _get_block_export_location(self, block_idx: int) -> Tuple[str, str]:
        """Return the file/key pair used by translation JSON exports."""
        block_source_file = "single_file"
        block_internal_key = ""
        ctx_block_map = getattr(self.ctx, 'block_to_project_file_map', None)
        store_block_map = getattr(self.data_store, 'block_to_project_file_map', None)
        block_map = None
        if isinstance(ctx_block_map, Mapping) and ctx_block_map:
            block_map = ctx_block_map
        elif isinstance(store_block_map, Mapping) and store_block_map:
            block_map = store_block_map
        project_manager = getattr(self.ctx, 'project_manager', None)
        project = getattr(project_manager, 'project', None) if project_manager else None

        if block_map and project:
            p_b_idx = block_map.get(block_idx)
            if p_b_idx is not None and 0 <= p_b_idx < len(project.blocks):
                block = project.blocks[p_b_idx]
                block_source_file = block.source_file
                block_internal_key = block.internal_key or ""
                if not block_internal_key:
                    mapped_block_count = sum(1 for mapped_idx in block_map.values() if mapped_idx == p_b_idx)
                    if mapped_block_count > 1:
                        block_internal_key = self.data_store.block_names.get(str(block_idx), f"block_{block_idx}")
        elif hasattr(self.data_store, 'block_names') and self.data_store.block_names:
            block_source_file = self.data_store.block_names.get(str(block_idx), f"block_{block_idx}")

        return block_source_file, block_internal_key

    def restore_translation(self, block_idx: int, string_idx: int) -> bool:
        """Restore translation."""
        manager = self.ctx.saved_translations_manager
        saved_text = manager.get_saved_translation(block_idx, string_idx)
        if saved_text is None:
            QMessageBox.warning(self.ctx, tr('Restore Error'), tr('No saved translation found for this line.'))
            return False
        
        # Check if current is different
        curr_text, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        if curr_text == saved_text:
            if hasattr(self.ctx, 'statusBar') and self.ctx.statusBar:
                self.ctx.statusBar.showMessage("Translation is already matching the saved one.", 2000)
            return True

        # Update
        has_undo = hasattr(self.ctx, 'undo_manager')
        if has_undo:
            self.ctx.undo_manager.begin_group()

        self.data_processor.update_edited_data(block_idx, string_idx, saved_text, action_type="RESTORE")

        if hasattr(self.ctx, 'text_operation_handler') and self.ctx.text_operation_handler:
            self.ctx.text_operation_handler._rescan_issues_for_current_string(block_idx, string_idx, saved_text)

        if has_undo:
            self.ctx.undo_manager.end_group("RESTORE")

        # Refreshes
        if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
            self.ui_updater.update_block_item_text_with_problem_count(block_idx)
        self.ui_updater.populate_current_view(force=True)
        self.ui_updater.update_text_views()
        
        if hasattr(self.ctx, 'statusBar') and self.ctx.statusBar:
            self.ctx.statusBar.showMessage(f"Restored saved translation for line {string_idx + 1}.", 2000)
        return True

    def restore_translations_for_strings(self, block_idx: int, string_indices: List[int]) -> None:
        """Restore translations for strings."""
        manager = self.ctx.saved_translations_manager
        translations = manager.load_all_saved_translations()
        has_undo = hasattr(self.ctx, 'undo_manager')
        if has_undo:
            self.ctx.undo_manager.begin_group()

        restored_count = 0
        try:
            for s_idx in string_indices:
                key = manager._get_string_unique_key(block_idx, s_idx)
                if key in translations:
                    saved_text = translations[key]
                    self.data_processor.update_edited_data(block_idx, s_idx, saved_text, action_type="RESTORE", skip_ui_refresh=True)
                    if hasattr(self.ctx, 'text_operation_handler') and self.ctx.text_operation_handler:
                        self.ctx.text_operation_handler._rescan_issues_for_current_string(block_idx, s_idx, saved_text)
                    restored_count += 1
        finally:
            if has_undo:
                self.ctx.undo_manager.end_group("RESTORE_STRINGS")

        if restored_count > 0:
            if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
                self.ui_updater.update_block_item_text_with_problem_count(block_idx)
            
            refresh_idx = self.data_store.current_block_idx
            if getattr(self.data_store, 'current_chapter_id', None) is not None:
                refresh_idx = -2
                
            self.ui_updater.populate_strings_for_block(refresh_idx, getattr(self.data_store, 'current_category_name', None), force=True)
            self.ui_updater.update_text_views()
            if hasattr(self.ctx, 'statusBar') and self.ctx.statusBar:
                self.ctx.statusBar.showMessage(f"Restored {restored_count} saved translations.", 2000)
        else:
            QMessageBox.information(self.ctx, tr('Restore Translation'), tr('No saved translations were found for the selected lines.'))

    def restore_translations_for_block(self, block_idx: int) -> None:
        """Restore translations for block."""
        if block_idx < 0 or not self.data_store.data or block_idx >= len(self.data_store.data):
            return
        num_strings = len(self.data_store.data[block_idx])
        self.restore_translations_for_strings(block_idx, list(range(num_strings)))

    def restore_all_saved_translations_action(self) -> None:
        """Restore all saved translations action."""
        if not self.data_store.data:
            return
            
        manager = self.ctx.saved_translations_manager
        translations = manager.load_all_saved_translations()
        if not translations:
            QMessageBox.information(self.ctx, tr('Restore All Translations'), tr('No saved translations found in the project.'))
            return
            
        reply = QMessageBox.question(
            self.ctx,
            tr('Restore All Translations'),
            tr('Are you sure you want to restore all saved translations in the project?\n\nThis will overwrite current edits in memory.'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return
            
        has_undo = hasattr(self.ctx, 'undo_manager')
        if has_undo:
            self.ctx.undo_manager.begin_group()
            
        restored_count = 0
        affected_blocks = set()
        try:
            for b_idx in range(len(self.data_store.data)):
                num_strings = len(self.data_store.data[b_idx])
                for s_idx in range(num_strings):
                    key = manager._get_string_unique_key(b_idx, s_idx)
                    if key in translations:
                        saved_text = translations[key]
                        curr_text, _ = self.data_processor.get_current_string_text(b_idx, s_idx)
                        if curr_text != saved_text:
                            self.data_processor.update_edited_data(b_idx, s_idx, saved_text, action_type="RESTORE", skip_ui_refresh=True)
                            if hasattr(self.ctx, 'text_operation_handler') and self.ctx.text_operation_handler:
                                self.ctx.text_operation_handler._rescan_issues_for_current_string(b_idx, s_idx, saved_text)
                            restored_count += 1
                            affected_blocks.add(b_idx)
        finally:
            if has_undo:
                self.ctx.undo_manager.end_group("RESTORE_ALL")
                
        if restored_count > 0:
            if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
                for b_idx in affected_blocks:
                    self.ui_updater.update_block_item_text_with_problem_count(b_idx)
                curr_block = getattr(self.data_store, 'current_block_idx', -1)
                curr_cat = getattr(self.data_store, 'current_category_name', None)
                self.ui_updater.populate_strings_for_block(curr_block, curr_cat, force=True)
                self.ui_updater.update_text_views()
            if hasattr(self.ctx, 'statusBar') and self.ctx.statusBar:
                self.ctx.statusBar.showMessage(f"Restored {restored_count} saved translations across {len(affected_blocks)} block(s).", 2000)
        else:
            QMessageBox.information(self.ctx, tr('Restore All Translations'), tr('All translations in memory are already matching the saved translations.'))

    def save_translation_action(self) -> None:
        """Save translation action."""
        block_idx = self.data_store.current_block_idx
        string_idx = self.data_store.current_string_idx
        if block_idx == -1 or string_idx == -1:
            QMessageBox.warning(self.ctx, tr('Save Translation'), tr('Please select a line first.'))
            return

        curr_text, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        original_text = self.data_processor._get_string_from_source(block_idx, string_idx, self.data_store.data, "original_data")
        
        if not curr_text or curr_text == original_text:
            QMessageBox.information(self.ctx, tr('Save Translation'), tr('This string does not have any translation/edits to save.'))
            return

        self.ctx.saved_translations_manager.save_translation(block_idx, string_idx, curr_text)
        QMessageBox.information(self.ctx, tr('Save Translation'), f"Translation for line {string_idx + 1} has been saved.")

    def restore_translation_action(self) -> None:
        """Restore translation action."""
        block_idx = self.data_store.current_block_idx
        string_idx = self.data_store.current_string_idx
        if block_idx == -1 or string_idx == -1:
            QMessageBox.warning(self.ctx, tr('Restore Translation'), tr('Please select a line first.'))
            return

        self.restore_translation(block_idx, string_idx)

    def update_memory_with_context_action(self) -> None:
        """Give the rows of the translation memory the context they were made under (D41), on a worker thread.

        The memory is replaced only when the plan completes and is not cancelled; the previous file is kept beside it.
        """
        manager = self.ctx.saved_translations_manager
        path = manager.memory_file()
        if path is None or not path.is_file():
            QMessageBox.information(self.ctx, tr('Update Translation Memory'), tr('This project has no translation memory yet.'))
            return
        if manager.context_for is None:
            QMessageBox.information(self.ctx, tr('Update Translation Memory'), tr('Open the project before its translation memory is updated.'))
            return
        if getattr(self, '_memory_worker', None) is not None and self._memory_worker.isRunning():
            return
        memory = copy.deepcopy(manager.load_translation_memory())
        data = [list(block) if isinstance(block, list) else [] for block in (self.data_store.data or [])]
        worker = MemoryContextWorker(
            path, memory, data, manager.block_key_prefixes(len(data)), dict(manager.load_all_saved_translations()),
            memory_context.place_context(manager.context_for), manager.tag_fields_of, parent=self.ctx,
        )
        dialog = QProgressDialog(tr('Giving the translation memory the context of its rows...'), tr('Cancel'), 0, 0, self.ctx)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        worker.progress.connect(lambda done, total: (dialog.setRange(0, max(total, 1)), dialog.setValue(done)),
                                Qt.ConnectionType.QueuedConnection)
        dialog.canceled.connect(worker.cancel)
        worker.done.connect(lambda result: self._memory_context_done(result, dialog, path), Qt.ConnectionType.QueuedConnection)
        worker.failed.connect(lambda text: self._memory_context_failed(text, dialog), Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(worker.deleteLater)
        self._memory_worker = worker
        worker.start()

    def _memory_context_done(self, result, dialog, path: Path) -> None:
        dialog.close()
        if result is None:
            QMessageBox.information(self.ctx, tr('Update Translation Memory'), tr('Cancelled. The translation memory is unchanged.'))
            return
        self.ctx.saved_translations_manager.clear_cache()
        backup = Path(path).with_name(memory_context.BACKUP_NAME)
        QMessageBox.information(self.ctx, tr('Update Translation Memory'), tr(
            'Rows updated: {updated}. Rows split by context: {split}. Rows given tag kinds: {tagged}. '
            'Saved strings without a row (left as they are): {missing}. Backup: {backup}.',
            updated=result.updated, split=result.split, tagged=result.tagged, missing=result.missing, backup=str(backup)))

    def _memory_context_failed(self, text: str, dialog) -> None:
        dialog.close()
        QMessageBox.warning(self.ctx, tr('Update Translation Memory'), tr('The translation memory was not updated: {error}', error=text))

    def fill_terms_from_glossary_action(self) -> None:
        """Preview the strings a series glossary term translates, and fill the untranslated ones (D45, item 1)."""
        from dialogs.glossary_term_fill_dialog import GlossaryTermFillDialog
        GlossaryTermFillDialog(self.ctx, self.ctx).exec()

    def restore_memory_before_context_action(self) -> None:
        """Put the translation memory back from the copy kept before the context update."""
        manager = self.ctx.saved_translations_manager
        path = manager.memory_file()
        if path is None or not memory_context.restore_backup(path):
            QMessageBox.information(self.ctx, tr('Update Translation Memory'), tr('No copy of the translation memory from before the update exists.'))
            return
        manager.clear_cache()
        QMessageBox.information(self.ctx, tr('Update Translation Memory'), tr('The translation memory is restored from its copy.'))

    def export_translations_to_json_action(self) -> None:
        """Export translations to json action."""
        if not self.data_store.data:
            QMessageBox.warning(self.ctx, tr('Export Error'), tr('No project or file is currently open.'))
            return

        # Determine target file name
        default_name = "project_translations_export.json"
        if hasattr(self.ctx, 'project_manager') and self.ctx.project_manager and self.ctx.project_manager.project:
            proj_name = self.ctx.project_manager.project.name.replace('/', '_').replace('\\', '_')
            default_name = f"{proj_name}_translations_export.json"
        elif self.data_store.json_path:
            file_name = Path(self.data_store.json_path).stem
            default_name = f"{file_name}_translations_export.json"

        save_path, _ = QFileDialog.getSaveFileName(
            self.ctx,
            'Export Translations to JSON',
            str(Path.home() / default_name),
            'JSON Files (*.json);;All Files (*)'
        )
        if not save_path:
            return

        # Collect all translations.
        export_data = {
            "exported_at": datetime.datetime.now().isoformat(),
            "project_name": self._get_project_name_for_export(),
            "files": {}
        }

        # Let's iterate over all data blocks
        for block_idx in range(len(self.data_store.data)):
            block_source_file, block_internal_key = self._get_block_export_location(block_idx)

            # Get all strings in this block
            num_strings = len(self.data_store.data[block_idx])
            block_translations = {}
            for s_idx in range(num_strings):
                if self.data_processor.is_string_translated(block_idx, s_idx):
                    curr_text, _ = self.data_processor.get_current_string_text(block_idx, s_idx)
                    block_translations[str(s_idx)] = curr_text

            if block_translations:
                # Add to export
                export_data["files"].setdefault(block_source_file, {})
                export_data["files"][block_source_file][block_internal_key] = block_translations

        try:
            atomic_write_json(save_path, export_data, ensure_ascii=False, indent=2)
            QMessageBox.information(
                self.ctx, tr('Export Translations'),
                f'Successfully exported translations to:\n{save_path}'
            )
        except Exception as e:
            QMessageBox.critical(self.ctx, tr('Export Error'), f'Failed to save JSON:\n{e}')

    def export_original_to_json_action(self) -> None:
        """Export original text to json action."""
        if not self.data_store.data:
            QMessageBox.warning(self.ctx, tr('Export Error'), tr('No project or file is currently open.'))
            return

        # Determine target file name
        default_name = "project_original_export.json"
        if hasattr(self.ctx, 'project_manager') and self.ctx.project_manager and self.ctx.project_manager.project:
            proj_name = self.ctx.project_manager.project.name.replace('/', '_').replace('\\', '_')
            default_name = f"{proj_name}_original_export.json"
        elif self.data_store.json_path:
            file_name = Path(self.data_store.json_path).stem
            default_name = f"{file_name}_original_export.json"

        save_path, _ = QFileDialog.getSaveFileName(
            self.ctx,
            'Export Original Text to JSON',
            str(Path.home() / default_name),
            'JSON Files (*.json);;All Files (*)'
        )
        if not save_path:
            return

        # Collect all original texts.
        export_data = {
            "exported_at": datetime.datetime.now().isoformat(),
            "project_name": self._get_project_name_for_export(),
            "files": {}
        }

        # Let's iterate over all data blocks
        for block_idx in range(len(self.data_store.data)):
            block_source_file, block_internal_key = self._get_block_export_location(block_idx)

            # Get all original strings in this block
            num_strings = len(self.data_store.data[block_idx])
            block_originals = {}
            for s_idx in range(num_strings):
                orig_text = self.data_processor._get_string_from_source(block_idx, s_idx, self.data_store.data, "original_data")
                if orig_text is not None:
                    block_originals[str(s_idx)] = orig_text

            if block_originals:
                # Add to export
                export_data["files"].setdefault(block_source_file, {})
                export_data["files"][block_source_file][block_internal_key] = block_originals

        try:
            atomic_write_json(save_path, export_data, ensure_ascii=False, indent=2)
            QMessageBox.information(
                self.ctx, tr('Export Original Text'),
                f'Successfully exported original text to:\n{save_path}'
            )
        except Exception as e:
            QMessageBox.critical(self.ctx, tr('Export Error'), f'Failed to save JSON:\n{e}')

    def import_translations_from_json_action(self) -> None:
        """Import translations from json action."""
        if not self.data_store.data:
            QMessageBox.warning(self.ctx, tr('Import Error'), tr('No project or file is currently open.'))
            return

        load_path, _ = QFileDialog.getOpenFileName(
            self.ctx,
            'Import Translations from JSON',
            str(Path.home()),
            'JSON Files (*.json);;All Files (*)'
        )
        if not load_path:
            return

        try:
            with open(load_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self.ctx, tr('Import Error'), f'Failed to load JSON file:\\n{e}')
            return

        files_data = import_data.get("files", {})
        if not files_data:
            QMessageBox.warning(self.ctx, tr('Import Error'), tr('The selected JSON does not contain valid translations.'))
            return

        # Confirm
        reply = QMessageBox.question(
            self.ctx,
            tr('Confirm Import'),
            tr('This will import matching translations into your current project/file edits in memory.\nDo you want to proceed?'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        imported_count = 0
        has_undo = hasattr(self.ctx, 'undo_manager')
        if has_undo:
            self.ctx.undo_manager.begin_group()

        try:
            for block_idx in range(len(self.data_store.data)):
                block_source_file, block_internal_key = self._get_block_export_location(block_idx)

                # Check if this file has imported translations
                file_imports = files_data.get(block_source_file, {})
                block_imports = file_imports.get(block_internal_key, {})
                if not block_imports:
                    continue

                for s_idx_str, trans_text in block_imports.items():
                    try:
                        s_idx = int(s_idx_str)
                        if 0 <= s_idx < len(self.data_store.data[block_idx]):
                            self.data_processor.update_edited_data(block_idx, s_idx, trans_text, action_type="IMPORT", skip_ui_refresh=True)
                            if hasattr(self.ctx, 'text_operation_handler') and self.ctx.text_operation_handler:
                                self.ctx.text_operation_handler._rescan_issues_for_current_string(block_idx, s_idx, trans_text)
                            imported_count += 1
                    except ValueError:
                        pass
        finally:
            if has_undo:
                self.ctx.undo_manager.end_group("IMPORT_TRANSLATIONS")

        if imported_count > 0:
            self.ui_updater.populate_blocks()
            self.ui_updater.populate_current_view(force=True)
            self.ui_updater.update_text_views()
            QMessageBox.information(
                self.ctx,
                tr('Import Translations'),
                f'Successfully imported {imported_count} translations.\n'
                'The changes are loaded in the editor. Click "Save" to save them.'
            )
        else:
            QMessageBox.information(self.ctx, tr('Import Translations'), tr('No matching translations were found to import.'))
