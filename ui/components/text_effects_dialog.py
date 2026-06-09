import math
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QCheckBox, QPushButton, QSlider, QSpinBox, QLabel, QDialogButtonBox,
    QColorDialog, QWidget
)
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush
from PyQt6.QtCore import Qt, pyqtSignal, QPointF


class AnglePickerWidget(QWidget):
    """Interactive wheel for choosing an angle (like in Photoshop)."""
    angleChanged = pyqtSignal(int)

    def __init__(self, parent=None, size=64):
        super().__init__(parent)
        self._angle = 0  # 0 to 359 degrees
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def angle(self) -> int:
        return self._angle

    def setAngle(self, angle: int):
        # Normalize to 0-359
        angle = (int(angle) % 360 + 360) % 360
        if self._angle != angle:
            self._angle = angle
            self.update()

    def paintEvent(self, event):
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            width = self.width()
            height = self.height()
            radius = min(width, height) / 2.0
            center = QPointF(width / 2.0, height / 2.0)

            # Draw main circle border and fill
            circle_radius = radius - 4.0
            
            # Subtle dark/light gradient or color fill depending on palette
            painter.setPen(QPen(QColor("#777777"), 1.5))
            is_dark = self.palette().color(self.backgroundRole()).lightness() < 128
            painter.setBrush(QBrush(QColor("#1e1e1e") if is_dark else QColor("#ffffff")))
            painter.drawEllipse(center, circle_radius, circle_radius)

            # Draw axis ticks
            tick_pen = QPen(QColor("#555555" if is_dark else "#cccccc"), 1)
            painter.setPen(tick_pen)
            
            tick_len = 4.0
            # Right (0)
            painter.drawLine(QPointF(center.x() + circle_radius - tick_len, center.y()), QPointF(center.x() + circle_radius, center.y()))
            # Left (180)
            painter.drawLine(QPointF(center.x() - circle_radius + tick_len, center.y()), QPointF(center.x() - circle_radius, center.y()))
            # Down (90)
            painter.drawLine(QPointF(center.x(), center.y() + circle_radius - tick_len), QPointF(center.x(), center.y() + circle_radius))
            # Up (270)
            painter.drawLine(QPointF(center.x(), center.y() - circle_radius + tick_len), QPointF(center.x(), center.y() - circle_radius))

            # Center dot
            painter.setBrush(QBrush(QColor("#ffffff" if is_dark else "#000000")))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(center, 2.0, 2.0)

            # Draw the needle representing the angle
            rad = math.radians(self._angle)
            line_len = circle_radius - 2.0
            target_x = center.x() + line_len * math.cos(rad)
            target_y = center.y() + line_len * math.sin(rad)
            target_point = QPointF(target_x, target_y)

            # Blue accent line for premium look
            accent_color = QColor("#007acc")
            painter.setPen(QPen(accent_color, 2))
            painter.drawLine(center, target_point)

            # Knob at needle tip
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.setPen(QPen(accent_color, 1.5))
            painter.drawEllipse(target_point, 4.0, 4.0)

    def _update_angle_from_mouse(self, pos):
        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        
        dx = pos.x() - center_x
        dy = pos.y() - center_y
        
        rad = math.atan2(dy, dx)
        deg = (int(math.degrees(rad)) % 360 + 360) % 360
        
        self.setAngle(deg)
        self.angleChanged.emit(deg)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._update_angle_from_mouse(event.pos())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._update_angle_from_mouse(event.pos())


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
        self.slider_alpha = QSlider(Qt.Orientation.Horizontal)
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
            # Angle row with interactive picker
            angle_layout = QHBoxLayout()
            
            # Interactive Angle Picker Wheel
            self.angle_picker = AnglePickerWidget(size=64)
            initial_angle = int(settings.get("angle", 315))
            self.angle_picker.setAngle(initial_angle)
            
            # Spin box for numerical entry
            self.spin_angle = QSpinBox()
            self.spin_angle.setRange(0, 359)
            self.spin_angle.setValue(initial_angle)
            self.spin_angle.setSuffix("°")
            self.spin_angle.setFixedWidth(70)
            
            # Connections for synchronization
            self.angle_picker.angleChanged.connect(self.spin_angle.setValue)
            self.spin_angle.valueChanged.connect(self.angle_picker.setAngle)
            
            # Text explanation
            lbl_angle_hint = QLabel("Drag needle or click wheel to set direction (Photoshop style).")
            lbl_angle_hint.setStyleSheet("color: #888; font-size: 9px;")
            lbl_angle_hint.setWordWrap(True)
            
            angle_layout.addWidget(self.angle_picker)
            
            right_col = QVBoxLayout()
            right_col.setSpacing(4)
            right_col.addWidget(self.spin_angle)
            right_col.addWidget(lbl_angle_hint)
            angle_layout.addLayout(right_col)
            
            form.addRow("Angle:", angle_layout)

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
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
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
