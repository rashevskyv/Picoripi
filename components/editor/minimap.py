from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt, QRect, QSize, QTimer
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPalette, QPen, QPixmap
from PyQt6.QtWidgets import QWidget


class TextMinimap(QWidget):
    """Small document overview for QPlainTextEdit-like editors."""

    WIDTH = 72
    MIN_EDITOR_WIDTH = 360
    MIN_HANDLE_HEIGHT = 24
    REBUILD_DEBOUNCE_MS = 180

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self._dragging = False
        self._drag_offset_y = 0
        self._map_cache = None
        self._map_cache_key = None
        self._content_dirty = False
        self._rebuild_timer = QTimer(self)
        self._rebuild_timer.setSingleShot(True)
        self._rebuild_timer.setInterval(self.REBUILD_DEBOUNCE_MS)
        self._rebuild_timer.timeout.connect(self.invalidate)

        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Document minimap")
        self.hide()

        editor.textChanged.connect(self.schedule_invalidate)
        editor.cursorPositionChanged.connect(self.update)

    def sizeHint(self):
        return QSize(self.WIDTH, 0)

    def effective_width(self) -> int:
        if not getattr(self.editor, "show_minimap", True):
            return 0
        if self.editor.width() < self.MIN_EDITOR_WIDTH:
            return 0
        if self.editor.document().blockCount() <= 1:
            return 0
        return self.WIDTH

    def sync_visibility(self) -> None:
        width = self.effective_width()
        self.setVisible(width > 0)

    def invalidate(self) -> None:
        self._rebuild_timer.stop()
        self._content_dirty = False
        self._map_cache = None
        self._map_cache_key = None
        self.update()

    def schedule_invalidate(self) -> None:
        self._content_dirty = True
        self._rebuild_timer.start()
        self.update()

    def _color_with_alpha(self, color: QColor, alpha: int) -> QColor:
        copy = QColor(color)
        copy.setAlpha(alpha)
        return copy

    def _block_y(self, block_number: int) -> int:
        block_count = max(1, self.editor.document().blockCount())
        return int(block_number * max(1, self.height()) / block_count)

    def _viewport_handle_height(self) -> int:
        bar = self.editor.verticalScrollBar()
        if bar.maximum() <= 0:
            return self.height()
        total = max(1, bar.maximum() + bar.pageStep())
        handle_height = int(self.height() * bar.pageStep() / total)
        return max(1, min(self.height(), max(self.MIN_HANDLE_HEIGHT, handle_height)))

    def _viewport_rect(self) -> QRect:
        bar = self.editor.verticalScrollBar()
        if self.height() <= 0:
            return QRect()
        if bar.maximum() <= 0:
            return QRect(1, 0, max(1, self.width() - 2), self.height())

        handle_height = self._viewport_handle_height()
        total = max(1, bar.maximum() + bar.pageStep())
        top = int(self.height() * bar.value() / total)
        top = max(0, min(top, max(0, self.height() - handle_height)))
        return QRect(1, top, max(1, self.width() - 2), handle_height)

    def _set_scroll_from_handle_top(self, top: int) -> None:
        bar = self.editor.verticalScrollBar()
        if bar.maximum() <= 0 or self.height() <= 0:
            return

        handle_height = self._viewport_handle_height()
        track_height = max(1, self.height() - handle_height)
        clamped_top = max(0, min(top, track_height))
        value = int(round(clamped_top * bar.maximum() / track_height))
        bar.setValue(max(bar.minimum(), min(value, bar.maximum())))
        self.update()

    def _event_pos(self, event: QMouseEvent):
        try:
            return event.position().toPoint()
        except AttributeError:
            return event.pos()

    def _cache_key(self):
        palette = self.editor.palette()
        return (
            self.width(),
            self.height(),
            self.editor.document().revision(),
            palette.color(QPalette.ColorRole.Base).rgba(),
            palette.color(QPalette.ColorRole.Text).rgba(),
        )

    def _iter_sampled_blocks(self, doc):
        block_count = max(1, doc.blockCount())
        height = max(1, self.height())
        if block_count <= height * 2:
            block = doc.firstBlock()
            while block.isValid():
                yield block
                block = block.next()
            return

        seen: set[int] = set()
        for y in range(height):
            start = int(y * block_count / height)
            end = max(start, int((y + 1) * block_count / height) - 1)
            middle = (start + end) // 2
            for block_number in (start, middle, end):
                if block_number in seen:
                    continue
                seen.add(block_number)
                block = doc.findBlockByNumber(block_number)
                if block.isValid():
                    yield block

    def _draw_document_map(self, painter: QPainter) -> None:
        palette = self.editor.palette()
        text = palette.color(QPalette.ColorRole.Text)
        doc = self.editor.document()
        line_color = self._color_with_alpha(text, 90)
        blank_color = self._color_with_alpha(text, 35)
        line_color_provider = getattr(self.editor, "minimap_line_color_for_block", None)
        max_text_width = max(8, self.width() - 10)

        lines_by_y: dict[int, tuple[int, int, QColor]] = {}
        for block in self._iter_sampled_blocks(doc):
            block_number = block.blockNumber()
            y = self._block_y(block_number)
            raw = block.text()
            stripped = raw.strip()

            if stripped:
                leading = len(raw) - len(raw.lstrip())
                x = 5 + min(18, leading // 2)
                width = min(max_text_width - (x - 5), max(6, int(len(stripped) * max_text_width / 120)))
                color = line_color
            else:
                x = 5
                width = 3
                color = blank_color

            if callable(line_color_provider):
                provided_color = line_color_provider(block_number)
                if provided_color:
                    color = self._color_with_alpha(QColor(provided_color), 165)

            current = lines_by_y.get(y)
            if current is None or width > current[1]:
                lines_by_y[y] = (x, max(1, width), color)

        painter.setPen(Qt.PenStyle.NoPen)
        for y, (x, width, color) in lines_by_y.items():
            painter.setBrush(color)
            painter.drawRect(x, y, max(1, width), 1)

    def _ensure_map_cache(self) -> None:
        key = self._cache_key()
        if self._map_cache is not None and self._map_cache_key == key:
            return
        if self._content_dirty and self._map_cache is not None:
            return

        palette = self.editor.palette()
        base = palette.color(QPalette.ColorRole.Base)
        text = palette.color(QPalette.ColorRole.Text)
        pixmap = QPixmap(max(1, self.width()), max(1, self.height()))
        pixmap.fill(self._color_with_alpha(base, 238))

        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            painter.fillRect(QRect(0, 0, 1, self.height()), self._color_with_alpha(text, 35))
            self._draw_document_map(painter)
        finally:
            painter.end()

        self._map_cache = pixmap
        self._map_cache_key = key
        self._content_dirty = False
        self._rebuild_timer.stop()

    def _draw_block_marker(self, painter: QPainter, block_number: int, color: QColor) -> None:
        if block_number < 0 or block_number >= self.editor.document().blockCount():
            return
        y = self._block_y(block_number)
        painter.fillRect(QRect(3, y, max(1, self.width() - 6), 2), color)

    def _draw_dynamic_overlays(self, painter: QPainter) -> None:
        palette = self.editor.palette()
        highlight = palette.color(QPalette.ColorRole.Highlight)
        current_line_color = self._color_with_alpha(highlight, 210)
        selected_line_color = self._color_with_alpha(highlight, 180)

        for block_number in getattr(self.editor, "_selected_lines", set()):
            self._draw_block_marker(painter, block_number, selected_line_color)
        self._draw_block_marker(painter, self.editor.textCursor().blockNumber(), current_line_color)

    def paintEvent(self, event):
        self._ensure_map_cache()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        if self._map_cache is not None:
            painter.drawPixmap(0, 0, self._map_cache)
        self._draw_dynamic_overlays(painter)

        palette = self.editor.palette()
        highlight = palette.color(QPalette.ColorRole.Highlight)
        viewport_rect = self._viewport_rect()
        painter.fillRect(viewport_rect, self._color_with_alpha(highlight, 42))
        pen = QPen(self._color_with_alpha(highlight, 170))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(viewport_rect.adjusted(0, 0, -1, -1))
        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._event_pos(event)
            viewport_rect = self._viewport_rect()
            self._dragging = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

            if viewport_rect.contains(pos):
                self._drag_offset_y = pos.y() - viewport_rect.top()
            else:
                self._drag_offset_y = viewport_rect.height() // 2
                self._set_scroll_from_handle_top(pos.y() - self._drag_offset_y)

            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging:
            pos = self._event_pos(event)
            self._set_scroll_from_handle_top(pos.y() - self._drag_offset_y)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            QTimer.singleShot(0, self.update)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        if not self._dragging:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().leaveEvent(event)

    def resizeEvent(self, event):
        self.invalidate()
        super().resizeEvent(event)

    def event(self, event) -> bool:
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self.invalidate()
        return super().event(event)
