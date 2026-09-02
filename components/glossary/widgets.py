"""Glossary dialog helper widgets and review brushes."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QStyledItemDelegate,
    QStyle,
    QTableWidget,
    QWidget,
)
from PyQt6.QtGui import QPalette, QTextDocument, QAbstractTextDocumentLayout, QColor, QBrush

# Rows awaiting a human decision. Two strengths so a choice-between-variants
# is darker than a translation that just has not been confirmed yet.
_UNREVIEWED_BRUSH = QBrush(QColor("#fff3b0"))
_MULTI_VARIANT_BRUSH = QBrush(QColor("#e67e22"))
_NEEDS_REVIEW_BRUSH = _UNREVIEWED_BRUSH
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
    """Detail splitter pane: allows flexible resizing without artificial minimum constraints."""

    def minimumSizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(0, 30)


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
