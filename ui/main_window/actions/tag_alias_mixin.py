from __future__ import annotations
from pathlib import Path
import json
from PyQt6.QtWidgets import QMessageBox, QProgressDialog, QDialog, QApplication
from PyQt6.QtCore import Qt
from dialogs.tag_alias_dialog import TagAliasDialog, AliasUpdateWorker
from utils.logging_utils import log_info, log_error
from core.i18n import tr


class MainWindowTagAliasActionsMixin:
    """Tag alias add/edit/remove helpers."""

    def add_tag_alias(self, original_tag: str):
        """Add tag alias."""
        dialog = TagAliasDialog(self.mw, "Add Tag Alias", original_tag)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
            
        alias, width = dialog.get_data()
        if not alias:
            QMessageBox.warning(self.mw, tr('Invalid Alias'), tr('Alias cannot be empty.'))
            return
            
        if not hasattr(self.mw, 'default_tag_mappings'):
            self.mw.default_tag_mappings = {}
            
        if alias in self.mw.default_tag_mappings:
            QMessageBox.warning(
                self.mw, 
                tr('Duplicate Alias'), 
                f"Alias '{alias}' is already registered for tag '{self.mw.default_tag_mappings[alias]}'."
            )
            return
            
        self.mw.default_tag_mappings[alias] = original_tag
        
        # Apply and save width override
        if not hasattr(self.mw, 'font_map_overrides') or self.mw.font_map_overrides is None:
            self.mw.font_map_overrides = {}
            
        if width is not None:
            self.mw.font_map_overrides[alias] = {"width": width}
        else:
            self.mw.font_map_overrides.pop(alias, None)
            
        # Save width overrides to disk
        self._save_font_overrides_to_disk()
        
        # Apply overrides in memory
        if hasattr(self.mw, 'font_map_loader') and self.mw.font_map_loader:
            self.mw.font_map_loader._apply_font_overrides(self.mw.font_map_overrides)
        
        # Save settings
        if hasattr(self.mw, 'settings_manager'):
            self.mw.settings_manager.save_settings()
            
        # Trigger recalculation of widths
        if hasattr(self.mw, 'issue_scan_handler'):
            self.mw.issue_scan_handler._perform_initial_silent_scan_all_issues()
            
        self._refresh_editors_after_alias_change()

    def edit_tag_alias(self, alias: str, original_tag: str):
        """Edit tag alias."""
        current_width = None
        if hasattr(self.mw, 'font_map_overrides') and self.mw.font_map_overrides:
            current_width = self.mw.font_map_overrides.get(alias, {}).get('width')
            
        dialog = TagAliasDialog(self.mw, "Edit Tag Alias", original_tag, current_alias=alias, current_width=current_width)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
            
        new_alias, width = dialog.get_data()
        new_alias = new_alias.strip()
        if not new_alias:
            QMessageBox.warning(self.mw, tr('Invalid Alias'), tr('Alias cannot be empty.'))
            return
            
        if not hasattr(self.mw, 'default_tag_mappings'):
            self.mw.default_tag_mappings = {}
            
        if new_alias != alias and new_alias in self.mw.default_tag_mappings:
            QMessageBox.warning(
                self.mw, 
                tr('Duplicate Alias'), 
                f"Alias '{new_alias}' is already registered for tag '{self.mw.default_tag_mappings[new_alias]}'."
            )
            return
            
        # Update mappings
        self.mw.default_tag_mappings.pop(alias, None)
        self.mw.default_tag_mappings[new_alias] = original_tag
        
        # Update width overrides
        if not hasattr(self.mw, 'font_map_overrides') or self.mw.font_map_overrides is None:
            self.mw.font_map_overrides = {}
            
        self.mw.font_map_overrides.pop(alias, None)
        if width is not None:
            self.mw.font_map_overrides[new_alias] = {"width": width}
            
        # Save width overrides to disk
        self._save_font_overrides_to_disk()
        
        # Apply overrides in memory
        if hasattr(self.mw, 'font_map_loader') and self.mw.font_map_loader:
            self.mw.font_map_loader._apply_font_overrides(self.mw.font_map_overrides)
            
        # Clean up stale alias from in-memory edits to prevent desync asynchronously
        def on_complete():
            # Save settings
            """Handle the complete event."""
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.save_settings()
                
            # Trigger recalculation of widths
            if hasattr(self.mw, 'issue_scan_handler'):
                self.mw.issue_scan_handler._perform_initial_silent_scan_all_issues()
                
            self._refresh_editors_after_alias_change()
            
        self._update_aliases_in_edited_data(alias, original_tag, on_complete)

    def remove_tag_alias(self, alias: str, original_tag: str):
        """Remove tag alias."""
        reply = QMessageBox.question(
            self.mw,
            tr('Remove Tag Alias'),
            f"Are you sure you want to remove the alias '{alias}' for tag '{original_tag}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if hasattr(self.mw, 'default_tag_mappings'):
                self.mw.default_tag_mappings.pop(alias, None)
                
            # Remove from overrides
            if hasattr(self.mw, 'font_map_overrides') and self.mw.font_map_overrides:
                self.mw.font_map_overrides.pop(alias, None)
                
            # Save overrides to disk
            self._save_font_overrides_to_disk()
            
            # Apply overrides in memory
            if hasattr(self.mw, 'font_map_loader') and self.mw.font_map_loader:
                self.mw.font_map_loader._apply_font_overrides(self.mw.font_map_overrides)
                
            # Clean up stale alias from in-memory edits to prevent desync asynchronously
            def on_complete():
                if hasattr(self.mw, 'settings_manager'):
                    self.mw.settings_manager.save_settings()
                    
                # Trigger recalculation of widths
                if hasattr(self.mw, 'issue_scan_handler'):
                    self.mw.issue_scan_handler._perform_initial_silent_scan_all_issues()
                    
                self._refresh_editors_after_alias_change()
                
            self._update_aliases_in_edited_data(alias, original_tag, on_complete)

    def _update_aliases_in_edited_data(self, alias: str, original_tag: str, on_complete_callback):
        """Clean up stale alias from in-memory edits in a background thread if needed."""
        ds = getattr(self.mw, 'data_store', None)
        if not ds:
            on_complete_callback()
            return

        has_edited = hasattr(ds, 'edited_data') and ds.edited_data
        has_data = hasattr(ds, 'data') and ds.data
        has_edited_file = hasattr(ds, 'edited_file_data') and ds.edited_file_data

        if not has_edited and not has_data and not has_edited_file:
            on_complete_callback()
            return

        # Check if we are running in tests or QApplication is not fully initialized
        is_test = bool(getattr(self.mw, '_is_test_mode', False)) or not isinstance(QApplication.instance(), QApplication)
        
        # High-performance shallow copies of the block string lists
        edited_data_copy = dict(ds.edited_data) if has_edited else {}
        data_copy = [list(block) for block in ds.data] if (has_data and isinstance(ds.data, list)) else []
        edited_file_data_copy = [list(block) for block in ds.edited_file_data] if (has_edited_file and isinstance(ds.edited_file_data, list)) else []
        
        # Create worker
        self._alias_worker = AliasUpdateWorker(edited_data_copy, data_copy, edited_file_data_copy, alias, original_tag)
        
        def on_worker_finished(updated_edited_data, updated_data, updated_edited_file_data):
            """Handle the worker finished event."""
            self.mw.data_store.edited_data = updated_edited_data
            if updated_data:
                self.mw.data_store.data = updated_data
            if updated_edited_file_data:
                self.mw.data_store.edited_file_data = updated_edited_file_data
            on_complete_callback()
            # Clean up reference
            self._alias_worker = None
            
        self._alias_worker.finished_signal.connect(on_worker_finished)

        if is_test:
            # Sync mode for tests
            self._alias_worker.run()
        else:
            # Async mode for production with non-blocking QProgressDialog
            self._progress_dialog = QProgressDialog("Updating tag aliases across the project...", None, 0, 0, self.mw)
            self._progress_dialog.setWindowTitle(tr('Tag Aliases'))
            self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self._progress_dialog.setCancelButton(None) # Remove cancel button to ensure integrity
            self._progress_dialog.show()
            
            # Connect progress dialog close to worker finish
            self._alias_worker.finished_signal.connect(self._progress_dialog.close)
            
            self._alias_worker.start()


    def _refresh_editors_after_alias_change(self):
        """Internal helper to update the editors after alias change."""
        rules = getattr(self.mw, 'current_game_rules', None)
        if rules:
            if hasattr(rules, 'tag_manager') and rules.tag_manager:
                if hasattr(rules.tag_manager, '_legitimate_exact_tags_cache'):
                    rules.tag_manager._legitimate_exact_tags_cache = None
                    
        if hasattr(self.mw, 'helper') and hasattr(self.mw.helper, 'reconfigure_all_highlighters'):
            self.mw.helper.reconfigure_all_highlighters()
            
        ui = getattr(self.mw, 'ui_updater', None)
        if ui:
            if hasattr(ui, 'update_text_views'):
                ui.update_text_views()

        # Force a scan on the currently edited string so that highlights (glossary, spellcheck)
        # are recalculated using the new alias lengths immediately.
        toh = getattr(self.mw, 'text_operation_handler', None)
        if toh and self.mw.data_store.current_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
            toh.text_edited()
                

    def _save_font_overrides_to_disk(self):
        """Internal helper to save font overrides to disk."""
        plugin_name = getattr(self.mw, 'active_game_plugin', None)
        if not plugin_name:
            return
        
        override_path = Path('plugins') / plugin_name / 'font_map.json'
        override_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with override_path.open('w', encoding='utf-8') as f:
                json.dump(self.mw.font_map_overrides, f, indent=4, ensure_ascii=False)
            log_info(f"Successfully saved {len(self.mw.font_map_overrides)} overrides to {override_path}")
        except Exception as e:
            log_error(f"Failed to save font_map.json to disk: {e}")
