from PyQt5.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem, QToolTip
from PyQt5.QtGui import QPainter, QColor, QPalette, QBrush, QPen, QFontMetrics, QFont, QIcon
from PyQt5.QtCore import QRect, Qt, QPoint, QSize, QModelIndex, QEvent
from utils.logging_utils import log_debug
from utils.constants import LT_PREVIEW_SELECTED_LINE_COLOR, DT_PREVIEW_SELECTED_LINE_COLOR

class CustomListItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.list_widget = parent
        
        self.problem_indicator_strip_width = 3 
        self.problem_indicator_strip_spacing = 2 
        self.max_problem_indicators = 3 

        self.color_marker_size = 8 
        self.color_marker_spacing = 3
        self.max_color_markers = 0 
        
        self.fixed_number_area_width_base_font_size = 10
        self.fixed_number_area_width_base_pixels = 58
        
        self.padding_after_number_area = 2 
        self.padding_after_color_marker_zone = 2
        self.padding_after_problem_indicator_zone = 2 
        self.indicator_v_offset = 2 

        self.marker_qcolors = {
            "red": QColor(Qt.red),
            "green": QColor(Qt.green),
            "blue": QColor(Qt.blue),
        }

    def _get_current_number_area_width(self, option: QStyleOptionViewItem) -> int:
        font_to_use = option.font
        if not font_to_use.family():
            font_for_metrics = QFont()
        else:
            font_for_metrics = font_to_use

        current_font_size = font_for_metrics.pointSize()
        if current_font_size <= 0: current_font_size = self.fixed_number_area_width_base_font_size

        scaled_width = int(self.fixed_number_area_width_base_pixels * \
                           (current_font_size / self.fixed_number_area_width_base_font_size))
        return max(scaled_width, 24)

    def _get_problem_indicator_zone_width(self) -> int:
        # Indicators are now drawn INSIDE the wider number area
        return 0
    
    def _get_color_marker_zone_width(self) -> int:
        if self.max_color_markers == 0: return 0
        return (self.color_marker_size * self.max_color_markers) + \
               (self.color_marker_spacing * (self.max_color_markers -1))

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        default_hint = super().sizeHint(option, index)
        font_to_use = option.font
        if not font_to_use.family():
            font_for_metrics = QFont()
        else:
            font_for_metrics = font_to_use

        fm = QFontMetrics(font_for_metrics)
        min_height = fm.height() + 6 

        current_number_area_width = self._get_current_number_area_width(option)
        problem_indicator_zone_total_width = self._get_problem_indicator_zone_width()
        color_marker_zone_total_width = self._get_color_marker_zone_width()

        calculated_width = current_number_area_width + \
                           self.padding_after_number_area + \
                           color_marker_zone_total_width + \
                           (self.padding_after_color_marker_zone if color_marker_zone_total_width > 0 else 0) + \
                           problem_indicator_zone_total_width + \
                           (self.padding_after_problem_indicator_zone if problem_indicator_zone_total_width > 0 else 0) + \
                           fm.horizontalAdvance(str(index.data(Qt.DisplayRole))) + 20

        return QSize(max(default_hint.width(), calculated_width), max(default_hint.height(), min_height))

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        is_selected = option.state & QStyle.State_Selected
        is_drag_hover = False
        if hasattr(self.list_widget, '_custom_drop_target') and self.list_widget._custom_drop_target:
            target_item, drop_pos = self.list_widget._custom_drop_target
            if drop_pos == "On" and target_item is self.list_widget.itemFromIndex(index):
                is_drag_hover = True
        
        if is_selected or is_drag_hover:
            highlight_color = option.palette.highlight().color() if is_selected else QColor("#0078D7")
            painter.fillRect(option.rect, highlight_color)
        else:
            is_alternate = option.features & QStyleOptionViewItem.Alternate
            bg_brush = option.palette.alternateBase() if is_alternate else option.palette.base()
            painter.fillRect(option.rect, bg_brush)
        
        main_window = self.list_widget.window() if self.list_widget else None
        theme = 'light'
        if main_window and hasattr(main_window, 'theme'):
            theme = main_window.theme

        item_rect = option.rect
        current_number_area_width = self._get_current_number_area_width(option)

        if theme == 'dark':
            if is_selected or is_drag_hover:
                number_area_bg = QColor("#0078D7").darker(110)
                number_text_color = option.palette.color(QPalette.HighlightedText)
            else:
                number_area_bg = QColor("#383838")
                number_text_color = QColor("#B0B0B0")
        else:
            if is_selected or is_drag_hover:
                number_area_bg = QColor("#0078D7").darker(105)
                number_text_color = QColor(Qt.white)
            else:
                number_area_bg = QColor("#F0F0F0")
                number_text_color = QColor(Qt.darkGray)
        
        active_color_markers_for_block = set()
        block_idx_data = index.data(Qt.UserRole)
        category_name = index.data(Qt.UserRole + 10)
        merged_folder_ids = index.data(Qt.UserRole + 2) # For compacted folders
        
        problem_definitions = {}
        block_problem_counts = {}
        has_unsaved_changes_in_item = False

        if main_window:
            pm = getattr(main_window, 'project_manager', None)
            project = pm.project if pm else None
            edited_keys = getattr(main_window, 'edited_data', {})
            unsaved_blocks = getattr(main_window, 'unsaved_block_indices', set())

            # 1. Determine Unsaved changes (*)
            if category_name:
                # ITEM is a Category (Virtual Sub-block)
                # Show star ONLY if this specific category has edited lines
                if project and block_idx_data is not None:
                    block_map = getattr(main_window, 'block_to_project_file_map', {})
                    proj_b_idx = block_map.get(block_idx_data, block_idx_data)
                    if 0 <= proj_b_idx < len(project.blocks):
                        block = project.blocks[proj_b_idx]
                        category = next((c for c in block.categories if c.name == category_name), None)
                        if category:
                            # Check if any line index belonging to this category is in edited_data
                            has_unsaved_changes_in_item = any(
                                (block_idx_data, l_idx) in edited_keys 
                                for l_idx in category.line_indices
                            )
            elif merged_folder_ids:
                # ITEM is a Folder (possibly compacted)
                # Show star if ANY block inside this folder subtree is unsaved
                if project:
                    # Collect ALL project block indices in this folder tree
                    all_p_indices = set()
                    for folder_id in merged_folder_ids:
                         all_p_indices.update(pm.get_all_block_indices_under_folder(folder_id))
                    
                    # If any edited data block maps to one of these project blocks, show star
                    block_map = getattr(main_window, 'block_to_project_file_map', {})
                    has_unsaved_changes_in_item = any(
                        block_map.get(data_idx) in all_p_indices 
                        for data_idx in unsaved_blocks
                    )
            elif block_idx_data is not None:
                # ITEM is a regular Block (Physical)
                has_unsaved_changes_in_item = block_idx_data in unsaved_blocks

            # 2. Other indicators
            if block_idx_data is not None:
                if hasattr(main_window, 'block_handler') and hasattr(main_window.block_handler, 'get_block_color_markers'):
                    active_color_markers_for_block = main_window.block_handler.get_block_color_markers(block_idx_data)

                if hasattr(main_window, 'current_game_rules') and main_window.current_game_rules:
                    problem_definitions = main_window.current_game_rules.get_problem_definitions()

                if hasattr(main_window, 'ui_updater') and hasattr(main_window.ui_updater, '_get_aggregated_problems_for_block'):
                    block_problem_counts = main_window.ui_updater._get_aggregated_problems_for_block(block_idx_data, category_name=category_name)


        # 1. Calculate Problem Colors Early
        problem_indicator_colors_to_draw = []
        if problem_definitions and block_problem_counts:
            sorted_block_problem_ids = sorted(
                block_problem_counts.keys(),
                key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)
            )
            for problem_id in sorted_block_problem_ids:
                if block_problem_counts[problem_id] > 0:
                    if len(problem_indicator_colors_to_draw) >= self.max_problem_indicators: break
                    problem_def = problem_definitions.get(problem_id)
                    if problem_def and "color" in problem_def:
                        indicator_color = QColor(problem_def["color"])
                        if indicator_color.alpha() < 120 and theme == 'dark':
                            indicator_color.setAlpha(180)
                        if indicator_color not in problem_indicator_colors_to_draw:
                            problem_indicator_colors_to_draw.append(indicator_color)

        # 2. Draw Number Gutter
        number_rect = QRect(item_rect.left(), item_rect.top(), current_number_area_width, item_rect.height())
        painter.fillRect(number_rect, number_area_bg)

        # Status Zone (Right side of gutter)
        # Increased to 32px for wider 5px shift stack
        indicator_zone_w = 32
        number_label_rect = number_rect.adjusted(0, 0, -indicator_zone_w, 0)
        status_rect_in_gutter = number_rect.adjusted(number_rect.width() - indicator_zone_w, 0, 0, 0)

        # Draw Number Text
        painter.setPen(number_text_color)
        current_font = option.font
        if not current_font.family(): current_font = QFont()
        painter.setFont(current_font)
        number_text = f"* {index.row() + 1}" if has_unsaved_changes_in_item else str(index.row() + 1)
        painter.drawText(number_label_rect, Qt.AlignCenter | Qt.TextShowMnemonic, number_text)

        # 3. Draw Icon(s) and Warnings in the SAME zone
        decoration = index.data(Qt.DecorationRole)
        compaction_type = index.data(Qt.UserRole + 3) # 1: Folder/Folder, 2: Folder/Block
        merged_ids = index.data(Qt.UserRole + 2) or []
        icon_size = 14
        style = main_window.style()
        icon_y = status_rect_in_gutter.top() + (status_rect_in_gutter.height() - icon_size) // 2
        
        def draw_stacked_icon(icon_obj, target_rect, p):
            # No stroke, just draw the icon
            icon_obj.paint(p, target_rect)

        if compaction_type in [1, 2] and merged_ids:
            icons_to_draw = []
            max_icons = 3 
            subset = merged_ids[:max_icons]
            
            # 1. Add folder icons for the merged chain
            for f_id in subset:
                icons_to_draw.append(style.standardIcon(QStyle.SP_DirIcon))
            
            # 2. If it's a folder-block compaction, add the file icon as the top layer
            if compaction_type == 2 and len(icons_to_draw) < max_icons:
                icons_to_draw.append(style.standardIcon(QStyle.SP_FileIcon))
            elif compaction_type == 2 and len(icons_to_draw) == max_icons:
                # Replace the last folder icon with a file icon if we reached the limit
                icons_to_draw[-1] = style.standardIcon(QStyle.SP_FileIcon)
            
            base_x = status_rect_in_gutter.left() + 2
            # Total shift is (num_icons - 1) * 3
            # We compensate icon_y to keep the stack centered
            total_v_shift = (len(icons_to_draw) - 1) * 3
            start_y_offset = - (total_v_shift // 2)
            
            # Draw in FORWARD order: root item first (index 0), then nested ones on top
            for i, icon_to_use in enumerate(icons_to_draw):
                shift_x = i * 5 # 5px right shift
                shift_y = i * 3 # 3px down shift
                rect = QRect(base_x + shift_x, icon_y + start_y_offset + shift_y, icon_size, icon_size)
                draw_stacked_icon(icon_to_use, rect, painter)
                
        elif decoration:
            # Regular item icon
            icon = QIcon(decoration)
            if not icon.isNull():
                icon_rect = QRect(status_rect_in_gutter.left() + 2, icon_y, icon_size, icon_size)
                draw_stacked_icon(icon, icon_rect, painter)

        # Draw Warning Strips (at the far right of the status zone)
        if problem_indicator_colors_to_draw:
            strip_x = status_rect_in_gutter.right() - (len(problem_indicator_colors_to_draw) * (self.problem_indicator_strip_width + 1)) - 1
            v_offset = self.indicator_v_offset + 1
            for color in problem_indicator_colors_to_draw:
                strip_rect = QRect(strip_x,
                                   status_rect_in_gutter.top() + v_offset,
                                   self.problem_indicator_strip_width,
                                   status_rect_in_gutter.height() - 2 * v_offset)
                painter.fillRect(strip_rect, color)
                strip_x += self.problem_indicator_strip_width + 1

        # 4. Draw Main Text
        text_start_x = number_rect.right() + self.padding_after_number_area
        
        # Calculate available text space
        string_count_text = ""
        count_width = 0
        if main_window and block_idx_data is not None and hasattr(main_window, 'data'):
            count = 0
            if category_name and hasattr(main_window, 'project_manager') and main_window.project_manager.project:
                pm = main_window.project_manager
                block_map = getattr(main_window, 'block_to_project_file_map', {})
                proj_b_idx = block_map.get(block_idx_data, block_idx_data)
                if proj_b_idx < len(pm.project.blocks):
                    block = pm.project.blocks[proj_b_idx]
                    category = next((c for c in block.categories if c.name == category_name), None)
                    if category:
                        count = len(category.line_indices)
            elif 0 <= block_idx_data < len(main_window.data):
                block_data = main_window.data[block_idx_data]
                if isinstance(block_data, list):
                    count = len(block_data)

            if count > 0 or not category_name:
                string_count_text = f"[{count}]"
                metrics = QFontMetrics(current_font)
                count_width = metrics.horizontalAdvance(string_count_text) + 10

        if string_count_text:
            count_rect = QRect(item_rect.right() - count_width, item_rect.top(), count_width, item_rect.height())
            painter.setPen(number_text_color)
            painter.drawText(count_rect, Qt.AlignCenter, string_count_text)
        
        header_end = item_rect.right() - count_width - 4
        available_text_w = header_end - text_start_x
        text_rect = QRect(text_start_x, item_rect.top(), max(30, available_text_w), item_rect.height())
        
        full_text = str(index.data(Qt.DisplayRole) or "")
        metrics = QFontMetrics(current_font)
        
        # 1. Split text into "Name" and "Metadata"
        import re
        # Find LAST occurrence of metadata in brackets or parentheses
        # Using [\[({\] to satisfy nested set check
        metadata_match = re.search(r'(\s*[\[({].*[\]})]\s*)$', full_text)
        
        painter.save()
        if metadata_match:
            meta_str = metadata_match.group(1)
            name_str = full_text[:metadata_match.start()]
            
            meta_w = metrics.horizontalAdvance(meta_str)
            name_w = metrics.horizontalAdvance(name_str)
            total_w = text_rect.width()

            # Priority: NAME is black, METADATA is gray
            # Since we have horizontal scrolling, we should be less aggressive with elision.
            if total_w > name_w + meta_w:
                painter.setPen(option.palette.color(QPalette.HighlightedText if (is_selected or is_drag_hover) else QPalette.Text))
                painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, name_str)
                name_actual_w = metrics.horizontalAdvance(name_str)
                meta_rect = text_rect.adjusted(name_actual_w, 0, 0, 0)
                if not (is_selected or is_drag_hover):
                    painter.setPen(QColor(140, 140, 140) if theme == 'light' else QColor(160, 160, 160))
                painter.drawText(meta_rect, Qt.AlignLeft | Qt.AlignVCenter, meta_str)
            else:
                # Still prioritize name. 
                painter.setPen(option.palette.color(QPalette.HighlightedText if (is_selected or is_drag_hover) else QPalette.Text))
                # If we have some space, show more of the name
                elided_name = metrics.elidedText(name_str, Qt.ElideRight, max(total_w - 5, 20))
                painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, elided_name)
                
                # Metadata only if we have extra space (rare if total_w < name_w + meta_w)
                name_disp_w = metrics.horizontalAdvance(elided_name)
                if total_w - name_disp_w > 20:
                    meta_rect = text_rect.adjusted(name_disp_w, 0, 0, 0)
                    elided_meta = metrics.elidedText(meta_str, Qt.ElideRight, total_w - name_disp_w)
                    if not (is_selected or is_drag_hover):
                        painter.setPen(QColor(140, 140, 140) if theme == 'light' else QColor(160, 160, 160))
                    painter.drawText(meta_rect, Qt.AlignLeft | Qt.AlignVCenter, elided_meta)
        else:
            # No metadata
            painter.setPen(option.palette.color(QPalette.HighlightedText if (is_selected or is_drag_hover) else QPalette.Text))
            # Less aggressive elision
            elided_all = metrics.elidedText(full_text, Qt.ElideRight, max(text_rect.width(), 20))
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, elided_all)
        painter.restore()

        painter.restore()

    def handle_tooltip(self, event, view, option, index):
        mouse_pos = event.pos()
        item_rect = option.rect
        main_window = self.list_widget.window() if self.list_widget else None
        if not main_window: return

        current_number_area_width = self._get_current_number_area_width(option)
        number_rect = QRect(item_rect.left(), item_rect.top(), current_number_area_width, item_rect.height())
        
        if number_rect.contains(mouse_pos):
            block_idx = index.data(Qt.UserRole)
            if block_idx is not None:
                tooltip_text = self._get_problems_tooltip_text(main_window, block_idx)
                if tooltip_text:
                    QToolTip.showText(event.globalPos(), tooltip_text, view)
                    return
        
        QToolTip.hideText()

    def _get_problems_tooltip_text(self, main_window, block_idx) -> str:
        problem_definitions = {}
        if hasattr(main_window, 'current_game_rules') and main_window.current_game_rules:
            problem_definitions = main_window.current_game_rules.get_problem_definitions()
        
        if hasattr(main_window, 'ui_updater') and hasattr(main_window.ui_updater, '_get_aggregated_problems_for_block'):
            block_problem_counts = main_window.ui_updater._get_aggregated_problems_for_block(block_idx)
            tooltip_lines = []
            if problem_definitions and block_problem_counts:
                sorted_ids = sorted(block_problem_counts.keys(), key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99))
                for pid in sorted_ids:
                    count = block_problem_counts[pid]
                    if count > 0:
                        prob_def = problem_definitions.get(pid, {})
                        name = prob_def.get("name", pid)
                        desc = prob_def.get("description", "")
                        tooltip_lines.append(f"<b>{name}</b>: {count} cases<br><i>{desc}</i>")
            
            if tooltip_lines:
                return "<br><br>".join(tooltip_lines)
        return ""

    def helpEvent(self, event, view, option, index) -> bool:
        if event.type() == QEvent.ToolTip:
            self.handle_tooltip(event, view, option, index)
            return True
        return super().helpEvent(event, view, option, index)

    def updateEditorGeometry(self, editor, option, index):
        item_rect = option.rect
        current_number_area_width = self._get_current_number_area_width(option)
        text_start_x = item_rect.left() + current_number_area_width + self.padding_after_number_area
        
        # The editor should fill the space from the end of the gutter to the end of the item
        editor_rect = QRect(text_start_x, item_rect.top(), item_rect.right() - text_start_x, item_rect.height())
        editor.setGeometry(editor_rect)
