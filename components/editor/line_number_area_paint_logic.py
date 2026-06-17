from PyQt6.QtGui import QPainter, QColor, QPen, QFont
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtWidgets import QMainWindow, QTextEdit
from utils.logging_utils import log_debug
from utils.utils import calculate_string_width, remove_all_tags, convert_dots_to_spaces_from_editor, ALL_TAGS_PATTERN
from .constants import PAIR_SEPARATOR_LINE_COLOR, PAIR_SEPARATOR_LINE_STYLE, PAIR_SEPARATOR_LINE_THICKNESS

class LNETLineNumberAreaPaintLogic:
    """L n e t line number area paint logic implementation."""

    def __init__(self, editor, helpers, main_window):
        """Initialize a new instance."""
        self.editor = editor
        self.helpers = helpers
        self.mw = main_window
        self.metadata_indicator_color = QColor(148, 0, 211, 180) # DarkViolet

    def execute_paint_event(self, event, painter_device):
        """Execute paint event."""
        painter = QPainter(painter_device)
        try:
            separator_lines = []
            if not self.mw:
                main_window_ref = self.editor.window()
            else:
                main_window_ref = self.mw

            game_rules = None
            problem_definitions = {}
            theme = 'light'
            detection_config = {}
            if isinstance(main_window_ref, QMainWindow):
                if hasattr(main_window_ref, 'current_game_rules') and main_window_ref.current_game_rules:
                    game_rules = main_window_ref.current_game_rules
                    problem_definitions = game_rules.get_problem_definitions()
                if hasattr(main_window_ref, 'theme'):
                    theme = main_window_ref.theme
                if hasattr(main_window_ref, 'detection_enabled'):
                    detection_config = main_window_ref.detection_enabled

            total_area_width = self.editor.lineNumberAreaWidth()
            extra_part_width = 0
            if self.editor.objectName() in["original_text_edit", "edited_text_edit"] and hasattr(main_window_ref, 'font_map') and main_window_ref.font_map:
                extra_part_width = self.editor.pixel_width_display_area_width
            elif self.editor.objectName() == "preview_text_edit":
                extra_part_width = self.editor.preview_indicator_area_width

            number_part_width = total_area_width - extra_part_width

            current_q_block = self.editor.firstVisibleBlock()
            current_q_block_number_in_editor_doc = current_q_block.blockNumber()
            viewport_offset = self.editor.contentOffset()
            block_rect = self.editor.blockBoundingGeometry(current_q_block).translated(viewport_offset)
            top = int(block_rect.top())
            bottom = int(block_rect.bottom())

            painter.setFont(self.editor.font())

            odd_bg_color_const = self.editor.lineNumberArea.odd_line_background
            even_bg_color_const = self.editor.lineNumberArea.even_line_background
            number_text_color_const = self.editor.lineNumberArea.number_color

            current_block_idx_data_mw = -1
            current_string_idx_data_mw = -1
            if isinstance(main_window_ref, QMainWindow) and hasattr(main_window_ref, 'data_store'):
                current_block_idx_data_mw = main_window_ref.data_store.current_block_idx
                current_string_idx_data_mw = main_window_ref.data_store.current_string_idx

            # Prepare mapping for string-level zebra striping if in Review Dialog
            string_color_map = {}
            is_dual_column = hasattr(self.editor, 'custom_subline_numbers') and self.editor.custom_subline_numbers is not None
            if is_dual_column and hasattr(self.editor, 'custom_line_numbers') and self.editor.custom_line_numbers:
                unique_strings = []
                seen = set()
                for snum in self.editor.custom_line_numbers:
                    if snum is not None and snum not in seen:
                        unique_strings.append(snum)
                        seen.add(snum)
                string_color_map = {snum: i % 2 for i, snum in enumerate(unique_strings)}

            while current_q_block.isValid() and top <= event.rect().bottom():
                if current_q_block.isVisible() and bottom >= event.rect().top():
                    line_height = int(self.editor.blockBoundingRect(current_q_block).height())
                    
                    is_preview = self.editor.objectName() == "preview_text_edit"
                    is_editor = self.editor.objectName() in["original_text_edit", "edited_text_edit"]
                    
                    real_idx = current_q_block_number_in_editor_doc
                    if is_preview and hasattr(main_window_ref, 'data_store') and main_window_ref.data_store.displayed_string_indices:
                        if 0 <= current_q_block_number_in_editor_doc < len(main_window_ref.data_store.displayed_string_indices):
                            real_idx = main_window_ref.data_store.displayed_string_indices[current_q_block_number_in_editor_doc]
                        else:
                            real_idx = -1

                    # 1. Determine background colors
                    # Subline-level zebra (right column)
                    bg_color_subline_zebra = even_bg_color_const
                    if (current_q_block_number_in_editor_doc + 1) % 2 != 0:
                        bg_color_subline_zebra = odd_bg_color_const
                    
                    # String-level zebra (left column in review mode)
                    bg_color_string_zebra = bg_color_subline_zebra
                    if is_dual_column:
                        if hasattr(self.editor, 'custom_message_numbers') and self.editor.custom_message_numbers:
                            if current_q_block_number_in_editor_doc < len(self.editor.custom_message_numbers):
                                snum = self.editor.custom_message_numbers[current_q_block_number_in_editor_doc]
                                if snum is not None:
                                    color_idx = string_color_map.get(snum, 0)
                                    bg_color_string_zebra = odd_bg_color_const if color_idx != 0 else even_bg_color_const
                                else:
                                    bg_color_string_zebra = even_bg_color_const # Spacer lines white
                        bg_color_subline_zebra = bg_color_string_zebra

                    bg_color_number_area = bg_color_subline_zebra
                    bg_color_extra_info_area = bg_color_number_area

                    # 2. Determine display numbers
                    display_number_for_line_area = ""
                    subline_number_text = ""
                    
                    if hasattr(self.editor, 'custom_line_numbers') and self.editor.custom_line_numbers:
                        if current_q_block_number_in_editor_doc < len(self.editor.custom_line_numbers):
                            custom_num = self.editor.custom_line_numbers[current_q_block_number_in_editor_doc]
                            display_number_for_line_area = str(custom_num) if custom_num is not None else ""
                    else:
                        display_number_for_line_area = str(current_q_block_number_in_editor_doc + 1)

                    if is_dual_column:
                        if current_q_block_number_in_editor_doc < len(self.editor.custom_subline_numbers):
                            sub_num = self.editor.custom_subline_numbers[current_q_block_number_in_editor_doc]
                            subline_number_text = str(sub_num) if sub_num is not None else ""

                    # 3. Handle unsaved status
                    is_unsaved = False
                    if is_preview:
                        if hasattr(main_window_ref, 'data_store'):
                            if isinstance(real_idx, tuple):
                                if real_idx in main_window_ref.data_store.edited_data:
                                    is_unsaved = True
                            else:
                                if (current_block_idx_data_mw, real_idx) in main_window_ref.data_store.edited_data:
                                    is_unsaved = True
                    elif is_editor and current_string_idx_data_mw != -1:
                        ds = getattr(main_window_ref, 'data_store', None)
                        edited_sublines = getattr(ds, 'edited_sublines', set()) if ds else set()
                        if current_q_block_number_in_editor_doc in edited_sublines:
                            is_unsaved = True

                    # Check if the row has a valid translation to show soft-green background under line number
                    is_translated = False
                    if hasattr(main_window_ref, 'data_processor') and main_window_ref.data_processor:
                        if is_preview and real_idx != -1:
                            if isinstance(real_idx, tuple):
                                is_translated = main_window_ref.data_processor.is_string_translated(real_idx[0], real_idx[1])
                            else:
                                is_translated = main_window_ref.data_processor.is_string_translated(current_block_idx_data_mw, real_idx)
                        elif is_editor and current_string_idx_data_mw != -1:
                            is_translated = main_window_ref.data_processor.is_string_translated(current_block_idx_data_mw, current_string_idx_data_mw)

                    if is_unsaved and display_number_for_line_area:
                        display_number_for_line_area = f"* {display_number_for_line_area}"

                    # Check for custom settings changes if it is a preview line
                    has_meta_changes = False
                    if is_preview:
                        string_meta = {}
                        if main_window_ref and hasattr(main_window_ref, 'string_metadata'):
                            if isinstance(real_idx, tuple):
                                string_meta = main_window_ref.string_metadata.get(real_idx, {})
                            else:
                                string_meta = main_window_ref.string_metadata.get((current_block_idx_data_mw, real_idx), {})
                        
                        default_font = getattr(main_window_ref, 'default_font_file', None)
                        max_width = getattr(main_window_ref, 'game_dialog_max_width_pixels', None)
                        
                        has_custom_font = "font_file" in string_meta and string_meta["font_file"] != default_font
                        has_custom_width = "width" in string_meta and string_meta["width"] != max_width
                        has_meta_changes = has_custom_font or has_custom_width

                    # 4. Painting
                    number_part_rect = QRect(0, top, number_part_width, line_height)
                    extra_info_part_rect = QRect(number_part_width, top, extra_part_width, line_height)

                    if is_dual_column:
                        # Dynamic split based on font metrics
                        fm = painter.fontMetrics()
                        max_str_idx = 1
                        if hasattr(self.editor, 'custom_line_numbers') and self.editor.custom_line_numbers:
                            vals = [v for v in self.editor.custom_line_numbers if v is not None]
                            if vals: max_str_idx = max(vals)
                        
                        str_digits = len(str(max_str_idx))
                        # Room for asterisk if needed
                        asterisk_room = fm.horizontalAdvance('* ') if is_unsaved else 0
                        left_col_w = asterisk_room + fm.horizontalAdvance('9') * str_digits + 12
                        right_col_w = number_part_width - left_col_w
                        
                        painter.fillRect(0, top, left_col_w, line_height, bg_color_string_zebra)
                        if is_translated:
                            green_bg = QColor(46, 139, 87, 40)
                            painter.fillRect(0, top, left_col_w, line_height, green_bg)
                        painter.fillRect(left_col_w, top, right_col_w, line_height, bg_color_subline_zebra)
                        
                        painter.setPen(number_text_color_const)
                        painter.drawText(QRect(0, top, left_col_w - 5, line_height), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, display_number_for_line_area)
                        
                        subline_pen = QColor(number_text_color_const)
                        subline_pen.setAlpha(150)
                        painter.setPen(subline_pen)
                        painter.drawText(QRect(left_col_w, top, right_col_w - 3, line_height), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, subline_number_text)
                    else:
                        painter.fillRect(number_part_rect, bg_color_number_area)
                        if is_translated:
                            green_bg = QColor(46, 139, 87, 40)
                            painter.fillRect(number_part_rect, green_bg)
                        painter.setPen(number_text_color_const)
                        painter.drawText(QRect(0, top, number_part_width - 3, line_height), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, display_number_for_line_area)

                    # Problem markers
                    problem_ids = set()
                    if isinstance(main_window_ref, QMainWindow) and hasattr(main_window_ref, 'data_store') and hasattr(main_window_ref.data_store, 'problems_per_subline'):
                        probs_dict = main_window_ref.data_store.problems_per_subline
                        if is_editor:
                            problem_key = (current_block_idx_data_mw, current_string_idx_data_mw, current_q_block_number_in_editor_doc)
                            problem_ids = probs_dict.get(problem_key, set())
                        elif is_preview:
                            for key, p_set in probs_dict.items():
                                if isinstance(real_idx, tuple):
                                    if key[0] == real_idx[0] and key[1] == real_idx[1]:
                                        problem_ids.update(p_set)
                                else:
                                    if key[0] == current_block_idx_data_mw and key[1] == real_idx:
                                        problem_ids.update(p_set)

                    filtered_problems = {p_id for p_id in problem_ids if detection_config.get(p_id, True)}
                    if is_editor and filtered_problems:
                        sorted_probs = sorted(list(filtered_problems), key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99))
                        N = len(sorted_probs)
                        w = extra_part_width / N
                        for i, p_id in enumerate(sorted_probs):
                            p_def = problem_definitions.get(p_id, {})
                            bg_color = QColor(p_def.get("color", Qt.GlobalColor.transparent))
                            if bg_color.isValid():
                                bg_color.setAlpha(160)
                                x_pos = number_part_width + i * w
                                # Handle last stripe to exactly cover pixel borders
                                current_w = int(w) + 1 if i < N - 1 else (number_part_width + extra_part_width - int(x_pos))
                                part_rect = QRect(int(x_pos), top, int(current_w), line_height)
                                painter.fillRect(part_rect, bg_color)
                    else:
                        painter.fillRect(extra_info_part_rect, bg_color_extra_info_area)

                    # Extra display: pixel width or indicators
                    if extra_part_width > 0:
                        if is_editor and hasattr(main_window_ref, 'font_map') and main_window_ref.font_map:
                            font_map = main_window_ref.helper.get_font_map_for_string(current_block_idx_data_mw, current_string_idx_data_mw)
                            default_tag_mappings = getattr(main_window_ref, 'default_tag_mappings', {}) if main_window_ref else {}
                            pixel_width = None
                            if game_rules and hasattr(game_rules, 'calculate_string_width_override'):
                                override_val = game_rules.calculate_string_width_override(
                                    convert_dots_to_spaces_from_editor(current_q_block.text()).rstrip(), font_map
                                )
                                if isinstance(override_val, (int, float)):
                                    pixel_width = override_val
                            if pixel_width is None:
                                pixel_width = calculate_string_width(convert_dots_to_spaces_from_editor(current_q_block.text()).rstrip(), font_map, icon_sequences=getattr(main_window_ref, 'icon_sequences', []), default_tag_mappings=default_tag_mappings)
                            painter.setPen(QColor(Qt.GlobalColor.darkGray) if theme == 'light' else QColor(Qt.GlobalColor.darkGray).darker(120))
                            painter.drawText(QRect(number_part_width, top, extra_part_width - 3, line_height), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(pixel_width))
                        elif is_preview:
                            # Draw metadata indicators in preview area
                            string_meta = {}
                            if main_window_ref and hasattr(main_window_ref, 'string_metadata'):
                                if isinstance(real_idx, tuple):
                                    string_meta = main_window_ref.string_metadata.get(real_idx, {})
                                else:
                                    string_meta = main_window_ref.string_metadata.get((current_block_idx_data_mw, real_idx), {})
                            
                            indicator_x_start = number_part_width + 2
                            has_custom_font = "font_file" in string_meta
                            has_custom_width = "width" in string_meta

                            if has_custom_font or has_custom_width:
                                indicator_rect = QRect(indicator_x_start, top + 2, self.editor.lineNumberArea.preview_indicator_width, line_height - 4)
                                if has_custom_font and has_custom_width:
                                    painter.fillRect(indicator_rect, self.metadata_indicator_color)
                                elif has_custom_font:
                                    top_half = QRect(indicator_rect.left(), indicator_rect.top(), indicator_rect.width(), indicator_rect.height() // 2)
                                    painter.fillRect(top_half, self.metadata_indicator_color)
                                elif has_custom_width:
                                    bottom_half = QRect(indicator_rect.left(), indicator_rect.top() + indicator_rect.height() // 2, indicator_rect.width(), indicator_rect.height() // 2)
                                    painter.fillRect(bottom_half, self.metadata_indicator_color)
                                indicator_x_start += self.editor.lineNumberArea.preview_indicator_width + self.editor.lineNumberArea.preview_indicator_spacing

                            # Preview area warning stripes
                            if filtered_problems:
                                s_x = indicator_x_start
                                s_w = 4
                                for p_id in sorted(list(filtered_problems), key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)):
                                    p_def = problem_definitions.get(p_id, {})
                                    s_color = QColor(p_def.get("color", Qt.GlobalColor.transparent))
                                    if s_color.isValid():
                                        s_color.setAlpha(220)
                                        painter.fillRect(s_x, top + 2, s_w, line_height - 4, s_color)
                                        s_x += s_w + 1
                                        if s_x + s_w > indicator_x_start + 15:
                                            break

                    # Draw separator line in LineNumberArea to match the text viewport separator
                    draw_separator = False
                    if not is_preview and is_dual_column:
                        if hasattr(self.editor, 'custom_message_numbers') and self.editor.custom_message_numbers:
                            if current_q_block_number_in_editor_doc < len(self.editor.custom_message_numbers):
                                msg_num = self.editor.custom_message_numbers[current_q_block_number_in_editor_doc]
                                if msg_num is not None:
                                    next_idx = current_q_block_number_in_editor_doc + 1
                                    is_last = (next_idx >= len(self.editor.custom_message_numbers))
                                    if is_last:
                                        draw_separator = True
                                    else:
                                        next_msg_num = self.editor.custom_message_numbers[next_idx]
                                        if next_msg_num != msg_num:
                                            draw_separator = True
                        elif hasattr(self.editor, 'custom_line_numbers') and self.editor.custom_line_numbers:
                            if current_q_block_number_in_editor_doc < len(self.editor.custom_line_numbers):
                                subline_num = None
                                if hasattr(self.editor, 'custom_subline_numbers') and self.editor.custom_subline_numbers:
                                    if current_q_block_number_in_editor_doc < len(self.editor.custom_subline_numbers):
                                        subline_num = self.editor.custom_subline_numbers[current_q_block_number_in_editor_doc]
                                
                                if subline_num is not None:
                                    next_idx = current_q_block_number_in_editor_doc + 1
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

                    if draw_separator:
                        layout = current_q_block.layout()
                        line_bottom_y = float(bottom)
                        if layout and layout.lineCount() > 0:
                            line = layout.lineAt(layout.lineCount() - 1)
                            if line.isValid():
                                line_bottom_y = block_rect.top() + line.rect().bottom()
                        separator_lines.append(line_bottom_y)

                current_q_block = current_q_block.next()
                if current_q_block.isValid():
                    block_rect = self.editor.blockBoundingGeometry(current_q_block).translated(viewport_offset)
                    top = int(block_rect.top())
                    bottom = int(block_rect.bottom())
                current_q_block_number_in_editor_doc += 1

            if separator_lines:
                pen_lines = QPen(PAIR_SEPARATOR_LINE_COLOR)
                pen_lines.setStyle(PAIR_SEPARATOR_LINE_STYLE)
                pen_lines.setWidth(PAIR_SEPARATOR_LINE_THICKNESS)
                painter.setPen(pen_lines)
                for y in separator_lines:
                    painter.drawLine(0, int(y), total_area_width, int(y))
        except Exception as e:
            from utils.logging_utils import log_error
            log_error(f"Error in LineNumberAreaPaintLogic: {e}", exc_info=True)
        finally:
            painter.end()