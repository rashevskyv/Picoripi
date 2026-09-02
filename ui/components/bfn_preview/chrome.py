"""BFN preview chrome widgets (side button, window bar, sidebar)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from core.i18n import tr
from ui.components.bfn_preview.helpers import _letter_icon, _preview_icon

if TYPE_CHECKING:
    from ui.components.bfn_preview.widget import BfnPreviewWidget

class BfnSideButton(QPushButton):
    """A compact square icon button for the BFN preview sidebar."""
    SIZE = 30

    def __init__(self, icon_key: str, tooltip: str, checkable: bool = False, parent=None,
                 text: str = ""):
        """Initialize a new instance."""
        super().__init__(text, parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setToolTip(tooltip)
        self.setCheckable(checkable)
        if icon_key:
            self.setIcon(_preview_icon(icon_key))
            self.setIconSize(QSize(16, 16))
        self._apply_style(False)

    def _apply_style(self, checked: bool):
        """Internal helper to apply style."""
        base = (
            "QPushButton {"
            "  background: #1e1e1e;"
            "  color: #cccccc;"
            "  border: 1px solid #3a3a3a;"
            "  border-radius: 5px;"
            "  font-size: 14px;"
            "}"
            "QPushButton:hover {"
            "  background: #2d2d2d;"
            "  border-color: #5a5a5a;"
            "}"
        )
        active = (
            "QPushButton:checked, QPushButton[active=\"true\"] {"
            "  background: #1c3a5e;"
            "  border-color: #0078d7;"
            "  color: #ffffff;"
            "}"
        )
        self.setStyleSheet(base + active)

    def setActive(self, active: bool):
        """Setactive."""
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)
class BfnPreviewWindowBar(QFrame):
    """Compact Auto / manual window-preset switcher placed under the preview.

    Ephemeral UI state only — never rewrites INF1/BMG attributes.
    """

    def __init__(self, preview_widget: 'BfnPreviewWidget'):
        super().__init__(preview_widget.parent() if preview_widget else None)
        self.preview = preview_widget
        self.setObjectName("bfn_preview_window_bar")
        self.setFixedHeight(28)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self.setStyleSheet(
            "BfnPreviewWindowBar {"
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
            "QLabel { color: #c8c8c8; font-size: 11px; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)
        self.btn_prev = QPushButton(tr(''), self)
        self.btn_next = QPushButton(tr(''), self)
        for btn, kind, tip in (
            (self.btn_prev, "prev", "Previous message-window preview preset"),
            (self.btn_next, "next", "Next message-window preview preset"),
        ):
            btn.setFixedSize(24, 22)
            btn.setIcon(_preview_icon(kind, 12))
            btn.setIconSize(QSize(12, 12))
            btn.setToolTip(tip)
        self.label = QLabel(tr('Auto'), self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.btn_prev.clicked.connect(lambda: self.preview.cycle_window_preset(-1))
        self.btn_next.clicked.connect(lambda: self.preview.cycle_window_preset(1))
        layout.addStretch(1)
        layout.addWidget(self.btn_prev)
        layout.addWidget(self.label)
        layout.addWidget(self.btn_next)
        layout.addStretch(1)
        self._lock_label_width()
        if preview_widget is not None:
            preview_widget.window_preset_bar = self
            preview_widget._refresh_window_preset_label()

    def _lock_label_width(self):
        """Keep arrows still when the preset name changes length."""
        fm = self.label.fontMetrics()
        widest = fm.horizontalAdvance("Auto: Dialogue")
        try:
            from plugins.zelda_bmg.window_kinds import (
                PREVIEW_WINDOW_PRESETS, preset_label, WINDOW_KIND_STYLES,
                EXPLAIN_WINDOW_STYLE,
            )
            names = [preset_label(p) for p in PREVIEW_WINDOW_PRESETS]
            names.extend("Auto: " + s.get("kind_name", "") for s in WINDOW_KIND_STYLES.values())
            names.append("Auto: " + EXPLAIN_WINDOW_STYLE.get("kind_name", "Explain"))
            for name in names:
                if name:
                    widest = max(widest, fm.horizontalAdvance(name))
        except Exception:
            widest = max(widest, 160)
        self.label.setMinimumWidth(widest + 12)

    def set_label(self, text: str):
        self.label.setText(text)
class BfnPreviewSideBar(QFrame):
    """Vertical toolbar pinned to the left side of BfnPreviewWidget."""
    WIDTH = 38

    def __init__(self, preview_widget: 'BfnPreviewWidget'):
        """Initialize a new instance."""
        super().__init__(preview_widget)
        self.pw = preview_widget
        self.setFixedWidth(self.WIDTH)
        self.setStyleSheet(
            "BfnPreviewSideBar {"
            "  background: rgba(15, 15, 15, 200);"
            "  border-right: 1px solid #2a2a2a;"
            "  border-top-left-radius: 6px;"
            "  border-bottom-left-radius: 6px;"
            "}"
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.btn_color = BfnSideButton("", "Text Color")
        self._update_color_btn()
        self.btn_color.clicked.connect(self.pw._open_text_color_dialog)
        layout.addWidget(self.btn_color)

        self.btn_shadow = BfnSideButton("shadow", "Drop Shadow (click to configure)", checkable=True)
        self.btn_shadow.setChecked(self.pw.shadow_enabled)
        self.btn_shadow.clicked.connect(self._on_shadow_clicked)
        layout.addWidget(self.btn_shadow)

        self.btn_glow = BfnSideButton("glow", "Outer Glow (click to configure)", checkable=True)
        self.btn_glow.setChecked(self.pw.glow_enabled)
        self.btn_glow.clicked.connect(self._on_glow_clicked)
        layout.addWidget(self.btn_glow)

        layout.addSpacing(6)

        self.btn_bg = BfnSideButton("image", "Set Background Image...")
        self.btn_bg.clicked.connect(self._on_set_bg)
        layout.addWidget(self.btn_bg)

        self.btn_hide_bg = BfnSideButton("eye", "Show / Hide Background", checkable=True)
        self.btn_hide_bg.setChecked(self.pw.bg_hidden)
        self.btn_hide_bg.setEnabled(bool(self.pw.bg_image_path))
        self.btn_hide_bg.clicked.connect(self._on_hide_bg)
        layout.addWidget(self.btn_hide_bg)

        layout.addSpacing(6)

        self.btn_spacing = BfnSideButton("spacing", "Set Line Spacing...")
        self.btn_spacing.clicked.connect(self._on_set_spacing)
        layout.addWidget(self.btn_spacing)

        layout.addStretch()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _update_color_btn(self):
        """Dark chrome like the other tools; an A glyph in the preview text color."""
        c = QColor(self.pw.text_color)
        if not c.isValid():
            c = QColor("#ffffff")
        self.btn_color.setText("")
        self.btn_color.setIcon(_letter_icon("A", c.name()))
        self.btn_color.setIconSize(QSize(16, 16))
        self.btn_color._apply_style(False)

    def refresh_state(self):
        """Sync button visual states with current widget settings."""
        self._update_color_btn()
        self.btn_shadow.setChecked(self.pw.shadow_enabled)
        self.btn_glow.setChecked(self.pw.glow_enabled)
        self.btn_hide_bg.setChecked(self.pw.bg_hidden)
        self.btn_hide_bg.setEnabled(bool(self.pw.bg_image_path))

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_shadow_clicked(self, checked: bool):
        """Open shadow dialog; if user cancels keep previous enabled state."""
        self.pw._open_shadow_dialog()
        self.btn_shadow.setChecked(self.pw.shadow_enabled)

    def _on_glow_clicked(self, checked: bool):
        """Internal helper to handle the glow clicked event."""
        self.pw._open_glow_dialog()
        self.btn_glow.setChecked(self.pw.glow_enabled)

    def _on_set_bg(self):
        """Internal helper to handle the set bg event."""
        file_path, _ = QFileDialog.getOpenFileName(
            self.pw, "Select Background Image", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not file_path:
            return
        self.pw.bg_image_path = file_path
        had_previous_image = self.pw.bg_image is not None and not self.pw.bg_image.isNull()
        try:
            new_image = QImage(file_path)
            self.pw.bg_image = new_image
            self.pw.mw.preview_bg_image_path = file_path
            if not new_image.isNull() and (not had_previous_image or
                    (self.pw.bg_offset_x == 0 and self.pw.bg_offset_y == 0)):
                sf = self.pw.bg_scale / 100.0
                self.pw.bg_offset_x = int((self.pw.width() - new_image.width() * sf) / 2)
                self.pw.bg_offset_y = int((self.pw.height() - new_image.height() * sf) / 2)
                self.pw.mw.preview_bg_offset_x = self.pw.bg_offset_x
                self.pw.mw.preview_bg_offset_y = self.pw.bg_offset_y
            if hasattr(self.pw.mw, 'settings_manager'):
                self.pw.mw.settings_manager.save_settings()
        except Exception:
            self.pw.bg_image = None
        self.refresh_state()
        self.pw.update()

    def _on_hide_bg(self, checked: bool):
        """Internal helper to handle the hide bg event."""
        self.pw.bg_hidden = checked
        self.pw.mw.preview_bg_hidden = checked
        if hasattr(self.pw.mw, 'settings_manager'):
            self.pw.mw.settings_manager.save_settings()
        self.pw.update()

    def _on_set_spacing(self):
        """Internal helper to handle the set spacing event."""
        val, ok = QInputDialog.getInt(
            self.pw, "Set Line Spacing", "Enter line spacing in pixels:",
            self.pw.line_spacing, -100, 100
        )
        if ok:
            self.pw.line_spacing = val
            self.pw.mw.preview_line_spacing = val
            if hasattr(self.pw.mw, 'settings_manager'):
                self.pw.mw.settings_manager.save_settings()
            self.pw.update()
