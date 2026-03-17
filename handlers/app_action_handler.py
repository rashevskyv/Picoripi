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

class AppActionHandler(BaseHandler):
    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any, game_rules_plugin: Optional[BaseGameRules]):
        super().__init__(main_window, data_processor, ui_updater)
        self.game_rules_plugin = game_rules_plugin

    def rescan_all_tags(self) -> None:
        if hasattr(self.mw, 'issue_scan_handler'):
            self.mw.issue_scan_handler.rescan_all_tags()

    def handle_close_event(self, event: QEvent) -> None:
        if self.mw.unsaved_changes:
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
        if self.mw.unsaved_changes:
            reply = QMessageBox.question(self.mw, 'Unsaved Changes', "Save before opening new file?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                if not self.save_data_action(ask_confirmation=True):
                    return
            elif reply == QMessageBox.Cancel:
                return
        
        start_dir = ""
        if self.mw.json_path:
            start_dir = str(Path(self.mw.json_path).parent)
            
        path, _ = QFileDialog.getOpenFileName(self.mw, "Open Original File", start_dir, "Supported Files (*.json *.txt);;JSON (*.json);;Text files (*.txt);;All (*)")
        if path:
            self.load_all_data_for_path(path, manually_set_edited_path=None, is_initial_load_from_settings=False)

    def open_changes_file_dialog_action(self) -> None:
        log_info("Open Changes File Dialog action triggered.")
        if not self.mw.json_path:
            QMessageBox.warning(self.mw, "Open Changes File", "Please open an original file first.")
            return
            
        start_dir = ""
        if self.mw.edited_json_path:
            start_dir = str(Path(self.mw.edited_json_path).parent)
        elif self.mw.json_path:
            start_dir = str(Path(self.mw.json_path).parent)
            
        path, _ = QFileDialog.getOpenFileName(self.mw, "Open Changes (Edited) File", start_dir, "Supported Files (*.json *.txt);;JSON Files (*.json);;Text Files (*.txt);;All Files (*)")
        if path:
            if self.mw.unsaved_changes:
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
            
            self.mw.edited_json_path = path
            self.mw.edited_file_data = new_edited_data
            self.mw.edited_data = {}
            self.mw.unsaved_changes = False
            
            self._perform_initial_silent_scan_all_issues()
            self.ui_updater.update_title()
            self.ui_updater.update_statusbar_paths()
            self.ui_updater.populate_blocks()
            if self.mw.block_list_widget.count() > 0 and self.mw.current_block_idx == -1:
                 custom_tree = getattr(self.mw, 'block_list_widget', None)
                 if custom_tree and hasattr(custom_tree, 'select_block_by_index'):
                     custom_tree.select_block_by_index(0)
            else:
                 self.ui_updater.populate_strings_for_block(self.mw.current_block_idx)

    def save_data_action(self, ask_confirmation: bool = True) -> bool:
        """
        High-level save action that delegates to the data processor.
        """
        log_info(f"AppActionHandler: save_data_action called (confirm={ask_confirmation})")
        return bool(self.data_processor.save_current_edits(ask_confirmation))

    def save_as_dialog_action(self) -> None:
        log_info("Save As Dialog action triggered.")
        if not self.mw.json_path:
            QMessageBox.warning(self.mw, "Save As Error", "No original file open.")
            return
            
        current_edited_path = self.mw.edited_json_path if self.mw.edited_json_path else self._derive_edited_path(self.mw.json_path)
        if not current_edited_path: 
            current_edited_path = str(Path(self.mw.json_path).parent / "untitled_edited.json") if self.mw.json_path else "untitled_edited.json"
            
        new_edited_path, _ = QFileDialog.getSaveFileName(self.mw, "Save Changes As...", current_edited_path, "Supported Files (*.json *.txt);;JSON (*.json);;All (*)")
        if new_edited_path:
            original_edited_path_backup = self.mw.edited_json_path
            self.mw.edited_json_path = new_edited_path
            save_success = self.save_data_action(ask_confirmation=False)
            if save_success:
                QMessageBox.information(self.mw, "Saved As", f"Changes saved to:\n{self.mw.edited_json_path}")
                self.ui_updater.update_statusbar_paths()
            else:
                QMessageBox.critical(self.mw, "Save As Error", f"Failed to save to:\n{self.mw.edited_json_path}")
                self.mw.edited_json_path = original_edited_path_backup
                self.ui_updater.update_statusbar_paths()

    def load_all_data_for_path(self, original_file_path: Union[str, Path], manually_set_edited_path: Optional[Union[str, Path]] = None, is_initial_load_from_settings: bool = False) -> None:
        log_info(f"Loading all data for path: '{original_file_path}'")
        self.mw.is_programmatically_changing_text = True
        
        if not self.mw.current_game_rules:
            QMessageBox.critical(self.mw, "Load Error", "Cannot load file: No game plugin is active.")
            self.mw.is_programmatically_changing_text = False
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
            self.mw.json_path = None
            self.mw.edited_json_path = None
            self.mw.data = []
            self.mw.edited_data = {}
            self.mw.edited_file_data = []
            self.mw.unsaved_changes = False
            self.ui_updater.update_title()
            self.ui_updater.update_statusbar_paths()
            self.ui_updater.populate_blocks()
            self.ui_updater.populate_strings_for_block(-1)
            self.mw.is_programmatically_changing_text = False
            QMessageBox.critical(self.mw, "Load Error", f"Failed to load: {original_file_path}\n{error}")
            return

        # Reset plugin state if it tracks keys (like pokemon_fr)
        if hasattr(self.mw.current_game_rules, 'original_keys'):
            self.mw.current_game_rules.original_keys = []
            
        data, block_names_from_plugin = self.mw.current_game_rules.load_data_from_json_obj(file_content)
        if not data and file_content is not None:
            QMessageBox.critical(self.mw, "Plugin Error", f"The active plugin '{self.mw.current_game_rules.get_display_name()}' could not parse the file:\n{original_file_path}")
            self.mw.json_path = None
            self.mw.data = []
            self.ui_updater.populate_blocks()
            self.ui_updater.populate_strings_for_block(-1)
            self.mw.is_programmatically_changing_text = False
            return

        self.mw.json_path = str(original_file_path)
        self.mw.data = data
        if block_names_from_plugin:
            self.mw.block_names.update(block_names_from_plugin)
        
        self.mw.edited_data = {}
        self.mw.unsaved_changes = False
        
        self.mw.edited_json_path = str(manually_set_edited_path) if manually_set_edited_path else self._derive_edited_path(self.mw.json_path)
        self.mw.edited_file_data = []
        if self.mw.edited_json_path and Path(self.mw.edited_json_path).exists():
            edited_file_content = None
            edit_error = None
            edited_path_obj = Path(self.mw.edited_json_path)
            edited_file_extension = edited_path_obj.suffix.lower()

            if edited_file_extension == '.json':
                edited_file_content, edit_error = load_json_file(edited_path_obj, parent_widget=self.mw)
            elif edited_file_extension == '.txt':
                edited_file_content, edit_error = load_text_file(edited_path_obj, parent_widget=self.mw)

            if edit_error:
                QMessageBox.warning(self.mw, "Edited Load Warning", f"Could not load changes file: {self.mw.edited_json_path}\n{edit_error}")
            else:
                plugin_keys_backup = None
                if hasattr(self.mw.current_game_rules, 'original_keys'):
                    plugin_keys_backup = list(self.mw.current_game_rules.original_keys)
                    
                edited_data_from_file, _ = self.mw.current_game_rules.load_data_from_json_obj(edited_file_content)
                
                if plugin_keys_backup is not None and hasattr(self.mw.current_game_rules, 'original_keys'):
                    self.mw.current_game_rules.original_keys = plugin_keys_backup
                    
                self.mw.edited_file_data = edited_data_from_file
        
        self.mw.current_block_idx = -1
        self.mw.current_string_idx = -1
        
        if hasattr(self.mw, 'undo_paste_action'):
            self.mw.can_undo_paste = False
            self.mw.undo_paste_action.setEnabled(False)
        if hasattr(self.mw, 'undo_manager'):
            self.mw.undo_manager.clear()
        
        self.mw.block_list_widget.clear()
        if hasattr(self.mw, 'preview_text_edit'):
            self.mw.preview_text_edit.clear()
        if hasattr(self.mw, 'original_text_edit'):
            self.mw.original_text_edit.clear()
        if hasattr(self.mw, 'edited_text_edit'):
            self.mw.edited_text_edit.clear()

        self._perform_initial_silent_scan_all_issues()
        
        self.ui_updater.update_title()
        self.ui_updater.update_statusbar_paths()
        self.ui_updater.populate_blocks()

        # Restore UI State (Session)
        state_restored = False
        if original_file_path:
            state = self.mw.settings_manager.session_state.get_state_for_file(str(original_file_path))
            if state:
                log_info(f"Restoring UI state for {original_file_path}")
                self.ui_updater.apply_tree_state(state)
                
                # Apply cursor and scroll positions
                if self.mw.edited_text_edit:
                    def _apply_scroll() -> None:
                        self.mw.edited_text_edit.verticalScrollBar().setValue(state.get("v_scroll", 0))
                        self.mw.edited_text_edit.horizontalScrollBar().setValue(state.get("h_scroll", 0))
                        if self.mw.preview_text_edit:
                            self.mw.preview_text_edit.verticalScrollBar().setValue(state.get("preview_v_scroll", 0))
                        if self.mw.original_text_edit:
                            self.mw.original_text_edit.verticalScrollBar().setValue(state.get("original_v_scroll", 0))
                        
                        cursor_pos = state.get("cursor_pos", 0)
                        doc_len = self.mw.edited_text_edit.document().characterCount() - 1
                        pos_to_set = min(cursor_pos, max(0, doc_len))
                        cursor = self.mw.edited_text_edit.textCursor()
                        cursor.setPosition(pos_to_set)
                        self.mw.edited_text_edit.setTextCursor(cursor)
                        self.mw.edited_text_edit.ensureCursorVisible()

                    from PyQt5.QtCore import QTimer
                    QTimer.singleShot(200, _apply_scroll)
                
                state_restored = True

        if not state_restored:
            if self.mw.block_list_widget.invisibleRootItem().childCount() > 0:
                if not is_initial_load_from_settings: 
                     custom_tree = getattr(self.mw, 'block_list_widget', None)
                     if custom_tree and hasattr(custom_tree, 'select_block_by_index'):
                         custom_tree.select_block_by_index(0)
            else:
                self.ui_updater.populate_strings_for_block(-1)
            
        self.mw.is_programmatically_changing_text = False

    def reload_original_data_action(self) -> None:
        log_info("Reload Original action triggered.")
        if not self.mw.json_path:
            QMessageBox.information(self.mw, "Reload", "No file open.")
            return
            
        if self.mw.unsaved_changes:
            reply = QMessageBox.question(self.mw, 'Unsaved Changes', "Reloading will discard current unsaved edits in memory. Proceed?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return
                
        current_edited_path_before_reload = self.mw.edited_json_path
        self.load_all_data_for_path(self.mw.json_path, manually_set_edited_path=current_edited_path_before_reload, is_initial_load_from_settings=False)

    def calculate_widths_for_block_action(self, block_idx: int) -> None:
        if block_idx < 0 or not self.mw.data or block_idx >= len(self.mw.data) or not isinstance(self.mw.data[block_idx], list):
            QMessageBox.warning(self.mw, "Calculate Widths Error", "Invalid block selected or no data.")
            return

        if not self.mw.font_map:
             QMessageBox.warning(self.mw, "Calculate Widths Error", "Font map is not loaded. Cannot calculate widths.")
             return
        if not self.game_rules_plugin:
            QMessageBox.warning(self.mw, "Calculate Widths Error", "Game rules plugin not loaded.")
            return

        num_strings = len(self.mw.data[block_idx])
        if num_strings == 0:
            QMessageBox.information(self.mw, "Calculate Line Widths", f"Block {self.mw.block_names.get(str(block_idx),str(block_idx))} is empty.")
            return

        progress = QProgressDialog(f"Calculating widths for block {self.mw.block_names.get(str(block_idx),str(block_idx))}...", "Cancel", 0, num_strings, self.mw)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        results: List[str] = []
        problem_definitions = self.game_rules_plugin.get_problem_definitions()
        
        # Use problem_analyzer if it exists, otherwise use the game rules object itself
        analyzer = getattr(self.game_rules_plugin, 'problem_analyzer', self.game_rules_plugin)

        for data_str_idx in range(num_strings):
            progress.setValue(data_str_idx)
            if progress.wasCanceled():
                log_info("Width calculation for block cancelled by user.")
                return

            current_text_data_line, source = self.data_processor.get_current_string_text(block_idx, data_str_idx)
            original_text_data_line = self.data_processor._get_string_from_source(block_idx, data_str_idx, self.mw.data, "width_calc_block_original_data")
            
            font_map_for_string = self.mw.helper.get_font_map_for_string(block_idx, data_str_idx)
            string_meta = self.mw.string_metadata.get((block_idx, data_str_idx), {})
            editor_warning_threshold = string_meta.get("width", self.mw.line_width_warning_threshold_pixels)

            line_report_parts = [f"Data Line {data_str_idx + 1}:"]
            
            sources_to_check = [
                ("Current", str(current_text_data_line), source),
                ("Original", str(original_text_data_line), "original_data")
            ]

            for title_prefix, text_to_analyze, text_source_info in sources_to_check:
                line_report_parts.append(f"  {title_prefix} (src:{text_source_info}):")
                
                logical_sublines: List[str] = []
                if hasattr(analyzer, '_get_sublines_from_data_string'):
                    logical_sublines = analyzer._get_sublines_from_data_string(text_to_analyze)
                else:
                    logical_sublines = text_to_analyze.split('\n')
                
                game_like_text_no_newlines_rstripped = remove_all_tags(text_to_analyze.replace('\\n','').replace('\\p','').replace('\\l','')).rstrip()
                total_game_width = calculate_string_width(game_like_text_no_newlines_rstripped, font_map_for_string)
                game_status = "OK"
                if total_game_width > self.mw.game_dialog_max_width_pixels:
                    game_status = f"EXCEEDS GAME DIALOG LIMIT ({total_game_width - self.mw.game_dialog_max_width_pixels}px)"
                line_report_parts.append(f"    Total (game dialog, rstripped): {total_game_width}px ({game_status})")

                for subline_idx, sub_line_text in enumerate(logical_sublines):
                    sub_line_no_tags_rstripped = remove_all_tags(sub_line_text).rstrip()
                    width_px = calculate_string_width(sub_line_no_tags_rstripped, font_map_for_string)
                    
                    current_subline_problems: set = set()
                    if hasattr(analyzer, 'analyze_data_string'):
                        problems_per_subline_list = analyzer.analyze_data_string(text_to_analyze, font_map_for_string, editor_warning_threshold)
                        current_subline_problems = problems_per_subline_list[subline_idx] if subline_idx < len(problems_per_subline_list) else set()
                    elif hasattr(analyzer, 'analyze_subline'):
                        next_subline = logical_sublines[subline_idx+1] if subline_idx + 1 < len(logical_sublines) else None
                        current_subline_problems = analyzer.analyze_subline(
                            text=sub_line_text, next_text=next_subline, subline_number_in_data_string=subline_idx, qtextblock_number_in_editor=subline_idx,
                            is_last_subline_in_data_string=(subline_idx == len(logical_sublines) - 1), editor_font_map=font_map_for_string,
                            editor_line_width_threshold=editor_warning_threshold,
                            full_data_string_text_for_logical_check=text_to_analyze
                        )
                    
                    statuses: List[str] = []
                    for prob_id in current_subline_problems:
                        if prob_id in problem_definitions:
                            statuses.append(problem_definitions[prob_id]['name'])
                    
                    status_str = ", ".join(statuses) if statuses else "OK"
                    line_report_parts.append(f"    Sub {subline_idx+1} (rstripped): {width_px}px ({status_str}) '{sub_line_no_tags_rstripped[:30]}...'")
                if title_prefix == "Current":
                    line_report_parts.append("")

            results.append("\n".join(line_report_parts))
        
        progress.setValue(num_strings)

        if not results:
            QMessageBox.information(self.mw, "Calculate Line Widths", f"Block {self.mw.block_names.get(str(block_idx),str(block_idx))} processed. No lines found or calculation error.")
            return
            
        result_text_title = (f"Widths for Block {self.mw.block_names.get(str(block_idx), str(block_idx))}\n"
                             f"(Editor Warning Threshold: {self.mw.line_width_warning_threshold_pixels}px - can be overridden per string)\n"
                             f"(Game Dialog Max Width (for total only): {self.mw.game_dialog_max_width_pixels}px)\n")
        result_text = result_text_title + "\n" + "\n\n".join(results)
        
        result_dialog = QMessageBox(self.mw)
        result_dialog.setWindowTitle("Line Widths Report")
        result_dialog.setTextFormat(Qt.PlainText)
        result_dialog.setText(result_text)
        result_dialog.setIcon(QMessageBox.Information)
        result_dialog.setStandardButtons(QMessageBox.Ok)
        result_dialog.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        text_edit_for_size = result_dialog.findChild(QPlainTextEdit)
        if text_edit_for_size:
            text_edit_for_size.setMinimumWidth(700)
            text_edit_for_size.setMinimumHeight(500)
        result_dialog.exec_()

    def _perform_initial_silent_scan_all_issues(self) -> None:
        if hasattr(self.mw, 'issue_scan_handler'):
            self.mw.issue_scan_handler._perform_initial_silent_scan_all_issues()

