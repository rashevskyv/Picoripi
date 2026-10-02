"""Tooltips for warnings and tags under the mouse in the editor."""
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QColor
from typing import Optional
import re


def _format_warning_dot(raw_color) -> str:
    """Format an opaque RGB colored dot (bullet) for warning tooltips."""
    if raw_color is None:
        return ""
    if isinstance(raw_color, QColor):
        if raw_color.isValid():
            return f"<span style='color: #{raw_color.red():02x}{raw_color.green():02x}{raw_color.blue():02x};'>●</span> "
        return ""
    if isinstance(raw_color, (list, tuple)) and len(raw_color) >= 3:
        try:
            r, g, b = int(raw_color[0]), int(raw_color[1]), int(raw_color[2])
            return f"<span style='color: #{r:02x}{g:02x}{b:02x};'>●</span> "
        except (TypeError, ValueError):
            return ""
    if isinstance(raw_color, str) and raw_color.strip():
        qc = QColor(raw_color)
        if qc.isValid():
            return f"<span style='color: #{qc.red():02x}{qc.green():02x}{qc.blue():02x};'>●</span> "
    return ""


class LNETTooltipLogic:
    """L n e t tooltip logic implementation."""
    def __init__(self, editor):
        """Initialize a new instance."""
        self.editor = editor

    def find_warning_tooltip_at(self, pos: QPoint) -> Optional[str]:
        # Get line under mouse
        """Find warning tooltip at."""
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
            if hasattr(main_window.data_store, 'displayed_string_indices') and main_window.data_store.displayed_string_indices:
                if 0 <= line_idx_in_widget < len(main_window.data_store.displayed_string_indices):
                    displayed = main_window.data_store.displayed_string_indices[line_idx_in_widget]
                    if isinstance(displayed, tuple) and len(displayed) == 2:
                        block_idx, string_idx = displayed
                    else:
                        string_idx = displayed
                else:
                    string_idx = -1

            if string_idx != -1:
                problems_map = getattr(main_window.data_store, 'problems_per_subline', {})
                for key, probs in problems_map.items():
                    if key[0] == block_idx and key[1] == string_idx:
                        problems.update(probs)
        else:
            if not hasattr(main_window.data_store, 'current_string_idx'):
                return None
            string_idx = main_window.data_store.current_string_idx
            block_idx = getattr(main_window.data_store, 'physical_block_idx', block_idx)
            problems = getattr(main_window.data_store, 'problems_per_subline', {}).get((block_idx, string_idx, line_idx_in_widget), set())
        
        tooltip_lines = []
        
        # Check for Unsaved Changes indicator (*)
        is_unsaved = False
        edited_data = getattr(main_window.data_store, 'edited_data', {})
        if is_preview:
            is_unsaved = (block_idx, string_idx) in edited_data
        elif is_editor and string_idx != -1:
            is_unsaved = (block_idx, string_idx) in edited_data
        
        if is_unsaved:
             tooltip_lines.append("<b>*</b>: Unsaved changes")

        # Check for Metadata indicators in Preview
        if is_preview:
            string_meta = getattr(main_window.data_store, 'string_metadata', {}).get((block_idx, string_idx), {})
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

                dot = _format_warning_dot(prob_def.get("color"))
                if name:
                    tooltip_lines.append(f"{dot}<b>{name}</b>: {desc}")
                else:
                    tooltip_lines.append(f"{dot}{desc}")
        
        if tooltip_lines:
            font_size = getattr(self.editor.window(), 'tooltip_font_size', 11)
            return f"<div style='font-size: {font_size}px;'>" + "<br><br>".join(tooltip_lines) + "</div>"
        return None

    def find_tag_tooltip_at(self, pos: QPoint) -> Optional[str]:
        """Return the active game plugin's explanation for the tag under the cursor."""
        cursor = self.editor.cursorForPosition(pos)
        block = cursor.block()
        if not block.isValid():
            return None
        position = cursor.positionInBlock()
        block_text = block.text()
        if not isinstance(block_text, str):
            return None
        for match in re.finditer(r"\{[^{}]+\}", block_text):
            if match.start() <= position < match.end():
                rules = getattr(self.editor.window(), "current_game_rules", None)
                if rules and hasattr(rules, "get_tag_tooltip"):
                    return rules.get_tag_tooltip(match.group(0)) or None
                return None
        return None
