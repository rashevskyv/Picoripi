import math
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QCheckBox, QPushButton, QSlider, QSpinBox, QLabel, QDialogButtonBox,
    QColorDialog
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt


class TextEffectsDialog(QDialog):
    """Generic dialog for configuring Drop Shadow or Outer Glow effect parameters."""

    MODE_SHADOW = "shadow"
    MODE_GLOW = "glow"

    def __init__(self, mode: str, settings: dict, parent=None):
        """
        Args:
            mode: TextEffectsDialog.MODE_SHADOW or MODE_GLOW
            settings: dict with current values:
                For shadow: enabled, color (hex str), alpha (0-255), angle (0-360), distance (0-30)
                For glow:   enabled, color (hex str), alpha (0-255), spread (1-20)
        """
        super().__init__(parent)
        self.mode = mode
        self._color_hex = settings.get("color", "#000000" if mode == self.MODE_SHADOW else "#ffffff")
        self._result = {}

        title = "Drop Shadow Settings" if mode == self.MODE_SHADOW else "Outer Glow Settings"
        self.setWindowTitle(title)
        self.setMinimumWidth(340)
        self.setModal(True)

        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(12)

        # ── Enabled checkbox ──────────────────────────────────────────────────
        self.chk_enabled = QCheckBox("Enable effect")
        self.chk_enabled.setChecked(bool(settings.get("enabled", False)))
        root_layout.addWidget(self.chk_enabled)

        # ── Group box with parameters ─────────────────────────────────────────
        group = QGroupBox("Parameters")
        form = QFormLayout(group)
        form.setSpacing(8)
        root_layout.addWidget(group)

        # Color row
        color_row = QHBoxLayout()
        self._color_preview = QLabel()
        self._color_preview.setFixedSize(32, 22)
        self._color_preview.setStyleSheet(f"background-color: {self._color_hex}; border: 1px solid #555; border-radius: 3px;")
        btn_color = QPushButton("Pick Color…")
        btn_color.setFixedWidth(100)
        btn_color.clicked.connect(self._pick_color)
        color_row.addWidget(self._color_preview)
        color_row.addWidget(btn_color)
        color_row.addStretch()
        form.addRow("Color:", color_row)

        # Alpha (opacity) row
        alpha_row = QHBoxLayout()
        self.slider_alpha = QSlider(Qt.Horizontal)
        self.slider_alpha.setRange(0, 255)
        self.slider_alpha.setValue(int(settings.get("alpha", 178)))
        self.spin_alpha = QSpinBox()
        self.spin_alpha.setRange(0, 255)
        self.spin_alpha.setValue(self.slider_alpha.value())
        self.spin_alpha.setFixedWidth(60)
        self.slider_alpha.valueChanged.connect(self.spin_alpha.setValue)
        self.spin_alpha.valueChanged.connect(self.slider_alpha.setValue)
        alpha_row.addWidget(self.slider_alpha)
        alpha_row.addWidget(self.spin_alpha)
        form.addRow("Opacity (0–255):", alpha_row)

        if mode == self.MODE_SHADOW:
            # Angle row
            angle_row = QHBoxLayout()
            self.spin_angle = QSpinBox()
            self.spin_angle.setRange(0, 360)
            self.spin_angle.setValue(int(settings.get("angle", 315)))
            self.spin_angle.setSuffix("°")
            self.spin_angle.setFixedWidth(80)
            lbl_angle_hint = QLabel("(0° = right, 90° = down, 270° = up, 315° = upper-left)")
            lbl_angle_hint.setStyleSheet("color: #888; font-size: 9px;")
            angle_row.addWidget(self.spin_angle)
            angle_row.addWidget(lbl_angle_hint)
            angle_row.addStretch()
            form.addRow("Angle:", angle_row)

            # Distance row
            self.spin_distance = QSpinBox()
            self.spin_distance.setRange(0, 30)
            self.spin_distance.setValue(int(settings.get("distance", 3)))
            self.spin_distance.setSuffix(" px")
            self.spin_distance.setFixedWidth(80)
            form.addRow("Distance:", self.spin_distance)

        else:  # GLOW
            # Spread row
            self.spin_spread = QSpinBox()
            self.spin_spread.setRange(1, 20)
            self.spin_spread.setValue(int(settings.get("spread", 4)))
            self.spin_spread.setSuffix(" px")
            self.spin_spread.setFixedWidth(80)
            form.addRow("Spread:", self.spin_spread)

        # ── OK / Cancel ───────────────────────────────────────────────────────
        bbox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bbox.accepted.connect(self._on_accept)
        bbox.rejected.connect(self.reject)
        root_layout.addWidget(bbox)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _pick_color(self):
        initial = QColor(self._color_hex)
        color = QColorDialog.getColor(initial, self, "Select Color")
        if color.isValid():
            self._color_hex = color.name()
            self._color_preview.setStyleSheet(
                f"background-color: {self._color_hex}; border: 1px solid #555; border-radius: 3px;"
            )

    def _on_accept(self):
        self._result["enabled"] = self.chk_enabled.isChecked()
        self._result["color"] = self._color_hex
        self._result["alpha"] = self.spin_alpha.value()
        if self.mode == self.MODE_SHADOW:
            self._result["angle"] = self.spin_angle.value()
            self._result["distance"] = self.spin_distance.value()
        else:
            self._result["spread"] = self.spin_spread.value()
        self.accept()

    def get_result(self) -> dict:
        """Returns the result dict after dialog was accepted."""
        return self._result
