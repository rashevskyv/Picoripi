from pathlib import Path
from utils.constants import APP_VERSION
from utils.utils import calculate_string_width, convert_dots_to_spaces_from_editor, remove_all_tags
from .base_ui_updater import BaseUIUpdater

class TitleStatusBarUpdater(BaseUIUpdater):
    def update_status_bar(self):
        if not hasattr(self.mw, 'edited_text_edit') or not self.mw.edited_text_edit or \
           not all(hasattr(self.mw, label_name) for label_name in ['status_label_part1', 'status_label_part2', 'status_label_part3']):
            return
        
        editor = self.mw.edited_text_edit
        cursor = editor.textCursor()
        
        font_map_for_string = self.mw.helper.get_font_map_for_string(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)
        icon_sequences = getattr(self.mw, 'icon_sequences', [])

        if cursor.hasSelection():
            self.update_status_bar_selection() 
        else:
            block = cursor.block()
            pos_in_block = cursor.positionInBlock()
            
            line_text_with_dots = block.text()
            line_text_with_spaces = convert_dots_to_spaces_from_editor(line_text_with_dots)
            
            line_text_no_all_tags = remove_all_tags(line_text_with_spaces)
            line_len_no_tags = len(line_text_no_all_tags)
            line_len_with_tags = len(line_text_with_spaces)

            text_to_cursor_with_dots = line_text_with_dots[:pos_in_block]
            text_to_cursor_with_spaces = convert_dots_to_spaces_from_editor(text_to_cursor_with_dots)
            
            pixel_width = calculate_string_width(text_to_cursor_with_spaces, font_map_for_string, icon_sequences=icon_sequences)
            
            self.mw.status_label_part1.setText(f"Pos: {pos_in_block}")
            self.mw.status_label_part2.setText(f"Line: {line_len_no_tags}/{line_len_with_tags}")
            self.mw.status_label_part3.setText(f"Width: {pixel_width}px")
        
        self.mw.ui_updater.synchronize_original_cursor()

    def update_status_bar_selection(self):
        if not hasattr(self.mw, 'edited_text_edit') or not self.mw.edited_text_edit or \
           not all(hasattr(self.mw, label_name) for label_name in ['status_label_part1', 'status_label_part2', 'status_label_part3']):
            return
        
        editor = self.mw.edited_text_edit
        cursor = editor.textCursor()
        
        font_map_for_string = self.mw.helper.get_font_map_for_string(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)
        icon_sequences = getattr(self.mw, 'icon_sequences', [])

        if not cursor.hasSelection():
            block = cursor.block()
            pos_in_block = cursor.positionInBlock()
            line_text_with_dots = block.text()
            line_text_with_spaces = convert_dots_to_spaces_from_editor(line_text_with_dots)
            line_text_no_all_tags = remove_all_tags(line_text_with_spaces)
            line_len_no_tags = len(line_text_no_all_tags)
            line_len_with_tags = len(line_text_with_spaces)
            text_to_cursor_with_dots = line_text_with_dots[:pos_in_block]
            text_to_cursor_with_spaces = convert_dots_to_spaces_from_editor(text_to_cursor_with_dots)
            pixel_width = calculate_string_width(text_to_cursor_with_spaces, font_map_for_string, icon_sequences=icon_sequences)
            self.mw.status_label_part1.setText(f"Pos: {pos_in_block}")
            self.mw.status_label_part2.setText(f"Line: {line_len_no_tags}/{line_len_with_tags}")
            self.mw.status_label_part3.setText(f"Width: {pixel_width}px")
            return

        selected_text_with_dots = cursor.selectedText()
        selected_text_with_spaces = convert_dots_to_spaces_from_editor(selected_text_with_dots)
        len_with_tags = len(selected_text_with_spaces)
        selected_text_no_all_tags = remove_all_tags(selected_text_with_spaces)
        len_no_tags = len(selected_text_no_all_tags)
        
        pixel_width = calculate_string_width(selected_text_with_spaces, font_map_for_string, icon_sequences=icon_sequences)
        
        sel_start_abs = cursor.selectionStart()
        sel_start_block_obj = editor.document().findBlock(sel_start_abs)
        sel_start_pos_in_block = sel_start_abs - sel_start_block_obj.position()
        
        self.mw.status_label_part1.setText(f"Sel: {len_no_tags}/{len_with_tags}")
        self.mw.status_label_part2.setText(f"At: {sel_start_pos_in_block}")
        self.mw.status_label_part3.setText(f"Width: {pixel_width}px")

    def clear_status_bar(self):
        if hasattr(self.mw, 'status_label_part1'): self.mw.status_label_part1.setText("Pos: 0")
        if hasattr(self.mw, 'status_label_part2'): self.mw.status_label_part2.setText("Line: 0/0")
        if hasattr(self.mw, 'status_label_part3'): self.mw.status_label_part3.setText("Width: 0px")

    def update_title(self):
        title = f"Picoripi v{APP_VERSION}"
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and hasattr(self.mw.project_manager, 'project') and self.mw.project_manager.project:
            title += f" - [{self.mw.project_manager.project.name}]"
        elif self.mw.data_store.json_path: 
            title += f" - [{Path(self.mw.data_store.json_path).name}]"
        else: 
            title += " - [No File Open]"
        if self.mw.data_store.unsaved_changes: 
            title += " *"
        self.mw.setWindowTitle(title)

    def update_plugin_status_label(self):
        if self.mw.plugin_status_label:
            if self.mw.current_game_rules:
                display_name = self.mw.current_game_rules.get_display_name()
                self.mw.plugin_status_label.setText(f"Plugin: {display_name}")
            else:
                self.mw.plugin_status_label.setText("Plugin: [None]")

    def update_statusbar_paths(self):
        if hasattr(self.mw, 'original_path_label') and self.mw.original_path_label:
            orig_filename = Path(self.mw.data_store.json_path).name if self.mw.data_store.json_path else "[not specified]"
            self.mw.original_path_label.setText(f"Original: {orig_filename}")
            self.mw.original_path_label.setToolTip(self.mw.data_store.json_path if self.mw.data_store.json_path else "Path to original file")
        if hasattr(self.mw, 'edited_path_label') and self.mw.edited_path_label:
            edited_filename = Path(self.mw.data_store.edited_json_path).name if self.mw.data_store.edited_json_path else "[not specified]"
            self.mw.edited_path_label.setText(f"Changes: {edited_filename}")
            self.mw.edited_path_label.setToolTip(self.mw.data_store.edited_json_path if self.mw.data_store.edited_json_path else "Path to changes file")