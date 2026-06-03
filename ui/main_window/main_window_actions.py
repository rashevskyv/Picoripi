# /home/runner/work/RAG_project/RAG_project/handlers/main_window_actions.py
from __future__ import annotations
from typing import TYPE_CHECKING
from PyQt5.QtWidgets import QApplication, QMessageBox, QInputDialog, QProgressDialog, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox
from PyQt5.QtGui import QIntValidator
from PyQt5.QtCore import QThread, pyqtSignal
from utils.logging_utils import log_info, log_error
import copy
from pathlib import Path
import json
from ui.settings_dialog import SettingsDialog

FORCE_ALIAS_INFO = (
    "You have enabled the Force Alias option for this tag.\n\n"
    "This permanently replaces the dynamic name tag with its plain text translation in the final exported game.\n\n"
    "In the original game, character and horse names are customizable, but we lock them to 'Link' and 'Epona'. "
    "This allows us to grammatically inflect them properly in our Slavic translation (e.g. 'Лінку', 'Епоні') and handle addressing properly.\n\n"
    "The AI will translate the name (e.g., 'Link' to 'Лінку'), and it will remain as plain text in the exported game."
)

class TagAliasDialog(QDialog):
    def __init__(self, parent, title: str, original_tag: str, current_alias: str = "", current_width: int = None):
        self._is_initializing = True
        self.mw = parent
        from PyQt5.QtWidgets import QWidget
        parent_widget = parent if isinstance(parent, QWidget) else None
        super().__init__(parent_widget)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(380, 245)
        
        layout = QVBoxLayout(self)
        
        # Info about original tag
        self.info_label = QLabel(f"Original tag: <b>{original_tag}</b>", self)
        layout.addWidget(self.info_label)
        
        # Force alias checkbox
        self.force_checkbox = QCheckBox("Force alias (convert tag to permanent plain text)", self)
        self.force_checkbox.setToolTip(FORCE_ALIAS_INFO)
        layout.addWidget(self.force_checkbox)
        
        # Alias field
        layout.addWidget(QLabel("Alias name (will be enclosed in curly braces):", self))
        
        alias_input_layout = QHBoxLayout()
        self.prefix_label = QLabel("F:", self)
        self.prefix_label.setStyleSheet("font-weight: bold; font-size: 11pt; color: #808080;")
        self.alias_edit = QLineEdit(self)
        alias_input_layout.addWidget(self.prefix_label)
        alias_input_layout.addWidget(self.alias_edit)
        layout.addLayout(alias_input_layout)
        
        # Custom width field (defined first so it exists when setting initial checkbox state)
        self.width_label = QLabel("Custom width in pixels (leave empty for none):", self)
        layout.addWidget(self.width_label)
        self.width_edit = QLineEdit(self)
        self.width_edit.setValidator(QIntValidator(1, 9999, self))
        if current_width is not None:
            self.width_edit.setText(str(current_width))
        layout.addWidget(self.width_edit)
        
        # Connect signals
        self.force_checkbox.stateChanged.connect(self._on_force_changed)
        self.alias_edit.textChanged.connect(self._on_text_changed)
        self.alias_edit.returnPressed.connect(self.accept)
        self.width_edit.returnPressed.connect(self.accept)

        # Populate initial values (this will trigger stateChanged and set enabled states correctly)
        display_alias = current_alias
        if display_alias.startswith('{') and display_alias.endswith('}'):
            display_alias = display_alias[1:-1]
            
        if display_alias.lower().startswith('f:'):
            self.force_checkbox.setChecked(True)
            self.alias_edit.setText(display_alias[2:])
            self.prefix_label.setVisible(True)
        else:
            self.force_checkbox.setChecked(False)
            self.alias_edit.setText(display_alias)
            self.prefix_label.setVisible(False)
            
        # Run _on_force_changed initially to ensure correct disabled state of the width field
        self._on_force_changed(None)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK", self)
        self.ok_button.setDefault(True)
        self.ok_button.clicked.connect(self.accept)
        
        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addWidget(self.ok_button)
        buttons_layout.addWidget(self.cancel_button)
        layout.addLayout(buttons_layout)
        self._is_initializing = False
        
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, self.alias_edit.setFocus)

    def showEvent(self, event):
        super().showEvent(event)
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(50, self.alias_edit.setFocus)
        QTimer.singleShot(100, self.alias_edit.selectAll)

    def _on_force_changed(self, state):
        is_checked = self.force_checkbox.isChecked()
        self.prefix_label.setVisible(is_checked)
        
        # Disable custom width when Force Alias is enabled
        self.width_label.setEnabled(not is_checked)
        self.width_edit.setEnabled(not is_checked)
        
        # Remove F: from text field if user checked the box
        text = self.alias_edit.text().strip()
        if is_checked and text.lower().startswith('f:'):
            self.alias_edit.setText(text[2:])
            
        # Show informational popup if manually checked by the user
        if is_checked and not self._is_initializing:
            if getattr(self.mw, 'show_force_alias_warning', True):
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Force Alias Enabled")
                msg_box.setText(FORCE_ALIAS_INFO)
                msg_box.setIcon(QMessageBox.Information)
                
                cb = QCheckBox("Don't show next time", msg_box)
                msg_box.setCheckBox(cb)
                
                msg_box.exec_()
                
                if cb.isChecked():
                    self.mw.show_force_alias_warning = False
                    if hasattr(self.mw, 'settings_manager') and self.mw.settings_manager:
                        self.mw.settings_manager.save_settings()

    def _on_text_changed(self, text):
        # If Force Alias is enabled, prevent user from typing the 'F:' prefix manually inside the text field
        if self.force_checkbox.isChecked() and text.lower().startswith('f:'):
            self.alias_edit.setText(text[2:])

    def get_data(self) -> tuple[str, int | None]:
        alias = self.alias_edit.text().strip()
        alias = alias.lstrip('{').rstrip('}')
        if alias.lower().startswith('f:'):
            alias = alias[2:]
            
        if alias:
            if self.force_checkbox.isChecked():
                alias = f"{{F:{alias}}}"
            else:
                alias = f"{{{alias}}}"
        
        width_str = self.width_edit.text().strip()
        width = int(width_str) if width_str.isdigit() else None
        return alias, width


class AliasUpdateWorker(QThread):
    finished_signal = pyqtSignal(object, object, object)

    def __init__(self, edited_data_copy: dict, data_copy: list, edited_file_data_copy: list, alias: str, original_tag: str):
        super().__init__()
        self.edited_data_copy = edited_data_copy
        self.data_copy = data_copy
        self.edited_file_data_copy = edited_file_data_copy
        self.alias = alias
        self.original_tag = original_tag

    def run(self):
        # 1. Update edited_data
        for key, val in list(self.edited_data_copy.items()):
            if isinstance(val, str) and self.alias in val:
                self.edited_data_copy[key] = val.replace(self.alias, self.original_tag)
                
        # 2. Update data (original read-only text)
        if self.data_copy:
            for b_idx in range(len(self.data_copy)):
                if isinstance(self.data_copy[b_idx], list):
                    for s_idx in range(len(self.data_copy[b_idx])):
                        val = self.data_copy[b_idx][s_idx]
                        if isinstance(val, str) and self.alias in val:
                            self.data_copy[b_idx][s_idx] = val.replace(self.alias, self.original_tag)
                            
        # 3. Update edited_file_data
        if self.edited_file_data_copy:
            for b_idx in range(len(self.edited_file_data_copy)):
                if isinstance(self.edited_file_data_copy[b_idx], list):
                    for s_idx in range(len(self.edited_file_data_copy[b_idx])):
                        val = self.edited_file_data_copy[b_idx][s_idx]
                        if isinstance(val, str) and self.alias in val:
                            self.edited_file_data_copy[b_idx][s_idx] = val.replace(self.alias, self.original_tag)
                            
        self.finished_signal.emit(self.edited_data_copy, self.data_copy, self.edited_file_data_copy)


class MainWindowActions:
    def __init__(self, main_window: MainWindow):
        self.mw = main_window
        self.helper = main_window.helper
    
    def open_settings_dialog(self):
        log_info("Opening settings dialog...")
        
        # Save current rules values to compare later
        old_game_dialog_max_width = self.mw.game_dialog_max_width_pixels
        old_line_width_warning = self.mw.line_width_warning_threshold_pixels
        old_lines_per_page = getattr(self.mw, 'lines_per_page', 4)
        
        dialog = SettingsDialog(self.mw)
        
        if not dialog.exec_():
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
            self.mw.string_settings_updater.update_string_settings_panel()

            if hasattr(self.mw, 'text_operation_handler'):
                self.mw.text_operation_handler._update_preview_content()
                self.mw.text_operation_handler.text_edited()


    def trigger_save_action(self):
        log_info("Save action triggered.", category="file_ops")
        try:
            log_info(f"trigger_save_action details: has_app_action_handler={hasattr(self.mw, 'app_action_handler')}, "
                     f"unsaved_changes={getattr(self.mw.data_store, 'unsaved_changes', 'N/A')}, "
                     f"edited_keys_count={len(getattr(self.mw.data_store, 'edited_data', {}))}", category="file_ops")
            if self.mw.app_action_handler.save_data_action(ask_confirmation=True):
                 self.helper.rebuild_unsaved_block_indices()
                 log_info("Save action processed and unsaved block indices rebuilt.", category="file_ops")
            else:
                 log_info("Save action was cancelled or returned False.", category="file_ops")
        except Exception as save_err:
            log_error(f"CRITICAL ERROR in trigger_save_action: {save_err}", exc_info=True, category="file_ops")

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
                if QMessageBox.question(self.mw, "Rescan Block", "Rescan the current block with the new mapping now?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes:
                    self.mw.issue_scan_handler.rescan_issues_for_single_block(self.mw.data_store.current_block_idx, use_default_mappings=True)
        else: log_info("User cancelled overwrite or no action taken.")

    def show_shortcuts_help(self):
        from components.help_dialog import show_shortcuts_dialog
        show_shortcuts_dialog(self.mw)

    # ------------------------------------------------------------------
    # BFN Font Editor integration
    # ------------------------------------------------------------------

    def open_mempalace_builder(self):
        """Open the MemePalace Context Builder dialog in modeless mode."""
        try:
            from PyQt5 import sip
        except ImportError:
            import sip

        if hasattr(self.mw, 'mempalace_builder_dialog') and self.mw.mempalace_builder_dialog:
            try:
                if not sip.isdeleted(self.mw.mempalace_builder_dialog):
                    self.mw.mempalace_builder_dialog.show()
                    self.mw.mempalace_builder_dialog.raise_()
                    self.mw.mempalace_builder_dialog.activateWindow()
                    return
            except (RuntimeError, TypeError, NameError):
                pass
            self.mw.mempalace_builder_dialog = None

        from ui.mempalace_builder_dialog import MemePalaceBuilderDialog
        dialog = MemePalaceBuilderDialog(self.mw)
        self.mw.mempalace_builder_dialog = dialog
        dialog.show()

    def open_mempalace_viewer(self):
        """Open the MemePalace Database Viewer dialog."""
        try:
            from PyQt5 import sip
        except ImportError:
            import sip

        if hasattr(self.mw, 'mempalace_viewer_dialog') and self.mw.mempalace_viewer_dialog:
            try:
                if not sip.isdeleted(self.mw.mempalace_viewer_dialog):
                    self.mw.mempalace_viewer_dialog.show()
                    self.mw.mempalace_viewer_dialog.raise_()
                    self.mw.mempalace_viewer_dialog.activateWindow()
                    return
            except (RuntimeError, TypeError, NameError):
                pass
            self.mw.mempalace_viewer_dialog = None

        from ui.mempalace_viewer_dialog import MemePalaceViewerDialog
        dialog = MemePalaceViewerDialog(self.mw)
        self.mw.mempalace_viewer_dialog = dialog
        dialog.show()

    def inspect_story_context(self):
        """Query and display visual context/timeline for the selected row from MemePalace without translating."""
        import os
        from PyQt5.QtWidgets import QMessageBox
        
        # 1. Verify that a project is loaded and a row is selected
        ds = getattr(self.mw, 'data_store', None)
        if not ds or ds.current_block_idx == -1 or ds.current_string_idx == -1:
            QMessageBox.warning(self.mw, "Story Inspector", "Please select a dialogue row to inspect.")
            return

        # 2. Get the current original text and IDs
        block_idx = ds.current_block_idx
        s_idx = ds.current_string_idx
        text, _ = self.mw.data_processor.get_current_string_text(block_idx, s_idx)
        if not text:
            QMessageBox.warning(self.mw, "Story Inspector", "Selected row is empty.")
            return

        # 3. Retrieve context via AIPromptComposer
        composer = None
        if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
            composer = getattr(self.mw.translation_handler, 'prompt_composer', None)
            
        if not composer:
            # Fallback to create composer if not present
            from handlers.translation.ai_prompt_composer import AIPromptComposer
            class DummyHandler:
                def __init__(self, mw):
                    self.mw = mw
                    self.data_processor = mw.data_processor
                    self.ui_updater = mw.ui_updater
                    self._glossary_manager = None
                    if hasattr(mw, 'translation_handler') and mw.translation_handler:
                        self._glossary_manager = getattr(mw.translation_handler, '_glossary_manager', None)
                def __getattr__(self, name):
                    return getattr(self.mw, name)
            composer = AIPromptComposer(DummyHandler(self.mw))
            
        story_context = composer._fetch_story_context(block_idx, s_idx, text)

        # Fetch character relations for the detected speaker(s)
        relations_html = ""
        script_res = composer._find_speaker_in_script(block_idx, s_idx, text)
        if not isinstance(script_res, (tuple, list)) or len(script_res) != 2:
            script_res = None
        client = composer._get_mempalace_client()
        
        # Deduce script line number and find Chapter AI Summary
        chapter_html = ""
        line_num = None
        if script_res and len(script_res) == 2:
            _, lines_str = script_res
            if lines_str and lines_str != "NONE":
                try:
                    line_num = int(lines_str.split(",")[0].strip())
                except Exception:
                    pass

        if line_num and client:
            wing_name = composer._get_wing_name()
            chapter_info = client.get_chapter_for_line(wing_name, line_num)
            if chapter_info:
                ch_title = f"Chapter {chapter_info['num']}: {chapter_info['title']}"
                ai_sum = chapter_info.get("ai_summary")
                if ai_sum:
                    events_list = None
                    try:
                        cleaned_json = ai_sum.strip()
                        if cleaned_json.startswith("```"):
                            lines_json = cleaned_json.splitlines()
                            if lines_json[0].startswith("```"):
                                lines_json = lines_json[1:]
                            if lines_json and lines_json[-1].startswith("```"):
                                lines_json = lines_json[:-1]
                            cleaned_json = "\n".join(lines_json).strip()
                        events_list = json.loads(cleaned_json)
                    except Exception:
                        events_list = None

                    if isinstance(events_list, list):
                        current_event = None
                        for ev in events_list:
                            if isinstance(ev, dict) and "start_line" in ev and "end_line" in ev:
                                if ev["start_line"] <= line_num <= ev["end_line"]:
                                    current_event = ev
                                    break
                        
                        events_html = ""
                        if current_event:
                            events_html += (
                                f"<div style='background-color: #e6f4ea; border-left: 4px solid #137333; padding: 8px; margin-bottom: 8px; border-radius: 4px;'>"
                                f"<b style='color: #137333;'>👉 Поточна подія (Current Event): {current_event.get('event_name', 'Без назви')} (Lines {current_event['start_line']}-{current_event['end_line']})</b><br>"
                                f"<span style='color: #202124;'>{current_event.get('summary_ukrainian', '')}</span>"
                                f"</div>"
                            )
                        else:
                            events_html += (
                                f"<div style='background-color: #fce8e6; border-left: 4px solid #c5221f; padding: 8px; margin-bottom: 8px; border-radius: 4px;'>"
                                f"<span style='color: #c5221f;'>Поточну подію для рядка {line_num} не знайдено в хронології.</span>"
                                f"</div>"
                            )
                            
                        timeline_items = []
                        for ev in events_list:
                            if isinstance(ev, dict) and "event_name" in ev:
                                is_current = (current_event and ev.get('event_name') == current_event.get('event_name') and ev.get('start_line') == current_event.get('start_line'))
                                marker = "<b>👉 [Поточна подія]</b> " if is_current else "• "
                                style = " style='background-color: #e2f0d9; padding: 4px 6px; border-radius: 3px; font-weight: bold;'" if is_current else ""
                                timeline_items.append(
                                    f"<div{style} style='padding: 2px 4px; margin-bottom: 2px;'>"
                                    f"{marker}{ev['event_name']} (Lines {ev.get('start_line')}-{ev.get('end_line')}): "
                                    f"<span style='color: #5f6368;'>{ev.get('summary_ukrainian', '')}</span>"
                                    f"</div>"
                                )
                        
                        timeline_html = "<br><b>Хронологія розділу (Timeline):</b><br>" + "".join(timeline_items)
                        
                        chapter_html = (
                            f"<div style='background-color: #f0f4f9; border-left: 4px solid #0078d7; padding: 10px; margin-bottom: 12px; border-radius: 4px;'>"
                            f"<b style='color: #0078d7; font-size: 14px;'>{ch_title}</b><br><br>"
                            f"{events_html}"
                            f"{timeline_html}"
                            f"</div>"
                        )
                    else:
                        chapter_html = (
                            f"<div style='background-color: #f0f4f9; border-left: 4px solid #0078d7; padding: 10px; margin-bottom: 12px; border-radius: 4px;'>"
                            f"<b style='color: #0078d7;'>{ch_title} (AI Summary):</b><br>"
                            f"<span style='font-style: italic; color: #333333;'>{ai_sum.replace(chr(10), '<br>')}</span>"
                            f"</div>"
                        )
                else:
                    chapter_html = (
                        f"<div style='background-color: #f3f3f3; border-left: 4px solid #cccccc; padding: 10px; margin-bottom: 12px; border-radius: 4px;'>"
                        f"<b style='color: #666666;'>{ch_title}</b> (AI Summary not analyzed yet)<br>"
                        f"</div>"
                    )

        if script_res and client:
            raw_spk, _ = script_res
            if raw_spk and raw_spk != "NONE":
                detected_speakers = [s.strip().upper() for s in raw_spk.split(",") if s.strip()]
                wing_name = composer._get_wing_name()
                all_relations = client.get_relations(wing_name)
                relevant_relations = []
                for r in all_relations:
                    src = r.get("source", "").strip().upper()
                    tgt = r.get("target", "").strip().upper()
                    if any(spk in src or spk in tgt for spk in detected_speakers):
                        relevant_relations.append(r)
                
                if relevant_relations:
                    relations_html = "<b>Character Relations (Відношення персонажів):</b><br>"
                    for r in relevant_relations:
                        src_trans = composer._translate_speaker(r['source'])
                        tgt_trans = composer._translate_speaker(r['target'])
                        rel_trans = r['relation']
                        if rel_trans == "addresses_informally":
                            rel_display = "звертається на 'ти' до"
                        elif rel_trans == "addresses_respectfully":
                            rel_display = "звертається на 'ви' до"
                        else:
                            rel_display = rel_trans
                        relations_html += f"• {src_trans} ({r['source']}) — <i>{rel_display}</i> —> {tgt_trans} ({r['target']})<br>"
                    relations_html += "<hr>"

        # 4. Display result
        if story_context:
            # Beautiful HTML-formatted dialogue box
            formatted_text = story_context.replace("\n", "<br>")
            
            QMessageBox.information(
                self.mw, 
                "Story Context Inspector",
                f"<h3>Story Context for Row #{s_idx + 1}</h3>"
                f"<hr>"
                f"<div style='font-family: Arial, sans-serif; font-size: 13px; line-height: 1.4; color: #333333;'>"
                f"{chapter_html}"
                f"{relations_html}"
                f"{formatted_text}"
                f"</div>"
            )
        elif chapter_html:
            # We have no visual room context, but chapter timeline was successfully resolved
            import html
            raw_spk = "NONE"
            lines_str = "NONE"
            if script_res:
                raw_spk, lines_str = script_res
            
            trans_spk = composer._translate_speaker(raw_spk) if raw_spk != "NONE" else "NONE"
            spk_display = f"{trans_spk} ({raw_spk})" if raw_spk != "NONE" else "NONE"
            
            fallback_text = (
                f"<b>Location/Timeline Mapped from Script Chapter:</b><br>"
                f"• Speaker: <code>{spk_display}</code><br>"
                f"• Script Line: <code>{lines_str}</code><br>"
                f"• Timeline: Mapped from script sequence (No detailed visual context generated)."
            )
            
            QMessageBox.information(
                self.mw,
                "Story Context Inspector",
                f"<h3>Story Context for Row #{s_idx + 1}</h3>"
                f"<hr>"
                f"<div style='font-family: Arial, sans-serif; font-size: 13px; line-height: 1.4; color: #333333;'>"
                f"{chapter_html}"
                f"{relations_html}"
                f"{fallback_text}"
                f"</div>"
            )
        else:
            # Gather debug variables
            db_path = client.db_path if client else "None"
            wing_name = composer._get_wing_name()
            block_label = composer._get_block_label(block_idx)
            bmg_id = f"{block_label}_Str_{s_idx}"
            
            script_info = ""
            if script_res:
                raw_spk, lines_str = script_res
                trans_spk = composer._translate_speaker(raw_spk) if raw_spk != "NONE" else "NONE"
                spk_display = f"{trans_spk} ({raw_spk})" if raw_spk != "NONE" else "NONE"
                script_info = (
                    f"<b>[Disk Script Fallback]</b><br>"
                    f"• Speaker: <code>{spk_display}</code><br>"
                    f"• Script Line: <code>{lines_str}</code><br><br>"
                )
            
            debug_info = (
                f"<b>[DEBUG INFO]</b><br>"
                f"• Client DB Path: <code>{db_path}</code><br>"
                f"• Wing Name: <code>{wing_name}</code><br>"
                f"• Block Label: <code>{block_label}</code><br>"
                f"• BMG ID Searched: <code>{bmg_id}</code><br>"
                f"• SQLite File Exists: <code>{os.path.exists(db_path) if db_path != 'None' else 'False'}</code>"
            )
            
            QMessageBox.information(
                self.mw,
                "Story Context Inspector",
                f"<h3>No Context Found</h3>"
                f"<hr>"
                f"<div style='font-family: Arial, sans-serif; font-size: 13px; line-height: 1.4; color: #333333;'>"
                f"{chapter_html}"
                f"{relations_html}"
                f"{script_info}"
                f"{debug_info}<br><br>"
                f"Please ensure you selected the correct file/block and active game plugin!"
                f"</div>"
            )


    def open_bfn_editor_standalone(self):
        """Open BFN Font Editor as a standalone window (no archive binding)."""
        from tools.bfn_editor import BfnEditorWindow
        if not hasattr(self.mw, '_bfn_editor_window') or self.mw._bfn_editor_window is None:
            self.mw._bfn_editor_window = BfnEditorWindow(parent=self.mw)
        
        editor = self.mw._bfn_editor_window
        
        # Initialize simulation input with current text from Picoripi translation editor
        current_text = ""
        ds = getattr(self.mw, 'data_store', None)
        if ds and ds.current_block_idx != -1 and ds.current_string_idx != -1:
            current_text, _ = self.mw.data_processor.get_current_string_text(ds.current_block_idx, ds.current_string_idx)
            if current_text is None:
                current_text = ""
        if current_text:
            sync_enabled = True
            if hasattr(editor, 'chk_sync_sim_text'):
                sync_enabled = editor.chk_sync_sim_text.isChecked()
            if sync_enabled:
                editor.sim_input.setPlainText(current_text)
            
        editor.show()
        editor.raise_()
        editor.activateWindow()

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
        self.mw._bfn_editor_window = editor

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

        # Initialize simulation input with current text from Picoripi translation editor
        current_text = ""
        ds = getattr(self.mw, 'data_store', None)
        if ds and ds.current_block_idx != -1 and ds.current_string_idx != -1:
            current_text, _ = self.mw.data_processor.get_current_string_text(ds.current_block_idx, ds.current_string_idx)
            if current_text is None:
                current_text = ""
        if current_text:
            sync_enabled = True
            if hasattr(editor, 'chk_sync_sim_text'):
                sync_enabled = editor.chk_sync_sim_text.isChecked()
            if sync_enabled:
                editor.sim_input.setPlainText(current_text)

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
        
        # Trigger UI refresh of text editors and preview widget
        ui = getattr(self.mw, 'ui_updater', None)
        if ui:
            if hasattr(ui, 'update_text_views'):
                ui.update_text_views()
            if hasattr(ui, 'populate_strings_for_block'):
                # Force refresh preview text lines cache
                ui.populate_strings_for_block(self.mw.data_store.current_block_idx, category_name=self.mw.data_store.current_category_name, force=True)
        
        # Proactively trigger silent project-wide recalculation after changes in glyphs
        if hasattr(self.mw, 'issue_scan_handler'):
            self.mw.issue_scan_handler._perform_initial_silent_scan_all_issues()
            
        log_info("BFN Editor: font metrics reloaded and silent full project recalculation started.")

    def export_current_bmg_to_json(self):
        """Export the currently selected BMG file's text content to a JSON file for inspection."""
        import json
        from pathlib import Path
        from PyQt5.QtWidgets import QMessageBox, QFileDialog
        from bmg_tool import BMGFile

        pm = getattr(self.mw, 'project_manager', None)
        ds = getattr(self.mw, 'data_store', None)

        if not pm or not pm.project or ds is None or ds.current_block_idx == -1:
            QMessageBox.warning(self.mw, 'Export BMG', 'No block selected. Please select a BMG block first.')
            return

        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(ds.current_block_idx)
        if proj_b_idx is None or proj_b_idx >= len(pm.project.blocks):
            QMessageBox.warning(self.mw, 'Export BMG', 'Cannot resolve the selected block to a project file.')
            return

        block = pm.project.blocks[proj_b_idx]
        is_archive = block.metadata.get('is_archive_member', False)

        # Determine which BMGs to export: translation first, then source
        def _read_bmg_bytes(is_translation: bool):
            if is_archive:
                arc_rel = block.metadata.get('archive_rel_path', '')
                inner = block.metadata.get('archive_file_name', '')
                try:
                    container = pm.get_archive_container(arc_rel, is_translation=is_translation)
                    return container.read_file(inner), f"{arc_rel}/{inner}"
                except Exception:
                    return None, ''
            else:
                path = pm.get_absolute_path(
                    block.translation_file if is_translation else block.source_file,
                    is_translation=is_translation
                )
                if Path(path).exists() and path.lower().endswith('.bmg'):
                    return Path(path).read_bytes(), path
                return None, ''

        # Try translation first, fallback to source
        raw_trans, label_trans = _read_bmg_bytes(is_translation=True)
        raw_src, label_src = _read_bmg_bytes(is_translation=False)

        if raw_trans is None and raw_src is None:
            QMessageBox.warning(self.mw, 'Export BMG',
                'The selected block does not appear to reference a BMG file.')
            return

        def bmg_bytes_to_dict(raw: bytes, label: str) -> dict:
            bmg = BMGFile()
            bmg.load(raw)
            messages = []
            for msg in bmg.messages:
                d = msg.to_dict()
                d['id'] = getattr(msg, 'id', None)
                messages.append(d)
            return {
                'source': label,
                'encoding': bmg.encoding,
                'endianness': 'big' if bmg.endianness == '>' else 'little',
                'file_id': bmg.id,
                'section_order': bmg.section_order,
                'message_count': len(messages),
                'messages': messages
            }

        export_data = {}
        if raw_src is not None:
            export_data['source'] = bmg_bytes_to_dict(raw_src, label_src)
        if raw_trans is not None:
            export_data['translation'] = bmg_bytes_to_dict(raw_trans, label_trans)

        # Ask where to save
        block_name = block.name.replace('/', '_').replace('\\', '_')
        default_name = f"{block_name}_bmg_export.json"
        save_path, _ = QFileDialog.getSaveFileName(
            self.mw,
            'Export BMG to JSON',
            str(Path.home() / default_name),
            'JSON Files (*.json);;All Files (*)'
        )
        if not save_path:
            return

        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(
                self.mw, 'Export BMG',
                f'Successfully exported BMG content to:\n{save_path}\n\n'
                f'Messages: {export_data.get("source", export_data.get("translation", {})).get("message_count", 0)}'
            )
        except Exception as e:
            QMessageBox.critical(self.mw, 'Export BMG', f'Failed to save JSON:\n{e}')

    def import_current_bmg_from_json(self):
        """Import BMG text content from an exported JSON file into the currently selected block."""
        import json
        from pathlib import Path
        from PyQt5.QtWidgets import QMessageBox, QFileDialog
        from bmg_tool import BMGMessage

        pm = getattr(self.mw, 'project_manager', None)
        ds = getattr(self.mw, 'data_store', None)

        if not pm or not pm.project or ds is None or ds.current_block_idx == -1:
            QMessageBox.warning(self.mw, 'Import BMG', 'No block selected. Please select a BMG block first.')
            return

        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(ds.current_block_idx)
        if proj_b_idx is None or proj_b_idx >= len(pm.project.blocks):
            QMessageBox.warning(self.mw, 'Import BMG', 'Cannot resolve the selected block to a project file.')
            return

        block = pm.project.blocks[proj_b_idx]

        # Choose the JSON file to import
        load_path, _ = QFileDialog.getOpenFileName(
            self.mw,
            'Import BMG from JSON',
            str(Path.home()),
            'JSON Files (*.json);;All Files (*)'
        )
        if not load_path:
            return

        try:
            with open(load_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self.mw, 'Import BMG', f'Failed to load JSON file:\n{e}')
            return

        # Determine which dictionary to read (translation or source)
        bmg_dict = None
        if 'translation' in import_data and 'source' in import_data:
            from PyQt5.QtWidgets import QInputDialog
            items = ["Translation (Current Translation)", "Source (English Original)"]
            item, ok = QInputDialog.getItem(
                self.mw, 
                "Select Data to Import", 
                "The JSON file contains both Source and Translation sections.\nWhich one would you like to import?", 
                items, 
                0, 
                False
            )
            if not ok:
                return
            if item == "Translation (Current Translation)":
                bmg_dict = import_data['translation']
            else:
                bmg_dict = import_data['source']
        elif 'translation' in import_data:
            bmg_dict = import_data['translation']
        elif 'source' in import_data:
            bmg_dict = import_data['source']
        elif 'messages' in import_data:
            bmg_dict = import_data
        else:
            QMessageBox.warning(self.mw, 'Import BMG', 'The selected JSON does not contain valid BMG export data.')
            return

        messages_list = bmg_dict.get('messages', [])
        if not messages_list:
            QMessageBox.warning(self.mw, 'Import BMG', 'No messages found in the JSON file.')
            return

        # Confirm with the user
        reply = QMessageBox.question(
            self.mw,
            'Confirm Import',
            f'This will replace all strings in the current block "{block.name}" with the {len(messages_list)} strings from the JSON file.\n'
            'Do you want to proceed?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        # Reconstruct the list of strings for the editor
        imported_strings = []
        try:
            for m_dict in messages_list:
                bmg_msg = BMGMessage.from_dict(m_dict)
                editor_text = self.mw.current_game_rules.msg_to_editor_text(bmg_msg)
                imported_strings.append(editor_text)
        except Exception as e:
            QMessageBox.critical(self.mw, 'Import BMG', f'Failed to parse messages from JSON:\n{e}')
            return

        # Remove any existing memory edits for this block first
        keys_to_remove = [k for k in ds.edited_data.keys() if isinstance(k, tuple) and k[0] == ds.current_block_idx]
        for key in keys_to_remove:
            del ds.edited_data[key]

        # Batch insert into edited_data (directly store all strings to ensure 100% clean overwrite)
        for string_idx, text in enumerate(imported_strings):
            ds.edited_data[(ds.current_block_idx, string_idx)] = text

        ds.unsaved_changes = bool(ds.edited_data)
        ds.unsaved_block_indices.add(ds.current_block_idx)

        # Trigger UI refresh
        self.helper.rebuild_unsaved_block_indices()
        
        ui = getattr(self.mw, 'ui_updater', None)
        if ui:
            if hasattr(ui, 'update_title'):
                ui.update_title()
            if hasattr(ui, 'populate_strings_for_block'):
                ui.populate_strings_for_block(ds.current_block_idx, force=True)
            if hasattr(ui, 'update_text_views'):
                ui.update_text_views()

        # Rescan issues for this block
        if hasattr(self.mw, 'issue_scan_handler'):
            self.mw.issue_scan_handler.rescan_issues_for_single_block(ds.current_block_idx)

        QMessageBox.information(
            self.mw,
            'Import BMG',
            f'Successfully imported {len(imported_strings)} strings from JSON into block "{block.name}".\n'
            'The changes are loaded in the editor. Click "Save" to save them to the translation file.'
        )

    def trigger_recalculate_widths(self):
        """Force recalculate text widths and issues for the entire project."""
        from PyQt5.QtWidgets import QMessageBox

        
        # 1. Reload font metrics
        sm = getattr(self.mw, 'settings_manager', None)
        if sm and hasattr(sm, 'load_all_font_maps'):
            sm.load_all_font_maps()
        elif hasattr(self.mw, 'font_map_loader'):
            self.mw.font_map_loader.load_all_font_maps()
            
        if hasattr(self.mw, 'string_settings_updater'):
            self.mw.string_settings_updater.update_font_combobox()
            
        # 2. Perform full silent scan of all issues (which recalculates all widths)
        if hasattr(self.mw, 'issue_scan_handler'):
            self.mw.issue_scan_handler._perform_initial_silent_scan_all_issues()
            
        # 3. Refresh text views and preview cache
        ui = getattr(self.mw, 'ui_updater', None)
        if ui:
            if hasattr(ui, 'update_text_views'):
                ui.update_text_views()
            if hasattr(ui, 'populate_strings_for_block'):
                ui.populate_strings_for_block(self.mw.data_store.current_block_idx, category_name=self.mw.data_store.current_category_name, force=True)
                
        QMessageBox.information(self.mw, "Recalculation Complete", "All text widths and issues have been successfully recalculated!")

    def add_tag_alias(self, original_tag: str):
        dialog = TagAliasDialog(self.mw, "Add Tag Alias", original_tag)
        if dialog.exec_() != QDialog.Accepted:
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
        current_width = None
        if hasattr(self.mw, 'font_map_overrides') and self.mw.font_map_overrides:
            current_width = self.mw.font_map_overrides.get(alias, {}).get('width')
            
        dialog = TagAliasDialog(self.mw, "Edit Tag Alias", original_tag, current_alias=alias, current_width=current_width)
        if dialog.exec_() != QDialog.Accepted:
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
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.save_settings()
                
            # Trigger recalculation of widths
            if hasattr(self.mw, 'issue_scan_handler'):
                self.mw.issue_scan_handler._perform_initial_silent_scan_all_issues()
                
            self._refresh_editors_after_alias_change()
            
        self._update_aliases_in_edited_data(alias, original_tag, on_complete)

    def remove_tag_alias(self, alias: str, original_tag: str):
        reply = QMessageBox.question(
            self.mw,
            "Remove Tag Alias",
            f"Are you sure you want to remove the alias '{alias}' for tag '{original_tag}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
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
        is_test = "Mock" in str(type(self.mw)) or not isinstance(QApplication.instance(), QApplication)
        
        # High-performance shallow copies of the block string lists
        edited_data_copy = dict(ds.edited_data) if has_edited else {}
        data_copy = [list(block) for block in ds.data] if (has_data and isinstance(ds.data, list)) else []
        edited_file_data_copy = [list(block) for block in ds.edited_file_data] if (has_edited_file and isinstance(ds.edited_file_data, list)) else []
        
        # Create worker
        self._alias_worker = AliasUpdateWorker(edited_data_copy, data_copy, edited_file_data_copy, alias, original_tag)
        
        def on_worker_finished(updated_edited_data, updated_data, updated_edited_file_data):
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
            self._progress_dialog.setWindowModality(2) # Qt.WindowModal
            self._progress_dialog.setCancelButton(None) # Remove cancel button to ensure integrity
            self._progress_dialog.show()
            
            # Connect progress dialog close to worker finish
            self._alias_worker.finished_signal.connect(self._progress_dialog.close)
            
            self._alias_worker.start()


    def _refresh_editors_after_alias_change(self):
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
        from PyQt5.QtWidgets import QMessageBox
        
        script_path = getattr(self.mw, 'external_script_path', "").strip()
        if not script_path:
            QMessageBox.warning(
                self.mw,
                "Run External Script",
                "No external script configured.\nPlease configure it in Settings -> Global tab."
            )
            return

        path_obj = Path(script_path)
        if not path_obj.exists():
            QMessageBox.critical(
                self.mw,
                "Run External Script",
                f"Configured script path does not exist:\n{script_path}"
            )
            return

        try:
            cwd = path_obj.parent.as_posix()
            
            import os
            creationflags = 0
            if os.name == 'nt':
                creationflags = 0x00000010  # CREATE_NEW_CONSOLE

            is_batch = path_obj.suffix.lower() in ('.bat', '.cmd')
            
            subprocess.Popen(
                [str(path_obj.resolve())] if not is_batch else str(path_obj.resolve()),
                cwd=cwd,
                shell=is_batch,
                creationflags=creationflags
            )
            
            if hasattr(self.mw, 'statusBar') and self.mw.statusBar:
                self.mw.statusBar.showMessage(f"Started script: {path_obj.name}", 3000)
                
        except Exception as e:
            QMessageBox.critical(
                self.mw,
                "Run External Script Error",
                f"Failed to start script:\n{e}"
            )

                

