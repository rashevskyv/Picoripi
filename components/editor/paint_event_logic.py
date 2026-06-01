import re
from PyQt5.QtGui import QPainter, QColor, QPen, QPaintEvent, QTextLine
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMainWindow
from utils.utils import calculate_string_width, remove_all_tags, convert_dots_to_spaces_from_editor
from .constants import PAIR_SEPARATOR_LINE_COLOR, PAIR_SEPARATOR_LINE_STYLE, PAIR_SEPARATOR_LINE_THICKNESS

class LNETPaintEventLogic:
    def __init__(self, editor, helpers):
        self.editor = editor
        self.helpers = helpers

    def execute_paint_event(self, event: QPaintEvent):
        painter_lines = QPainter(self.editor.viewport())
        
        is_preview = self.editor.objectName() == "preview_text_edit"
        
        # Draw visual line backgrounds (zebra stripes) - Now handled by ExtraSelections in highlightManager
        # We keep the block loop if needed for separators, but backgrounds are removed here.
        block = self.editor.firstVisibleBlock()
        viewport_offset = self.editor.contentOffset()
        
        doc_visual_line_index = 0
        temp_block = self.editor.document().firstBlock()
        while temp_block.isValid() and temp_block != block:
            if temp_block.layout():
                doc_visual_line_index += temp_block.layout().lineCount()
            temp_block = temp_block.next()

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

        if hasattr(main_window, 'data_store') and hasattr(main_window, 'helper'):
            block_idx = main_window.data_store.current_block_idx
            string_idx = main_window.data_store.current_string_idx
            if block_idx != -1 and string_idx != -1:
                font_map = main_window.helper.get_font_map_for_string(block_idx, string_idx)

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
                        if hasattr(self.editor, 'custom_line_numbers') and self.editor.custom_line_numbers:
                            # In Review Dialog: Draw separator AFTER a block that has a custom number, 
                            # ONLY if the next block is a spacer (None)
                            if doc_visual_line_index < len(self.editor.custom_line_numbers):
                                current_custom_num = self.editor.custom_line_numbers[doc_visual_line_index]
                                if current_custom_num is not None:
                                    next_idx = doc_visual_line_index + 1
                                    if next_idx < len(self.editor.custom_line_numbers):
                                        if self.editor.custom_line_numbers[next_idx] is None:
                                            draw_separator = True
                        else:
                            # Default behavior: draw line every page_size lines
                            if (doc_visual_line_index + 1) % page_size == 0:
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
                                    int(line_bottom_y_in_viewport) -1,
                                    self.editor.viewport().width(),
                                    int(line_bottom_y_in_viewport) -1
                                )
                    doc_visual_line_index += 1

            # Draw dynamic line width guidelines if enabled
            if draw_guidelines and layout.lineCount() > 0:
                block_text_raw = convert_dots_to_spaces_from_editor(block.text())
                block_width_px = calculate_string_width(block_text_raw.rstrip(), font_map, icon_sequences=sequences)

                # Determine pen styling based on the whole block's width
                if block_width_px > limit_px:
                    pen_guide = QPen(QColor(255, 0, 0, 180))
                    pen_guide.setWidth(2)
                    pen_guide.setStyle(Qt.SolidLine)
                else:
                    pen_guide = QPen(self.editor.width_threshold_line_color)
                    color = QColor(self.editor.width_threshold_line_color)
                    color.setAlpha(120)
                    pen_guide.setColor(color)
                    pen_guide.setWidth(self.editor.width_threshold_line_width)
                    pen_guide.setStyle(self.editor.width_threshold_line_style)

                # Draw vertical tick for each visual line of the block individually
                for i in range(layout.lineCount()):
                    line = layout.lineAt(i)
                    if not line.isValid():
                        continue

                    block_num = block.blockNumber()
                    if not hasattr(self.editor, 'guideline_positions'):
                        self.editor.guideline_positions = {}

                    if (block_num, i) not in self.editor.guideline_positions:
                        self.editor.calculate_block_guidelines(block, font_map, sequences, limit_px)

                    limit_x = self.editor.guideline_positions.get((block_num, i))
                    if limit_x is False or limit_x is None:
                        continue

                    y_top = block_rect.top() + line.rect().top()
                    y_bottom = block_rect.top() + line.rect().bottom()
                    painter_lines.setPen(pen_guide)
                    painter_lines.drawLine(int(limit_x), int(y_top), int(limit_x), int(y_bottom))

            if block_rect.bottom() > self.editor.viewport().height():
                break
            block = block.next()

        painter_lines.end()