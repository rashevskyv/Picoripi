# --- START OF FILE components/editor/line_number_area_paint_logic.py ---
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtWidgets import QMainWindow, QTextEdit
from utils.logging_utils import log_debug
from utils.utils import calculate_string_width, remove_all_tags, convert_dots_to_spaces_from_editor, ALL_TAGS_PATTERN

class LNETLineNumberAreaPaintLogic:

    def __init__(self, editor, helpers, main_window):
        self.editor = editor
        self.helpers = helpers
        self.mw = main_window
        self.metadata_indicator_color = QColor(148, 0, 211, 180) # DarkViolet

    def execute_paint_event(self, event, painter_device):
        painter = QPainter(painter_device)
        try:
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

            default_bg_color_for_area = self.editor.palette().base().color()
            if self.editor.isReadOnly():
                default_bg_color_for_area = self.editor.palette().window().color().lighter(105)

            total_area_width = self.editor.lineNumberAreaWidth()
            extra_part_width = 0
            if self.editor.objectName() in["original_text_edit", "edited_text_edit"] and hasattr(self.mw, 'font_map') and self.mw.font_map:
                extra_part_width = self.editor.pixel_width_display_area_width
            elif self.editor.objectName() == "preview_text_edit":
                extra_part_width = self.editor.preview_indicator_area_width

            number_part_width = total_area_width - extra_part_width

            current_q_block = self.editor.firstVisibleBlock()
            current_q_block_number_in_editor_doc = current_q_block.blockNumber()
            top = int(self.editor.blockBoundingGeometry(current_q_block).translated(self.editor.contentOffset()).top())
            bottom = top + int(self.editor.blockBoundingRect(current_q_block).height())

            current_font_for_numbers = self.editor.font()
            painter.setFont(current_font_for_numbers)

            odd_bg_color_const = self.editor.lineNumberArea.odd_line_background
            even_bg_color_const = self.editor.lineNumberArea.even_line_background
            number_text_color_const = self.editor.lineNumberArea.number_color

            # ВИПРАВЛЕНО: Відступи для цих рядків збільшено на 4 пробіли, щоб вони знаходились всередині блоку try:
            current_block_idx_data_mw = -1
            current_string_idx_data_mw = -1
            if isinstance(main_window_ref, QMainWindow) and hasattr(main_window_ref, 'data_store'):
                current_block_idx_data_mw = main_window_ref.data_store.current_block_idx
                current_string_idx_data_mw = main_window_ref.data_store.current_string_idx

            while current_q_block.isValid() and top <= event.rect().bottom():
                if current_q_block.isVisible() and bottom >= event.rect().top():
                    line_height = int(self.editor.blockBoundingRect(current_q_block).height())
                    
                    # Basic indexes and state
                    is_preview = self.editor.objectName() == "preview_text_edit"
                    is_editor = self.editor.objectName() in["original_text_edit", "edited_text_edit"]
                    
                    real_idx = current_q_block_number_in_editor_doc
                    if is_preview and hasattr(main_window_ref, 'data_store') and main_window_ref.data_store.displayed_string_indices:
                        if 0 <= current_q_block_number_in_editor_doc < len(main_window_ref.data_store.displayed_string_indices):
                            real_idx = main_window_ref.data_store.displayed_string_indices[current_q_block_number_in_editor_doc]
                        else:
                            real_idx = -1

                    # 1. Determine base number text
                    if hasattr(self.editor, 'custom_line_numbers') and self.editor.custom_line_numbers:
                        if current_q_block_number_in_editor_doc < len(self.editor.custom_line_numbers):
                            custom_num = self.editor.custom_line_numbers[current_q_block_number_in_editor_doc]
                            display_number_for_line_area = str(custom_num) if custom_num is not None else ""
                        else:
                            display_number_for_line_area = str(current_q_block_number_in_editor_doc + 1)
                    else:
                        display_number_for_line_area = str(current_q_block_number_in_editor_doc + 1)
                    
                    # 2. Determine unsaved status from global data_processor state
                    is_unsaved = False
                    if is_preview:
                        if hasattr(main_window_ref, 'data_store') and (current_block_idx_data_mw, real_idx) in main_window_ref.data_store.edited_data:
                            is_unsaved = True
                    elif is_editor and current_string_idx_data_mw != -1:
                        # Check only THIS specific subline (QTextBlock), not the entire string
                        edited_sublines = getattr(main_window_ref, 'edited_sublines', set())
                        if current_q_block_number_in_editor_doc in edited_sublines:
                            is_unsaved = True

                    if is_unsaved and display_number_for_line_area:
                        display_number_for_line_area = f"* {display_number_for_line_area}"

                    number_part_rect = QRect(0, top, number_part_width, line_height)
                    extra_info_part_rect = QRect(number_part_width, top, extra_part_width, line_height)

                    # Check if block has custom background color (e.g., zebra striping in spellcheck dialog)
                    block_format = current_q_block.blockFormat()
                    if block_format.hasProperty(block_format.BackgroundBrush):
                        block_bg_color = block_format.background().color()
                        if block_bg_color.isValid():
                            bg_color_number_area = block_bg_color
                            bg_color_extra_info_area = block_bg_color
                        else:
                            # Default zebra striping
                            bg_color_number_area = even_bg_color_const
                            if (current_q_block_number_in_editor_doc + 1) % 2 != 0:
                                bg_color_number_area = odd_bg_color_const
                            bg_color_extra_info_area = bg_color_number_area
                    else:
                        # Default zebra striping
                        bg_color_number_area = even_bg_color_const
                        if (current_q_block_number_in_editor_doc + 1) % 2 != 0:
                            bg_color_number_area = odd_bg_color_const
                        bg_color_extra_info_area = bg_color_number_area

                    problem_ids_for_this_qtextblock = set()

                    data_line_idx_for_lookup = current_string_idx_data_mw if is_editor else current_q_block_number_in_editor_doc
                    qtextblock_idx_for_lookup = current_q_block_number_in_editor_doc

                    problem_key = (current_block_idx_data_mw, data_line_idx_for_lookup, qtextblock_idx_for_lookup)

                    if isinstance(main_window_ref, QMainWindow) and hasattr(main_window_ref, 'problems_per_subline') and problem_key in main_window_ref.problems_per_subline:
                        problem_ids_for_this_qtextblock = main_window_ref.problems_per_subline[problem_key]

                    filtered_problems = {p_id for p_id in problem_ids_for_this_qtextblock if detection_config.get(p_id, True)}
                    
                    if is_editor and filtered_problems:
                        sorted_probs = sorted(
                            list(filtered_problems),
                            key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)
                        )
                        
                        # 1. Background color for the ENTIRE extra_info_part_rect
                        bg_prob_id = sorted_probs[0]
                        bg_prob_def = problem_definitions.get(bg_prob_id, {})
                        bg_color = QColor(bg_prob_def.get("color", Qt.transparent))
                        
                        # Make background slightly transparent for a better look
                        if bg_color.alpha() > 180:
                            bg_color.setAlpha(160)
                        elif bg_color.alpha() < 100:
                            bg_color.setAlpha(140)

                        painter.fillRect(number_part_rect, bg_color_number_area)
                        painter.fillRect(extra_info_part_rect, bg_color)
                        
                        # 2. Draw other warnings as thin stripes on top of the background
                        if len(sorted_probs) > 1:
                            stripe_w = 3
                            current_stripe_x = extra_info_part_rect.left() + 1
                            for prob_id in sorted_probs[1:]:
                                prob_def = problem_definitions.get(prob_id, {})
                                stripe_color = QColor(prob_def.get("color", Qt.transparent))
                                if stripe_color.isValid():
                                    if stripe_color.alpha() < 180:
                                        stripe_color.setAlpha(220)
                                    
                                    painter.fillRect(current_stripe_x, top + 1, stripe_w, line_height - 2, stripe_color)
                                    current_stripe_x += stripe_w + 1
                                    if current_stripe_x + stripe_w > extra_info_part_rect.right():
                                        break
                    else:
                        painter.fillRect(number_part_rect, bg_color_number_area)
                        painter.fillRect(extra_info_part_rect, bg_color_extra_info_area)

                    painter.setPen(number_text_color_const)
                    painter.drawText(QRect(0, top, number_part_width - 3, line_height), Qt.AlignRight | Qt.AlignVCenter, display_number_for_line_area)

                    if extra_part_width > 0:
                        if is_editor and self.editor.objectName() in["edited_text_edit", "original_text_edit"] and self.mw and hasattr(self.mw, 'font_map') and self.mw.font_map:
                            font_map_for_line = self.mw.helper.get_font_map_for_string(current_block_idx_data_mw, current_string_idx_data_mw)
                            
                            q_block_text_raw_dots_paint_text = current_q_block.text()
                            q_block_text_spaces_paint_text = convert_dots_to_spaces_from_editor(q_block_text_raw_dots_paint_text)
                            
                            icon_sequences = getattr(self.mw, 'icon_sequences',[])
                            pixel_width = calculate_string_width(q_block_text_spaces_paint_text.rstrip(), font_map_for_line, icon_sequences=icon_sequences)
                            width_str_text = str(pixel_width)
                            
                            text_color_for_extra_part = QColor(Qt.darkGray) if theme == 'light' else QColor(Qt.darkGray).darker(120)
                            painter.setPen(text_color_for_extra_part)
                            painter.drawText(QRect(number_part_width, top, extra_part_width -3 , line_height), Qt.AlignRight | Qt.AlignVCenter, width_str_text)

                        elif is_preview and isinstance(main_window_ref, QMainWindow) and current_block_idx_data_mw != -1 and game_rules:
                            indicator_x_start = number_part_width + 2
                            
                            # Use absolute index if possible
                            real_idx = current_q_block_number_in_editor_doc
                            if hasattr(main_window_ref, 'data_store') and main_window_ref.data_store.displayed_string_indices:
                                if 0 <= current_q_block_number_in_editor_doc < len(main_window_ref.data_store.displayed_string_indices):
                                    real_idx = main_window_ref.data_store.displayed_string_indices[current_q_block_number_in_editor_doc]
                                else:
                                    real_idx = -1

                            string_meta = main_window_ref.string_metadata.get((current_block_idx_data_mw, real_idx), {})
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

                            # 2. Warning Indicators (Consolidated with stripes)
                            aggregated_probs = set()
                            preview_prob_key = (current_block_idx_data_mw, real_idx)
                            if real_idx != -1 and hasattr(main_window_ref, 'problems_per_subline'):
                                for key, problems in main_window_ref.problems_per_subline.items():
                                    if key[0] == preview_prob_key[0] and key[1] == preview_prob_key[1]:
                                        aggregated_probs.update(problems)

                            filtered_preview_probs = {p_id for p_id in aggregated_probs if detection_config.get(p_id, True)}

                            if filtered_preview_probs:
                                sorted_preview_probs = sorted(
                                    list(filtered_preview_probs),
                                    key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)
                                )
                                
                                # Style for preview area: only vertical stripes, no full background fill
                                s_x = indicator_x_start
                                s_w = 4
                                for p_id in sorted_preview_probs:
                                    p_def = problem_definitions.get(p_id, {})
                                    s_color = QColor(p_def.get("color", Qt.transparent))
                                    if s_color.isValid():
                                        if s_color.alpha() < 200:
                                            s_color.setAlpha(220)
                                        painter.fillRect(s_x, top + 2, s_w, line_height - 4, s_color)
                                        s_x += s_w + 1
                                        if s_x + s_w > indicator_x_start + 15: # Indicator cap
                                            break

                current_q_block = current_q_block.next()
                top = bottom
                bottom = top + int(self.editor.blockBoundingRect(current_q_block).height())
                current_q_block_number_in_editor_doc += 1
        finally:
            painter.end()