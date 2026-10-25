"""Glossary dialog helper widgets and review brushes."""
from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt, QSize
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QStyledItemDelegate,
    QStyle,
    QTableWidget,
    QSplitter,
    QWidget,
)
from PyQt6.QtGui import QPalette, QTextDocument, QAbstractTextDocumentLayout, QColor, QBrush
from utils.thread_utils import single_shot

# Rows awaiting a human decision. Two strengths so a choice-between-variants
# is darker than a translation that just has not been confirmed yet.
_UNREVIEWED_BRUSH = QBrush(QColor("#fff3b0"))
_MULTI_VARIANT_BRUSH = QBrush(QColor("#e67e22"))
_NEEDS_REVIEW_BRUSH = _UNREVIEWED_BRUSH
# A term the project and the series glossary translate differently.
_CONFLICT_BRUSH = QBrush(QColor("#f8b4b4"))
# Foreground color for provisional game-code character rows, matching
# Merge Speakers "Unmatched manual rows".
_PROVISIONAL_FOREGROUND = QBrush(QColor("#6a1b9a"))


class _GlossaryTermTable(QTableWidget):
    """Term list: never pan sideways on click or current-cell change."""

    def scrollTo(self, index, hint=QAbstractItemView.ScrollHint.EnsureVisible):
        bar = self.horizontalScrollBar()
        x = bar.value()
        super().scrollTo(index, hint)
        bar.setValue(x)


class _DetailPane(QWidget):
    """Detail splitter pane that keeps its section header visible when collapsed."""

    def __init__(self, parent=None, *, flexible_minimum=False):
        super().__init__(parent)
        self._header_layout = None
        self._collapsed = False
        self._refresh_pending = False
        self._rebalance_callback = None
        self._flexible_minimum = flexible_minimum

    def set_rebalance_callback(self, callback) -> None:
        self._rebalance_callback = callback

    def watch_header(self, layout) -> None:
        """Track header controls so live font, style, and visibility changes resize this pane."""
        self._header_layout = layout
        self._watch_layout_widgets(layout)
        self._refresh_collapsed_height()

    def _watch_layout_widgets(self, layout) -> None:
        for index in range(layout.count()):
            item = layout.itemAt(index)
            widget = item.widget()
            if widget is not None:
                widget.installEventFilter(self)
            elif item.layout() is not None:
                self._watch_layout_widgets(item.layout())

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self._refresh_collapsed_height()

    def _refresh_collapsed_height(self) -> None:
        if self.layout() is not None:
            self.layout().activate()
        self.setMinimumHeight(0)
        self.setMaximumHeight(self.minimumSizeHint().height() if self._collapsed else 16777215)
        self.updateGeometry()
        splitter = self.parentWidget()
        if isinstance(splitter, QSplitter):
            splitter.refresh()
            splitter.setSizes(splitter.sizes())
            splitter.updateGeometry()
            parent_layout = splitter.parentWidget().layout()
            if parent_layout is not None:
                parent_layout.invalidate()

    def _schedule_refresh(self) -> None:
        if self._refresh_pending:
            return
        self._refresh_pending = True
        single_shot(0, self, self._refresh_after_layout)

    def _refresh_after_layout(self) -> None:
        self._refresh_pending = False
        self._refresh_collapsed_height()
        if self._rebalance_callback is not None:
            self._rebalance_callback()

    def minimumSizeHint(self) -> QSize:  # type: ignore[override]
        if self._header_layout is None:
            if self._flexible_minimum:
                return QSize(0, 30)
            return super().minimumSizeHint()
        layout = self.layout()
        if layout is None:
            return QSize(0, 0)
        header = layout.itemAt(0)
        header_layout = header.layout() if header is not None else None
        header_height = max(header.sizeHint().height(), header.minimumSize().height()) if header is not None else 0
        if header_layout is not None:
            for index in range(header_layout.count()):
                widget = header_layout.itemAt(index).widget()
                if widget is not None and not widget.isHidden():
                    header_height = max(header_height, widget.sizeHint().height(), widget.minimumSizeHint().height())
        margins = layout.contentsMargins()
        return QSize(0, header_height + margins.top() + margins.bottom())

    def changeEvent(self, event: QEvent) -> None:
        """Refresh splitter geometry when a collapsed header's font or style changes."""
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange, QEvent.Type.LayoutDirectionChange):
            self._schedule_refresh()

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange, QEvent.Type.Show, QEvent.Type.Hide):
            self._schedule_refresh()
        return super().eventFilter(watched, event)


class _RichTextItemDelegate(QStyledItemDelegate):
    """Render rich-text list items (e.g., occurrences list)."""

    def paint(self, painter, option, index):  # type: ignore[override]
        """Paint."""
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if not text:
            super().paint(painter, option, index)
            return

        doc = QTextDocument()
        doc.setDefaultFont(option.font)
        doc.setHtml(str(text))
        
        # Add 6px padding on left/right
        text_rect = option.rect.adjusted(6, 6, -6, -6)
        doc.setTextWidth(text_rect.width())

        painter.save()
        paint_context = QAbstractTextDocumentLayout.PaintContext()

        color_group = QPalette.ColorGroup.Active if option.state & QStyle.StateFlag.State_Active else QPalette.ColorGroup.Inactive
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
            paint_context.palette.setColor(
                QPalette.ColorRole.Text,
                option.palette.color(color_group, QPalette.ColorRole.HighlightedText),
            )
        else:
            paint_context.palette.setColor(
                QPalette.ColorRole.Text,
                option.palette.color(color_group, QPalette.ColorRole.Text),
            )

        painter.translate(text_rect.topLeft())
        painter.setClipRect(text_rect.translated(-text_rect.topLeft()))
        doc.documentLayout().draw(painter, paint_context)
        painter.restore()

        # Draw light gray separating line at the bottom
        painter.save()
        painter.setPen(QColor(220, 220, 220))
        painter.drawLine(option.rect.left(), option.rect.bottom(), option.rect.right(), option.rect.bottom())
        painter.restore()

    def sizeHint(self, option, index):  # type: ignore[override]
        """Sizehint."""
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if not text:
            return super().sizeHint(option, index)

        doc = QTextDocument()
        doc.setDefaultFont(option.font)
        doc.setHtml(str(text))
        width = option.rect.width()
        if width <= 0 and option.widget is not None:
            viewport = getattr(option.widget, 'viewport', None)
            if callable(viewport):
                width = viewport().width()
        if width > 0:
            doc.setTextWidth(width - 12) # Subtract 12px for padding (6px left, 6px right)
        size = doc.documentLayout().documentSize()
        return QSize(int(size.width()), int(size.height()) + 14) # 6px top, 6px bottom + 2px line space


class _VariantItemDelegate(QStyledItemDelegate):
    """Render variant list items with a horizontal separating line."""

    def paint(self, painter, option, index):  # type: ignore[override]
        """Paint."""
        super().paint(painter, option, index)
        painter.save()
        painter.setPen(QColor(220, 220, 220))
        painter.drawLine(option.rect.left(), option.rect.bottom(), option.rect.right(), option.rect.bottom())
        painter.restore()

    def sizeHint(self, option, index):  # type: ignore[override]
        """Sizehint."""
        size = super().sizeHint(option, index)
        return QSize(size.width(), max(size.height() + 6, 26))
