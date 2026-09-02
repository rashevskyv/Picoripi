"""Line number area, minimap geometry, resize, paint, wheel, and key handling."""
from __future__ import annotations

from PyQt6.QtGui import QPaintEvent, QKeyEvent
from PyQt6.QtCore import Qt, QRect, QRectF


class LayoutMixin:
    """Line number area, minimap geometry, resize, paint, wheel, and key handling."""

    def wheelEvent(self, event):
        """Wheelevent."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            main_window = self.window()
            if hasattr(main_window, 'handle_zoom'):
                target = 'preview' if self.objectName() == "preview_text_edit" else 'editors'
                main_window.handle_zoom(event.angleDelta().y(), target=target)
                event.accept()
                return
            else:
                # Default zoom for non-main windows (e.g. Review Dialog)
                delta = event.angleDelta().y()
                if delta > 0:
                    self.zoomIn(1)
                elif delta < 0:
                    self.zoomOut(1)
                self.updateLineNumberAreaWidth(0)
                event.accept()
                return

        super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        """Keypressevent."""
        if self.keyboard_handler.handle_key_press(event):
            event.accept()
            return
        super().keyPressEvent(event)

    def lineNumberAreaWidth(self):
        """Linenumberareawidth."""
        total_blocks = self.override_total_lines if self.override_total_lines is not None else self.blockCount()
        if hasattr(self, 'custom_line_numbers') and self.custom_line_numbers:
            max_num = max((v for v in self.custom_line_numbers if v is not None), default=1)
            total_blocks = max(total_blocks, max_num)
        digits = 1; max_val = max(1, total_blocks)
        while max_val >= 10: max_val //= 10; digits += 1
        
        # In review dialog, we have dual columns
        is_dual = hasattr(self, 'custom_subline_numbers') and self.custom_subline_numbers is not None
        if is_dual:
            # Add room for second column + separator
            digits += 4

        current_font_metrics = self.fontMetrics()
        # Account for potential "* " prefix for unsaved changes
        asterisk_width = current_font_metrics.horizontalAdvance('* ')
        # Add extra padding for dual column
        padding = 15 if not is_dual else 25
        base_width = asterisk_width + current_font_metrics.horizontalAdvance('9') * (digits) + padding
        additional_width = 0
        if self.objectName() in ["original_text_edit", "edited_text_edit"] and hasattr(self.window(), 'font_map') and self.window().font_map:
            additional_width = self.pixel_width_display_area_width
        elif self.objectName() == "preview_text_edit":
            additional_width = self.preview_indicator_area_width
        return base_width + additional_width

    def minimapAreaWidth(self):
        """Return the right-side minimap margin width."""
        if hasattr(self, 'minimap'):
            return self.minimap.effective_width()
        return 0

    def updateLineNumberAreaWidth(self, _):
        """Updatelinenumberareawidth."""
        new_width = self.lineNumberAreaWidth()
        minimap_width = self.minimapAreaWidth()
        margins = self.viewportMargins()
        if margins.left() != new_width or margins.right() != minimap_width:
            self.setViewportMargins(new_width, 0, minimap_width, 0)
        if hasattr(self, 'lineNumberArea'): 
            self.lineNumberArea.updateGeometry()
            self.lineNumberArea.update()
        if hasattr(self, 'minimap'):
            self.minimap.sync_visibility()
            self._update_minimap_geometry()
            self.minimap.update()

    def updateLineNumberArea(self, rect: QRectF, dy: int):
        """Updatelinenumberarea."""
        if hasattr(self, 'lineNumberArea'): 
            if dy: self.lineNumberArea.scroll(0, dy)
            else: self.lineNumberArea.update(0, 0, self.lineNumberArea.width(), self.lineNumberArea.height())
        if hasattr(self, 'minimap'):
            self._update_minimap_geometry()
            self.minimap.update()

    def _update_minimap_geometry(self):
        """Position the minimap in the right margin before the scrollbar."""
        if not hasattr(self, 'minimap'):
            return

        minimap_width = self.minimapAreaWidth()
        if minimap_width <= 0:
            self.minimap.hide()
            return

        cr = self.contentsRect()
        vbar = self.verticalScrollBar()
        hbar = self.horizontalScrollBar()
        vbar_width = vbar.width() if vbar.isVisible() else 0
        hbar_height = hbar.height() if hbar.isVisible() else 0
        minimap_right = cr.right() - vbar_width
        minimap_height = max(0, cr.height() - hbar_height)
        self.minimap.setGeometry(
            QRect(minimap_right - minimap_width + 1, cr.top(), minimap_width, minimap_height)
        )
        self.minimap.show()

    def resizeEvent(self, event):
        """Resizeevent."""
        super().resizeEvent(event)
        self.updateLineNumberAreaWidth(0)
        cr = self.contentsRect()
        if hasattr(self, 'lineNumberArea'): 
            self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))
        self._update_minimap_geometry()
        if self.isVisible():
            self.viewport().update()
            if hasattr(self, 'minimap'):
                self.minimap.update()

    def paintEvent(self, event: QPaintEvent):
        """Paintevent."""
        super().paintEvent(event)
        if hasattr(self, 'paint_event_logic'): 
            self.paint_event_logic.execute_paint_event(event)

    def lineNumberAreaPaintEvent(self, event, painter_device):
        """Linenumberareapaintevent."""
        if hasattr(self.lineNumberArea, 'paint_logic'):
            self.lineNumberArea.paint_logic.execute_paint_event(event, painter_device)
