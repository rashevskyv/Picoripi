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
                    # Don't draw lines if custom line numbers are set (e.g., spellcheck dialog)
                    if not is_preview and not (hasattr(self.editor, 'custom_line_numbers') and self.editor.custom_line_numbers):
                        # Default behavior: draw line every page_size lines
                        if (doc_visual_line_index + 1) % page_size == 0:
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
        
        if self.editor.objectName() == "edited_text_edit" and hasattr(self.editor, 'highlightManager'):
            if self.editor.highlightManager:
                self.editor.highlightManager._width_exceed_char_selections = [] 

        main_window = self.editor.window()
        if not isinstance(main_window, QMainWindow):
            return
        
        if self.editor.objectName() == "edited_text_edit":
            block = self.editor.firstVisibleBlock()
            while block.isValid() and block.isVisible():
                layout = block.layout()
                if not layout:
                    block = block.next()
                    continue
                
                string_meta = main_window.string_metadata.get((main_window.data_store.current_block_idx, main_window.data_store.current_string_idx), {})
                current_threshold_game_px = string_meta.get("width", self.editor.line_width_warning_threshold_pixels)

                q_block_text_raw_dots = block.text() 

                for i in range(layout.lineCount()):
                    line: QTextLine = layout.lineAt(i)
                    if not line.isValid():
                        continue

                    raw_line_text_with_tags_and_display_chars = q_block_text_raw_dots[line.textStart() : line.textStart() + line.textLength()]
                    line_text_with_spaces_and_tags = convert_dots_to_spaces_from_editor(raw_line_text_with_tags_and_display_chars)
                    line_text_no_tags_for_width_calc = remove_all_tags(line_text_with_spaces_and_tags).rstrip()

                    if not line_text_no_tags_for_width_calc:
                        continue
                    
                    font_map_for_line = main_window.helper.get_font_map_for_string(main_window.data_store.current_block_idx, main_window.data_store.current_string_idx)
                    visual_line_width_game_px = calculate_string_width(line_text_no_tags_for_width_calc, font_map_for_line)
                    
                    if visual_line_width_game_px > current_threshold_game_px:
                        words_in_no_tag_segment = []
                        for match in re.finditer(r'\S+', line_text_no_tags_for_width_calc):
                            words_in_no_tag_segment.append({'text': match.group(0), 'start_idx_in_segment': match.start()})
                        
                        target_char_index_in_no_tag_segment = 0
                        if words_in_no_tag_segment:
                            found_target_word = False
                            for word_info in reversed(words_in_no_tag_segment):
                                text_before_word_no_tags = line_text_no_tags_for_width_calc[:word_info['start_idx_in_segment']]
                                width_before_word_game_px = calculate_string_width(text_before_word_no_tags, font_map_for_line)
                                if width_before_word_game_px <= current_threshold_game_px:
                                    target_char_index_in_no_tag_segment = word_info['start_idx_in_segment']
                                    found_target_word = True
                                    break
                            if not found_target_word:
                                target_char_index_in_no_tag_segment = 0
                        
                        actual_char_index_in_raw_qtextline = self.helpers._map_no_tag_index_to_raw_text_index(
                            raw_line_text_with_tags_and_display_chars,
                            line_text_no_tags_for_width_calc, 
                            target_char_index_in_no_tag_segment
                        )
                        
                        char_index_in_block = line.textStart() + actual_char_index_in_raw_qtextline
                        
                        if hasattr(self.editor, 'highlightManager') and self.editor.highlightManager:
                            highlight_color = QColor("#90EE90") 
                            self.editor.highlightManager.add_width_exceed_char_highlight(block, char_index_in_block, highlight_color)
                        break 
                block = block.next()
            
            if hasattr(self.editor, 'highlightManager') and self.editor.highlightManager:
                self.editor.highlightManager.applyHighlights()