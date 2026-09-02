"""Mouse interaction and context menu for BFN preview."""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMenu

from core.i18n import tr

class BfnPreviewMouseMixin:
    """Mixin: drag/resize/background gestures and context menu."""

    def mousePressEvent(self, event):
        """Mousepressevent."""
        if event.button() == Qt.MouseButton.LeftButton:
            modifiers = event.modifiers()
            if modifiers & Qt.KeyboardModifier.ControlModifier and self.bg_image:
                # Ctrl + Left Mouse Button -> Scale background
                self.scale_drag_active = True
                self.drag_start_pos = event.pos()
                self.drag_start_scale = self.bg_scale
            elif modifiers & Qt.KeyboardModifier.AltModifier and self.bg_image:
                # Alt + Left Mouse Button -> Move background
                self.move_bg_drag_active = True
                self.drag_start_pos = event.pos()
                self.drag_start_offset_x = self.bg_offset_x
                self.drag_start_offset_y = self.bg_offset_y
            elif not self._is_using_preset_geometry():
                # Editable text-rect drag/resize only when no preset geometry.
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
        """Mousemoveevent."""
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
        elif self.drag_active and not self._is_using_preset_geometry():
            dx = event.pos().x() - self.drag_start_pos.x()
            dy = event.pos().y() - self.drag_start_pos.y()
            new_x = self.drag_start_rect.x() + dx
            new_y = self.drag_start_rect.y() + dy
            self.text_rect.moveTo(new_x, new_y)
            self.update()
        elif self.resize_active and not self._is_using_preset_geometry():
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
        elif self._is_using_preset_geometry():
            self.hover_handle = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            handle = self.get_handle_under_mouse(event.pos())
            self.hover_handle = handle
            abs_rect = self.get_absolute_text_rect()
            
            if handle:
                if handle in ['top-left', 'bottom-right']:
                    self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                elif handle in ['top-right', 'bottom-left']:
                    self.setCursor(Qt.CursorShape.SizeBDiagCursor)
                elif handle in ['top', 'bottom']:
                    self.setCursor(Qt.CursorShape.SizeVerCursor)
                elif handle in ['left', 'right']:
                    self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif abs_rect.contains(event.pos()):
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Mousereleaseevent."""
        if event.button() == Qt.MouseButton.LeftButton:
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
        """Show context menu."""
        menu = QMenu(self)
        
        action_set_bg = menu.addAction(tr('Set Background Image...'))
        action_hide_bg = menu.addAction(tr('Hide Background'))
        action_hide_bg.setCheckable(True)
        action_hide_bg.setChecked(self.bg_hidden)
        action_hide_bg.setEnabled(bool(self.bg_image_path))
        action_clear_bg = menu.addAction(tr('Clear Background Image'))
        action_clear_bg.setEnabled(bool(self.bg_image_path))
        
        menu.addSeparator()
        action_set_spacing = menu.addAction(tr('Set Line Spacing...'))
        action_reset_rect = menu.addAction(tr('Reset Text Area'))
        
        action_fix_scale = menu.addAction(tr('Fix Font Scale'))
        action_fix_scale.setCheckable(True)
        action_fix_scale.setChecked(self.fix_font_scale)

        menu.addSeparator()
        fx_menu = menu.addMenu(tr('Text Effects'))
        action_text_color = fx_menu.addAction(tr('Text Color...'))
        action_shadow = fx_menu.addAction(tr('Drop Shadow...'))
        action_glow = fx_menu.addAction(tr('Outer Glow...'))

        action = menu.exec(self.mapToGlobal(pos))
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
        elif action == action_fix_scale:
            self.fix_font_scale = action_fix_scale.isChecked()
            if self.fix_font_scale:
                self.fixed_font_scale = self._last_computed_scale_factor
            self.mw.preview_fix_font_scale = self.fix_font_scale
            self.mw.preview_fixed_font_scale = self.fixed_font_scale
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.save_settings()
            self.update()
        elif action == action_text_color:
            self._open_text_color_dialog()
        elif action == action_shadow:
            self._open_shadow_dialog()
        elif action == action_glow:
            self._open_glow_dialog()
