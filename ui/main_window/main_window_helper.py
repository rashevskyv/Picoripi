from __future__ import annotations
from typing import TYPE_CHECKING
from PyQt6.QtWidgets import QMessageBox, QApplication
from PyQt6.QtCore import QRect, QProcess, QPoint
from utils.logging_utils import log_debug, log_info, log_error
import copy
from pathlib import Path
import sys

if TYPE_CHECKING:
    from main import MainWindow

class MainWindowHelper:
    """Main window helper implementation."""
    def __init__(self, main_window: MainWindow):
        """Initialize a new instance."""
        self.mw = main_window

    def get_font_map_for_string(self, block_idx: int, string_idx: int) -> dict:
        """Get the font map for string."""
        metadata_key = (block_idx, string_idx)
        string_meta = self.mw.string_metadata.get(metadata_key, {})
        
        custom_font_file = string_meta.get("font_file")
        if custom_font_file:
            if custom_font_file in self.mw.all_font_maps:
                return self.mw.all_font_maps[custom_font_file]
            for key, font_map in self.mw.all_font_maps.items():
                if key.endswith("/" + custom_font_file):
                    return font_map
            
        return self.mw.font_map

    def restart_application(self):
        """Restart application."""
        log_info("Restarting application...")
        self.mw.close()
        QProcess.startDetached(sys.executable, sys.argv)

    def rebuild_unsaved_block_indices(self):
        """Rebuild unsaved block indices."""
        self.mw.data_store.unsaved_block_indices.clear()
        for block_idx, _ in self.mw.data_store.edited_data.keys():
            self.mw.data_store.unsaved_block_indices.add(block_idx)
        if hasattr(self.mw, 'block_list_widget'):
             self.mw.block_list_widget.viewport().update()

    def execute_find_next_shortcut(self):
        """Execute find next shortcut."""
        query_to_use = ""
        case_sensitive_to_use = False
        search_in_original_to_use = False
        ignore_tags_to_use = True
        is_fuzzy_to_use = False

        if self.mw.search_panel_widget.isVisible():
            query_to_use, case_sensitive_to_use, search_in_original_to_use, ignore_tags_to_use, is_fuzzy_to_use = self.mw.search_panel_widget.get_search_parameters()
            if not query_to_use:
                self.mw.search_panel_widget.set_status_message("Enter query for F3", is_error=True)
                self.mw.search_panel_widget.focus_search_input()
                return
        else:
            query_to_use, case_sensitive_to_use, search_in_original_to_use, ignore_tags_to_use, is_fuzzy_to_use = self.mw.search_handler.get_current_search_params()
            if not query_to_use:
                self.toggle_search_panel()
                self.mw.search_panel_widget.set_status_message("Enter query", is_error=True)
                return

        found = self.mw.search_handler.find_next(query_to_use, case_sensitive_to_use, search_in_original_to_use, ignore_tags_to_use, is_fuzzy_to_use)
        if not found and not self.mw.search_panel_widget.isVisible():
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self.mw, "Find", f"Not found: \"{query_to_use}\"")

    def execute_find_previous_shortcut(self):
        """Execute find previous shortcut."""
        query_to_use = ""
        case_sensitive_to_use = False
        search_in_original_to_use = False
        ignore_tags_to_use = True
        is_fuzzy_to_use = False

        if self.mw.search_panel_widget.isVisible():
            query_to_use, case_sensitive_to_use, search_in_original_to_use, ignore_tags_to_use, is_fuzzy_to_use = self.mw.search_panel_widget.get_search_parameters()
            if not query_to_use:
                self.mw.search_panel_widget.set_status_message("Enter query for Shift+F3", is_error=True)
                self.mw.search_panel_widget.focus_search_input()
                return
        else:
            query_to_use, case_sensitive_to_use, search_in_original_to_use, ignore_tags_to_use, is_fuzzy_to_use = self.mw.search_handler.get_current_search_params()
            if not query_to_use:
                self.toggle_search_panel()
                self.mw.search_panel_widget.set_status_message("Enter query", is_error=True)
                return

        found = self.mw.search_handler.find_previous(query_to_use, case_sensitive_to_use, search_in_original_to_use, ignore_tags_to_use, is_fuzzy_to_use)
        if not found and not self.mw.search_panel_widget.isVisible():
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self.mw, "Find", f"Not found: \"{query_to_use}\"")

    def handle_panel_find_next(self, query, case_sensitive, search_in_original, ignore_tags, is_fuzzy):
        """Handle panel find next."""
        self.mw.search_handler.find_next(query, case_sensitive, search_in_original, ignore_tags, is_fuzzy)

    def handle_panel_find_previous(self, query, case_sensitive, search_in_original, ignore_tags, is_fuzzy):
        """Handle panel find previous."""
        self.mw.search_handler.find_previous(query, case_sensitive, search_in_original, ignore_tags, is_fuzzy)

    def toggle_search_panel(self):
        """Toggle search panel."""
        if self.mw.search_panel_widget.isVisible():
            self.mw.search_panel_widget.focus_search_input()
        else:
            self.mw.search_panel_widget.setVisible(True)
            # Fix: added is_fuzzy to unpacking
            last_query, case_sensitive, search_in_original, ignore_tags, is_fuzzy = self.mw.search_handler.get_current_search_params()

            self.mw.search_panel_widget.set_query(last_query if last_query else "")
            self.mw.search_panel_widget.set_search_options(case_sensitive, search_in_original, ignore_tags, is_fuzzy)

            if hasattr(self.mw, 'search_history_to_save'):
                 self.mw.search_panel_widget.load_history(self.mw.search_history_to_save)
            else:
                 self.mw.search_panel_widget._update_combobox_items()
            self.mw.search_panel_widget.focus_search_input()

    def hide_search_panel(self):
        """Hide search panel."""
        self.mw.search_panel_widget.setVisible(False)
        self.mw.search_handler.clear_all_search_highlights()

    def open_advanced_search(self, query, case_sensitive, search_in_original, ignore_tags, is_fuzzy):
        """Open advanced search."""
        try:
            log_debug(f"MainWindowHelper: open_advanced_search called for Q='{query}'")
            
            if not self.mw.data_store.data:
                QMessageBox.warning(self.mw, "Advanced Search", "No project data loaded.")
                return

            edited_data = self.mw.data_store.edited_data
            
            all_lines = []
            for b_idx in range(len(self.mw.data_store.data)):
                block_data = self.mw.data_store.data[b_idx]
                if not isinstance(block_data, list):
                    continue
                for string_idx in range(len(block_data)):
                    if search_in_original:
                        text = self.mw.data_processor._get_string_from_source(
                            b_idx, string_idx, self.mw.data_store.data, "dialog_original"
                        )
                    else:
                        text, _ = self.mw.data_processor.get_current_string_text(b_idx, string_idx)
                    if text is not None:
                        all_lines.append((b_idx, string_idx, text))

            # Filter lines that actually contain the query
            text_parts = []
            line_numbers = []
            block_indices = []

            import re
            from utils.utils import prepare_text_for_tagless_search, is_fuzzy_match, find_smart_matches

            effective_query = query
            if ignore_tags and query:
                effective_query = prepare_text_for_tagless_search(query)

            if query and effective_query:
                if is_fuzzy:
                    word_pattern = re.compile(r'\w+')
                    for b_idx, string_idx, text in all_lines:
                        if ignore_tags:
                            text_for_search = prepare_text_for_tagless_search(text)
                        else:
                            text_for_search = text.replace('·', ' ')

                        has_match = False
                        for match in word_pattern.finditer(text_for_search):
                            word = match.group(0)
                            if is_fuzzy_match(effective_query, word, threshold=0.75):
                                has_match = True
                                break
                        if has_match:
                            text_parts.append(text)
                            subline_count = text.count('\n') + 1
                            for _ in range(subline_count):
                                line_numbers.append(string_idx)
                                block_indices.append(b_idx)
                else:
                    for b_idx, string_idx, text in all_lines:
                        if ignore_tags:
                            text_for_search = prepare_text_for_tagless_search(text)
                        else:
                            text_for_search = text.replace('·', ' ')

                        if find_smart_matches(text_for_search, effective_query, case_sensitive):
                            text_parts.append(text)
                            subline_count = text.count('\n') + 1
                            for _ in range(subline_count):
                                line_numbers.append(string_idx)
                                block_indices.append(b_idx)
            else:
                # If query is empty, do not load all lines into the editor initially to prevent freezing.
                # The dialog will open instantly, and the user can write a query and click Find.
                pass

            if query and not text_parts:
                QMessageBox.information(self.mw, "Advanced Search", f"No matches found for \"{query}\" in all blocks.")
                return

            text_to_check = '\n'.join(text_parts)
            
            from dialogs.search_review_dialog import SearchReviewDialog
            dialog = SearchReviewDialog(self.mw, text_to_check, query,
                                       starting_line_number=0, line_numbers=line_numbers,
                                       case_sensitive=case_sensitive, is_fuzzy=is_fuzzy,
                                       search_in_original=search_in_original, ignore_tags=ignore_tags,
                                       block_idx=self.mw.data_store.current_block_idx, block_indices=block_indices)

            if dialog.exec():
                corrected_text = dialog.get_corrected_text()
                corrected_lines = corrected_text.split('\n')

                # Reconstruct multi-line strings using our ZIP logic with block indices
                grouped_lines = {}
                for line_text, s_idx, b_idx in zip(corrected_lines, dialog.line_numbers, dialog.block_indices):
                    if s_idx is not None and b_idx is not None:
                        key = (b_idx, s_idx)
                        if key not in grouped_lines:
                            grouped_lines[key] = []
                        grouped_lines[key].append(line_text)

                changes_made = False
                changed_blocks = set()

                undo_manager = getattr(self.mw, "undo_manager", None)
                if undo_manager:
                    undo_manager.begin_group()

                for (b_idx, string_idx), lines_list in grouped_lines.items():
                    new_text = '\n'.join(lines_list)
                    old_text, _ = self.mw.data_processor.get_current_string_text(b_idx, string_idx)
                    if new_text != old_text:
                        key = (b_idx, string_idx)
                        edited_data[key] = new_text
                        changes_made = True
                        changed_blocks.add(b_idx)
                        
                        # Restore subline asterisks if this is the currently edited string
                        if b_idx == self.mw.data_store.current_block_idx and string_idx == self.mw.data_store.current_string_idx:
                            if hasattr(self.mw, 'text_operation_handler'):
                                self.mw.text_operation_handler.sync_subline_asterisks(
                                    b_idx, string_idx, new_text
                                )

                if undo_manager:
                    undo_manager.end_group("ADVANCED_SEARCH_REPLACE")

                if changes_made:
                    self.mw.data_store.unsaved_changes = True
                    for b_idx in changed_blocks:
                        self.mw.data_store.unsaved_block_indices.add(b_idx)
                    
                    for b_idx in changed_blocks:
                        if hasattr(self.mw, 'ui_updater'):
                            self.mw.ui_updater.update_block_item_text_with_problem_count(b_idx)
                            
                    current_block_idx = self.mw.data_store.current_block_idx
                    if current_block_idx in changed_blocks:
                        if hasattr(self.mw, 'ui_updater'):
                            self.mw.ui_updater.populate_strings_for_block(current_block_idx)
                            self.mw.ui_updater.update_text_views()
                        
                    if hasattr(self.mw, 'edited_text_edit') and self.mw.edited_text_edit:
                        if hasattr(self.mw.edited_text_edit, 'lineNumberArea'):
                            self.mw.edited_text_edit.lineNumberArea.update()
                            
                    QMessageBox.information(self.mw, "Advanced Search", "Replacements applied successfully!")
        except Exception as e:
            log_error(f"MainWindowHelper: Error in open_advanced_search: {e}", exc_info=True)
            QMessageBox.critical(self.mw, "Error", f"An error occurred: {e}")

    def load_all_data_for_path(self, original_file_path, manually_set_edited_path=None, is_initial_load_from_settings=False):
        """Load all data for path."""
        self.mw.app_action_handler.load_all_data_for_path(original_file_path, manually_set_edited_path, is_initial_load_from_settings)
        self.rebuild_unsaved_block_indices()
        for editor_widget in [self.mw.preview_text_edit, self.mw.original_text_edit, self.mw.edited_text_edit]:
            if editor_widget:
                editor_widget.line_width_warning_threshold_pixels = self.mw.line_width_warning_threshold_pixels
                editor_widget.font_map = self.mw.font_map
                editor_widget.game_dialog_max_width_pixels = self.mw.game_dialog_max_width_pixels
                editor_widget.show_width_guideline = getattr(self.mw, 'show_width_guideline', True)
                if hasattr(editor_widget, 'updateLineNumberAreaWidth'):
                    editor_widget.updateLineNumberAreaWidth(0)

    def apply_text_wrap_settings(self):
        """Apply text wrap settings."""
        from PyQt6.QtWidgets import QPlainTextEdit
        preview_wrap_mode = QPlainTextEdit.LineWrapMode.WidgetWidth if self.mw.preview_wrap_lines else QPlainTextEdit.LineWrapMode.NoWrap
        editors_wrap_mode = QPlainTextEdit.LineWrapMode.WidgetWidth if self.mw.editors_wrap_lines else QPlainTextEdit.LineWrapMode.NoWrap
        if hasattr(self.mw, 'preview_text_edit'): self.mw.preview_text_edit.setLineWrapMode(preview_wrap_mode)
        if hasattr(self.mw, 'original_text_edit'): self.mw.original_text_edit.setLineWrapMode(editors_wrap_mode)
        if hasattr(self.mw, 'edited_text_edit'): self.mw.edited_text_edit.setLineWrapMode(editors_wrap_mode)

    def reconfigure_all_highlighters(self):
        # Compose newline CSS
        """Reconfigure all highlighters."""
        nl_color = getattr(self.mw, 'newline_color_rgba', "#A020F0")
        nl_css_parts = [f"color: {nl_color}"]
        if getattr(self.mw, 'newline_bold', True): nl_css_parts.append("font-weight: bold")
        if getattr(self.mw, 'newline_italic', False): nl_css_parts.append("font-style: italic")
        if getattr(self.mw, 'newline_underline', False): nl_css_parts.append("text-decoration: underline")
        newline_css_str = "; ".join(nl_css_parts) + ";"

        common_args = {
            "newline_symbol": self.mw.newline_display_symbol, "newline_css_str": newline_css_str,
            "tag_css_str": "", "show_multiple_spaces_as_dots": self.mw.show_multiple_spaces_as_dots,
            "space_dot_color_hex": self.mw.space_dot_color_hex, "bracket_tag_color_hex": getattr(self.mw, 'tag_color_rgba', "#FF8C00")
        }
        text_edits_with_highlighters = []
        if hasattr(self.mw, 'preview_text_edit') and hasattr(self.mw.preview_text_edit, 'highlighter'): text_edits_with_highlighters.append(self.mw.preview_text_edit)
        if hasattr(self.mw, 'original_text_edit') and hasattr(self.mw.original_text_edit, 'highlighter'): text_edits_with_highlighters.append(self.mw.original_text_edit)
        if hasattr(self.mw, 'edited_text_edit') and hasattr(self.mw.edited_text_edit, 'highlighter'): text_edits_with_highlighters.append(self.mw.edited_text_edit)
        for text_edit in text_edits_with_highlighters:
            if text_edit.highlighter:
                text_edit.highlighter.reconfigure_styles(**common_args)
                text_edit.highlighter.rehighlight()

    def prepare_to_close(self):
        """Prepare to close."""
        if hasattr(self.mw, 'spellchecker_manager') and self.mw.spellchecker_manager:
            try:
                self.mw.spellchecker_manager.prepare_to_close()
            except Exception:
                pass

        if hasattr(self.mw, 'editor_operation_handler') and self.mw.editor_operation_handler:
            try:
                self.mw.editor_operation_handler.preview_update_timer.stop()
            except Exception:
                pass

        if hasattr(self.mw, 'issue_scan_handler') and self.mw.issue_scan_handler:
            try:
                if hasattr(self.mw.issue_scan_handler, '_scan_timer') and self.mw.issue_scan_handler._scan_timer:
                    self.mw.issue_scan_handler._scan_timer.stop()
            except Exception:
                pass

        try:
            from handlers.async_issue_scanner import get_scanner_thread_pool
            pool = get_scanner_thread_pool()
            pool.clear()
            pool.waitForDone(1000)
        except Exception:
            pass

        if hasattr(self.mw, 'ai_chat_handler') and self.mw.ai_chat_handler:
            try:
                self.mw.ai_chat_handler.prepare_to_close()
            except Exception:
                pass

        if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
            try:
                if hasattr(self.mw.translation_handler, 'ai_lifecycle_manager') and self.mw.translation_handler.ai_lifecycle_manager:
                    self.mw.translation_handler.ai_lifecycle_manager.prepare_to_close()
            except Exception:
                pass

        self.mw.data_store.last_selected_block_index = self.mw.data_store.current_block_idx
        self.mw.data_store.last_selected_string_index = self.mw.data_store.current_string_idx
        
        if hasattr(self.mw, 'edited_text_edit') and self.mw.edited_text_edit:
            self.mw.last_cursor_position_in_edited = self.mw.edited_text_edit.textCursor().position()
            self.mw.last_edited_text_edit_scroll_value_v = self.mw.edited_text_edit.verticalScrollBar().value()
            self.mw.last_edited_text_edit_scroll_value_h = self.mw.edited_text_edit.horizontalScrollBar().value()
        
        if hasattr(self.mw, 'preview_text_edit') and self.mw.preview_text_edit:
            self.mw.last_preview_text_edit_scroll_value_v = self.mw.preview_text_edit.verticalScrollBar().value()
        if hasattr(self.mw, 'original_text_edit') and self.mw.original_text_edit:
            self.mw.last_original_text_edit_scroll_value_v = self.mw.original_text_edit.verticalScrollBar().value()
            self.mw.last_original_text_edit_scroll_value_h = self.mw.original_text_edit.horizontalScrollBar().value()

        if hasattr(self.mw, 'search_panel_widget') and self.mw.search_panel_widget:
            self.mw.search_history_to_save = self.mw.search_panel_widget.get_history()
        
        # Save UI Session State for the current file/project
        current_path = None
        is_project = False
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project_file_path:
            current_path = self.mw.project_manager.project_file_path
            is_project = True
        elif self.mw.data_store.json_path:
            current_path = self.mw.data_store.json_path
            
        if current_path:
            state = self.mw.ui_updater.get_tree_state()
            state.update({
                "cursor_pos": self.mw.last_cursor_position_in_edited,
                "v_scroll": self.mw.last_edited_text_edit_scroll_value_v,
                "h_scroll": self.mw.last_edited_text_edit_scroll_value_h,
                "preview_v_scroll": self.mw.last_preview_text_edit_scroll_value_v,
                "original_v_scroll": self.mw.last_original_text_edit_scroll_value_v
            })
            if is_project and self.mw.project_manager.project:
                self.mw.project_manager.project.metadata['session_state'] = state
                self.mw.project_manager.save_settings_to_project(self.mw)
                
            self.mw.settings_manager.session_state.set_state_for_file(str(current_path), state)
            self.mw.settings_manager.set("last_opened_path", str(current_path))

        self.mw.window_was_maximized_on_close = self.mw.isMaximized()
        if self.mw.window_was_maximized_on_close:
            self.mw.window_normal_geometry_on_close = self.mw.normalGeometry()
        else:
            self.mw.window_normal_geometry_on_close = self.mw.geometry()


    def restore_state_after_settings_load(self):
        """Restore state after settings load."""
        from utils.logging_utils import log_info
        log_info("Restoring state after settings load.")
        
        # Restore hide empty strings state
        hide_empty_val = self.mw.settings_manager.get('hide_empty_strings', False)
        self.mw.data_store.hide_empty_strings = hide_empty_val
        if hasattr(self.mw, 'hide_empty_strings_checkbox') and self.mw.hide_empty_strings_checkbox:
            self.mw.hide_empty_strings_checkbox.setChecked(hide_empty_val)
        
        # Restore global splitters state
        try:
            import base64
            for splitter_attr, setting_key in [
                ("main_splitter", "main_splitter_state"),
                ("right_splitter", "right_splitter_state"),
                ("bottom_right_splitter", "bottom_right_splitter_state"),
                ("editor_preview_splitter", "editor_preview_splitter_state")
            ]:
                splitter = getattr(self.mw, splitter_attr, None)
                state_val = self.mw.settings_manager.get(setting_key)
                if splitter and state_val:
                    try:
                        splitter.restoreState(base64.b64decode(state_val.encode('ascii')))
                    except Exception as restore_err:
                        log_info(f"Failed to restore state for {splitter_attr}: {restore_err}")
        except Exception as e:
            log_info(f"Failed to restore global splitter state(s): {e}")
        
        if hasattr(self.mw, 'window_geometry_to_restore') and self.mw.window_geometry_to_restore:
            geom_dict = self.mw.window_geometry_to_restore
            if all(k in geom_dict for k in ('x', 'y', 'width', 'height')):
                pos = QPoint(geom_dict.get('x', 0), geom_dict.get('y', 0))
                screen = QApplication.screenAt(pos)
                if not screen:
                    screen = QApplication.primaryScreen()
                screen_geom = screen.geometry() if screen else QRect(0, 0, 1920, 1080)
                
                # Enforce minimum size, and cap to screen size
                width = max(min(geom_dict['width'], screen_geom.width()), 800)
                height = max(min(geom_dict['height'], screen_geom.height()), 600)
                
                x = geom_dict['x']
                y = geom_dict['y']
                
                # Keep within screen bounds
                if x + width > screen_geom.right() or x < screen_geom.left():
                    x = screen_geom.left() + (screen_geom.width() - width) // 2
                if y + height > screen_geom.bottom() or y < screen_geom.top():
                    y = screen_geom.top() + (screen_geom.height() - height) // 2
                    
                self.mw.setGeometry(x, y, width, height)
            else:
                self.mw.resize(1280, 800)
        else:
            self.mw.resize(1280, 800)


        # Determine which path to auto-open
        path_to_open = getattr(self.mw, 'last_opened_path', "")
        
        if path_to_open and Path(path_to_open).exists():
            log_info(f"Auto-opening: {path_to_open}")
            p_obj = Path(path_to_open)
            
            if p_obj.suffix.lower() == ".uiproj":
                if hasattr(self.mw, 'project_action_handler'):
                    self.mw.project_action_handler._open_recent_project(str(p_obj))
            else:
                if hasattr(self.mw, 'app_action_handler'):
                    # Search for associated edited file if possible
                    edited_path = self.mw.app_action_handler._derive_edited_path(str(p_obj))
                    self.mw.app_action_handler.load_all_data_for_path(str(p_obj), edited_path, is_initial_load_from_settings=True)
        else:
             # Legacy/Fallback if paths are provided separately
             if hasattr(self.mw, 'initial_load_path') and self.mw.initial_load_path and Path(self.mw.initial_load_path).exists():
                log_info(f"Loading initial file: {self.mw.initial_load_path}")
                self.mw.app_action_handler.load_all_data_for_path(self.mw.initial_load_path, self.mw.initial_edited_load_path, is_initial_load_from_settings=True)
             else:
                log_info("No file/project to auto-load, updating initial UI state.")
                self.mw.ui_updater.update_title()
                self.mw.ui_updater.update_statusbar_paths()
                self.mw.ui_updater.populate_blocks()
                self.mw.ui_updater.populate_strings_for_block(-1)


        if hasattr(self.mw, 'search_history_to_save') and self.mw.search_panel_widget:
            self.mw.search_panel_widget.load_history(self.mw.search_history_to_save)
            if self.mw.search_history_to_save:
                last_query = self.mw.search_history_to_save[0]
                self.mw.search_handler.current_query = last_query
                # Fix: unpacking 5 values
                _, cs, so, it, is_fuzzy = self.mw.search_panel_widget.get_search_parameters()
                self.mw.search_handler.is_case_sensitive = cs
                self.mw.search_handler.search_in_original = so
                self.mw.search_handler.ignore_tags_newlines = it
                self.mw.search_handler.is_fuzzy = is_fuzzy