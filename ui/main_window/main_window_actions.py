# --- START OF FILE ui/main_window/main_window_actions.py ---
# --- START OF FILE main_window_actions.py ---
# /home/runner/work/RAG_project/RAG_project/handlers/main_window_actions.py
from __future__ import annotations
from typing import TYPE_CHECKING
from PyQt5.QtWidgets import QApplication, QMessageBox
from utils.logging_utils import log_info
import copy
from pathlib import Path
import json
from ui.settings_dialog import SettingsDialog

if TYPE_CHECKING:
    from main import MainWindow

class MainWindowActions:
    def __init__(self, main_window: MainWindow):
        self.mw = main_window
        self.helper = main_window.helper
    
    def open_settings_dialog(self):
        log_info("Opening settings dialog...")
        
        dialog = SettingsDialog(self.mw)
        
        if not dialog.exec_():
            log_info("Settings dialog cancelled.")
            return

        new_settings = dialog.get_settings()
        
        font_file_changed = new_settings.get('default_font_file') != self.mw.default_font_file
        
        spellchecker_lang_changed = new_settings.get('spellchecker_language') != self.mw.spellchecker_manager.language
        spellchecker_enabled_changed = new_settings.get('spellchecker_enabled') != self.mw.spellchecker_manager.enabled

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

            self.mw.settings_manager._save_global_settings()
            
            self.mw.is_restart_in_progress = True
            self.helper.restart_application()
        else:
            log_info("Settings changed without restart. Applying settings.")
            
            initial_paths = (self.mw.data_store.json_path, self.mw.data_store.edited_json_path)
            restore_session_before = self.mw.restore_unsaved_on_startup

            for key, value in new_settings.items():
                setattr(self.mw, key, value)
            
            restore_session_after = self.mw.restore_unsaved_on_startup
            
            if restore_session_before and not restore_session_after and self.mw.data_store.unsaved_changes:
                reply = QMessageBox.question(self.mw, "Discard Unsaved Changes?",
                                             "You have disabled session restore.\nDo you want to discard the current unsaved changes now?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.mw.data_store.edited_data.clear()
                    self.mw.data_store.unsaved_changes = False
                    self.mw.helper.rebuild_unsaved_block_indices()
                    if hasattr(self.mw, 'ui_updater'):
                        self.mw.ui_updater.update_title()
                        self.mw.ui_updater.populate_blocks()
                        self.mw.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx)
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


    def trigger_save_action(self):
        log_info("Save action triggered.")
        if self.mw.app_action_handler.save_data_action(ask_confirmation=True):
             self.helper.rebuild_unsaved_block_indices()

    def trigger_revert_action(self):
        log_info("Revert changes file action triggered.")
        if self.mw.data_processor.revert_edited_file_to_original():
            log_info("Revert successful.")
            self.helper.rebuild_unsaved_block_indices()
            if hasattr(self.mw.ui_updater, 'clear_all_problem_block_highlights_and_text'):
                self.mw.ui_updater.clear_all_problem_block_highlights_and_text()
        else: log_info("Revert was cancelled or failed.")

    def trigger_undo_paste_action(self):
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
            self.mw.preview_updater.update_preview_for_block(self.mw.data_store.current_block_idx)
        elif hasattr(self.mw.ui_updater, 'populate_strings_for_block'):
            self.mw.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx)
        
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
                    if QMessageBox.question(self.mw, "Rescan Block", "Rescan the current block with the new mappings?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes:
                        self.mw.issue_scan_handler.rescan_issues_for_single_block(self.mw.data_store.current_block_idx, use_default_mappings=True)
            else:
                QMessageBox.warning(self.mw, "Reload Error", "'default_tag_mappings' not found in plugin config.")

        except Exception as e:
            QMessageBox.critical(self.mw, "Reload Error", f"Failed to read plugin config:\n{e}")

    def handle_add_tag_mapping_request(self, bracket_tag: str, curly_tag: str):
        log_info(f"Received request to map '{bracket_tag}' -> '{curly_tag}'")
        if not bracket_tag or not curly_tag:
            QMessageBox.warning(self.mw, "Add Tag Mapping Error", "Both tags must be non-empty.")
            return
        if not hasattr(self.mw, 'default_tag_mappings'): self.mw.default_tag_mappings = {}
        if bracket_tag in self.mw.default_tag_mappings and self.mw.default_tag_mappings[bracket_tag] == curly_tag:
            QMessageBox.information(self.mw, "Add Tag Mapping", f"Mapping '{bracket_tag}' -> '{curly_tag}' already exists.")
            return
        reply = QMessageBox.Yes
        if bracket_tag in self.mw.default_tag_mappings:
            reply = QMessageBox.question(self.mw, "Confirm Overwrite",
                                         f"Tag '{bracket_tag}' is already mapped to '{self.mw.default_tag_mappings[bracket_tag]}'.\n"
                                         f"Overwrite with '{curly_tag}'?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.mw.default_tag_mappings[bracket_tag] = curly_tag
            log_info(f"Added/Updated mapping: {bracket_tag} -> {curly_tag}. Total mappings: {len(self.mw.default_tag_mappings)}")
            QMessageBox.information(self.mw, "Tag Mapping Added",
                                    f"Mapping '{bracket_tag}' -> '{curly_tag}' has been added/updated.\n"
                                    "This change will be saved to the plugin's config file when settings are saved.")
            if self.mw.data_store.current_block_idx != -1:
                if QMessageBox.question(self.mw, "Rescan Block", "Rescan the current block with the new mapping now?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes:
                    self.mw.issue_scan_handler.rescan_issues_for_single_block(self.mw.data_store.current_block_idx, use_default_mappings=True)
        else: log_info("User cancelled overwrite or no action taken.")

    def show_shortcuts_help(self):
        from components.help_dialog import show_shortcuts_dialog
        show_shortcuts_dialog(self.mw)

    # ------------------------------------------------------------------
    # BFN Font Editor integration
    # ------------------------------------------------------------------

    def open_bfn_editor_standalone(self):
        """Open BFN Font Editor as a standalone window (no archive binding)."""
        from tools.bfn_editor import BfnEditorWindow
        if not hasattr(self.mw, '_bfn_editor_window') or self.mw._bfn_editor_window is None:
            self.mw._bfn_editor_window = BfnEditorWindow(parent=self.mw)
        self.mw._bfn_editor_window.show()
        self.mw._bfn_editor_window.raise_()
        self.mw._bfn_editor_window.activateWindow()

    def open_bfn_editor_for_block(self, block_idx: int):
        """
        Open BFN Font Editor bound to a specific .bfn block (may be inside an archive).
        After saving, updates the archive in RAM and reloads font metrics.
        """
        from tools.bfn_editor import BfnEditorWindow
        from PyQt5.QtWidgets import QMessageBox
        from pathlib import Path

        pm = getattr(self.mw, 'project_manager', None)
        ds = getattr(self.mw, 'data_store', None)
        if not pm or not pm.project:
            QMessageBox.warning(self.mw, 'BFN Editor', 'No project is open.')
            return

        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(block_idx, block_idx)
        if proj_b_idx >= len(pm.project.blocks):
            QMessageBox.warning(self.mw, 'BFN Editor', 'Could not resolve block file.')
            return

        block = pm.project.blocks[proj_b_idx]
        is_archive_member = block.metadata.get('is_archive_member', False)

        editor = BfnEditorWindow(parent=self.mw)

        if is_archive_member:
            archive_rel_path = block.metadata.get('archive_rel_path', '')
            inner_file_name = block.metadata.get('archive_file_name', '')
            try:
                container = pm.get_archive_container(archive_rel_path, is_translation=False)
                bfn_bytes = container.read_file(inner_file_name)
                
                # Collect all BFN files from the archive
                archive_files = {}
                for path in container.list_files():
                    if path.lower().endswith(".bfn"):
                        try:
                            archive_files[path] = container.read_file(path)
                        except Exception:
                            pass
            except Exception as e:
                QMessageBox.critical(self.mw, 'BFN Editor', f'Failed to read .bfn from archive:\n{e}')
                return

            def save_callback(filename: str, new_bytes: bytes):
                """Write updated BFN back into the in-memory archive and persist to disk."""
                try:
                    container.write_file(filename, new_bytes)
                    archive_abs = pm.get_absolute_path(archive_rel_path, is_translation=False)
                    Path(archive_abs).write_bytes(container.pack())
                    log_info(f"BFN Editor: saved '{filename}' back to archive '{archive_rel_path}'.")
                except Exception as ex:
                    QMessageBox.critical(editor, 'BFN Editor', f'Failed to write back to archive:\n{ex}')

            editor.open_from_bytes(
                bfn_bytes,
                bfn_name=inner_file_name,
                save_callback=save_callback,
                font_sync_callback=self._bfn_font_sync,
                archive_name=Path(archive_rel_path).name,
                archive_files=archive_files
            )
        else:
            # Regular file on disk
            src_abs = pm.get_absolute_path(block.source_file, is_translation=False)
            editor.open_from_path(src_abs, font_sync_callback=self._bfn_font_sync)

        editor.show()
        editor.raise_()

    def _bfn_font_sync(self):
        """Reload font metrics in Picoripi after BFN editor saves changes."""
        sm = getattr(self.mw, 'settings_manager', None)
        if sm and hasattr(sm, 'load_all_font_maps'):
            sm.load_all_font_maps()
        elif hasattr(self.mw, 'font_map_loader'):
            self.mw.font_map_loader.load_all_font_maps()
        if hasattr(self.mw, 'string_settings_updater'):
            self.mw.string_settings_updater.update_font_combobox()
        # Trigger UI refresh of text editors (width warnings)
        ui = getattr(self.mw, 'ui_updater', None)
        if ui and hasattr(ui, 'refresh_all_views'):
            ui.refresh_all_views()
        elif ui and hasattr(ui, 'update_text_views'):
            ui.update_text_views()
        log_info("BFN Editor: font metrics reloaded after save.")
