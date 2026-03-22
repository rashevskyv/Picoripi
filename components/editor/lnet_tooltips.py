from PyQt5.QtWidgets import QMainWindow, QToolTip, QApplication
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QTextCursor
from typing import Optional

class LNETTooltipLogic:
    def __init__(self, editor):
        self.editor = editor

    def find_warning_tooltip_at(self, pos: QPoint) -> Optional[str]:
        # Get line under mouse
        cursor = self.editor.cursorForPosition(pos)
        block = cursor.block()
        if not block.isValid():
            return None
        
        line_idx_in_widget = block.blockNumber() 
        main_window = self.editor.window()
        if not hasattr(main_window, 'data_store') or not hasattr(main_window.data_store, 'current_block_idx'):
            return None
            
        block_idx = main_window.data_store.current_block_idx
        problems = set()
        
        is_preview = self.editor.objectName() == "preview_text_edit"
        is_editor = self.editor.objectName() in ["original_text_edit", "edited_text_edit"]

        if is_preview:
            string_idx = line_idx_in_widget
            if hasattr(main_window, 'displayed_string_indices') and main_window.data_store.displayed_string_indices:
                if 0 <= line_idx_in_widget < len(main_window.data_store.displayed_string_indices):
                    string_idx = main_window.data_store.displayed_string_indices[line_idx_in_widget]
                else:
                    string_idx = -1

            if string_idx != -1:
                for key, probs in getattr(main_window, 'problems_per_subline', {}).items():
                    if key[0] == block_idx and key[1] == string_idx:
                        problems.update(probs)
        else:
            if not hasattr(main_window, 'current_string_idx'):
                return None
            string_idx = main_window.data_store.current_string_idx
            problems = getattr(main_window, 'problems_per_subline', {}).get((block_idx, string_idx, line_idx_in_widget), set())
        
        tooltip_lines = []
        
        # Check for Unsaved Changes indicator (*)
        is_unsaved = False
        if is_preview:
            is_unsaved = (block_idx, string_idx) in getattr(main_window, 'edited_data', {})
        elif is_editor and string_idx != -1:
            is_unsaved = (block_idx, string_idx) in getattr(main_window, 'edited_data', {})
        
        if is_unsaved:
             tooltip_lines.append("<b>*</b>: Unsaved changes")

        # Check for Metadata indicators in Preview
        if is_preview:
            string_meta = getattr(main_window, 'string_metadata', {}).get((block_idx, string_idx), {})
            if "font_file" in string_meta or "width" in string_meta:
                meta_info = []
                if "font_file" in string_meta:
                    from pathlib import Path
                    font_name = Path(string_meta['font_file']).name
                    meta_info.append(f"font (<b>{font_name}</b>)")
                if "width" in string_meta:
                    meta_info.append(f"width (<b>{string_meta['width']}px</b>)")
                
                tooltip_lines.append(f"<span style='color: DarkViolet;'>■</span>: Line has individual settings: {', '.join(meta_info)}")

        if problems:
            problem_definitions = main_window.current_game_rules.get_problem_definitions() if main_window.current_game_rules else {}
            for prob_id in sorted(list(problems)):
                prob_def = problem_definitions.get(prob_id, {})
                desc = prob_def.get("description", prob_id)
                name = prob_def.get("name", "")
                
                detection_config = getattr(main_window, 'detection_enabled', {})
                if not detection_config.get(prob_id, True):
                    continue

                if name:
                    tooltip_lines.append(f"<b>{name}</b>: {desc}")
                else:
                    tooltip_lines.append(desc)
        
        return "<br><br>".join(tooltip_lines) if tooltip_lines else None
