# /home/runner/work/RAG_project/RAG_project/handlers/main_window_actions.py
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Any, List
if TYPE_CHECKING:
    from main import MainWindow
from PyQt6.QtWidgets import QApplication, QMessageBox, QInputDialog, QProgressDialog, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox
from PyQt6.QtGui import QIntValidator
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from utils.logging_utils import log_info, log_error
import copy
from pathlib import Path
import json
from ui.settings_dialog import SettingsDialog

from dialogs.tag_alias_dialog import TagAliasDialog, AliasUpdateWorker


class MainWindowActions:
    """Main window actions implementation."""
    def __init__(self, main_window: MainWindow):
        """Initialize a new instance."""
        self.mw = main_window
        self.helper = main_window.helper
        from ui.main_window.bfn_actions import BfnActions
        from ui.main_window.mempalace_actions import MempalaceActions
        self.bfn_actions = BfnActions(self.mw)
        self.mempalace_actions = MempalaceActions(self.mw)
    
    def open_settings_dialog(self):
        """Open settings dialog."""
        log_info("Opening settings dialog...")
        
        # Save current rules values to compare later
        old_game_dialog_max_width = self.mw.game_dialog_max_width_pixels
        old_line_width_warning = self.mw.line_width_warning_threshold_pixels
        old_lines_per_page = getattr(self.mw, 'lines_per_page', 4)
        
        dialog = SettingsDialog(self.mw)
        
        if not dialog.exec():
            log_info("Settings dialog cancelled.")
            return

        new_settings = dialog.get_settings()
        
        # Check if rules values were actually changed to trigger rescan
        new_game_dialog_max_width = new_settings.get('game_dialog_max_width_pixels', old_game_dialog_max_width)
        new_line_width_warning = new_settings.get('line_width_warning_threshold_pixels', old_line_width_warning)
        new_lines_per_page = new_settings.get('lines_per_page', old_lines_per_page)
        
        if (new_game_dialog_max_width != old_game_dialog_max_width or
            new_line_width_warning != old_line_width_warning or
            new_lines_per_page != old_lines_per_page):
            dialog.rules_changed_requires_rescan = True
        
        new_font_file = new_settings.get('default_font_file') or ""
        old_font_file = getattr(self.mw, 'default_font_file', '') or ""
        font_file_changed = new_font_file != old_font_file
        
        spellchecker_lang_changed = new_settings.get('spellchecker_language') != self.mw.spellchecker_manager.language
        spellchecker_enabled_changed = new_settings.get('spellchecker_enabled') != self.mw.spellchecker_manager.enabled

        restore_session_before = self.mw.restore_unsaved_on_startup

        # Apply ALL new settings to self.mw immediately so they are captured by subsequent save_settings()
        for key, value in new_settings.items():
            setattr(self.mw, key, value)
        if hasattr(self.mw, 'toggle_preview_action'):
            self.mw.toggle_preview_action.setChecked(bool(self.mw.preview_enabled))
        if hasattr(self.mw, 'ui_updater'):
            self.mw.ui_updater.update_preview_visibility(
                bool(self.mw.preview_enabled), persist=False
            )

        if not (dialog.plugin_changed_requires_restart or dialog.theme_changed_requires_restart or font_file_changed):
            self.mw.string_settings_updater.update_string_settings_panel()

        if dialog.plugin_changed_requires_restart or dialog.theme_changed_requires_restart or font_file_changed:
            log_info(f"Restart required. Plugin change: {dialog.plugin_changed_requires_restart}, Theme change: {dialog.theme_changed_requires_restart}, Font file change: {font_file_changed}")
            
            self.mw.current_font_size = new_settings.get('font_size')
            self.mw.show_multiple_spaces_as_dots = new_settings.get('show_multiple_spaces_as_dots')
            self.mw.space_dot_color_hex = new_settings.get('space_dot_color_hex')
            self.mw.restore_unsaved_on_startup = new_settings.get('restore_unsaved_on_startup')
            self.mw.default_font_file = new_settings.get('default_font_file')

            self.mw.settings_manager.save_settings()

            self.mw.active_game_plugin = new_settings.get('active_game_plugin')
            self.mw.theme = new_settings.get('theme')
            log_info(f"Set new active plugin: {self.mw.active_game_plugin}, theme: {self.mw.theme}, font file: {self.mw.default_font_file}")

            # Update plugin and paths in current project if project is open
            if hasattr(self.mw, 'project_manager') and self.mw.project_manager and \
               hasattr(self.mw.project_manager, 'current_project') and self.mw.project_manager.current_project:
                proj = self.mw.project_manager.current_project
                proj.plugin_name = self.mw.active_game_plugin
                proj.metadata['source_path'] = new_settings.get('original_file_path')
                proj.metadata['translation_path'] = new_settings.get('edited_file_path')
                proj.metadata['is_directory_mode'] = new_settings.get('is_directory_mode', False)
                proj.metadata['auto_generate_translation_path'] = new_settings.get('auto_generate_translation_path', False)
                
                # Save project-specific settings to metadata
                self.mw.project_manager.save_settings_to_project(self.mw)
                self.mw.project_manager.save()
                log_info(f"Updated project plugin to '{self.mw.active_game_plugin}', paths, and saved project with settings")

            self.mw.settings_manager.save_settings()
            
            self.mw.is_restart_in_progress = True
            self.helper.restart_application()
        else:
            log_info("Settings changed without restart. Applying settings.")
            
            initial_paths = (self.mw.data_store.json_path, self.mw.data_store.edited_json_path)
            restore_session_after = self.mw.restore_unsaved_on_startup
            
            if restore_session_before and not restore_session_after and self.mw.data_store.unsaved_changes:
                reply = QMessageBox.question(self.mw, "Discard Unsaved Changes?",
                                             "You have disabled session restore.\nDo you want to discard the current unsaved changes now?",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self.mw.data_store.edited_data.clear()
                    self.mw.data_store.unsaved_changes = False
                    self.mw.helper.rebuild_unsaved_block_indices()
                    if hasattr(self.mw, 'ui_updater'):
                        self.mw.ui_updater.update_title()
                        self.mw.ui_updater.populate_blocks()
                        self.mw.ui_updater.populate_current_view()
                    if hasattr(self.mw, 'preview_text_edit'):
                        self.mw.preview_text_edit.viewport().update()
                    if hasattr(self.mw, 'edited_text_edit'):
                        self.mw.edited_text_edit.viewport().update()

                    log_info("User discarded unsaved changes after disabling session restore.")

            if spellchecker_enabled_changed:
                self.mw.spellchecker_manager.set_enabled(new_settings.get('spellchecker_enabled', False))
            
            if spellchecker_lang_changed:
                self.mw.spellchecker_manager.reload_dictionary(new_settings.get('spellchecker_language', 'uk'))
            
            if spellchecker_enabled_changed or spellchecker_lang_changed:
                if hasattr(self.mw, 'edited_text_edit'):
                    self.mw.edited_text_edit.highlighter.rehighlight()

            self.mw.settings_manager.save_settings()

            # Handle path changes
            is_project_active = hasattr(self.mw, 'project_manager') and self.mw.project_manager and \
                               self.mw.project_manager.current_project is not None
            
            new_orig = new_settings.get('original_file_path')
            new_edited = new_settings.get('edited_file_path')
            new_is_dir = new_settings.get('is_directory_mode', False)
            new_auto_gen = new_settings.get('auto_generate_translation_path', False)

            if is_project_active:
                proj = self.mw.project_manager.current_project
                old_source = proj.metadata.get('source_path', '')
                old_translation = proj.metadata.get('translation_path', '')
                old_is_dir = proj.metadata.get('is_directory_mode', False)
                old_auto_gen = proj.metadata.get('auto_generate_translation_path', False)
                
                paths_changed = (new_orig != old_source or 
                                 new_edited != old_translation or 
                                 new_is_dir != old_is_dir or
                                 new_auto_gen != old_auto_gen)
                
                if paths_changed:
                    log_info(f"Project paths/mode updated: source='{new_orig}', translation='{new_edited}', is_dir={new_is_dir}, auto_gen={new_auto_gen}")
                    proj.metadata['source_path'] = new_orig
                    proj.metadata['translation_path'] = new_edited
                    proj.metadata['is_directory_mode'] = new_is_dir
                    proj.metadata['auto_generate_translation_path'] = new_auto_gen
                
                self.mw.project_manager.save_settings_to_project(self.mw)
                self.mw.project_manager.save()
                log_info("Saved project-specific settings to project metadata")
                
                if paths_changed:
                    # Re-sync files because paths changed!
                    self.mw.project_manager.sync_project_files(plugin=self.mw.current_game_rules)
                    # Re-populate blocks
                    if hasattr(self.mw, 'project_action_handler'):
                        self.mw.project_action_handler._populate_blocks_from_project()
            else:
                self.mw.is_directory_mode = new_is_dir
                self.mw.auto_generate_translation_path = new_auto_gen
                if new_orig != initial_paths[0] or new_edited != initial_paths[1]:
                    if new_orig and Path(new_orig).exists():
                        log_info(f"File paths changed in settings. Loading new data from: {new_orig}")
                        self.mw.helper.load_all_data_for_path(new_orig, new_edited, is_initial_load_from_settings=False)

            self.mw.ui_handler.apply_font_size()
            self.mw.helper.reconfigure_all_highlighters()
            self.mw.helper.apply_text_wrap_settings()
            self.mw.ui_handler.update_editor_rules_properties()
            
            if dialog.rules_changed_requires_rescan:
                log_info("Rules were changed. Triggering a full rescan of all issues.")
                QMessageBox.information(self.mw, "Settings Changed", "Rules have been updated. Rescanning all issues...")
                if hasattr(self.mw, 'app_action_handler'):
                    self.mw.app_action_handler.rescan_all_tags()

            # Reload font maps and update combobox in case custom font dir changed
            self.mw.settings_manager.load_all_font_maps()
            self.mw.string_settings_updater.update_font_combobox()
            self.mw.string_settings_updater.update_string_settings_panel()

            if hasattr(self.mw, 'text_operation_handler'):
                self.mw.text_operation_handler._update_preview_content()
                self.mw.text_operation_handler.text_edited()

            if hasattr(self.mw, 'plugin_handler') and self.mw.plugin_handler:
                self.mw.plugin_handler.update_warnings_filter_button()


    def trigger_save_action(self):
        """Trigger save action."""
        log_info("Save action triggered.", category="file_ops")
        try:
            log_info(f"trigger_save_action details: has_app_action_handler={hasattr(self.mw, 'app_action_handler')}, "
                     f"unsaved_changes={getattr(self.mw.data_store, 'unsaved_changes', 'N/A')}, "
                     f"edited_keys_count={len(getattr(self.mw.data_store, 'edited_data', {}))}", category="file_ops")
            
            def on_save_finished(success: bool):
                if success:
                    self.helper.rebuild_unsaved_block_indices()
                    log_info("Save action processed and unsaved block indices rebuilt.", category="file_ops")
                else:
                    log_info("Save action was cancelled or returned False.", category="file_ops")

            self.mw.app_action_handler.save_data_action(ask_confirmation=False, on_finished_callback=on_save_finished)
        except Exception as save_err:
            log_error(f"CRITICAL ERROR in trigger_save_action: {save_err}", exc_info=True, category="file_ops")

    def trigger_revert_action(self):
        """Trigger revert action."""
        log_info("Revert changes file action triggered.")
        if self.mw.data_processor.revert_edited_file_to_original():
            log_info("Revert successful.")
            self.helper.rebuild_unsaved_block_indices()
            if hasattr(self.mw.ui_updater, 'clear_all_problem_block_highlights_and_text'):
                self.mw.ui_updater.clear_all_problem_block_highlights_and_text()
        else: log_info("Revert was cancelled or failed.")

    def trigger_undo_paste_action(self):
        """Trigger undo paste action."""
        log_info("Undo Paste Block action triggered.")
        if not self.mw.can_undo_paste:
            QMessageBox.information(self.mw, "Undo Paste", "Nothing to undo for the last paste operation.")
            if hasattr(self.mw, 'statusBar'): self.mw.statusBar.showMessage("Nothing to undo for paste.", 2000)
            return

        block_to_refresh_ui_for = self.mw.before_paste_block_idx_affected

        keys_to_remove_from_edited_data = [k for k in self.mw.data_store.edited_data.keys() if k[0] == block_to_refresh_ui_for]
        for key_to_remove in keys_to_remove_from_edited_data:
            del self.mw.data_store.edited_data[key_to_remove]
        for key_snapshot, value_snapshot in self.mw.before_paste_edited_data_snapshot.items():
            self.mw.data_store.edited_data[key_snapshot] = value_snapshot
        
        keys_to_remove_from_problems = [k for k in self.mw.data_store.problems_per_subline.keys() if k[0] == block_to_refresh_ui_for]
        for key_to_remove in keys_to_remove_from_problems:
            del self.mw.data_store.problems_per_subline[key_to_remove]
        for key_snapshot, value_snapshot in self.mw.before_paste_problems_per_subline_snapshot.items():
            self.mw.data_store.problems_per_subline[key_snapshot] = value_snapshot.copy() 

        self.helper.rebuild_unsaved_block_indices() 
        self.mw.data_store.unsaved_changes = bool(self.mw.data_store.edited_data) 
        
        if hasattr(self.mw, 'title_status_bar_updater'):
            self.mw.title_status_bar_updater.update_title()
        elif hasattr(self.mw.ui_updater, 'update_title'):
             self.mw.ui_updater.update_title()

        self.mw.is_programmatically_changing_text = True 

        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit and hasattr(preview_edit, 'highlightManager'):
            preview_edit.highlightManager.clearAllProblemHighlights() 

        if hasattr(self.mw, 'block_list_updater'):
            self.mw.block_list_updater.update_block_item_text_with_problem_count(block_to_refresh_ui_for)
        elif hasattr(self.mw.ui_updater, 'update_block_item_text_with_problem_count'):
            self.mw.ui_updater.update_block_item_text_with_problem_count(block_to_refresh_ui_for)

        if hasattr(self.mw, 'preview_updater') and hasattr(self.mw.preview_updater, 'update_preview_for_block'):
            self.mw.preview_updater.populate_current_view()
        elif hasattr(self.mw.ui_updater, 'populate_strings_for_block'):
            self.mw.ui_updater.populate_current_view()
        
        if hasattr(self.mw, 'editor_state_updater') and hasattr(self.mw.editor_state_updater, 'update_editor_content'):
             self.mw.editor_state_updater.update_editor_content()
        elif hasattr(self.mw.ui_updater, 'update_text_views'):
            self.mw.ui_updater.update_text_views()
        
        if self.mw.data_store.current_block_idx != block_to_refresh_ui_for:
            if hasattr(self.mw, 'block_list_updater'):
                self.mw.block_list_updater.update_block_item_text_with_problem_count(block_to_refresh_ui_for)
            elif hasattr(self.mw.ui_updater, 'update_block_item_text_with_problem_count'):
                self.mw.ui_updater.update_block_item_text_with_problem_count(block_to_refresh_ui_for)

        self.mw.is_programmatically_changing_text = False 
        self.mw.can_undo_paste = False
        if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.setEnabled(False)
        if hasattr(self.mw, 'statusBar'): self.mw.statusBar.showMessage("Last paste operation undone.", 2000)

    def trigger_reload_tag_mappings(self):
        """Trigger reload tag mappings."""
        log_info("Reload Tag Mappings action triggered.")
        
        if not self.mw.settings_manager: return
        plugin_config_path = self.mw.settings_manager._get_plugin_config_path()
        if not plugin_config_path or not Path(plugin_config_path).exists():
            QMessageBox.warning(self.mw, "Reload Error", "Plugin configuration file not found.")
            return

        try:
            with open(plugin_config_path, 'r', encoding='utf-8') as f:
                plugin_data = json.load(f)
            
            if "default_tag_mappings" in plugin_data:
                self.mw.default_tag_mappings = plugin_data["default_tag_mappings"]
                QMessageBox.information(self.mw, "Tag Mappings Reloaded", f"Default tag mappings reloaded from\n{Path(plugin_config_path).name}.")
                if self.mw.data_store.current_block_idx != -1:
                    if QMessageBox.question(self.mw, "Rescan Block", "Rescan the current block with the new mappings?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes) == QMessageBox.StandardButton.Yes:
                        self.mw.issue_scan_handler.rescan_issues_for_single_block(self.mw.data_store.current_block_idx, use_default_mappings=True)
            else:
                QMessageBox.warning(self.mw, "Reload Error", "'default_tag_mappings' not found in plugin config.")

        except Exception as e:
            QMessageBox.critical(self.mw, "Reload Error", f"Failed to read plugin config:\n{e}")

    def handle_add_tag_mapping_request(self, bracket_tag: str, curly_tag: str):
        """Handle add tag mapping request."""
        log_info(f"Received request to map '{bracket_tag}' -> '{curly_tag}'")
        if not bracket_tag or not curly_tag:
            QMessageBox.warning(self.mw, "Add Tag Mapping Error", "Both tags must be non-empty.")
            return
        if not hasattr(self.mw, 'default_tag_mappings'): self.mw.default_tag_mappings = {}
        if bracket_tag in self.mw.default_tag_mappings and self.mw.default_tag_mappings[bracket_tag] == curly_tag:
            QMessageBox.information(self.mw, "Add Tag Mapping", f"Mapping '{bracket_tag}' -> '{curly_tag}' already exists.")
            return
        reply = QMessageBox.StandardButton.Yes
        if bracket_tag in self.mw.default_tag_mappings:
            reply = QMessageBox.question(self.mw, "Confirm Overwrite",
                                         f"Tag '{bracket_tag}' is already mapped to '{self.mw.default_tag_mappings[bracket_tag]}'.\n"
                                         f"Overwrite with '{curly_tag}'?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.mw.default_tag_mappings[bracket_tag] = curly_tag
            log_info(f"Added/Updated mapping: {bracket_tag} -> {curly_tag}. Total mappings: {len(self.mw.default_tag_mappings)}")
            
            # Save mappings immediately to both project settings and project metadata
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.save_settings()
            if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                self.mw.project_manager.save_settings_to_project(self.mw)
                self.mw.project_manager.save()

            QMessageBox.information(self.mw, "Tag Mapping Added",
                                    f"Mapping '{bracket_tag}' -> '{curly_tag}' has been added/updated.\n"
                                    "This change has been saved to the project settings.")
            if self.mw.data_store.current_block_idx != -1:
                if QMessageBox.question(self.mw, "Rescan Block", "Rescan the current block with the new mapping now?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes) == QMessageBox.StandardButton.Yes:
                    self.mw.issue_scan_handler.rescan_issues_for_single_block(self.mw.data_store.current_block_idx, use_default_mappings=True)
        else: log_info("User cancelled overwrite or no action taken.")

    def show_shortcuts_help(self):
        """Show shortcuts help."""
        from components.help_dialog import show_shortcuts_dialog
        show_shortcuts_dialog(self.mw)

    # ------------------------------------------------------------------
    # BFN Font Editor integration
    # ------------------------------------------------------------------

    def open_script_markup_studio(self):
        """Open the Script Markup Studio dialog in modeless mode."""
        try:
            from PyQt6 import sip
        except ImportError:
            import sip

        if hasattr(self.mw, 'script_markup_studio_dialog') and self.mw.script_markup_studio_dialog:
            try:
                if not sip.isdeleted(self.mw.script_markup_studio_dialog):
                    self.mw.script_markup_studio_dialog.show()
                    self.mw.script_markup_studio_dialog.raise_()
                    self.mw.script_markup_studio_dialog.activateWindow()
                    return
            except (RuntimeError, TypeError, NameError):
                pass
            self.mw.script_markup_studio_dialog = None

        from ui.script_markup_studio_dialog import ScriptMarkupStudioDialog
        dialog = ScriptMarkupStudioDialog(self.mw)
        self.mw.script_markup_studio_dialog = dialog
        dialog.show()

    def open_mempalace_builder(self):
        """Open the MemePalace Context Builder dialog in modeless mode."""
        self.mempalace_actions.open_mempalace_builder()

    def open_mempalace_viewer(self):
        """Open the MemePalace Database Viewer dialog."""
        self.mempalace_actions.open_mempalace_viewer()

    def inspect_story_context(self):
        """Query and display visual context/timeline for the selected row from MemePalace without translating."""
        self.mempalace_actions.inspect_story_context()

    def open_bfn_editor_standalone(self):
        """Open BFN Font Editor as a standalone window (no archive binding)."""
        self.bfn_actions.open_bfn_editor_standalone()

    def open_bfn_editor_for_block(self, block_idx: int):
        """
        Open BFN Font Editor bound to a specific .bfn block (may be inside an archive).
        After saving, updates the archive in RAM and reloads font metrics.
        """
        self.bfn_actions.open_bfn_editor_for_block(block_idx)

    def _bfn_font_sync(self):
        """Reload font metrics in Picoripi after BFN editor saves changes."""
        self.bfn_actions._bfn_font_sync()

    def export_current_bmg_to_json(self):
        """Export the currently selected BMG file's text content to a JSON file for inspection."""
        self.bfn_actions.export_current_bmg_to_json()

    def import_current_bmg_from_json(self):
        """Import BMG text content from an exported JSON file into the currently selected block."""
        self.bfn_actions.import_current_bmg_from_json()

    def trigger_recalculate_widths(self):
        """Force recalculate text widths and issues for the entire project."""
        from PyQt6.QtWidgets import QMessageBox

        # 1. Reload font metrics
        sm = getattr(self.mw, 'settings_manager', None)
        if sm and hasattr(sm, 'load_all_font_maps'):
            sm.load_all_font_maps()
        elif hasattr(self.mw, 'font_map_loader'):
            self.mw.font_map_loader.load_all_font_maps()
            
        if hasattr(self.mw, 'string_settings_updater'):
            self.mw.string_settings_updater.update_font_combobox()
            
        def on_recalculate_completed():
            # 3. Refresh text views and preview cache
            ui = getattr(self.mw, 'ui_updater', None)
            if ui:
                if hasattr(ui, 'update_text_views'):
                    ui.update_text_views()
                if hasattr(ui, 'populate_strings_for_block'):
                    ui.populate_current_view(force=True)
                    
            QMessageBox.information(self.mw, "Recalculation Complete", "All text widths and issues have been successfully recalculated!")

        # 2. Perform full silent scan of all issues (which recalculates all widths) with force=True
        if hasattr(self.mw, 'issue_scan_handler'):
            self.mw.issue_scan_handler._perform_initial_silent_scan_all_issues(on_completed=on_recalculate_completed, force=True)
        else:
            on_recalculate_completed()

    def add_tag_alias(self, original_tag: str):
        """Add tag alias."""
        dialog = TagAliasDialog(self.mw, "Add Tag Alias", original_tag)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
            
        alias, width = dialog.get_data()
        if not alias:
            QMessageBox.warning(self.mw, "Invalid Alias", "Alias cannot be empty.")
            return
            
        if not hasattr(self.mw, 'default_tag_mappings'):
            self.mw.default_tag_mappings = {}
            
        if alias in self.mw.default_tag_mappings:
            QMessageBox.warning(
                self.mw, 
                "Duplicate Alias", 
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
            QMessageBox.warning(self.mw, "Invalid Alias", "Alias cannot be empty.")
            return
            
        if not hasattr(self.mw, 'default_tag_mappings'):
            self.mw.default_tag_mappings = {}
            
        if new_alias != alias and new_alias in self.mw.default_tag_mappings:
            QMessageBox.warning(
                self.mw, 
                "Duplicate Alias", 
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
            "Remove Tag Alias",
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
            self._progress_dialog.setWindowTitle("Tag Aliases")
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


    def run_external_script(self):
        """Asynchronously run configured external script (e.g. ROM builder / emulator)"""
        import subprocess
        from PyQt6.QtWidgets import QMessageBox
        from pathlib import Path
        import os

        script_path = getattr(self.mw, 'external_script_path', "").strip()
        if not script_path:
            QMessageBox.warning(
                self.mw,
                "Run External Tool/Script",
                "No script or tool path configured.\n\nPlease go to Project -> Settings -> Global and set the path."
            )
            return

        path_obj = Path(script_path)
        if not path_obj.exists() or not path_obj.is_file():
            QMessageBox.critical(
                self.mw,
                "Run External Tool/Script",
                f"Configured script path does not exist or is not a file:\n{script_path}"
            )
            return

        try:
            cwd = path_obj.parent.as_posix()
            if os.name == 'nt':
                # Launch via cmd.exe /k to open a new console window and keep it open
                # so the user can see the executed script and its output.
                cmd = ["cmd.exe", "/k", str(path_obj.resolve())]
                subprocess.Popen(
                    cmd,
                    cwd=cwd,
                    creationflags=0x00000010  # CREATE_NEW_CONSOLE
                )
            else:
                subprocess.Popen(
                    [str(path_obj.resolve())],
                    cwd=cwd
                )
            if hasattr(self.mw, 'statusBar') and self.mw.statusBar:
                self.mw.statusBar.showMessage(f"Started script: {path_obj.name}", 3000)
        except Exception as e:
            QMessageBox.critical(
                self.mw,
                "Run External Script Error",
                f"Failed to start script:\n{e}"
            )
