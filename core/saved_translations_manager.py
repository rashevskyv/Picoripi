# core/saved_translations_manager.py
import json
import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QDialog

from utils.logging_utils import log_info, log_error, log_debug

class SavedTranslationsManager:
    def __init__(self, main_window: Any):
        self.mw = main_window

    def _get_saved_translations_path(self) -> Optional[Path]:
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project_dir:
            return Path(self.mw.project_manager.project_dir) / "saved_translations.json"
        elif hasattr(self.mw, 'data_store') and self.mw.data_store.json_path:
            p = Path(self.mw.data_store.json_path)
            return p.parent / f"{p.stem}_saved_translations.json"
        return None

    def _get_string_unique_key(self, block_idx: int, string_idx: int) -> str:
        block_source_file = "single_file"
        block_internal_key = ""
        if hasattr(self.mw, 'block_to_project_file_map') and self.mw.block_to_project_file_map:
            p_b_idx = self.mw.block_to_project_file_map.get(block_idx)
            if p_b_idx is not None and self.mw.project_manager and self.mw.project_manager.project and p_b_idx < len(self.mw.project_manager.project.blocks):
                block = self.mw.project_manager.project.blocks[p_b_idx]
                block_source_file = block.source_file
                block_internal_key = block.internal_key or ""
        elif hasattr(self.mw, 'data_store') and self.mw.data_store.block_names:
            block_source_file = self.mw.data_store.block_names.get(str(block_idx), f"block_{block_idx}")
            
        return f"{block_source_file}::{block_internal_key}::{string_idx}"

    def load_all_saved_translations(self) -> Dict[str, str]:
        path = self._get_saved_translations_path()
        if not path or not path.exists():
            return {}
        try:
            with path.open('r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log_error(f"Failed to load saved translations: {e}")
            return {}

    def save_all_saved_translations(self, data: Dict[str, str]) -> bool:
        path = self._get_saved_translations_path()
        if not path:
            return False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            log_error(f"Failed to save translations to {path}: {e}")
            return False

    def has_saved_translation(self, block_idx: int, string_idx: int) -> bool:
        key = self._get_string_unique_key(block_idx, string_idx)
        translations = self.load_all_saved_translations()
        return key in translations

    def get_saved_translation(self, block_idx: int, string_idx: int) -> Optional[str]:
        key = self._get_string_unique_key(block_idx, string_idx)
        translations = self.load_all_saved_translations()
        return translations.get(key)

    def save_translation(self, block_idx: int, string_idx: int, text: str) -> None:
        if not text or not text.strip():
            return
        key = self._get_string_unique_key(block_idx, string_idx)
        translations = self.load_all_saved_translations()
        translations[key] = text
        self.save_all_saved_translations(translations)
        log_info(f"Saved translation for key {key}")

    def save_translations_bulk(self, block_idx: int, string_indices_and_texts: List[Tuple[int, str]]) -> None:
        translations = self.load_all_saved_translations()
        any_saved = False
        for string_idx, text in string_indices_and_texts:
            if text and text.strip():
                key = self._get_string_unique_key(block_idx, string_idx)
                translations[key] = text
                any_saved = True
        if any_saved:
            self.save_all_saved_translations(translations)
            log_info(f"Bulk saved {len(string_indices_and_texts)} translations for block {block_idx}")

    def restore_translation(self, block_idx: int, string_idx: int) -> bool:
        saved_text = self.get_saved_translation(block_idx, string_idx)
        if saved_text is None:
            QMessageBox.warning(self.mw, "Restore Error", "No saved translation found for this line.")
            return False
        
        # Check if current is different
        curr_text, _ = self.mw.data_processor.get_current_string_text(block_idx, string_idx)
        if curr_text == saved_text:
            if hasattr(self.mw, 'statusBar') and self.mw.statusBar:
                self.mw.statusBar.showMessage("Translation is already matching the saved one.", 2000)
            return True

        # Update
        has_undo = hasattr(self.mw, 'undo_manager')
        if has_undo:
            self.mw.undo_manager.begin_group()

        self.mw.data_processor.update_edited_data(block_idx, string_idx, saved_text, action_type="RESTORE")

        if hasattr(self.mw, 'text_operation_handler') and self.mw.text_operation_handler:
            self.mw.text_operation_handler._rescan_issues_for_current_string(block_idx, string_idx, saved_text)

        if has_undo:
            self.mw.undo_manager.end_group("RESTORE")

        # Refreshes
        if hasattr(self.mw.ui_updater, 'update_block_item_text_with_problem_count'):
            self.mw.ui_updater.update_block_item_text_with_problem_count(block_idx)
        self.mw.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx, force=True)
        self.mw.ui_updater.update_text_views()
        
        if hasattr(self.mw, 'statusBar') and self.mw.statusBar:
            self.mw.statusBar.showMessage(f"Restored saved translation for line {string_idx + 1}.", 2000)
        return True

    def restore_translations_for_strings(self, block_idx: int, string_indices: List[int]) -> None:
        translations = self.load_all_saved_translations()
        has_undo = hasattr(self.mw, 'undo_manager')
        if has_undo:
            self.mw.undo_manager.begin_group()

        restored_count = 0
        try:
            for s_idx in string_indices:
                key = self._get_string_unique_key(block_idx, s_idx)
                if key in translations:
                    saved_text = translations[key]
                    self.mw.data_processor.update_edited_data(block_idx, s_idx, saved_text, action_type="RESTORE", skip_ui_refresh=True)
                    if hasattr(self.mw, 'text_operation_handler') and self.mw.text_operation_handler:
                        self.mw.text_operation_handler._rescan_issues_for_current_string(block_idx, s_idx, saved_text)
                    restored_count += 1
        finally:
            if has_undo:
                self.mw.undo_manager.end_group("RESTORE_STRINGS")

        if restored_count > 0:
            if hasattr(self.mw.ui_updater, 'update_block_item_text_with_problem_count'):
                self.mw.ui_updater.update_block_item_text_with_problem_count(block_idx)
            
            refresh_idx = self.mw.data_store.current_block_idx
            if getattr(self.mw.data_store, 'current_chapter_id', None) is not None:
                refresh_idx = -2
                
            self.mw.ui_updater.populate_strings_for_block(refresh_idx, getattr(self.mw.data_store, 'current_category_name', None), force=True)
            self.mw.ui_updater.update_text_views()
            if hasattr(self.mw, 'statusBar') and self.mw.statusBar:
                self.mw.statusBar.showMessage(f"Restored {restored_count} saved translations.", 2000)
        else:
            QMessageBox.information(self.mw, "Restore Translation", "No saved translations were found for the selected lines.")

    def restore_translations_for_block(self, block_idx: int) -> None:
        if block_idx < 0 or not self.mw.data_store.data or block_idx >= len(self.mw.data_store.data):
            return
        num_strings = len(self.mw.data_store.data[block_idx])
        self.restore_translations_for_strings(block_idx, list(range(num_strings)))

    def restore_all_saved_translations_action(self) -> None:
        if not self.mw.data_store.data:
            return
            
        translations = self.load_all_saved_translations()
        if not translations:
            QMessageBox.information(self.mw, "Restore All Translations", "No saved translations found in the project.")
            return
            
        reply = QMessageBox.question(
            self.mw,
            "Restore All Translations",
            "Are you sure you want to restore all saved translations in the project?\n\n"
            "This will overwrite current edits in memory.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return
            
        has_undo = hasattr(self.mw, 'undo_manager')
        if has_undo:
            self.mw.undo_manager.begin_group()
            
        restored_count = 0
        affected_blocks = set()
        try:
            for b_idx in range(len(self.mw.data_store.data)):
                num_strings = len(self.mw.data_store.data[b_idx])
                for s_idx in range(num_strings):
                    key = self._get_string_unique_key(b_idx, s_idx)
                    if key in translations:
                        saved_text = translations[key]
                        curr_text, _ = self.mw.data_processor.get_current_string_text(b_idx, s_idx)
                        if curr_text != saved_text:
                            self.mw.data_processor.update_edited_data(b_idx, s_idx, saved_text, action_type="RESTORE", skip_ui_refresh=True)
                            if hasattr(self.mw, 'text_operation_handler') and self.mw.text_operation_handler:
                                self.mw.text_operation_handler._rescan_issues_for_current_string(b_idx, s_idx, saved_text)
                            restored_count += 1
                            affected_blocks.add(b_idx)
        finally:
            if has_undo:
                self.mw.undo_manager.end_group("RESTORE_ALL")
                
        if restored_count > 0:
            if hasattr(self.mw, 'ui_updater'):
                for b_idx in affected_blocks:
                    self.mw.ui_updater.update_block_item_text_with_problem_count(b_idx)
                curr_block = getattr(self.mw.data_store, 'current_block_idx', -1)
                curr_cat = getattr(self.mw.data_store, 'current_category_name', None)
                self.mw.ui_updater.populate_strings_for_block(curr_block, curr_cat, force=True)
                self.mw.ui_updater.update_text_views()
            if hasattr(self.mw, 'statusBar') and self.mw.statusBar:
                self.mw.statusBar.showMessage(f"Restored {restored_count} saved translations across {len(affected_blocks)} block(s).", 2000)
        else:
            QMessageBox.information(self.mw, "Restore All Translations", "All translations in memory are already matching the saved translations.")


    def save_translation_action(self) -> None:
        block_idx = self.mw.data_store.current_block_idx
        string_idx = self.mw.data_store.current_string_idx
        if block_idx == -1 or string_idx == -1:
            QMessageBox.warning(self.mw, "Save Translation", "Please select a line first.")
            return

        curr_text, _ = self.mw.data_processor.get_current_string_text(block_idx, string_idx)
        original_text = self.mw.data_processor._get_string_from_source(block_idx, string_idx, self.mw.data_store.data, "original_data")
        
        if not curr_text or curr_text == original_text:
            QMessageBox.information(self.mw, "Save Translation", "This string does not have any translation/edits to save.")
            return

        self.save_translation(block_idx, string_idx, curr_text)
        QMessageBox.information(self.mw, "Save Translation", f"Translation for line {string_idx + 1} has been saved.")

    def restore_translation_action(self) -> None:
        block_idx = self.mw.data_store.current_block_idx
        string_idx = self.mw.data_store.current_string_idx
        if block_idx == -1 or string_idx == -1:
            QMessageBox.warning(self.mw, "Restore Translation", "Please select a line first.")
            return

        self.restore_translation(block_idx, string_idx)

    def export_translations_to_json_action(self) -> None:
        if not self.mw.data_store.data:
            QMessageBox.warning(self.mw, "Export Error", "No project or file is currently open.")
            return

        # Determine target file name
        default_name = "project_translations_export.json"
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
            proj_name = self.mw.project_manager.project.name.replace('/', '_').replace('\\', '_')
            default_name = f"{proj_name}_translations_export.json"
        elif self.mw.data_store.json_path:
            file_name = Path(self.mw.data_store.json_path).stem
            default_name = f"{file_name}_translations_export.json"

        save_path, _ = QFileDialog.getSaveFileName(
            self.mw,
            'Export Translations to JSON',
            str(Path.home() / default_name),
            'JSON Files (*.json);;All Files (*)'
        )
        if not save_path:
            return

        # Collect all translations.
        export_data = {
            "exported_at": datetime.datetime.now().isoformat(),
            "project_name": getattr(self.mw.project_manager.project, 'name', 'Single File') if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project else 'Single File',
            "files": {}
        }

        # Let's iterate over all data blocks
        for block_idx in range(len(self.mw.data_store.data)):
            # Determine block paths
            block_source_file = "single_file"
            block_internal_key = ""
            if hasattr(self.mw, 'block_to_project_file_map') and self.mw.block_to_project_file_map:
                p_b_idx = self.mw.block_to_project_file_map.get(block_idx)
                if p_b_idx is not None and self.mw.project_manager and self.mw.project_manager.project and p_b_idx < len(self.mw.project_manager.project.blocks):
                    block = self.mw.project_manager.project.blocks[p_b_idx]
                    block_source_file = block.source_file
                    block_internal_key = block.internal_key or ""
            elif hasattr(self.mw, 'data_store') and self.mw.data_store.block_names:
                block_source_file = self.mw.data_store.block_names.get(str(block_idx), f"block_{block_idx}")

            # Get all strings in this block
            num_strings = len(self.mw.data_store.data[block_idx])
            block_translations = {}
            for s_idx in range(num_strings):
                if self.mw.data_processor.is_string_translated(block_idx, s_idx):
                    curr_text, _ = self.mw.data_processor.get_current_string_text(block_idx, s_idx)
                    block_translations[str(s_idx)] = curr_text

            if block_translations:
                # Add to export
                export_data["files"].setdefault(block_source_file, {})
                export_data["files"][block_source_file][block_internal_key] = block_translations

        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(
                self.mw, 'Export Translations',
                f'Successfully exported translations to:\n{save_path}'
            )
        except Exception as e:
            QMessageBox.critical(self.mw, 'Export Error', f'Failed to save JSON:\n{e}')

    def import_translations_from_json_action(self) -> None:
        if not self.mw.data_store.data:
            QMessageBox.warning(self.mw, "Import Error", "No project or file is currently open.")
            return

        load_path, _ = QFileDialog.getOpenFileName(
            self.mw,
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
            QMessageBox.critical(self.mw, 'Import Error', f'Failed to load JSON file:\n{e}')
            return

        files_data = import_data.get("files", {})
        if not files_data:
            QMessageBox.warning(self.mw, 'Import Error', 'The selected JSON does not contain valid translations.')
            return

        # Confirm
        reply = QMessageBox.question(
            self.mw,
            'Confirm Import',
            'This will import matching translations into your current project/file edits in memory.\n'
            'Do you want to proceed?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        imported_count = 0
        has_undo = hasattr(self.mw, 'undo_manager')
        if has_undo:
            self.mw.undo_manager.begin_group()

        try:
            for block_idx in range(len(self.mw.data_store.data)):
                # Determine block paths
                block_source_file = "single_file"
                block_internal_key = ""
                if hasattr(self.mw, 'block_to_project_file_map') and self.mw.block_to_project_file_map:
                    p_b_idx = self.mw.block_to_project_file_map.get(block_idx)
                    if p_b_idx is not None and self.mw.project_manager and self.mw.project_manager.project and p_b_idx < len(self.mw.project_manager.project.blocks):
                        block = self.mw.project_manager.project.blocks[p_b_idx]
                        block_source_file = block.source_file
                        block_internal_key = block.internal_key or ""
                elif hasattr(self.mw, 'data_store') and self.mw.data_store.block_names:
                    block_source_file = self.mw.data_store.block_names.get(str(block_idx), f"block_{block_idx}")

                # Check if this file has imported translations
                file_imports = files_data.get(block_source_file, {})
                block_imports = file_imports.get(block_internal_key, {})
                if not block_imports:
                    continue

                for s_idx_str, trans_text in block_imports.items():
                    try:
                        s_idx = int(s_idx_str)
                        if 0 <= s_idx < len(self.mw.data_store.data[block_idx]):
                            self.mw.data_processor.update_edited_data(block_idx, s_idx, trans_text, action_type="IMPORT", skip_ui_refresh=True)
                            if hasattr(self.mw, 'text_operation_handler') and self.mw.text_operation_handler:
                                self.mw.text_operation_handler._rescan_issues_for_current_string(block_idx, s_idx, trans_text)
                            imported_count += 1
                    except ValueError:
                        pass
        finally:
            if has_undo:
                self.mw.undo_manager.end_group("IMPORT_TRANSLATIONS")

        if imported_count > 0:
            self.mw.ui_updater.populate_blocks()
            self.mw.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx, force=True)
            self.mw.ui_updater.update_text_views()
            QMessageBox.information(
                self.mw,
                'Import Translations',
                f'Successfully imported {imported_count} translations.\n'
                'The changes are loaded in the editor. Click "Save" to save them.'
            )
        else:
            QMessageBox.information(self.mw, "Import Translations", "No matching translations were found to import.")
