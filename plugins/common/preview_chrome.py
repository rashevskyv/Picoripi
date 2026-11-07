"""The chrome of a plugin's own preview widget, the same as the BFN preview (ui/components/bfn_preview/chrome.py).

A picture scaled to fit its space and a dark bar with the < > page arrows and the page count. Used by the Lunar
dialogue preview and the TotK-engine talk window (Tears of the Kingdom, Ocarina of Time on Switch 2).
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from core.i18n import tr
from ui.components.bfn_preview.helpers import _preview_icon

BAR_HEIGHT = 28
# The dark strip and bar of the BFN preview (ui/components/bfn_preview/chrome.py, BfnPreviewWindowBar).
BAR_STYLE = (
    "QFrame {"
    "  background: #181818;"
    "  border: 1px solid #2a2a2a;"
    "  border-radius: 4px;"
    "}"
    "QPushButton {"
    "  background: #1e1e1e;"
    "  color: #cccccc;"
    "  border: 1px solid #3a3a3a;"
    "  border-radius: 4px;"
    "}"
    "QPushButton:hover { background: #2d2d2d; color: #ffffff; }"
    "QLabel { color: #c8c8c8; font-size: 11px; border: none; background: transparent; }"
)


class ScaledPicture(QLabel):
    """A picture that fills its space, scaled both ways with its aspect kept and the pixels kept sharp."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._source = QPixmap()
        self.setMinimumSize(1, 1)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_picture(self, pixmap: QPixmap) -> None:
        self._source = pixmap
        self._fit()

    def clear_picture(self) -> None:
        self._source = QPixmap()
        self.clear()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

    def _fit(self) -> None:
        if self._source.isNull():
            return
        self.setPixmap(self._source.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.FastTransformation))


class PageBar(QFrame):
    """The dark bar under the picture: < page count >. ``turned`` carries -1 or 1."""

    turned = pyqtSignal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(BAR_HEIGHT)
        self.setStyleSheet(BAR_STYLE)
        self.prev = QPushButton(self)
        self.next = QPushButton(self)
        for button, kind, tip, step in ((self.prev, "prev", "Previous page", -1), (self.next, "next", "Next page", 1)):
            button.setFixedSize(24, 22)
            button.setIcon(_preview_icon(kind, 12))
            button.setIconSize(QSize(12, 12))
            button.setToolTip(tr(tip))
            button.clicked.connect(lambda _checked=False, step=step: self.turned.emit(step))
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)
        layout.addStretch(1)
        layout.addWidget(self.prev)
        layout.addWidget(self.label)
        layout.addWidget(self.next)
        layout.addStretch(1)

    def show_page(self, index: int, count: int) -> None:
        """Page ``index`` (from 0) of ``count``; no pages clears the count and turns both arrows off."""
        self.label.setText(tr("Page {0} of {1}").format(index + 1, count) if count else "")
        self.prev.setEnabled(count > 0 and index > 0)
        self.next.setEnabled(index < count - 1)
