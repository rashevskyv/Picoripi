# handlers/app_action_handler.py
from pathlib import Path
from typing import Optional, Any, Union, List, Dict, Tuple
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QProgressDialog, QPlainTextEdit
from PyQt6.QtCore import Qt, QEvent, QThread, pyqtSignal
from .base_handler import BaseHandler
from utils.logging_utils import log_debug, log_info, log_error
from utils.utils import convert_dots_to_spaces_from_editor, calculate_string_width, remove_all_tags, ALL_TAGS_PATTERN, convert_spaces_to_dots_for_display
from core.tag_utils import apply_default_mappings_only
from core.data_manager import load_json_file, load_text_file
from plugins.base_game_rules import BaseGameRules
from core.state_manager import AppState
from .width_calculation_worker import WidthCalculationWorker
from components.report_dialog import LargeTextReportDialog
from components.toast import ToastNotification

class SaveWorker(QThread):
    """Save worker implementation."""
    progress_updated = pyqtSignal(int, int, str)  # current_step, total_steps, label_text
    finished_with_result = pyqtSignal(bool, list, list)  # success, warnings, errors

    def __init__(self, data_processor: Any, output_data_list: List[Any], edited_data_for_transaction: Optional[Dict[Tuple[int, int], str]] = None):
        """Initialize a new instance."""
        super().__init__()
        self.data_processor = data_processor
        self.output_data_list = output_data_list
        self.edited_data_for_transaction = edited_data_for_transaction

    def run(self):
        """Run."""
        try:
            success, warnings, errors = self.data_processor._perform_save_impl(
                self.output_data_list, 
                progress_callback=self.progress_updated.emit,
                edited_data_for_transaction=self.edited_data_for_transaction
            )
            self.finished_with_result.emit(success, warnings, errors)
        except Exception as e:
            log_error(f"SaveWorker execution failed: {e}", exc_info=True)
            self.finished_with_result.emit(False, [], [str(e)])


class AppActionHandler(BaseHandler):
    """Handler for app action operations."""
    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any, game_rules_plugin: Optional[BaseGameRules]):
        """Initialize a new instance."""
        super().__init__(main_window, data_processor, ui_updater)
        self.game_rules_plugin = game_rules_plugin

    def rescan_all_tags(self) -> None:
        """Rescan all tags."""
        if hasattr(self.mw, 'issue_scan_handler'):
            self.mw.issue_scan_handler.rescan_all_tags()

    def handle_close_event(self, event: QEvent) -> None:
        """Handle close event."""
        if getattr(self.mw, 'is_testing', False):
            event.accept()
            if self.mw.project_manager:
                self.mw.project_manager.cleanup_temp_dir()
            return

        event.accept()
        if event.isAccepted():
            if hasattr(self.data_processor, '_autosave_session'):
                self.data_processor._autosave_session(force=True)
            if self.mw.project_manager:
                self.mw.project_manager.cleanup_temp_dir()
            
    def _derive_edited_path(self, original_path: Union[str, Path]) -> Optional[str]:
        """Internal helper to derive edited path."""
        if not original_path:
            return None
        p = Path(original_path)
        return str(p.parent / f"{p.stem}_edited{p.suffix}")

    def open_file_dialog_action(self) -> None:
        """Open file dialog action."""
        log_info("Open File Dialog action triggered.")
        if self.mw.data_store.unsaved_changes:
            reply = QMessageBox.question(self.mw, 'Unsaved Changes', "Save before opening new file?", QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                def on_save_done(success: bool):
                    if success:
                        self._show_open_file_dialog()
                self.save_data_action(ask_confirmation=True, on_finished_callback=on_save_done)
            elif reply == QMessageBox.StandardButton.Discard:
                self._show_open_file_dialog()
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        else:
            self._show_open_file_dialog()

    def _show_open_file_dialog(self) -> None:
        """Internal helper to show open file dialog."""
        start_dir = ""
        if self.mw.data_store.json_path:
            start_dir = str(Path(self.mw.data_store.json_path).parent)
            
        path, _ = QFileDialog.getOpenFileName(self.mw, "Open Original File", start_dir, "Supported Files (*.json *.txt *.bmg *.bfn *.arc *.rarc);;BMG (*.bmg);;BFN (*.bfn);;ARC (*.arc *.rarc);;JSON (*.json);;Text files (*.txt);;All (*)")
        if path:
            self.load_all_data_for_path(path, manually_set_edited_path=None, is_initial_load_from_settings=False)

    def open_changes_file_dialog_action(self) -> None:
        """Open changes file dialog action."""
        log_info("Open Changes File Dialog action triggered.")
        if not self.mw.data_store.json_path:
            QMessageBox.warning(self.mw, "Open Changes File", "Please open an original file first.")
            return
            
        start_dir = ""
        if self.mw.data_store.edited_json_path:
            start_dir = str(Path(self.mw.data_store.edited_json_path).parent)
        elif self.mw.data_store.json_path:
            start_dir = str(Path(self.mw.data_store.json_path).parent)
            
        path, _ = QFileDialog.getOpenFileName(self.mw, "Open Changes (Edited) File", start_dir, "Supported Files (*.json *.txt *.bmg *.bfn *.arc *.rarc);;BMG Files (*.bmg);;BFN Files (*.bfn);;ARC Files (*.arc *.rarc);;JSON Files (*.json);;Text Files (*.txt);;All Files (*)")
        if path:
            if self.mw.data_store.unsaved_changes:
                 reply = QMessageBox.question(self.mw, 'Unsaved Changes', "Loading a new changes file will discard current unsaved edits. Proceed?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                 if reply == QMessageBox.StandardButton.No:
                     return
            
            file_content = None
            error = None
            path_obj = Path(path)
            file_extension = path_obj.suffix.lower()
            
            if file_extension == '.json':
                file_content, error = load_json_file(path_obj)
            elif file_extension == '.txt':
                file_content, error = load_text_file(path_obj)
            elif file_extension == '.bmg':
                try:
                    with path_obj.open('rb') as f:
                        file_content = f.read()
                except Exception as e:
                    error = f"Failed to read BMG file: {e}"
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
            if hasattr(self.ui_updater, 'preview_updater'):
                self.ui_updater.preview_updater.schedule_pre_cache()
            self.ui_updater.update_title()
            self.ui_updater.update_statusbar_paths()
            self.ui_updater.populate_blocks()
            if self.mw.block_list_widget.count() > 0 and self.mw.data_store.current_block_idx == -1:
                 custom_tree = getattr(self.mw, 'block_list_widget', None)
                 if custom_tree and hasattr(custom_tree, 'select_block_by_index'):
                     custom_tree.select_block_by_index(0)
            else:
                 self.ui_updater.populate_strings_for_block(self.mw.data_store.current_block_idx)

    def save_data_action(self, ask_confirmation: bool = True, on_finished_callback: Optional[Any] = None) -> bool:
        """
        High-level save action that delegates to the data processor.

        Returns:
            bool: In async mode, returns True if the saving process was successfully started
                  (or was not needed/skipped). In sync mode, returns True if saving to disk succeeded.
                  Returns False if saving failed or couldn't be started.
        """
        log_info(f"AppActionHandler: save_data_action called (confirm={ask_confirmation})", category="file_ops")
        try:
            res = bool(self.data_processor.save_current_edits(ask_confirmation, on_finished_callback=on_finished_callback))
            log_info(f"AppActionHandler: save_data_action finished with start result={res}", category="file_ops")
            return res
        except Exception as err:
            log_error(f"Error in AppActionHandler.save_data_action: {err}", exc_info=True, category="file_ops")
            if on_finished_callback:
                on_finished_callback(False)
            return False

    def perform_async_save_flow(self, output_data_list: List[Any], ask_confirmation: bool = True, on_finished_callback: Optional[Any] = None, edited_data_for_transaction: Optional[Dict[Tuple[int, int], str]] = None) -> None:
        """Perform async save flow."""
        log_info("Starting async save flow...", category="file_ops")
        
        # Block interface by setting SAVING_DATA state
        self.mw.state.set_active(AppState.SAVING_DATA, True)
        
        # Create SaveWorker
        self.save_worker = SaveWorker(self.data_processor, output_data_list, edited_data_for_transaction=edited_data_for_transaction)
        
        # Prepare QProgressDialog
        progress_dialog = QProgressDialog("Initializing save operation...", None, 0, 100, self.mw)
        progress_dialog.setWindowTitle("Saving Changes")
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setCancelButton(None)  # Disable cancel to prevent corrupted saves
        
        self.save_progress = progress_dialog
        
        def on_progress(current_step, total_steps, label_text):
            """Handle the progress event."""
            if total_steps > 0:
                val = int((current_step / total_steps) * 100)
                progress_dialog.setValue(val)
            progress_dialog.setLabelText(label_text)
            
        def on_finished(success, warnings, errors):
            """Handle the finished event."""
            progress_dialog.close()
            
            # Release interface state
            self.mw.state.set_active(AppState.SAVING_DATA, False)
            
            self.save_progress = None
            self.save_worker = None
            
            if not success:
                if errors:
                    QMessageBox.critical(self.mw, "Save Error", "Failed to save files:\n" + "\n".join(errors))
                else:
                    QMessageBox.critical(self.mw, "Save Error", "Failed to save files due to an unknown error.")
            
            if on_finished_callback:
                on_finished_callback(success, warnings, errors)

        self.save_worker.progress_updated.connect(on_progress)
        self.save_worker.finished_with_result.connect(on_finished)
        
        # Run worker thread
        self.save_worker.start()
        progress_dialog.show()

    def save_as_dialog_action(self) -> None:
        """Save as dialog action."""
        log_info("Save As Dialog action triggered.")
        if not self.mw.data_store.json_path:
            QMessageBox.warning(self.mw, "Save As Error", "No original file open.")
            return
            
        current_edited_path = self.mw.data_store.edited_json_path if self.mw.data_store.edited_json_path else self._derive_edited_path(self.mw.data_store.json_path)
        if not current_edited_path: 
            current_edited_path = str(Path(self.mw.data_store.json_path).parent / "untitled_edited.json") if self.mw.data_store.json_path else "untitled_edited.json"
            
        new_edited_path, _ = QFileDialog.getSaveFileName(self.mw, "Save Changes As...", current_edited_path, "Supported Files (*.json *.txt *.bmg);;BMG (*.bmg);;JSON (*.json);;All (*)")
        if new_edited_path:
            original_edited_path_backup = self.mw.data_store.edited_json_path
            self.mw.data_store.edited_json_path = new_edited_path
            
            def on_save_finished(success: bool):
                if success:
                    QMessageBox.information(self.mw, "Saved As", f"Changes saved to:\n{self.mw.data_store.edited_json_path}")
                    self.ui_updater.update_statusbar_paths()
                else:
                    QMessageBox.critical(self.mw, "Save As Error", f"Failed to save to:\n{self.mw.data_store.edited_json_path}")
                    self.mw.data_store.edited_json_path = original_edited_path_backup
                    self.ui_updater.update_statusbar_paths()
            
            self.save_data_action(ask_confirmation=False, on_finished_callback=on_save_finished)

    def load_all_data_for_path(self, original_file_path: Union[str, Path], manually_set_edited_path: Optional[Union[str, Path]] = None, is_initial_load_from_settings: bool = False) -> None:
        """Load all data for path."""
        log_info(f"Loading all data for path: '{original_file_path}'")
        
        # Set paths beforehand so get_session_file_path can locate the session file
        self.mw.data_store.json_path = str(original_file_path)
        self.mw.data_store.edited_json_path = str(manually_set_edited_path) if manually_set_edited_path else self._derive_edited_path(str(original_file_path))
        
        # Check if we can restore from local session file instead of parsing raw files
        if hasattr(self.data_processor, 'load_session_file') and self.data_processor.load_session_file() is True:
            if hasattr(self.mw, 'close_project_action') and self.mw.close_project_action:
                self.mw.close_project_action.setEnabled(True)
            for act_name in ['save_translated_action', 'restore_translated_action', 'export_translations_action', 'import_translations_action']:
                act = getattr(self.mw, act_name, None)
                if act:
                    act.setEnabled(True)
            return

        with self.mw.state.enter(AppState.LOADING_DATA), self.mw.state.enter(AppState.PROGRAMMATIC_TEXT_CHANGE):
            if not self.mw.current_game_rules:
                QMessageBox.critical(self.mw, "Load Error", "Cannot load file: No game plugin is active.")
                return

            file_content = None
            error = None
            path_obj = Path(original_file_path)
            file_extension = path_obj.suffix.lower()

            if file_extension == '.json':
                file_content, error = load_json_file(path_obj)
            elif file_extension == '.txt':
                file_content, error = load_text_file(path_obj)
            elif file_extension == '.bmg':
                try:
                    with path_obj.open('rb') as f:
                        file_content = f.read()
                except Exception as e:
                    error = f"Failed to read BMG file: {e}"
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
                    edited_file_content, edit_error = load_json_file(edited_path_obj)
                elif edited_file_extension == '.txt':
                    edited_file_content, edit_error = load_text_file(edited_path_obj)
                elif edited_file_extension == '.bmg':
                    try:
                        with edited_path_obj.open('rb') as f:
                            edited_file_content = f.read()
                    except Exception as e:
                        edit_error = f"Failed to read BMG changes file: {e}"

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
            if hasattr(self.ui_updater, 'preview_updater'):
                self.ui_updater.preview_updater.schedule_pre_cache()
            
            self.ui_updater.update_title()
            self.ui_updater.update_statusbar_paths()
            self.ui_updater.populate_blocks()

            if hasattr(self.mw, 'close_project_action') and self.mw.close_project_action:
                self.mw.close_project_action.setEnabled(True)
            for act_name in ['save_translated_action', 'restore_translated_action', 'export_translations_action', 'import_translations_action']:
                act = getattr(self.mw, act_name, None)
                if act:
                    act.setEnabled(True)

            # Restore UI State (Session)
            if original_file_path and hasattr(self.mw, 'settings_manager'):
                 state = self.mw.settings_manager.session_state.get_state_for_file(str(original_file_path))
                 if state:
                     self.ui_updater.apply_tree_state(state)

    def reload_original_data_action(self) -> None:
        """Update the original data action."""
        log_info("Reload Original action triggered.")
        if not self.mw.data_store.json_path:
            QMessageBox.information(self.mw, "Reload", "No file open.")
            return
            
        if self.mw.data_store.unsaved_changes:
            reply = QMessageBox.question(self.mw, 'Unsaved Changes', "Reloading will discard current unsaved edits in memory. Proceed?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
                
        current_edited_path_before_reload = self.mw.data_store.edited_json_path
        self.load_all_data_for_path(self.mw.data_store.json_path, manually_set_edited_path=current_edited_path_before_reload, is_initial_load_from_settings=False)

    def calculate_widths_for_block_action(self, block_idx: int, category_name: Optional[str] = None) -> None:
        """Calculate widths for block action."""
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
            QMessageBox.information(self.mw, "Calculate Line Widths", "Target is empty.")
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
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        
        self.width_progress = progress
        
        def cleanup():
            self.width_progress = None
            self.width_worker = None

        def on_finished(result_dict):
            """Handle the finished event."""
            if progress.isVisible():
                progress.close()
            
            report_text = result_dict.get('report_text', '')
            entries = result_dict.get('entries', [])
            all_fonts_top_entries = result_dict.get('all_fonts_top_entries', {})

            cleanup()

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
            """Handle the cancelled event."""
            log_info("Width calculation worker cancelled.")
            progress.close()
            cleanup()

        self.width_worker.progress_updated.connect(progress.setValue)
        self.width_worker.calculation_finished.connect(on_finished)
        self.width_worker.cancelled.connect(on_cancelled)
        progress.canceled.connect(self.width_worker.cancel)
        
        self.width_worker.start()
        progress.show()

    def _perform_initial_silent_scan_all_issues(self) -> None:
        """Internal helper to perform initial silent scan all issues."""
        if hasattr(self.mw, 'issue_scan_handler'):
            self.mw.issue_scan_handler._perform_initial_silent_scan_all_issues()

