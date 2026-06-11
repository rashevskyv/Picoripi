import re
from PyQt6.QtGui import QPainter, QColor, QPen, QPaintEvent, QTextLine
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow
from utils.utils import calculate_string_width, remove_all_tags, convert_dots_to_spaces_from_editor
from .constants import PAIR_SEPARATOR_LINE_COLOR, PAIR_SEPARATOR_LINE_STYLE, PAIR_SEPARATOR_LINE_THICKNESS

class LNETPaintEventLogic:
    def __init__(self, editor, helpers):
        self.editor = editor
        self.helpers = helpers

    def execute_paint_event(self, event: QPaintEvent):
        painter_lines = QPainter(self.editor.viewport())
        try:
            is_preview = self.editor.objectName() == "preview_text_edit"
            
            # Draw visual line backgrounds (zebra stripes) - Now handled by ExtraSelections in highlightManager
            # We keep the block loop if needed for separators, but backgrounds are removed here.
            block = self.editor.firstVisibleBlock()
            viewport_offset = self.editor.contentOffset()
            


            main_window = self.editor.window()
            page_size = 4  # Default
            if isinstance(main_window, QMainWindow):
                # Always use lines_per_page from settings if available
                page_size = getattr(main_window, 'lines_per_page', None)
                if page_size is None:
                    # Fall back to game rules method only if lines_per_page is not set
                    if hasattr(main_window, 'current_game_rules') and main_window.current_game_rules:
                        if hasattr(main_window.current_game_rules, 'get_editor_page_size'):
                            page_size = main_window.current_game_rules.get_editor_page_size()
                        else:
                            page_size = 4
                    else:
                        page_size = 4
                # Debug: print once per paint to see what value is used
                if not hasattr(self.editor, '_last_logged_page_size') or self.editor._last_logged_page_size != page_size:
                    from utils.logging_utils import log_debug
                    log_debug(f"Using page_size={page_size} for horizontal lines")
                    self.editor._last_logged_page_size = page_size

            draw_guidelines = (
                self.editor.line_width_warning_threshold_pixels > 0
                and self.editor.objectName() != "preview_text_edit"
                and getattr(self.editor, 'show_width_guideline', True)
            )
            
            limit_px = self.editor.line_width_warning_threshold_pixels
            main_window = self.editor.window()
            font_map = getattr(self.editor, 'font_map', {})
            if not font_map and hasattr(main_window, 'font_map'):
                font_map = main_window.font_map

            block_idx = -1
            string_idx = -1
            if hasattr(main_window, 'data_store') and hasattr(main_window, 'helper'):
                block_idx = main_window.data_store.current_block_idx
                string_idx = main_window.data_store.current_string_idx
                if block_idx != -1 and string_idx != -1:
                    font_map = main_window.helper.get_font_map_for_string(block_idx, string_idx)

            # Calculate max allowed physical width (Game Dialog Limit)
            max_allowed_width = getattr(main_window, 'game_dialog_max_width_pixels', limit_px)
            if block_idx != -1 and string_idx != -1:
                string_meta = getattr(main_window, 'string_metadata', {}).get((block_idx, string_idx), {})
                if "width" in string_meta:
                    custom_w = string_meta["width"]
                    max_allowed_width = custom_w
                    global_max = getattr(main_window, 'game_dialog_max_width_pixels', limit_px)
                    standard_threshold = getattr(main_window, 'line_width_warning_threshold_pixels', limit_px)
                    if global_max > 0:
                        limit_px = int(custom_w * (standard_threshold / global_max))
                    else:
                        limit_px = custom_w

            sequences = getattr(main_window, 'icon_sequences', []) if main_window else []
            left_margin = viewport_offset.x() + self.editor.document().documentMargin()

            while block.isValid() and block.layout():
                layout = block.layout()
                block_rect = self.editor.blockBoundingGeometry(block).translated(viewport_offset)

                if not is_preview:
                    pen_lines = QPen(PAIR_SEPARATOR_LINE_COLOR)
                    pen_lines.setStyle(PAIR_SEPARATOR_LINE_STYLE)
                    pen_lines.setWidth(PAIR_SEPARATOR_LINE_THICKNESS)
                    painter_lines.setPen(pen_lines)

                    for i in range(layout.lineCount()):
                        line = layout.lineAt(i)
                        if not line.isValid():
                            continue

                        # Check if we should draw separator line
                        draw_separator = False
                        if not is_preview:
                            if i == layout.lineCount() - 1:
                                current_block_num = block.blockNumber()
                                if hasattr(self.editor, 'custom_message_numbers') and self.editor.custom_message_numbers:
                                    if current_block_num < len(self.editor.custom_message_numbers):
                                        msg_num = self.editor.custom_message_numbers[current_block_num]
                                        if msg_num is not None:
                                            next_idx = current_block_num + 1
                                            is_last = (next_idx >= len(self.editor.custom_message_numbers))
                                            if is_last:
                                                draw_separator = True
                                            else:
                                                next_msg_num = self.editor.custom_message_numbers[next_idx]
                                                if next_msg_num != msg_num:
                                                    draw_separator = True
                                elif hasattr(self.editor, 'custom_line_numbers') and self.editor.custom_line_numbers:
                                    if current_block_num < len(self.editor.custom_line_numbers):
                                        subline_num = None
                                        if hasattr(self.editor, 'custom_subline_numbers') and self.editor.custom_subline_numbers:
                                            if current_block_num < len(self.editor.custom_subline_numbers):
                                                subline_num = self.editor.custom_subline_numbers[current_block_num]
                                        
                                        if subline_num is not None:
                                            next_idx = current_block_num + 1
                                            is_last = (next_idx >= len(self.editor.custom_line_numbers))
                                            if is_last:
                                                draw_separator = True
                                            else:
                                                next_subline_num = None
                                                if hasattr(self.editor, 'custom_subline_numbers') and self.editor.custom_subline_numbers:
                                                    if next_idx < len(self.editor.custom_subline_numbers):
                                                        next_subline_num = self.editor.custom_subline_numbers[next_idx]
                                                if next_subline_num == 1 or next_subline_num is None:
                                                    draw_separator = True
                                else:
                                    # Default behavior: draw line every page_size logical blocks (lines)
                                    if (current_block_num + 1) % page_size == 0:
                                        draw_separator = True

                        if draw_separator:
                             line_bottom_y_in_viewport = block_rect.top() + line.rect().bottom()

                             has_next_line_in_block = (i < layout.lineCount() - 1)
                             has_next_block = block.next().isValid()

                             if has_next_line_in_block or has_next_block:
                                if line_bottom_y_in_viewport >= -PAIR_SEPARATOR_LINE_THICKNESS and \
                                   line_bottom_y_in_viewport <= self.editor.viewport().height() + PAIR_SEPARATOR_LINE_THICKNESS:
                                    painter_lines.drawLine(
                                        0,
                                        int(line_bottom_y_in_viewport),
                                        self.editor.viewport().width(),
                                        int(line_bottom_y_in_viewport)
                                    )

                # Draw dynamic line width guidelines if enabled
                if draw_guidelines and layout.lineCount() > 0:
                    block_num = block.blockNumber()
                    if not hasattr(self.editor, 'guideline_positions'):
                        self.editor.guideline_positions = {}

                    # Draw vertical tick for each visual line of the block individually
                    for i in range(layout.lineCount()):
                        line = layout.lineAt(i)
                        if not line.isValid():
                            continue

                        if (block_num, i) not in self.editor.guideline_positions:
                            default_tag_mappings = getattr(main_window, 'default_tag_mappings', {}) if main_window else {}
                            self.editor.calculate_block_guidelines(block, font_map, sequences, limit_px, default_tag_mappings=default_tag_mappings)

                        val = self.editor.guideline_positions.get((block_num, i))
                        if val is False or val is None:
                            continue

                        if isinstance(val, tuple):
                            limit_x, is_exceeded = val
                        else:
                            limit_x = val
                            is_exceeded = False

                        # Determine pen styling based on the guideline limit (is_exceeded)
                        if is_exceeded:
                            pen_guide = QPen(QColor(255, 0, 0, 180))
                            pen_guide.setWidth(2)
                            pen_guide.setStyle(Qt.PenStyle.SolidLine)
                        else:
                            pen_guide = QPen(self.editor.width_threshold_line_color)
                            color = QColor(self.editor.width_threshold_line_color)
                            color.setAlpha(120)
                            pen_guide.setColor(color)
                            pen_guide.setWidth(self.editor.width_threshold_line_width)
                            pen_guide.setStyle(self.editor.width_threshold_line_style)

                        y_top = block_rect.top() + line.rect().top()
                        y_bottom = block_rect.top() + line.rect().bottom()
                        painter_lines.setPen(pen_guide)
                        painter_lines.drawLine(int(limit_x), int(y_top), int(limit_x), int(y_bottom))

                if block_rect.bottom() > self.editor.viewport().height():
                    break
                block = block.next()
        finally:
            painter_lines.end()