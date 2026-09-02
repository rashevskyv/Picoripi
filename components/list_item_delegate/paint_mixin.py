import re

from PyQt6.QtWidgets import QStyle, QStyleOptionViewItem
from PyQt6.QtGui import QPainter, QColor, QFontMetrics, QFont, QIcon, QPalette
from PyQt6.QtCore import QRect, Qt, QPoint
from utils.logging_utils import log_debug

_ITEM_METADATA_TAIL = re.compile(r'(\s*[\[({].*[\]})]\s*)$')


class CustomListItemPaintMixin:
    """Paint implementation for list item delegate."""

    def _project_indices_for_folders(self, pm, folder_ids):
        key = (id(getattr(pm, "project", None)), tuple(folder_ids or ()))
        cache = getattr(self, "_folder_proj_cache", None)
        if cache is None:
            cache = {}
            self._folder_proj_cache = cache
        hit = cache.get(key)
        if hit is not None:
            return hit
        indices = set()
        for folder_id in folder_ids or ():
            indices.update(pm.get_all_block_indices_under_folder(folder_id))
        if len(cache) > 256:
            cache.clear()
        cache[key] = indices
        return indices

    def _data_indices_for_project_block(self, mw, proj_b_idx):
        block_map = getattr(mw, "block_to_project_file_map", {}) or {}
        indices = [d_idx for d_idx, p_idx in block_map.items() if p_idx == proj_b_idx]
        if not indices:
            indices = [proj_b_idx]
        elif proj_b_idx not in indices:
            indices.append(proj_b_idx)
        return indices

    def _block_has_layout_overrides(self, mw, block_idx, line_indices=None) -> bool:
        dsp = getattr(mw, "data_processor", None)
        if dsp is None or not hasattr(dsp, "get_overrides_set"):
            return False
        overrides = dsp.get_overrides_set(block_idx)
        if not overrides:
            return False
        if line_indices is None:
            return True
        return bool(overrides.intersection(line_indices))

    def _project_block_is_unsaved(self, block_map, unsaved_blocks, project_block_idx) -> bool:
        if not unsaved_blocks:
            return False
        if not isinstance(block_map, dict) or not block_map:
            return project_block_idx in unsaved_blocks
        key = (id(block_map), id(unsaved_blocks), len(unsaved_blocks))
        cached = getattr(self, "_unsaved_proj_cache", None)
        if cached is None or cached[0] != key:
            proj_unsaved = {block_map.get(data_idx, data_idx) for data_idx in unsaved_blocks}
            self._unsaved_proj_cache = (key, proj_unsaved)
            cached = self._unsaved_proj_cache
        return project_block_idx in cached[1]

    def _item_has_layout_overrides(self, mw, index) -> bool:
        if not hasattr(mw, "string_metadata"):
            return False
        block_idx_data = index.data(Qt.ItemDataRole.UserRole)
        category_name = index.data(Qt.ItemDataRole.UserRole + 10)
        merged_folder_ids = index.data(Qt.ItemDataRole.UserRole + 2)
        pm = getattr(mw, "project_manager", None)
        project = pm.project if pm else None

        if category_name and project and block_idx_data is not None:
            data_indices = self._data_indices_for_project_block(mw, block_idx_data)
            if 0 <= block_idx_data < len(project.blocks):
                category = next(
                    (c for c in project.blocks[block_idx_data].categories if c.name == category_name),
                    None,
                )
                if category:
                    lines = set(category.line_indices)
                    return any(
                        self._block_has_layout_overrides(mw, b_idx, lines) for b_idx in data_indices
                    )
            return False
        if merged_folder_ids and project and pm:
            all_p_indices = self._project_indices_for_folders(pm, merged_folder_ids)
            block_map = getattr(mw, "block_to_project_file_map", {}) or {}
            data_indices = [d_idx for d_idx, p_idx in block_map.items() if p_idx in all_p_indices]
            data_indices = set(data_indices).union(all_p_indices)
            return any(self._block_has_layout_overrides(mw, b_idx) for b_idx in data_indices)
        if block_idx_data is not None and block_idx_data != -2:
            data_indices = self._data_indices_for_project_block(mw, block_idx_data)
            return any(self._block_has_layout_overrides(mw, b_idx) for b_idx in data_indices)
        return False

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        """Paint."""
        painter.save()
        try:
            self._paint_item(painter, option, index)
        finally:
            painter.restore()

    def _paint_item(self, painter: QPainter, option: QStyleOptionViewItem, index):
        is_selected = option.state & QStyle.StateFlag.State_Selected
        is_drag_hover = False
        if hasattr(self.list_widget, '_custom_drop_target') and self.list_widget._custom_drop_target:
            target_item, drop_pos = self.list_widget._custom_drop_target
            if drop_pos == "On" and target_item is self.list_widget.itemFromIndex(index):
                is_drag_hover = True
        
        if is_selected or is_drag_hover:
            highlight_color = option.palette.highlight().color() if is_selected else self._color_selected_default
            painter.fillRect(option.rect, highlight_color)
        else:
            is_alternate = option.features & QStyleOptionViewItem.ViewItemFeature.Alternate
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
                number_area_bg = self._color_dark_selected_bg
                number_text_color = option.palette.color(QPalette.HighlightedText)
            else:
                number_area_bg = self._color_dark_normal_bg
                number_text_color = self._color_dark_normal_text
        else:
            if is_selected or is_drag_hover:
                number_area_bg = self._color_light_selected_bg
                number_text_color = self._color_white
            else:
                number_area_bg = self._color_light_normal_bg
                number_text_color = self._color_dark_gray
        
        active_color_markers_for_block = set()
        block_idx_data = index.data(Qt.ItemDataRole.UserRole)
        category_name = index.data(Qt.ItemDataRole.UserRole + 10)
        merged_folder_ids = index.data(Qt.ItemDataRole.UserRole + 2) # For compacted folders
        
        problem_definitions = {}
        block_problem_counts = {}
        has_unsaved_changes_in_item = False
        is_virtual_row = bool(index.data(Qt.ItemDataRole.UserRole + 12))
        has_metadata_changes = bool(main_window) and self._item_has_layout_overrides(main_window, index)

        if main_window:
            pm = getattr(main_window, 'project_manager', None)
            project = pm.project if pm else None
            ds = getattr(main_window, 'data_store', None)
            edited_keys = getattr(ds, 'edited_data', {}) if ds else {}
            unsaved_blocks = getattr(ds, 'unsaved_block_indices', set()) if ds else set()

            stored_unsaved = index.data(Qt.ItemDataRole.UserRole + 21)
            if stored_unsaved is not None:
                has_unsaved_changes_in_item = bool(stored_unsaved)
            else:
                if is_virtual_row:
                    s_idx_data = index.data(Qt.ItemDataRole.UserRole + 1)
                    has_unsaved_changes_in_item = (block_idx_data, s_idx_data) in edited_keys
                elif category_name:
                    if project and block_idx_data is not None:
                        block_map = getattr(main_window, 'block_to_project_file_map', {})
                        if isinstance(block_map, dict):
                            data_indices = [d_idx for d_idx, p_idx in block_map.items() if p_idx == block_idx_data]
                        else:
                            data_indices = []
                        if not data_indices:
                            data_indices = [block_idx_data]
                        if 0 <= block_idx_data < len(project.blocks):
                            category = next((c for c in project.blocks[block_idx_data].categories if c.name == category_name), None)
                            if category:
                                has_unsaved_changes_in_item = any(
                                    (d_idx, l_idx) in edited_keys
                                    for d_idx in data_indices
                                    for l_idx in category.line_indices
                                )
                elif merged_folder_ids:
                    if project:
                        all_p_indices = self._project_indices_for_folders(pm, merged_folder_ids)
                        block_map = getattr(main_window, 'block_to_project_file_map', {})
                        if isinstance(block_map, dict) and block_map:
                            has_unsaved_changes_in_item = any(
                                block_map.get(data_idx) in all_p_indices
                                for data_idx in unsaved_blocks
                            )
                        else:
                            has_unsaved_changes_in_item = any(
                                data_idx in all_p_indices for data_idx in unsaved_blocks
                            )
                elif block_idx_data is not None:
                    block_map = getattr(main_window, 'block_to_project_file_map', {})
                    has_unsaved_changes_in_item = self._project_block_is_unsaved(
                        block_map, unsaved_blocks, block_idx_data
                    )

            # 2. Other indicators — counts are stamped on the item at populate.
            if block_idx_data is not None:
                if hasattr(main_window, 'block_handler') and hasattr(main_window.block_handler, 'get_block_color_markers'):
                    active_color_markers_for_block = main_window.block_handler.get_block_color_markers(block_idx_data)

                if hasattr(main_window, 'current_game_rules') and main_window.current_game_rules:
                    problem_definitions = main_window.current_game_rules.get_problem_definitions()

                stored_counts = index.data(Qt.ItemDataRole.UserRole + 20)
                if isinstance(stored_counts, dict):
                    block_problem_counts = stored_counts


        # 1. Calculate Problem Colors Early
        problem_indicator_colors_to_draw = []
        
        # Add metadata custom indicator strip (purple) first if has_metadata_changes is True
        if has_metadata_changes:
            metadata_color = self._color_metadata_indicator_dark if theme == 'dark' else self._color_metadata_indicator
            problem_indicator_colors_to_draw.append(metadata_color)

        # Progress bar fill — stamped at populate; compute only if the item is stale.
        stored_pct = index.data(Qt.ItemDataRole.UserRole + 22)
        if isinstance(stored_pct, (int, float)) and not isinstance(stored_pct, bool):
            percentage = float(stored_pct)
        else:
            percentage = 0.0

        if percentage > 0.0:
            x_start = item_rect.left() + current_number_area_width
            fill_w = int((item_rect.width() - current_number_area_width) * percentage)
            if fill_w > 0:
                progress_rect = QRect(x_start, item_rect.top(), fill_w, item_rect.height())
                # Soft pastel-green background with 25 alpha (SeaGreen color)
                painter.fillRect(progress_rect, self._color_progress_bg)
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
        painter.drawText(number_label_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextShowMnemonic, number_text)

        # 3. Draw Icon(s) and Warnings in the SAME zone
        decoration = index.data(Qt.ItemDataRole.DecorationRole)
        compaction_type = index.data(Qt.ItemDataRole.UserRole + 3) # 1: Folder/Folder, 2: Folder/Block
        merged_ids = index.data(Qt.ItemDataRole.UserRole + 2) or []
        icon_size = 14
        style = main_window.style()
        icon_y = status_rect_in_gutter.top() + (status_rect_in_gutter.height() - icon_size) // 2
        
        def draw_stacked_icon(icon_obj, target_rect, p):
            # No stroke, just draw the icon
            """Draw stacked icon."""
            icon_obj.paint(p, target_rect)

        if compaction_type in [1, 2] and merged_ids:
            icons_to_draw = []
            max_icons = 3 
            subset = merged_ids[:max_icons]
            
            # 1. Add folder icons for the merged chain
            for f_id in subset:
                icons_to_draw.append(style.standardIcon(QStyle.StandardPixmap.SP_DirIcon))
            
            # 2. If it's a folder-block compaction, add the file icon as the top layer
            if compaction_type == 2 and len(icons_to_draw) < max_icons:
                icons_to_draw.append(style.standardIcon(QStyle.StandardPixmap.SP_FileIcon))
            elif compaction_type == 2 and len(icons_to_draw) == max_icons:
                # Replace the last folder icon with a file icon if we reached the limit
                icons_to_draw[-1] = style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)
            
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
                
                # Draw cloud if it's a category
                category_name = index.data(Qt.ItemDataRole.UserRole + 10)
                if category_name:
                    painter.save()
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    cloud_color = self._color_cloud_light if theme == "light" else self._color_cloud_dark
                    cloud_border = self._color_cloud_border_light if theme == "light" else self._color_cloud_border_dark
                    painter.setPen(cloud_border)
                    painter.setBrush(cloud_color)
                    
                    cx = icon_rect.right() - 2
                    cy = icon_rect.top() + 4
                    
                    # Draw 3 overlapping circles
                    painter.drawEllipse(QPoint(cx - 3, cy), 3, 3)
                    painter.drawEllipse(QPoint(cx + 3, cy), 3, 3)
                    painter.drawEllipse(QPoint(cx, cy - 2), 4, 4)
                    
                    # Fill the gap over the bottom border of the top circle
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRect(cx - 2, cy - 1, 5, 4)
                    painter.restore()

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
        if not is_virtual_row and main_window and block_idx_data is not None and hasattr(main_window, 'data_store') and hasattr(main_window.data_store, 'data'):
            count = 0
            ch_mappings = index.data(Qt.ItemDataRole.UserRole + 13)
            if ch_mappings is not None:
                count = len(ch_mappings)
            elif category_name and hasattr(main_window, 'project_manager') and main_window.project_manager.project:
                pm = main_window.project_manager
                block_map = getattr(main_window, 'block_to_project_file_map', {})
                proj_b_idx = block_map.get(block_idx_data, block_idx_data)
                if proj_b_idx < len(pm.project.blocks):
                    block = pm.project.blocks[proj_b_idx]
                    category = next((c for c in block.categories if c.name == category_name), None)
                    if category:
                        count = len(category.line_indices)
            elif 0 <= block_idx_data < len(main_window.data_store.data):
                block_data = main_window.data_store.data[block_idx_data]
                if isinstance(block_data, list):
                    count = len(block_data)

            if count > 0 or (not category_name and block_idx_data not in (-2, -3)):
                string_count_text = f"[{count}]"
                metrics = QFontMetrics(current_font)
                count_width = metrics.horizontalAdvance(string_count_text) + 10

        if string_count_text:
            count_rect = QRect(item_rect.right() - count_width, item_rect.top(), count_width, item_rect.height())
            painter.setPen(number_text_color)
            painter.drawText(count_rect, Qt.AlignmentFlag.AlignCenter, string_count_text)
        
        header_end = item_rect.right() - count_width - 4
        available_text_w = header_end - text_start_x
        text_rect = QRect(text_start_x, item_rect.top(), max(30, available_text_w), item_rect.height())
        
        full_text = index.data(Qt.ItemDataRole.DisplayRole)
        if not isinstance(full_text, str) or not full_text:
            stored = index.data(Qt.ItemDataRole.UserRole + 4)
            full_text = stored if isinstance(stored, str) else ""
        full_text = full_text or ""
        metrics = QFontMetrics(current_font)
        
        # 1. Split text into "Name" and "Metadata"
        metadata_match = _ITEM_METADATA_TAIL.search(full_text)
        
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
                painter.setPen(option.palette.color(QPalette.ColorRole.HighlightedText if (is_selected or is_drag_hover) else QPalette.ColorRole.Text))
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name_str)
                name_actual_w = metrics.horizontalAdvance(name_str)
                meta_rect = text_rect.adjusted(name_actual_w, 0, 0, 0)
                if not (is_selected or is_drag_hover):
                    painter.setPen(self._color_text_gray_light if theme == 'light' else self._color_text_gray_dark)
                painter.drawText(meta_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, meta_str)
            else:
                # Still prioritize name. 
                painter.setPen(option.palette.color(QPalette.ColorRole.HighlightedText if (is_selected or is_drag_hover) else QPalette.ColorRole.Text))
                # If we have some space, show more of the name
                elided_name = metrics.elidedText(name_str, Qt.TextElideMode.ElideRight, max(total_w - 5, 20))
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_name)
                
                # Metadata only if we have extra space (rare if total_w < name_w + meta_w)
                name_disp_w = metrics.horizontalAdvance(elided_name)
                if total_w - name_disp_w > 20:
                    meta_rect = text_rect.adjusted(name_disp_w, 0, 0, 0)
                    elided_meta = metrics.elidedText(meta_str, Qt.TextElideMode.ElideRight, total_w - name_disp_w)
                    if not (is_selected or is_drag_hover):
                        painter.setPen(self._color_text_gray_light if theme == 'light' else self._color_text_gray_dark)
                    painter.drawText(meta_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_meta)
        else:
            # No metadata
            painter.setPen(option.palette.color(QPalette.ColorRole.HighlightedText if (is_selected or is_drag_hover) else QPalette.ColorRole.Text))
            # Less aggressive elision
            elided_all = metrics.elidedText(full_text, Qt.TextElideMode.ElideRight, max(text_rect.width(), 20))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_all)
        painter.restore()
