# handlers/app_action_handler.py
from pathlib import Path
from typing import Optional, Any, Union, List, Dict, Tuple
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QProgressDialog, QPlainTextEdit
from PyQt5.QtCore import Qt, QEvent
from .base_handler import BaseHandler
from utils.logging_utils import log_debug, log_info, log_error
from utils.utils import convert_dots_to_spaces_from_editor, calculate_string_width, remove_all_tags, ALL_TAGS_PATTERN, convert_spaces_to_dots_for_display
from core.tag_utils import apply_default_mappings_only
from core.data_manager import load_json_file, load_text_file
from plugins.base_game_rules import BaseGameRules
from core.state_manager import AppState
from .width_calculation_worker import WidthCalculationWorker
from components.report_dialog import LargeTextReportDialog

class AppActionHandler(BaseHandler):
    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any, game_rules_plugin: Optional[BaseGameRules]):
        super().__init__(main_window, data_processor, ui_updater)
        self.game_rules_plugin = game_rules_plugin

    def rescan_all_tags(self) -> None:
        if hasattr(self.mw, 'issue_scan_handler'):
            self.mw.issue_scan_handler.rescan_all_tags()

    def handle_close_event(self, event: QEvent) -> None:
        if self.mw.data_store.unsaved_changes:
            reply = QMessageBox.question(
                self.mw, 'Unsaved Changes',
                "Save changes before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Cancel
            )
            if reply == QMessageBox.Save:
                if not self.save_data_action(ask_confirmation=False):
                    event.ignore()
                    return
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
        event.accept()
            
    def _derive_edited_path(self, original_path: Union[str, Path]) -> Optional[str]:
        if not original_path:
            return None
        p = Path(original_path)
        return str(p.parent / f"{p.stem}_edited{p.suffix}")

    def open_file_dialog_action(self) -> None:
        log_info("Open File Dialog action triggered.")
        if self.mw.data_store.unsaved_changes:
            reply = QMessageBox.question(self.mw, 'Unsaved Changes', "Save before opening new file?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                if not self.save_data_action(ask_confirmation=True):
                    return
            elif reply == QMessageBox.Cancel:
                return
        
        start_dir = ""
        if self.mw.data_store.json_path:
            start_dir = str(Path(self.mw.data_store.json_path).parent)
            
        path, _ = QFileDialog.getOpenFileName(self.mw, "Open Original File", start_dir, "Supported Files (*.json *.txt);;JSON (*.json);;Text files (*.txt);;All (*)")
        if path:
            self.load_all_data_for_path(path, manually_set_edited_path=None, is_initial_load_from_settings=False)

    def open_changes_file_dialog_action(self) -> None:
        log_info("Open Changes File Dialog action triggered.")
        if not self.mw.data_store.json_path:
            QMessageBox.warning(self.mw, "Open Changes File", "Please open an original file first.")
            return
            
        start_dir = ""
        if self.mw.data_store.edited_json_path:
            start_dir = str(Path(self.mw.data_store.edited_json_path).parent)
        elif self.mw.data_store.json_path:
            start_dir = str(Path(self.mw.data_store.json_path).parent)
            
        path, _ = QFileDialog.getOpenFileName(self.mw, "Open Changes (Edited) File", start_dir, "Supported Files (*.json *.txt);;JSON Files (*.json);;Text Files (*.txt);;All Files (*)")
        if path:
            if self.mw.data_store.unsaved_changes:
                 reply = QMessageBox.question(self.mw, 'Unsaved Changes', "Loading a new changes file will discard current unsaved edits. Proceed?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                 if reply == QMessageBox.No:
                     return
            
            file_content = None
            error = None
            path_obj = Path(path)
            file_extension = path_obj.suffix.lower()
            
            if file_extension == '.json':
                file_content, error = load_json_file(path_obj)
            elif file_extension == '.txt':
                file_content, error = load_text_file(path_obj)
            else:
                error = f"Unsupported file type: {file_extension}"

            if error:
                QMessageBox.critical(self.mw, "Load Error", f"Failed to load selected changes file:\n{path}\n\n{error}")
                return
                
            if not self.mw.current_game_rules:
                QMessageBox.critical(self.mw, "Load Error", "No game plugin active to parse the file.")
                return

            # Backup authoritative original keys
            plugin_keys_backup = None
            if hasattr(self.mw.current_game_rules, 'original_keys'):
                plugin_keys_backup = list(self.mw.current_game_rules.original_keys)

            new_edited_data, _ = self.mw.current_game_rules.load_data_from_json_obj(file_content)
            
            # Restore authoritative original keys
            if plugin_keys_backup is not None and hasattr(self.mw.current_game_rules, 'original_keys'):
                self.mw.current_game_rules.original_keys = plugin_keys_backup
            
            self.mw.data_store.edited_json_path = path
            self.mw.data_store.edited_file_data = new_edited_data
            self.mw.data_store.edited_data = {}
            self.mw.data_store.unsaved_changes = False
            
            self._perform_initial_silent_scan_all_issues()
            self.ui_updater.update_title()
            self.ui_updater.update_statusbar_paths()
            self.ui_updater.populate_blocks()
            if self.mw.block_list_widget.count() > 0 and self.mw.data_store.current_block_idx == -1:
                 custom_tree = getattr(self.mw, 'block_list_widget', None)
                 if custom_tree and hasattr(custom_tree, 'select_block_by_index'):
                     custom_tree.select_block_by_index(0)
            else:
                 self.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx)

    def save_data_action(self, ask_confirmation: bool = True) -> bool:
        """
        High-level save action that delegates to the data processor.
        """
        log_info(f"AppActionHandler: save_data_action called (confirm={ask_confirmation})")
        return bool(self.data_processor.save_current_edits(ask_confirmation))

    def save_as_dialog_action(self) -> None:
        log_info("Save As Dialog action triggered.")
        if not self.mw.data_store.json_path:
            QMessageBox.warning(self.mw, "Save As Error", "No original file open.")
            return
            
        current_edited_path = self.mw.data_store.edited_json_path if self.mw.data_store.edited_json_path else self._derive_edited_path(self.mw.data_store.json_path)
        if not current_edited_path: 
            current_edited_path = str(Path(self.mw.data_store.json_path).parent / "untitled_edited.json") if self.mw.data_store.json_path else "untitled_edited.json"
            
        new_edited_path, _ = QFileDialog.getSaveFileName(self.mw, "Save Changes As...", current_edited_path, "Supported Files (*.json *.txt);;JSON (*.json);;All (*)")
        if new_edited_path:
            original_edited_path_backup = self.mw.data_store.edited_json_path
            self.mw.data_store.edited_json_path = new_edited_path
            save_success = self.save_data_action(ask_confirmation=False)
            if save_success:
                QMessageBox.information(self.mw, "Saved As", f"Changes saved to:\n{self.mw.data_store.edited_json_path}")
                self.ui_updater.update_statusbar_paths()
            else:
                QMessageBox.critical(self.mw, "Save As Error", f"Failed to save to:\n{self.mw.data_store.edited_json_path}")
                self.mw.data_store.edited_json_path = original_edited_path_backup
                self.ui_updater.update_statusbar_paths()

    def load_all_data_for_path(self, original_file_path: Union[str, Path], manually_set_edited_path: Optional[Union[str, Path]] = None, is_initial_load_from_settings: bool = False) -> None:
        log_info(f"Loading all data for path: '{original_file_path}'")
        
        with self.mw.state.enter(AppState.LOADING_DATA), self.mw.state.enter(AppState.PROGRAMMATIC_TEXT_CHANGE):
            if not self.mw.current_game_rules:
                QMessageBox.critical(self.mw, "Load Error", "Cannot load file: No game plugin is active.")
                return

            file_content = None
            error = None
            path_obj = Path(original_file_path)
            file_extension = path_obj.suffix.lower()

            if file_extension == '.json':
                file_content, error = load_json_file(path_obj, parent_widget=self.mw)
            elif file_extension == '.txt':
                file_content, error = load_text_file(path_obj, parent_widget=self.mw)
            else:
                error = f"Unsupported file type: {file_extension}"

            if error:
                self.mw.data_store.json_path = None
                self.mw.data_store.edited_json_path = None
                self.mw.data_store.data = []
                self.mw.data_store.edited_data = {}
                self.mw.data_store.edited_file_data = []
                self.mw.data_store.unsaved_changes = False
                self.ui_updater.update_title()
                self.ui_updater.update_statusbar_paths()
                self.ui_updater.populate_blocks()
                self.ui_updater.populate_strings_for_block(-1)
                QMessageBox.critical(self.mw, "Load Error", f"Failed to load: {original_file_path}\n{error}")
                return

            # Reset plugin state if it tracks keys (like pokemon_fr)
            if hasattr(self.mw.current_game_rules, 'original_keys'):
                self.mw.current_game_rules.original_keys = []
                
            data, block_names_from_plugin = self.mw.current_game_rules.load_data_from_json_obj(file_content)
            if not data and file_content is not None:
                QMessageBox.critical(self.mw, "Plugin Error", f"The active plugin '{self.mw.current_game_rules.get_display_name()}' could not parse the file:\n{original_file_path}")
                self.mw.data_store.json_path = None
                self.mw.data_store.data = []
                self.ui_updater.populate_blocks()
                self.ui_updater.populate_strings_for_block(-1)
                return

            self.mw.data_store.json_path = str(original_file_path)
            self.mw.data_store.data = data
            if block_names_from_plugin:
                self.mw.data_store.block_names.update(block_names_from_plugin)
            
            self.mw.data_store.edited_data = {}
            self.mw.data_store.unsaved_changes = False
            
            self.mw.data_store.edited_json_path = str(manually_set_edited_path) if manually_set_edited_path else self._derive_edited_path(self.mw.data_store.json_path)
            self.mw.data_store.edited_file_data = []
            if self.mw.data_store.edited_json_path and Path(self.mw.data_store.edited_json_path).exists():
                edited_file_content = None
                edit_error = None
                edited_path_obj = Path(self.mw.data_store.edited_json_path)
                edited_file_extension = edited_path_obj.suffix.lower()

                if edited_file_extension == '.json':
                    edited_file_content, edit_error = load_json_file(edited_path_obj, parent_widget=self.mw)
                elif edited_file_extension == '.txt':
                    edited_file_content, edit_error = load_text_file(edited_path_obj, parent_widget=self.mw)

                if edit_error:
                    QMessageBox.warning(self.mw, "Edited Load Warning", f"Could not load changes file: {self.mw.data_store.edited_json_path}\n{edit_error}")
                else:
                    plugin_keys_backup = None
                    if hasattr(self.mw.current_game_rules, 'original_keys'):
                        plugin_keys_backup = list(self.mw.current_game_rules.original_keys)
                        
                    edited_data_from_file, _ = self.mw.current_game_rules.load_data_from_json_obj(edited_file_content)
                    
                    if plugin_keys_backup is not None and hasattr(self.mw.current_game_rules, 'original_keys'):
                        self.mw.current_game_rules.original_keys = plugin_keys_backup
                        
                    self.mw.data_store.edited_file_data = edited_data_from_file
            
            self.mw.data_store.current_block_idx = -1
            self.mw.data_store.current_string_idx = -1
            
            if hasattr(self.mw, 'undo_paste_action') and self.mw.undo_paste_action:
                self.mw.can_undo_paste = False
                self.mw.undo_paste_action.setEnabled(False)
            if hasattr(self.mw, 'undo_manager') and self.mw.undo_manager:
                self.mw.undo_manager.clear()
            
            self.mw.block_list_widget.clear()
            if hasattr(self.mw, 'preview_text_edit') and self.mw.preview_text_edit:
                self.mw.preview_text_edit.clear()
            if hasattr(self.mw, 'original_text_edit') and self.mw.original_text_edit:
                self.mw.original_text_edit.clear()
            if hasattr(self.mw, 'edited_text_edit') and self.mw.edited_text_edit:
                self.mw.edited_text_edit.clear()

            self._perform_initial_silent_scan_all_issues()
            
            self.ui_updater.update_title()
            self.ui_updater.update_statusbar_paths()
            self.ui_updater.populate_blocks()

            # Restore UI State (Session)
            if original_file_path and hasattr(self.mw, 'settings_manager'):
                 state = self.mw.settings_manager.get_session_state(str(original_file_path))
                 if state:
                     self.mw.block_handler.restore_ui_state_from_dict(state)

    def reload_original_data_action(self) -> None:
        log_info("Reload Original action triggered.")
        if not self.mw.data_store.json_path:
            QMessageBox.information(self.mw, "Reload", "No file open.")
            return
            
        if self.mw.data_store.unsaved_changes:
            reply = QMessageBox.question(self.mw, 'Unsaved Changes', "Reloading will discard current unsaved edits in memory. Proceed?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return
                
        current_edited_path_before_reload = self.mw.data_store.edited_json_path
        self.load_all_data_for_path(self.mw.data_store.json_path, manually_set_edited_path=current_edited_path_before_reload, is_initial_load_from_settings=False)

    def calculate_widths_for_block_action(self, block_idx: int, category_name: Optional[str] = None) -> None:
        if block_idx < 0 or not self.mw.data_store.data or block_idx >= len(self.mw.data_store.data) or not isinstance(self.mw.data_store.data[block_idx], list):
            QMessageBox.warning(self.mw, "Calculate Widths Error", "Invalid block selected or no data.")
            return

        if not self.mw.font_map:
             QMessageBox.warning(self.mw, "Calculate Widths Error", "Font map is not loaded. Cannot calculate widths.")
             return
        if not self.game_rules_plugin:
            QMessageBox.warning(self.mw, "Calculate Widths Error", "Game rules plugin not loaded.")
            return

        # Handle "virtual block" (category) logic
        target_indices = None
        if category_name:
            pm = getattr(self.mw, 'project_manager', None)
            if pm and pm.project:
                block_map = getattr(self.mw, 'block_to_project_file_map', {})
                proj_b_idx = block_map.get(block_idx, block_idx)
                if proj_b_idx < len(pm.project.blocks):
                    block_obj = pm.project.blocks[proj_b_idx]
                    category = next((c for c in block_obj.categories if c.name == category_name), None)
                    if category:
                        target_indices = set(category.line_indices)

        all_strings_in_block = self.mw.data_store.data[block_idx]
        num_strings_total = len(all_strings_in_block)
        
        # If category is selected, use filtered count for progress bar
        num_to_process = len(target_indices) if target_indices is not None else num_strings_total

        if num_to_process == 0:
            QMessageBox.information(self.mw, "Calculate Line Widths", f"Target is empty.")
            return

        block_data = list(all_strings_in_block) # snapshot
        block_name = self.mw.data_store.block_names.get(str(block_idx), str(block_idx))
        if category_name:
            block_name = f"{block_name} ({category_name})"
        
        # Prepare settings snapshot for thread-safety
        mw_settings = {
            'string_metadata': self.mw.string_metadata.copy(),
            'line_width_warning_threshold_pixels': self.mw.line_width_warning_threshold_pixels,
            'game_dialog_max_width_pixels': self.mw.game_dialog_max_width_pixels
        }
        
        self.width_worker = WidthCalculationWorker(
            block_idx, block_data, block_name, 
            self.mw.helper, self.data_processor, 
            self.game_rules_plugin, mw_settings, 
            all_font_maps=getattr(self.mw, 'all_font_maps', {}),
            target_indices=target_indices, parent=self.mw
        )
        
        progress = QProgressDialog(f"Calculating widths for {block_name}...", "Cancel", 0, num_to_process, self.mw)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        
        def on_finished(result_dict):
            if progress.isVisible():
                progress.close()
            
            report_text = result_dict.get('report_text', '')
            entries = result_dict.get('entries', [])
            all_fonts_top_entries = result_dict.get('all_fonts_top_entries', {})

            if not report_text and not entries:
                QMessageBox.information(self.mw, "Calculate Line Widths", f"Block {block_name} processed. No lines found.")
                return

            if hasattr(self.mw, 'text_analysis_handler') and entries:
                # Restore visual report with charts as requested by user
                self.mw.text_analysis_handler.show_diagnostic_analysis(
                    entries, 
                    title=f"Block Width Analysis: {block_name}",
                    all_fonts_top_entries=all_fonts_top_entries
                )
            else:
                # Fallback to text report if analysis handler is not available
                report_title = (f"Widths for Block {block_name}\n"
                                f"(Editor Threshold: {mw_settings['line_width_warning_threshold_pixels']}px)\n"
                                f"(Game Dialog Limit: {mw_settings['game_dialog_max_width_pixels']}px)\n")
                full_report = report_title + "\n" + report_text
                
                from components.report_dialog import LargeTextReportDialog
                result_dialog = LargeTextReportDialog("Line Widths Report", full_report, self.mw)
                result_dialog.show()
        
        def on_cancelled():
            log_info("Width calculation worker cancelled.")
            progress.close()

        self.width_worker.progress_updated.connect(progress.setValue)
        self.width_worker.calculation_finished.connect(on_finished)
        self.width_worker.cancelled.connect(on_cancelled)
        progress.canceled.connect(self.width_worker.cancel)
        
        self.width_worker.start()
        progress.exec_()

    def _perform_initial_silent_scan_all_issues(self) -> None:
        if hasattr(self.mw, 'issue_scan_handler'):
            self.mw.issue_scan_handler._perform_initial_silent_scan_all_issues()

