# --- START OF FILE ui/main_window/main_window_helper.py ---
# --- START OF FILE main_window_helper.py ---
# --- START OF FILE handlers/main_window_helper.py ---
from __future__ import annotations
from typing import TYPE_CHECKING
from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtCore import QRect, QProcess
from utils.logging_utils import log_debug, log_info
import copy
from pathlib import Path
import sys

if TYPE_CHECKING:
    from main import MainWindow

class MainWindowHelper:
    def __init__(self, main_window: MainWindow):
        self.mw = main_window

    def get_font_map_for_string(self, block_idx: int, string_idx: int) -> dict:
        metadata_key = (block_idx, string_idx)
        string_meta = self.mw.string_metadata.get(metadata_key, {})
        
        custom_font_file = string_meta.get("font_file")
        if custom_font_file and custom_font_file in self.mw.all_font_maps:
            return self.mw.all_font_maps[custom_font_file]
            
        return self.mw.font_map

    def restart_application(self):
        log_info("Restarting application...")
        self.mw.close()
        QProcess.startDetached(sys.executable, sys.argv)

    def rebuild_unsaved_block_indices(self):
        self.mw.unsaved_block_indices.clear()
        for block_idx, _ in self.mw.edited_data.keys():
            self.mw.unsaved_block_indices.add(block_idx)
        if hasattr(self.mw, 'block_list_widget'):
             self.mw.block_list_widget.viewport().update()

    def execute_find_next_shortcut(self):
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
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self.mw, "Find", f"Not found: \"{query_to_use}\"")

    def execute_find_previous_shortcut(self):
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
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self.mw, "Find", f"Not found: \"{query_to_use}\"")

    def handle_panel_find_next(self, query, case_sensitive, search_in_original, ignore_tags, is_fuzzy):
        self.mw.search_handler.find_next(query, case_sensitive, search_in_original, ignore_tags, is_fuzzy)

    def handle_panel_find_previous(self, query, case_sensitive, search_in_original, ignore_tags, is_fuzzy):
        self.mw.search_handler.find_previous(query, case_sensitive, search_in_original, ignore_tags, is_fuzzy)

    def toggle_search_panel(self):
        if self.mw.search_panel_widget.isVisible():
            self.hide_search_panel()
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
        self.mw.search_panel_widget.setVisible(False)
        self.mw.search_handler.clear_all_search_highlights()

    def load_all_data_for_path(self, original_file_path, manually_set_edited_path=None, is_initial_load_from_settings=False):
        self.mw.app_action_handler.load_all_data_for_path(original_file_path, manually_set_edited_path, is_initial_load_from_settings)
        self.rebuild_unsaved_block_indices()
        for editor_widget in [self.mw.preview_text_edit, self.mw.original_text_edit, self.mw.edited_text_edit]:
            if editor_widget:
                editor_widget.line_width_warning_threshold_pixels = self.mw.line_width_warning_threshold_pixels
                editor_widget.font_map = self.mw.font_map
                editor_widget.game_dialog_max_width_pixels = self.mw.game_dialog_max_width_pixels
                if hasattr(editor_widget, 'updateLineNumberAreaWidth'):
                    editor_widget.updateLineNumberAreaWidth(0)

    def apply_text_wrap_settings(self):
        preview_wrap_mode = self.mw.preview_text_edit.WidgetWidth if self.mw.preview_wrap_lines else self.mw.preview_text_edit.NoWrap
        editors_wrap_mode = self.mw.edited_text_edit.WidgetWidth if self.mw.editors_wrap_lines else self.mw.edited_text_edit.NoWrap
        if hasattr(self.mw, 'preview_text_edit'): self.mw.preview_text_edit.setLineWrapMode(preview_wrap_mode)
        if hasattr(self.mw, 'original_text_edit'): self.mw.original_text_edit.setLineWrapMode(editors_wrap_mode)
        if hasattr(self.mw, 'edited_text_edit'): self.mw.edited_text_edit.setLineWrapMode(editors_wrap_mode)

    def reconfigure_all_highlighters(self):
        # Compose newline CSS
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
        self.mw.last_selected_block_index = self.mw.current_block_idx
        self.mw.last_selected_string_index = self.mw.current_string_idx
        
        if self.mw.edited_text_edit:
            self.mw.last_cursor_position_in_edited = self.mw.edited_text_edit.textCursor().position()
            self.mw.last_edited_text_edit_scroll_value_v = self.mw.edited_text_edit.verticalScrollBar().value()
            self.mw.last_edited_text_edit_scroll_value_h = self.mw.edited_text_edit.horizontalScrollBar().value()
        
        if self.mw.preview_text_edit:
            self.mw.last_preview_text_edit_scroll_value_v = self.mw.preview_text_edit.verticalScrollBar().value()
        if self.mw.original_text_edit:
            self.mw.last_original_text_edit_scroll_value_v = self.mw.original_text_edit.verticalScrollBar().value()
            self.mw.last_original_text_edit_scroll_value_h = self.mw.original_text_edit.horizontalScrollBar().value()

        if self.mw.search_panel_widget:
            self.mw.search_history_to_save = self.mw.search_panel_widget.get_history()
        
        # Save UI Session State for the current file/project
        current_path = None
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project_file_path:
            current_path = self.mw.project_manager.project_file_path
        elif self.mw.json_path:
            current_path = self.mw.json_path
            
        if current_path:
            state = self.mw.ui_updater.get_tree_state()
            state.update({
                "cursor_pos": self.mw.last_cursor_position_in_edited,
                "v_scroll": self.mw.last_edited_text_edit_scroll_value_v,
                "h_scroll": self.mw.last_edited_text_edit_scroll_value_h,
                "preview_v_scroll": self.mw.last_preview_text_edit_scroll_value_v,
                "original_v_scroll": self.mw.last_original_text_edit_scroll_value_v
            })
            self.mw.settings_manager.session_state.set_state_for_file(str(current_path), state)
            self.mw.settings_manager.set("last_opened_path", str(current_path))

        self.mw.window_was_maximized_on_close = self.mw.isMaximized()
        if self.mw.window_was_maximized_on_close:
            self.mw.window_normal_geometry_on_close = self.mw.normalGeometry()
        else:
            self.mw.window_normal_geometry_on_close = self.mw.geometry()


    def restore_state_after_settings_load(self):
        from utils.logging_utils import log_info
        log_info("Restoring state after settings load.")
        
        if hasattr(self.mw, 'window_geometry_to_restore') and self.mw.window_geometry_to_restore:
            geom_dict = self.mw.window_geometry_to_restore
            if all(k in geom_dict for k in ('x', 'y', 'width', 'height')):
                self.mw.setGeometry(geom_dict['x'], geom_dict['y'], geom_dict['width'], geom_dict['height'])
            if hasattr(self.mw, 'window_was_maximized_at_save') and self.mw.window_was_maximized_at_save:
                self.mw.showMaximized()

        # Determine which path to auto-open
        path_to_open = getattr(self.mw, 'last_opened_path', "")
        if not path_to_open and hasattr(self.mw, 'recent_projects') and self.mw.recent_projects:
            # Fallback to the most recent project if no specific last_opened_path
            path_to_open = self.mw.recent_projects[0]
        
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