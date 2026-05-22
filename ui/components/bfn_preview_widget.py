import json
import re
from pathlib import Path
from PyQt5.QtWidgets import QWidget, QMenu, QFileDialog, QInputDialog
from PyQt5.QtGui import QPainter, QColor, QImage, QPen, QPainterPath
from PyQt5.QtCore import Qt, QRect, QPoint, QRectF

class BfnPreviewWidget(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.mw = main_window
        self.text = ""
        self.active_font_name = None
        self.translation_map = None
        
        self.setMinimumHeight(150)  # Increased minimum height to accommodate dialogue frames nicely
        self.setStyleSheet("BfnPreviewWidget { background-color: #111111; border: 1px solid #333333; border-radius: 6px; }")
        
        # Load translation map if available
        self.load_translation_map()
        
        # State variables for background image and spacing
        self.bg_image_path = getattr(self.mw, 'preview_bg_image_path', "")
        self.bg_image = None
        if self.bg_image_path and Path(self.bg_image_path).exists():
            try:
                self.bg_image = QImage(self.bg_image_path)
            except Exception:
                self.bg_image = None
                
        self.line_spacing = getattr(self.mw, 'preview_line_spacing', 10)
        rect_list = getattr(self.mw, 'preview_text_rect', [15, 15, 300, 120])
        self.text_rect = QRect(rect_list[0], rect_list[1], rect_list[2], rect_list[3])
        
        # UI Interaction state
        self.mouse_inside = False
        self.drag_active = False
        self.resize_active = False
        self.resize_handle = None
        self.drag_start_pos = None
        self.drag_start_rect = None
        self.hover_handle = None
        
        self.setMouseTracking(True)
        
        # Context Menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def load_translation_map(self):
        project_dir = None
        if self.mw and hasattr(self.mw, 'project_manager') and self.mw.project_manager:
            project_dir = self.mw.project_manager.project_dir
            
        mapping_path = None
        if project_dir:
            proj_map_path = Path(project_dir) / 'translation_map.json'
            if not proj_map_path.exists():
                plugin_name = getattr(self.mw, 'active_game_plugin', None)
                if plugin_name:
                    plugin_map = Path("plugins") / plugin_name / 'translation_map.json'
                    try:
                        if plugin_map.exists():
                            import shutil
                            shutil.copy2(plugin_map, proj_map_path)
                        else:
                            with proj_map_path.open('w', encoding='utf-8') as f:
                                f.write("{}")
                    except Exception:
                        pass
            mapping_path = proj_map_path
        else:
            plugin_name = getattr(self.mw, 'active_game_plugin', None)
            if plugin_name:
                mapping_path = Path("plugins") / plugin_name / 'translation_map.json'
                
        if mapping_path and mapping_path.exists():
            try:
                with mapping_path.open('r', encoding='utf-8') as f:
                    self.translation_map = json.load(f)
            except Exception:
                self.translation_map = None
        else:
            self.translation_map = None

    def update_preview_text(self, text: str):
        """Update the text and request redraw."""
        self.text = text
        self.update()

    def get_active_bfn_font(self):
        """Find the active BFN font for the current string."""
        block_idx = getattr(self.mw.data_store, 'current_block_idx', -1)
        string_idx = getattr(self.mw.data_store, 'current_string_idx', -1)
        
        font_file = None
        if block_idx != -1 and string_idx != -1:
            string_meta = self.mw.string_metadata.get((block_idx, string_idx), {})
            font_file = string_meta.get("font_file")

        if not font_file or font_file == "default":
            font_file = getattr(self.mw, 'default_font_file', None)

        if not font_file:
            return None

        all_bfn_fonts = getattr(self.mw, 'all_bfn_fonts', {})
        if font_file in all_bfn_fonts:
            return all_bfn_fonts[font_file]
            
        for key, bfn in all_bfn_fonts.items():
            if key.endswith("/" + font_file):
                return bfn

        return None

    def get_handles_dict(self):
        rx, ry, rw, rh = self.text_rect.x(), self.text_rect.y(), self.text_rect.width(), self.text_rect.height()
        handle_size = 6
        half_handle = handle_size // 2
        return {
            'top-left': QRect(rx - half_handle, ry - half_handle, handle_size, handle_size),
            'top-right': QRect(rx + rw - half_handle, ry - half_handle, handle_size, handle_size),
            'bottom-left': QRect(rx - half_handle, ry + rh - half_handle, handle_size, handle_size),
            'bottom-right': QRect(rx + rw - half_handle, ry + rh - half_handle, handle_size, handle_size),
            'top': QRect(rx + rw//2 - half_handle, ry - half_handle, handle_size, handle_size),
            'bottom': QRect(rx + rw//2 - half_handle, ry + rh - half_handle, handle_size, handle_size),
            'left': QRect(rx - half_handle, ry + rh//2 - half_handle, handle_size, handle_size),
            'right': QRect(rx + rw - half_handle, ry + rh//2 - half_handle, handle_size, handle_size),
        }

    def get_handle_under_mouse(self, pos):
        for name, rect in self.get_handles_dict().items():
            if rect.contains(pos):
                return name
        return None

    def draw_bounding_box(self, painter):
        if self.mouse_inside or self.drag_active or self.resize_active:
            # Active state: solid blue border
            painter.setPen(QPen(QColor("#0078d7"), 1.5, Qt.SolidLine))
            painter.drawRect(self.text_rect)
            
            # Draw resize handles
            for name, h_rect in self.get_handles_dict().items():
                if self.hover_handle == name:
                    painter.setPen(QPen(QColor("#005a9e"), 1.5))
                    painter.setBrush(QColor("#0078d7"))
                else:
                    painter.setPen(QPen(QColor("#0078d7"), 1.5))
                    painter.setBrush(QColor("#ffffff"))
                painter.drawRect(h_rect)
        else:
            # Inactive state: thin dashed gray border
            painter.setPen(QPen(QColor("#555555"), 1.0, Qt.DashLine))
            painter.drawRect(self.text_rect)

    def enterEvent(self, event):
        self.mouse_inside = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.mouse_inside = False
        self.hover_handle = None
        self.setCursor(Qt.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            handle = self.get_handle_under_mouse(event.pos())
            if handle:
                self.resize_active = True
                self.resize_handle = handle
                self.drag_start_pos = event.pos()
                self.drag_start_rect = QRect(self.text_rect)
            elif self.text_rect.contains(event.pos()):
                self.drag_active = True
                self.drag_start_pos = event.pos()
                self.drag_start_rect = QRect(self.text_rect)
            self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_active:
            dx = event.pos().x() - self.drag_start_pos.x()
            dy = event.pos().y() - self.drag_start_pos.y()
            new_x = self.drag_start_rect.x() + dx
            new_y = self.drag_start_rect.y() + dy
            # Keep boundaries safe (allow dragging partially offscreen but keep interactive)
            new_x = max(-self.text_rect.width() + 10, min(new_x, self.width() - 10))
            new_y = max(-self.text_rect.height() + 10, min(new_y, self.height() - 10))
            self.text_rect.moveTo(new_x, new_y)
            self.update()
        elif self.resize_active:
            dx = event.pos().x() - self.drag_start_pos.x()
            dy = event.pos().y() - self.drag_start_pos.y()
            r = QRect(self.drag_start_rect)
            min_w, min_h = 20, 20
            
            x1, y1, x2, y2 = r.left(), r.top(), r.right(), r.bottom()
            
            if 'left' in self.resize_handle:
                x1 += dx
                if x2 - x1 < min_w:
                    x1 = x2 - min_w
            if 'right' in self.resize_handle:
                x2 += dx
                if x2 - x1 < min_w:
                    x2 = x1 + min_w
            if 'top' in self.resize_handle:
                y1 += dy
                if y2 - y1 < min_h:
                    y1 = y2 - min_h
            if 'bottom' in self.resize_handle:
                y2 += dy
                if y2 - y1 < min_h:
                    y2 = y1 + min_h
            
            self.text_rect = QRect(QPoint(x1, y1), QPoint(x2, y2))
            self.update()
        else:
            handle = self.get_handle_under_mouse(event.pos())
            self.hover_handle = handle
            
            if handle:
                if handle in ['top-left', 'bottom-right']:
                    self.setCursor(Qt.SizeFDiagCursor)
                elif handle in ['top-right', 'bottom-left']:
                    self.setCursor(Qt.SizeBDiagCursor)
                elif handle in ['top', 'bottom']:
                    self.setCursor(Qt.SizeVerCursor)
                elif handle in ['left', 'right']:
                    self.setCursor(Qt.SizeHorCursor)
            elif self.text_rect.contains(event.pos()):
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.drag_active or self.resize_active:
                # Save to settings
                self.mw.preview_text_rect = [
                    self.text_rect.x(), self.text_rect.y(),
                    self.text_rect.width(), self.text_rect.height()
                ]
                if hasattr(self.mw, 'settings_manager'):
                    self.mw.settings_manager.save_settings()
            self.drag_active = False
            self.resize_active = False
            self.resize_handle = None
            self.update()
        super().mouseReleaseEvent(event)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        
        action_set_bg = menu.addAction("Set Background Image...")
        action_clear_bg = menu.addAction("Clear Background Image")
        action_clear_bg.setEnabled(bool(self.bg_image_path))
        
        menu.addSeparator()
        action_set_spacing = menu.addAction("Set Line Spacing...")
        action_reset_rect = menu.addAction("Reset Text Area")
        
        action = menu.exec_(self.mapToGlobal(pos))
        if action == action_set_bg:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Background Image", "", "Images (*.png *.jpg *.jpeg *.bmp)"
            )
            if file_path:
                self.bg_image_path = file_path
                try:
                    self.bg_image = QImage(file_path)
                    self.mw.preview_bg_image_path = file_path
                    if hasattr(self.mw, 'settings_manager'):
                        self.mw.settings_manager.save_settings()
                except Exception:
                    self.bg_image = None
                self.update()
        elif action == action_clear_bg:
            self.bg_image_path = ""
            self.bg_image = None
            self.mw.preview_bg_image_path = ""
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.save_settings()
            self.update()
        elif action == action_set_spacing:
            val, ok = QInputDialog.getInt(
                self, "Set Line Spacing", "Enter line spacing in pixels:", self.line_spacing, -100, 100
            )
            if ok:
                self.line_spacing = val
                self.mw.preview_line_spacing = val
                if hasattr(self.mw, 'settings_manager'):
                    self.mw.settings_manager.save_settings()
                self.update()
        elif action == action_reset_rect:
            self.text_rect = QRect(15, 15, 300, 120)
            self.mw.preview_text_rect = [15, 15, 300, 120]
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.save_settings()
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        
        # Draw background inside border with rounded corners clipping
        painter.save()
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 6, 6)
        painter.setClipPath(path)
        
        if self.bg_image and not self.bg_image.isNull():
            painter.drawImage(self.rect(), self.bg_image)
        else:
            painter.fillRect(self.rect(), QColor("#121212"))
        painter.restore()
        
        bfn = self.get_active_bfn_font()
        if not bfn or not self.text:
            painter.setPen(QColor("#777777"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No BFN font loaded or text is empty")
            self.draw_bounding_box(painter)
            return
            
        sheets = bfn.get_sheets_qimages()
        if not sheets:
            painter.setPen(QColor("#ffaa00"))
            painter.drawText(self.rect(), Qt.AlignCenter, "BFN sheets not loaded")
            self.draw_bounding_box(painter)
            return

        # Reload translation map to ensure dynamic updates
        self.load_translation_map()

        # Clean tags from text before rendering
        cleaned_text = self.text
        rules = getattr(self.mw, 'current_game_rules', None)
        if rules:
            if hasattr(rules, 'get_spellcheck_ignore_pattern'):
                pattern = rules.get_spellcheck_ignore_pattern()
                if pattern:
                    try:
                        cleaned_text = re.sub(pattern, "", cleaned_text)
                    except Exception:
                        pass
        # Fallback to remove basic curly and square bracket tags
        cleaned_text = re.sub(r'\{[^}]*\}', "", cleaned_text)
        cleaned_text = re.sub(r'\[[^\]]*\]', "", cleaned_text)

        encoded_text = cleaned_text

        # Extract glyph metrics
        gly = bfn.gly1[0]
        cell_w = gly["cell_width"]
        cell_h = gly["cell_height"]
        cols = gly["glyph_horizontal_count"]
        rows = gly["glyph_vertical_count"]
        start_glyph = gly["start_glyph"]
        end_glyph = gly["end_glyph"]

        # Helper to decode character code based on CP1252 to match translation map
        def code_to_char(code):
            try:
                return bytes([code]).decode('cp1252')
            except Exception:
                return chr(code)

        # Parse MAP1 map
        char_to_glyph = {}
        if bfn.map1:
            m1 = bfn.map1[0]
            m_type = m1["mapping_type"]
            m_first = m1["first_char"]
            m_last = m1["last_char"]
            entries = m1["entries"]
            
            if m_type == 0:
                for idx in range(m_first, m_last + 1):
                    char_to_glyph[code_to_char(idx)] = idx
            elif m_type == 2:
                for idx, code in enumerate(entries):
                    char_to_glyph[code_to_char(code)] = idx
            elif m_type == 3:
                half = len(entries) // 2
                for k in range(half):
                    code = entries[k]
                    g_idx = entries[half + k]
                    char_to_glyph[code_to_char(code)] = g_idx

        # Extract width packets
        wid = bfn.wid1[0]
        first_code = wid["first_code_included"]
        packets = wid["packets"]

        # Calculate text dimensions at 1.0 scale to determine scaling factor
        lines = encoded_text.split('\n')
        total_width = 0
        for line in lines:
            line_w = 0
            for char in line:
                if char == ' ':
                    line_w += cell_w // 2
                    continue
                elif char == '\t':
                    line_w += cell_w * 2
                    continue

                glyph_idx = char_to_glyph.get(char, -1)
                if glyph_idx == -1 and self.translation_map:
                    fallback_char = self.translation_map.get(char)
                    if fallback_char:
                        glyph_idx = char_to_glyph.get(fallback_char, -1)

                if glyph_idx == -1 or glyph_idx > end_glyph:
                    line_w += cell_w // 2
                    continue

                width = cell_w
                wid_idx = glyph_idx - first_code
                if 0 <= wid_idx < len(packets):
                    width = packets[wid_idx]["width"]
                line_w += width
            if line_w > total_width:
                total_width = line_w

        total_height = len(lines) * cell_h
        if len(lines) > 1:
            total_height += (len(lines) - 1) * self.line_spacing

        # Determine scaling factor to fit text within text_rect preserving aspect ratio
        scale_factor = 1.0
        if total_width > 0 and total_height > 0:
            scale_x = self.text_rect.width() / total_width
            scale_y = self.text_rect.height() / total_height
            scale_factor = min(scale_x, scale_y)

        # Save painter state, translate to the bounding box, and scale
        painter.save()
        painter.translate(self.text_rect.topLeft())
        painter.scale(scale_factor, scale_factor)

        # Visual rendering offset settings (relative to 0,0 now because of translate)
        current_y = 0

        for line in lines:
            current_x = 0
            for char in line:
                if char == ' ':
                    current_x += cell_w // 2
                    continue
                elif char == '\t':
                    current_x += cell_w * 2
                    continue

                glyph_idx = char_to_glyph.get(char, -1)
                if glyph_idx == -1 and self.translation_map:
                    fallback_char = self.translation_map.get(char)
                    if fallback_char:
                        glyph_idx = char_to_glyph.get(fallback_char, -1)

                if glyph_idx == -1 or glyph_idx > end_glyph:
                    # Draw fallback dark gray outline box for missing glyphs
                    painter.setPen(QColor("#444444"))
                    painter.drawRect(current_x, current_y, cell_w - 2, cell_h - 2)
                    current_x += cell_w // 2
                    continue

                rem = glyph_idx - start_glyph
                sheet_idx = rem // (rows * cols)
                cell_idx = rem % (rows * cols)

                if sheet_idx < 0 or sheet_idx >= len(sheets):
                    current_x += cell_w // 2
                    continue

                gx = cell_idx % cols
                gy = cell_idx // cols

                cell_x = gx * cell_w
                cell_y = gy * cell_h

                kerning = 0
                width = cell_w
                wid_idx = glyph_idx - first_code
                if 0 <= wid_idx < len(packets):
                    kerning = packets[wid_idx]["kerning"]
                    width = packets[wid_idx]["width"]

                crop_x = cell_x + kerning
                crop_w = width
                if crop_w <= 0:
                    crop_w = 1

                # Render decoded white/rgba glyph
                sheet_img = sheets[sheet_idx]
                painter.drawImage(current_x, current_y, sheet_img, crop_x, cell_y, crop_w, cell_h)

                # Move spacing cursor by character visual width
                current_x += width

            # Apply custom line spacing between rows
            current_y += cell_h + self.line_spacing

        painter.restore()

        # Draw interactive bounding box frame over text
        self.draw_bounding_box(painter)
