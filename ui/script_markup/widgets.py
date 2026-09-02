"""Helper widgets and compact labels for Script Markup Studio."""
from __future__ import annotations

from PyQt6 import sip
from PyQt6.QtWidgets import (
    QLabel, QPlainTextEdit, QLineEdit, QTreeWidget, QTreeWidgetItem,
    QWidget, QToolTip,
)
from PyQt6.QtGui import (
    QSyntaxHighlighter, QTextCharFormat, QColor,
    QPainter, QDrag, QPixmap, QFontMetrics,
)
from PyQt6.QtCore import Qt, QTimer, QEvent, QPoint, QRect, QSize, QItemSelectionModel, pyqtSignal

from components.editor.minimap import TextMinimap
from core.script_markup import LineKind

from ui.script_markup.constants import (
    _KIND_COLORS,
    _BLOCK_HEAD,
    _BLOCK_BODY,
    _RAW_HIERARCHY_GUTTER_WIDTH,
)

class _ClassificationHighlighter(QSyntaxHighlighter):
    """Tints each line of the raw editor by its precomputed classification."""

    def __init__(self, document):
        super().__init__(document)
        self.line_kinds: dict[int, str] = {}
        self.line_blocks: dict[int, int] = {}   # line index -> block parity (0/1)
        self.line_speakers: dict[int, str] = {}
        self.line_colors: dict[int, str] = {}

    def set_line_kinds(
        self,
        line_kinds: dict[int, str],
        line_blocks: dict[int, int] | None = None,
        line_speakers: dict[int, str] | None = None,
        line_colors: dict[int, str] | None = None,
    ):
        line_kinds = dict(line_kinds)
        line_blocks = dict(line_blocks or {})
        line_speakers = dict(line_speakers or {})
        line_colors = dict(line_colors or {})
        if (
            self.line_kinds == line_kinds
            and self.line_blocks == line_blocks
            and self.line_speakers == line_speakers
            and self.line_colors == line_colors
        ):
            return
        self.line_kinds = line_kinds
        self.line_blocks = line_blocks
        self.line_speakers = line_speakers
        self.line_colors = line_colors
        self.rehighlight()

    def highlightBlock(self, text: str):
        bn = self.currentBlock().blockNumber()
        kind = self.line_kinds.get(bn)
        if not kind or kind in (LineKind.NARRATION, LineKind.BLANK):
            return
        color = self.line_colors.get(bn)
        if color:
            pass
        elif kind in (LineKind.SPEAKER, LineKind.GUTTER_SPEAKER):
            color = _BLOCK_HEAD[self.line_blocks.get(bn, 0)]
        elif kind == LineKind.DIALOGUE_CONT:
            color = _BLOCK_BODY[self.line_blocks.get(bn, 0)]
        else:
            color = _KIND_COLORS.get(kind)
        if not color:
            return
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(color))
        self.setFormat(0, len(text), fmt)


class _RawHierarchyGutter(QWidget):
    """Dedicated non-text gutter for hierarchy guides and fold controls."""

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setFixedWidth(_RAW_HIERARCHY_GUTTER_WIDTH)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

    def sizeHint(self):
        return QSize(_RAW_HIERARCHY_GUTTER_WIDTH, 0)

    def paintEvent(self, event):
        self.editor.studio._paint_raw_hierarchy_gutter(self, event.rect())

    def mousePressEvent(self, event):
        if self.editor.studio._raw_hierarchy_gutter_mouse_press(event):
            return
        super().mousePressEvent(event)


class _SearchLineEdit(QLineEdit):
    """Search field that keeps Return/Enter navigation inside the search flow."""

    findNextRequested = pyqtSignal()
    findPreviousRequested = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.findPreviousRequested.emit()
            else:
                self.findNextRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class _ScriptMarkupRawEdit(QPlainTextEdit):
    """Raw script editor with Studio-specific marking actions and tooltips."""

    def __init__(self, studio):
        super().__init__()
        self.studio = studio
        self.show_minimap = True
        self.hierarchy_gutter = _RawHierarchyGutter(self)
        self.minimap = TextMinimap(self)
        self._sync_viewport_margins()
        self.updateRequest.connect(self._update_hierarchy_gutter)
        self.textChanged.connect(self._sync_viewport_margins)

    def minimapAreaWidth(self):
        return self.minimap.effective_width() if hasattr(self, "minimap") else 0

    def minimap_line_color_for_block(self, block_number: int):
        highlighter = getattr(self.studio, "highlighter", None)
        if highlighter is None:
            return None

        color = highlighter.line_colors.get(block_number)
        if color:
            return QColor(color)

        kind = highlighter.line_kinds.get(block_number)
        if kind in (LineKind.SPEAKER, LineKind.GUTTER_SPEAKER):
            return QColor(_BLOCK_HEAD[highlighter.line_blocks.get(block_number, 0)])
        if kind == LineKind.DIALOGUE_CONT:
            return QColor(_BLOCK_BODY[highlighter.line_blocks.get(block_number, 0)])
        if kind:
            raw_color = _KIND_COLORS.get(kind)
            return QColor(raw_color) if raw_color else None
        return None

    def _sync_viewport_margins(self):
        minimap_width = self.minimapAreaWidth()
        margins = self.viewportMargins()
        if margins.left() != _RAW_HIERARCHY_GUTTER_WIDTH or margins.right() != minimap_width:
            self.setViewportMargins(_RAW_HIERARCHY_GUTTER_WIDTH, 0, minimap_width, 0)
        self._update_minimap_geometry()
        self.minimap.sync_visibility()
        self.minimap.update()

    def _update_minimap_geometry(self):
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

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu(event.pos())
        self.studio._add_mark_context_actions(menu, event.pos())
        menu.exec(event.globalPos())

    def paintEvent(self, event):
        super().paintEvent(event)
        self.studio._paint_raw_edit_overlays(self.viewport(), event.rect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_viewport_margins()
        cr = self.contentsRect()
        self.hierarchy_gutter.setGeometry(
            QRect(cr.left(), cr.top(), _RAW_HIERARCHY_GUTTER_WIDTH, cr.height())
        )

    def _update_hierarchy_gutter(self, rect, dy):
        if dy:
            self.hierarchy_gutter.scroll(0, dy)
        else:
            self.hierarchy_gutter.update(0, rect.y(), _RAW_HIERARCHY_GUTTER_WIDTH, rect.height())
        if rect.contains(self.viewport().rect()):
            self.hierarchy_gutter.update()
        self._update_minimap_geometry()
        self.minimap.update()

    def _show_studio_tooltip(self, event) -> bool:
        tip = self.studio._tooltip_for_raw_position(event.pos())
        if tip:
            QToolTip.showText(event.globalPos(), tip, self.viewport())
        else:
            QToolTip.hideText()
        event.accept()
        return True

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.ToolTip:
            return self._show_studio_tooltip(event)
        return super().viewportEvent(event)

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            return self._show_studio_tooltip(event)
        return super().event(event)

    def mousePressEvent(self, event):
        if self.studio._range_edit_mouse_press(event):
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.studio._range_edit_mouse_move(event):
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.studio._range_edit_mouse_release(event):
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if self.studio._handle_history_key(event):
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            steps = int(event.angleDelta().y() / 120)
            if steps > 0:
                self.zoomIn(steps)
            elif steps < 0:
                self.zoomOut(-steps)
            event.accept()
            self._sync_viewport_margins()
            return
        super().wheelEvent(event)


class _ScriptTreeWidget(QTreeWidget):
    """Tree view that turns drag/drop into hierarchy depth changes."""

    def __init__(self, studio):
        super().__init__()
        self.studio = studio
        self._selection_anchor_item: QTreeWidgetItem | None = None
        self._pending_rename_item: QTreeWidgetItem | None = None
        self._pending_rename_timer = QTimer(self)
        self._pending_rename_timer.setSingleShot(True)
        self._pending_rename_timer.setInterval(450)
        self._pending_rename_timer.timeout.connect(self._open_pending_rename)

    def _item_is_alive(self, item: QTreeWidgetItem | None) -> bool:
        try:
            return item is not None and not sip.isdeleted(item)
        except RuntimeError:
            return False

    def _visible_items(self) -> list[QTreeWidgetItem]:
        items: list[QTreeWidgetItem] = []

        def walk(item: QTreeWidgetItem):
            if not self._item_is_alive(item) or item.isHidden():
                return
            items.append(item)
            if item.isExpanded():
                for idx in range(item.childCount()):
                    walk(item.child(idx))

        for idx in range(self.topLevelItemCount()):
            walk(self.topLevelItem(idx))
        return items

    def _set_current_without_selection_change(self, item: QTreeWidgetItem):
        index = self.indexFromItem(item, 0)
        self.selectionModel().setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)

    def _event_pos(self, event) -> QPoint:
        try:
            return event.position().toPoint()
        except AttributeError:
            return event.pos()

    def _item_at_row(self, pos: QPoint) -> QTreeWidgetItem | None:
        item = self.itemAt(pos)
        if item is not None:
            return item
        for visible_item in self._visible_items():
            rect = self.visualItemRect(visible_item)
            if rect.isValid() and rect.top() <= pos.y() <= rect.bottom():
                return visible_item
        return None

    def _cancel_pending_rename(self):
        self._pending_rename_timer.stop()
        self._pending_rename_item = None

    def _schedule_pending_rename(self, item: QTreeWidgetItem):
        self._pending_rename_item = item
        self._pending_rename_timer.start()

    def _position_is_disclosure(self, item: QTreeWidgetItem, pos: QPoint) -> bool:
        if item.childCount() <= 0:
            return False
        rect = self.visualItemRect(item)
        return rect.isValid() and pos.x() < rect.left()

    def _open_pending_rename(self):
        item = self._pending_rename_item
        self._pending_rename_item = None
        if self._item_is_alive(item):
            self.studio._rename_outline_item(item)

    def _select_range_to_item(self, item: QTreeWidgetItem) -> bool:
        anchor = self._selection_anchor_item
        if not self._item_is_alive(anchor):
            anchor = self.currentItem() if self._item_is_alive(self.currentItem()) else item
        visible = self._visible_items()
        if anchor not in visible or item not in visible:
            return False
        start = visible.index(anchor)
        end = visible.index(item)
        if start > end:
            start, end = end, start
        self.clearSelection()
        for selected in visible[start:end + 1]:
            selected.setSelected(True)
        self._set_current_without_selection_change(item)
        return True

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._event_pos(event)
            item = self.itemAt(pos)
            row_item = item or self._item_at_row(pos)
            modifiers = event.modifiers()
            if row_item is not None and modifiers & Qt.KeyboardModifier.ShiftModifier:
                self._cancel_pending_rename()
                if self._select_range_to_item(row_item):
                    event.accept()
                    return
            if row_item is not None and modifiers & Qt.KeyboardModifier.ControlModifier:
                self._cancel_pending_rename()
                row_item.setSelected(not row_item.isSelected())
                self._selection_anchor_item = row_item
                self._set_current_without_selection_change(row_item)
                event.accept()
                return
            if (
                row_item is not None
                and item is None
                and modifiers == Qt.KeyboardModifier.NoModifier
            ):
                self._cancel_pending_rename()
                self.clearSelection()
                row_item.setSelected(True)
                self.setCurrentItem(row_item)
                self._selection_anchor_item = row_item
                event.accept()
                return
            if (
                item is not None
                and modifiers == Qt.KeyboardModifier.NoModifier
                and item is self.currentItem()
                and item.isSelected()
                and not self._position_is_disclosure(item, pos)
            ):
                self._schedule_pending_rename(item)
            else:
                self._cancel_pending_rename()
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._event_pos(event)
            item = self._item_at_row(pos)
            if item is not None and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._selection_anchor_item = item

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._cancel_pending_rename()
        super().mouseMoveEvent(event)

    def _drag_preview_pixmap(self) -> QPixmap:
        selected = [
            item for item in self.selectedItems()
            if self._item_is_alive(item) and not item.isHidden()
        ]
        selected.sort(key=lambda item: self.visualItemRect(item).top())
        visible_rows = [
            (item, self.visualItemRect(item))
            for item in selected[:8]
            if self.visualItemRect(item).isValid()
        ]
        if not visible_rows:
            return QPixmap()

        width = min(420, max(rect.width() for _item, rect in visible_rows))
        height = sum(rect.height() for _item, rect in visible_rows)
        preview = QPixmap(max(1, width), max(1, height))
        preview.fill(Qt.GlobalColor.transparent)
        painter = QPainter(preview)
        painter.setOpacity(0.45)
        y = 0
        for _item, rect in visible_rows:
            source_rect = QRect(rect.left(), rect.top(), width, rect.height())
            row = self.viewport().grab(source_rect)
            painter.drawPixmap(0, y, row)
            y += rect.height()
        painter.end()
        return preview

    def startDrag(self, supported_actions):
        indexes = self.selectedIndexes()
        if not indexes:
            return
        mime_data = self.model().mimeData(indexes)
        if mime_data is None:
            return
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        preview = self._drag_preview_pixmap()
        if not preview.isNull():
            drag.setPixmap(preview)
            drag.setHotSpot(QPoint(min(24, preview.width() // 2), min(12, preview.height() // 2)))
        drag.exec(supported_actions, Qt.DropAction.MoveAction)

    def mouseDoubleClickEvent(self, event):
        self._cancel_pending_rename()
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._event_pos(event)
            item = self._item_at_row(pos)
            if item is not None and self._position_is_disclosure(item, pos):
                super().mouseDoubleClickEvent(event)
                return
            if item is not None and self.studio._jump_to_flag(item):
                self._selection_anchor_item = item
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        depth_shortcut_modifiers = (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.ShiftModifier
        )
        if (
            event.modifiers() == depth_shortcut_modifiers
            and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down)
        ):
            self._cancel_pending_rename()
            delta = -1 if event.key() == Qt.Key.Key_Up else 1
            self.studio._change_selected_outline_depth(self.selectedItems(), delta)
            event.accept()
            return
        if event.key() == Qt.Key.Key_F2:
            self._cancel_pending_rename()
            if self.studio._rename_outline_item(self.currentItem()):
                event.accept()
                return
        super().keyPressEvent(event)

    def dropEvent(self, event):
        self._cancel_pending_rename()
        pos = self._event_pos(event)
        moved = self.studio._handle_outline_drop(
            self.selectedItems(),
            self._item_at_row(pos),
            self.dropIndicatorPosition(),
        )
        if moved:
            event.acceptProposedAction()
            return



def _get_stats_variants(text: str) -> list[str]:
    parts = []
    # Спершу розбиваємо за " | "
    for p in text.split(" | "):
        p = p.strip()
        if not p:
            continue
        if p.startswith("(via "):
            continue
        # Тепер розбиваємо за ", "
        for sub_p in p.split(", "):
            sub_p = sub_p.strip()
            if sub_p:
                parts.append(sub_p)

    full_items = []
    med_items = []
    short_items = []

    for item in parts:
        if ":" in item:
            label, val = item.split(":", 1)
            label = label.strip()
            val = val.strip()

            full_items.append(f"{label}: {val}")

            # 3-літерний
            med_label = label[:3]
            if label == "Max depth":
                med_label = "Mxd"
            elif label == "Chapters/Rooms":
                med_label = "ChR"
            med_items.append(f"{med_label}: {val}")

            # 1-літерний
            if label == "Nodes":
                c = "N"
            elif label == "Max depth":
                c = "D"
            elif label == "Speakers":
                c = "S"
            elif label == "Dialogue":
                c = "Dial"
            elif label == "Chapters" or label == "Chapters/Rooms":
                c = "C"
            elif label == "Locations":
                c = "L"
            elif label == "Flags":
                c = "F"
            elif label == "Actions":
                c = "A"
            else:
                c = label[0].upper() if label else "?"
            short_items.append(f"{c}: {val}")
        else:
            full_items.append(item)
            med_items.append(item[:3] if len(item) > 3 else item)
            short_items.append(item[0] if item else "")

    return [
        " | ".join(full_items),
        " | ".join(med_items),
        " | ".join(short_items)
    ]


def _get_legend_variants(html: str) -> list[str]:
    import re
    # Витягуємо безпосередньо колір до першої крапки з комою або лапки
    span_pattern = re.compile(r'<span style="background:([^;"]+);?[^>]*>([^<]+)</span>')
    matches = span_pattern.findall(html)
    if not matches:
        return [html, html, html]

    full_spans = []
    med_spans = []
    short_spans = []

    for color, label in matches:
        label = label.strip()
        color = color.strip()
        # Для гарного контрасту колір тексту темно-сірий (#111), тонка рамка і tooltip title
        full_spans.append(
            f'<span title="{label}" style="background:{color}; color:#111; '
            f'font-weight:bold; font-size:10px; padding:1px 5px; border-radius:3px; '
            f'border:1px solid #999; margin-right:2px;">{label}</span>'
        )

        med_label = label[:3]
        med_spans.append(
            f'<span title="{label}" style="background:{color}; color:#111; '
            f'font-weight:bold; font-size:10px; padding:1px 5px; border-radius:3px; '
            f'border:1px solid #999; margin-right:2px;">{med_label}</span>'
        )

        first_letter = label[0].upper() if label else "?"
        short_spans.append(
            f'<span title="{label}" style="background:{color}; color:#111; '
            f'font-weight:bold; font-size:10px; padding:1px 5px; border-radius:3px; '
            f'border:1px solid #999; margin-right:2px;">{first_letter}</span>'
        )

    # Об'єднуємо плашки з нерозривними пробілами &nbsp;&nbsp;, щоб дати "повітря" між ними в QLabel
    return [
        "&nbsp;&nbsp;".join(full_spans),
        "&nbsp;&nbsp;".join(med_spans),
        "&nbsp;&nbsp;".join(short_spans)
    ]


class CompactStatsLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._raw_text = ""
        self._variants = ["", "", ""]
        self.setStyleSheet("color:#111; font-weight:bold; font-size:10px;")

    def setText(self, text: str):
        self._raw_text = text
        self.setToolTip(text)
        self._variants = _get_stats_variants(text)
        self._adapt_text()

    def text(self) -> str:
        return self._raw_text

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adapt_text()

    def _adapt_text(self):
        if not self._variants[0]:
            return
        fm = QFontMetrics(self.font())
        available_w = self.width()
        if available_w <= 0:
            available_w = 400
        for variant in self._variants:
            w = fm.horizontalAdvance(variant)
            if w <= available_w:
                if super().text() != variant:
                    super().setText(variant)
                return
        if super().text() != self._variants[2]:
            super().setText(self._variants[2])


class CompactLegendLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._raw_html = ""
        self._variants = ["", "", ""]
        self._labels = []
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setStyleSheet("font-size: 10px;")

    def setText(self, text: str):
        if text.startswith("<") or "style=" in text:
            self._raw_html = text
            self._variants = _get_legend_variants(text)
            import re
            self._labels = re.findall(r'<span style="background:[^"]+;[^>]*>([^<]+)</span>', text)
            tooltip_html = (
                f'<div style="background:#fff; border:1px solid #ccc; padding:6px; border-radius:4px;">'
                f'<b style="color:#333;">Legend:</b><br/><br/>'
                f'{self._variants[0]}'
                f'</div>'
            )
            self.setToolTip(tooltip_html)
            self._adapt_text()
        else:
            self._raw_html = text
            self._variants = [text, text, text]
            self._labels = [text]
            self.setToolTip(text)
            super().setText(text)

    def text(self) -> str:
        return self._raw_html

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adapt_text()

    def _adapt_text(self):
        if not self._variants[0]:
            return
        fm = QFontMetrics(self.font())
        available_w = self.width()
        if available_w <= 0:
            available_w = 400
        w_full = sum(fm.horizontalAdvance(l) + 16 for l in self._labels)
        if w_full <= available_w:
            if super().text() != self._variants[0]:
                super().setText(self._variants[0])
            return
        w_med = sum(fm.horizontalAdvance(l[:3]) + 16 for l in self._labels)
        if w_med <= available_w:
            if super().text() != self._variants[1]:
                super().setText(self._variants[1])
            return
        if super().text() != self._variants[2]:
            super().setText(self._variants[2])
