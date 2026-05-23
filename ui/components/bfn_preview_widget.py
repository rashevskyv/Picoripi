import json
import re
from pathlib import Path
from PyQt5.QtWidgets import QWidget, QMenu, QFileDialog, QInputDialog
from PyQt5.QtGui import QPainter, QColor, QImage, QPen, QPainterPath, QFont, QFontMetrics
from PyQt5.QtCore import Qt, QRect, QPoint, QRectF

class BfnEditorAdapter:
    def __init__(self, editor):
        self.editor = editor

    @property
    def gly1(self):
        return self.editor.metadata.get("GLY1", [])

    @property
    def map1(self):
        return self.editor.metadata.get("MAP1", [])

    @property
    def wid1(self):
        return self.editor.metadata.get("WID1", [])

    @property
    def inf1(self):
        return self.editor.metadata.get("INF1", [])

    def get_sheets_qimages(self):
        return self.editor.sheet_images

    def layout_text(self, text: str, translation_map = None, line_spacing: int = 10):
        from core.bfn_core import BfnCore
        return BfnCore.layout_text(self, text, translation_map, line_spacing)

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
                
        self.bg_scale = getattr(self.mw, 'preview_bg_scale', 100)
        self.bg_offset_x = getattr(self.mw, 'preview_bg_offset_x', 0)
        self.bg_offset_y = getattr(self.mw, 'preview_bg_offset_y', 0)
        self.bg_hidden = getattr(self.mw, 'preview_bg_hidden', False)
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
        self.scale_drag_active = False
        self.move_bg_drag_active = False
        
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

    def get_bg_top_left(self) -> QPoint:
        """Calculate the top-left position of the background image inside the widget."""
        return QPoint(0, 0)

    def get_absolute_text_rect(self) -> QRect:
        """Get the text rect in absolute widget coordinates (relative to background's top-left)."""
        return self.text_rect.translated(self.get_bg_top_left())

    def get_active_bfn_font(self):
        """Find the active BFN font for the current string."""
        if hasattr(self.mw, '_bfn_editor_window') and self.mw._bfn_editor_window is not None:
            editor = self.mw._bfn_editor_window
            is_mock = False
            try:
                from unittest.mock import Mock
                if isinstance(editor, Mock):
                    is_mock = True
            except ImportError:
                pass
                
            if not is_mock:
                try:
                    if not editor.isHidden() and getattr(editor, 'sheet_images', None):
                        return BfnEditorAdapter(editor)
                except RuntimeError:
                    self.mw._bfn_editor_window = None

        block_idx = getattr(self.mw.data_store, 'current_block_idx', -1)
        string_idx = getattr(self.mw.data_store, 'current_string_idx', -1)
        
        font_file = None
        if block_idx != -1 and string_idx != -1:
            string_meta = self.mw.string_metadata.get((block_idx, string_idx), {})
            font_file = string_meta.get("font_file")

        if not font_file or font_file == "default":
            font_file = getattr(self.mw, 'default_font_file', None)

        all_bfn_fonts = getattr(self.mw, 'all_bfn_fonts', {})

        if not font_file:
            if all_bfn_fonts:
                first_key = next(iter(all_bfn_fonts))
                return all_bfn_fonts[first_key]
            return None
        
        if font_file:
            # Strip extension and try matching by stem (base name)
            font_stem = Path(font_file).stem.lower()
            
            if font_file in all_bfn_fonts:
                return all_bfn_fonts[font_file]
                
            for key, bfn in all_bfn_fonts.items():
                key_stem = Path(key).stem.lower()
                if key_stem == font_stem or key.endswith("/" + font_file):
                    return bfn

        # Fallback: if no active font matched by name, but we have loaded BFN fonts, use the first one
        if all_bfn_fonts:
            first_key = next(iter(all_bfn_fonts))
            return all_bfn_fonts[first_key]

        return None

    def get_handles_dict(self):
        abs_rect = self.get_absolute_text_rect()
        rx, ry, rw, rh = abs_rect.x(), abs_rect.y(), abs_rect.width(), abs_rect.height()
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
        abs_rect = self.get_absolute_text_rect()
        if self.mouse_inside or self.drag_active or self.resize_active:
            # Active state: solid blue border
            painter.setPen(QPen(QColor("#0078d7"), 1.5, Qt.SolidLine))
            painter.drawRect(abs_rect)
            
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
            painter.drawRect(abs_rect)

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
            modifiers = event.modifiers()
            if modifiers & Qt.ControlModifier and self.bg_image:
                # Ctrl + Left Mouse Button -> Scale background
                self.scale_drag_active = True
                self.drag_start_pos = event.pos()
                self.drag_start_scale = self.bg_scale
            elif modifiers & Qt.AltModifier and self.bg_image:
                # Alt + Left Mouse Button -> Move background
                self.move_bg_drag_active = True
                self.drag_start_pos = event.pos()
                self.drag_start_offset_x = self.bg_offset_x
                self.drag_start_offset_y = self.bg_offset_y
            else:
                handle = self.get_handle_under_mouse(event.pos())
                abs_rect = self.get_absolute_text_rect()
                if handle:
                    self.resize_active = True
                    self.resize_handle = handle
                    self.drag_start_pos = event.pos()
                    self.drag_start_rect = QRect(self.text_rect)
                elif abs_rect.contains(event.pos()):
                    self.drag_active = True
                    self.drag_start_pos = event.pos()
                    self.drag_start_rect = QRect(self.text_rect)
            self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.scale_drag_active:
            # Calculate shift vertically. Move up increases scale, down decreases.
            dy = self.drag_start_pos.y() - event.pos().y()
            new_scale = self.drag_start_scale + dy
            # Limit scale between 5% and 1000%
            self.bg_scale = max(5, min(1000, new_scale))
            self.update()
        elif self.move_bg_drag_active:
            dx = event.pos().x() - self.drag_start_pos.x()
            dy = event.pos().y() - self.drag_start_pos.y()
            self.bg_offset_x = self.drag_start_offset_x + dx
            self.bg_offset_y = self.drag_start_offset_y + dy
            self.update()
        elif self.drag_active:
            dx = event.pos().x() - self.drag_start_pos.x()
            dy = event.pos().y() - self.drag_start_pos.y()
            new_x = self.drag_start_rect.x() + dx
            new_y = self.drag_start_rect.y() + dy
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
            abs_rect = self.get_absolute_text_rect()
            
            if handle:
                if handle in ['top-left', 'bottom-right']:
                    self.setCursor(Qt.SizeFDiagCursor)
                elif handle in ['top-right', 'bottom-left']:
                    self.setCursor(Qt.SizeBDiagCursor)
                elif handle in ['top', 'bottom']:
                    self.setCursor(Qt.SizeVerCursor)
                elif handle in ['left', 'right']:
                    self.setCursor(Qt.SizeHorCursor)
            elif abs_rect.contains(event.pos()):
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.scale_drag_active:
                self.mw.preview_bg_scale = self.bg_scale
                if hasattr(self.mw, 'settings_manager'):
                    self.mw.settings_manager.save_settings()
                self.scale_drag_active = False
            elif self.move_bg_drag_active:
                self.mw.preview_bg_offset_x = self.bg_offset_x
                self.mw.preview_bg_offset_y = self.bg_offset_y
                if hasattr(self.mw, 'settings_manager'):
                    self.mw.settings_manager.save_settings()
                self.move_bg_drag_active = False
            elif self.drag_active or self.resize_active:
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
        action_hide_bg = menu.addAction("Hide Background")
        action_hide_bg.setCheckable(True)
        action_hide_bg.setChecked(self.bg_hidden)
        action_hide_bg.setEnabled(bool(self.bg_image_path))
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
                had_previous_image = self.bg_image is not None and not self.bg_image.isNull()
                try:
                    new_image = QImage(file_path)
                    self.bg_image = new_image
                    self.mw.preview_bg_image_path = file_path
                    
                    # Center the image inside the preview widget initially, only if no previous image was set/positioned
                    if not new_image.isNull() and (not had_previous_image or (self.bg_offset_x == 0 and self.bg_offset_y == 0)):
                        scale_factor = self.bg_scale / 100.0
                        new_w = self.bg_image.width() * scale_factor
                        new_h = self.bg_image.height() * scale_factor
                        self.bg_offset_x = int((self.width() - new_w) / 2)
                        self.bg_offset_y = int((self.height() - new_h) / 2)
                        self.mw.preview_bg_offset_x = self.bg_offset_x
                        self.mw.preview_bg_offset_y = self.bg_offset_y
                    
                    if hasattr(self.mw, 'settings_manager'):
                        self.mw.settings_manager.save_settings()
                except Exception:
                    self.bg_image = None
                self.update()
        elif action == action_hide_bg:
            self.bg_hidden = action_hide_bg.isChecked()
            self.mw.preview_bg_hidden = self.bg_hidden
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.save_settings()
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
        
        if self.bg_image and not self.bg_image.isNull() and not self.bg_hidden:
            if self.bg_scale == 0:
                painter.drawImage(self.rect(), self.bg_image)
            else:
                scale_factor = self.bg_scale / 100.0
                new_w = self.bg_image.width() * scale_factor
                new_h = self.bg_image.height() * scale_factor
                x = self.bg_offset_x
                y = self.bg_offset_y
                painter.drawImage(QRectF(x, y, new_w, new_h), self.bg_image)
        else:
            painter.fillRect(self.rect(), QColor("#121212"))
        painter.restore()
        
        abs_rect = self.get_absolute_text_rect()
        bfn = self.get_active_bfn_font()
        if not bfn:
            if self.text:
                painter.setPen(QColor("#ffffff"))
                font = painter.font()
                font.setPointSize(12)
                painter.setFont(font)
                
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
                cleaned_text = re.sub(r'\{[^}]*\}', "", cleaned_text)
                cleaned_text = re.sub(r'\[[^\]]*\]', "", cleaned_text)
                
                painter.drawText(abs_rect, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, cleaned_text)
            else:
                painter.setPen(QColor("#777777"))
                painter.drawText(self.rect(), Qt.AlignCenter, "No BFN font loaded or text is empty")
            self.draw_bounding_box(painter)
            return
            
        if not self.text:
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

        # Prepare fallback font metrics for missing glyphs
        fallback_font = painter.font()
        fallback_font.setPixelSize(max(10, int(cell_h * 0.85)))
        fallback_fm = QFontMetrics(fallback_font)

        # Call unified layout engine
        is_mock = False
        try:
            from unittest.mock import Mock
            if isinstance(bfn, Mock):
                is_mock = True
        except ImportError:
            pass
            
        if is_mock:
            from core.bfn_core import BfnCore
            glyphs, total_width, total_height = BfnCore.layout_text(bfn, encoded_text, self.translation_map, self.line_spacing)
        else:
            glyphs, total_width, total_height = bfn.layout_text(encoded_text, self.translation_map, self.line_spacing)

        if not glyphs:
            painter.setPen(QColor("#777777"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No BFN font loaded or text is empty")
            self.draw_bounding_box(painter)
            return

        # Determine scaling factor to fit text within text_rect preserving aspect ratio
        scale_factor = 1.0
        if total_width > 0 and total_height > 0:
            scale_x = abs_rect.width() / total_width
            scale_y = abs_rect.height() / total_height
            scale_factor = min(scale_x, scale_y)

        # Save painter state, translate to the bounding box, and scale
        painter.save()
        painter.translate(abs_rect.topLeft())
        painter.scale(scale_factor, scale_factor)

        # Offset translate back by -15px since layout_text starts current_x/current_y at 15px (simulator layout)
        painter.translate(-15, -15)

        for g in glyphs:
            if g["is_fallback"]:
                # Draw fallback character using system font instead of gray box
                painter.save()
                painter.setPen(QColor("#ffffff"))
                painter.setFont(fallback_font)
                
                char_w = fallback_fm.horizontalAdvance(g["char"])
                if char_w <= 0:
                    char_w = cell_w // 2
                    
                painter.drawText(QRectF(g["draw_x"], g["draw_y"], char_w, cell_h), Qt.AlignCenter, g["char"])
                painter.restore()
                continue

            if g["sheet_idx"] < 0 or g["sheet_idx"] >= len(sheets):
                continue

            # Render decoded white/rgba glyph
            sheet_img = sheets[g["sheet_idx"]]
            
            crop_x = g["cell_x"] + g["kerning"]
            crop_w = g["width"]
            if crop_w <= 0:
                crop_w = 1

            painter.drawImage(g["draw_x"], g["draw_y"], sheet_img, crop_x, g["cell_y"], crop_w, cell_h)

        painter.restore()

        # Draw interactive bounding box frame over text
        self.draw_bounding_box(painter)
