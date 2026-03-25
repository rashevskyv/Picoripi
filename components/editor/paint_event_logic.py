# --- START OF FILE components/editor/paint_event_logic.py ---
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

            if block_rect.bottom() > self.editor.viewport().height():
                break
            block = block.next()
        
        # Extracted width exceed logic from paintEvent. It should be handled in apply_highlights_to_editor instead.