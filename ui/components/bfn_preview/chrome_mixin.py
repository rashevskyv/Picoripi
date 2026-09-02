"""Stylesheets, source button, page bar chrome, sidebar, hover resize events."""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QFrame, QLabel, QLayout, QPushButton, QVBoxLayout

from core.i18n import tr
from ui.components.bfn_preview.chrome import BfnPreviewSideBar
from ui.components.bfn_preview.helpers import _letter_icon, _preview_icon

class BfnPreviewChromeMixin:
    """Mixin: preview chrome positioning and stylesheets."""

    def _button_stylesheet(self) -> str:
        return (
            "QPushButton {"
            "  background: #1e1e1e;"
            "  color: #cccccc;"
            "  border: 1px solid #3a3a3a;"
            "  border-radius: 5px;"
            "  font-size: 11px;"
            "}"
            "QPushButton:hover {"
            "  background: #2d2d2d;"
            "  border-color: #5a5a5a;"
            "  color: #ffffff;"
            "}"
            "QPushButton:disabled {"
            "  color: #444444;"
            "  background: #121212;"
            "  border-color: #222222;"
            "}"
        )

    def _indicator_stylesheet(self) -> str:
        return (
            "QPushButton {"
            "  background: transparent;"
            "  border: 2px solid #555555;"
            "  border-radius: 2px;"
            "}"
            "QPushButton:hover {"
            "  border-color: #888888;"
            "}"
            "QPushButton:checked {"
            "  background: #0078d7;"
            "  border-color: #0078d7;"
            "}"
        )

    def _build_source_button(self):
        """Top-right toggle between original and translated preview text."""
        self.source_btn = QPushButton(self)
        self.source_btn.setFixedSize(30, 30)
        self.source_btn.setStyleSheet(self._button_stylesheet())
        self.source_btn.clicked.connect(self._toggle_preview_source)
        self._refresh_source_button()

    def _refresh_source_button(self):
        if not hasattr(self, "source_btn"):
            return
        showing_orig = self._preview_shows_original
        self.source_btn.setIcon(_letter_icon("O" if showing_orig else "T", "#e0e0e0"))
        self.source_btn.setIconSize(QSize(16, 16))
        self.source_btn.setToolTip(
            "Previewing original. Click to show the translation."
            if showing_orig else
            "Previewing translation. Click to show the original."
        )
        self._position_source_button()

    def _position_source_button(self):
        if hasattr(self, "source_btn"):
            self.source_btn.move(self.width() - 34, 4)
            self.source_btn.raise_()

    def _toggle_preview_source(self):
        self._preview_shows_original = not self._preview_shows_original
        self.text = (self._original_preview_text if self._preview_shows_original
                     else self._edited_preview_text)
        self._preview_page = 0
        self._refresh_source_button()
        self._refresh_page_bar()
        self.update()

    def _build_page_bar(self):
        """Fixed-size up / n/N / down control. Never stretches with the preview."""
        self.page_bar = QFrame(self)
        self.page_bar.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self.page_bar.setFixedSize(32, 84)
        self.page_bar.setStyleSheet(
            "QFrame {"
            "  background: rgba(18, 18, 18, 230);"
            "  border: 1px solid #3a3a3a;"
            "  border-radius: 6px;"
            "}"
        )
        layout = QVBoxLayout(self.page_bar)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        self.btn_page_prev = QPushButton(tr(''), self.page_bar)
        self.btn_page_prev.setFixedSize(26, 26)
        self.btn_page_prev.setIcon(_preview_icon("up", 12))
        self.btn_page_prev.setIconSize(QSize(12, 12))
        self.btn_page_prev.setStyleSheet(self._button_stylesheet())
        self.btn_page_prev.clicked.connect(lambda: self._change_page(-1))
        self.btn_page_prev.setToolTip(tr('Previous page'))
        layout.addWidget(self.btn_page_prev, 0, Qt.AlignmentFlag.AlignHCenter)

        self.page_index_label = QLabel(tr('1/1'), self.page_bar)
        self.page_index_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_index_label.setFixedSize(26, 16)
        self.page_index_label.setStyleSheet("QLabel { color: #dddddd; font-size: 10px; }")
        layout.addWidget(self.page_index_label, 0, Qt.AlignmentFlag.AlignHCenter)

        self.btn_page_next = QPushButton(tr(''), self.page_bar)
        self.btn_page_next.setFixedSize(26, 26)
        self.btn_page_next.setIcon(_preview_icon("down", 12))
        self.btn_page_next.setIconSize(QSize(12, 12))
        self.btn_page_next.setStyleSheet(self._button_stylesheet())
        self.btn_page_next.clicked.connect(lambda: self._change_page(1))
        self.btn_page_next.setToolTip(tr('Next page'))
        layout.addWidget(self.btn_page_next, 0, Qt.AlignmentFlag.AlignHCenter)

        self.indicator_buttons = []
        self.page_bar.hide()

    def _position_page_bar(self):
        if not hasattr(self, "page_bar") or self.page_bar.isHidden():
            return
        bar_w, bar_h = self.page_bar.width(), self.page_bar.height()
        x = self.width() - bar_w - 4
        y = max(38, (self.height() - bar_h) // 2)
        y = min(y, max(38, self.height() - bar_h - 4))
        self.page_bar.move(x, y)
        self.page_bar.raise_()
        self._position_source_button()

    def _position_sidebar(self):
        """Pin the sidebar to the left edge, full height."""
        if hasattr(self, 'sidebar'):
            self.sidebar.setGeometry(0, 0, BfnPreviewSideBar.WIDTH, self.height())
            self.sidebar.raise_()

    def resizeEvent(self, event):
        """Resizeevent."""
        super().resizeEvent(event)
        self._position_sidebar()
        self._position_page_bar()
        self._position_source_button()

    def enterEvent(self, event):
        """Enterevent."""
        self.mouse_inside = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Leaveevent."""
        self.mouse_inside = False
        self.hover_handle = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        super().leaveEvent(event)
