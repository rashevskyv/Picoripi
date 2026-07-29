import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPointF, Qt, QEvent
from PyQt6.QtGui import QMouseEvent
from ui.components.text_effects_dialog import AnglePickerWidget, TextEffectsDialog


@pytest.fixture(scope="module")
def qapp():
    """Ensure a QApplication exists for widget testing."""
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_angle_picker_init(qapp):
    picker = AnglePickerWidget()
    assert picker.angle() == 0
    
    picker.setAngle(90)
    assert picker.angle() == 90


def test_angle_picker_normalization(qapp):
    picker = AnglePickerWidget()
    
    picker.setAngle(-45)
    assert picker.angle() == 315
    
    picker.setAngle(450)
    assert picker.angle() == 90
    
    picker.setAngle(360)
    assert picker.angle() == 0


def test_angle_picker_mouse_event(qapp):
    picker = AnglePickerWidget(size=100)  # Center is at (50, 50)
    
    # Track signal emits
    emitted_angles = []
    picker.angleChanged.connect(emitted_angles.append)
    
    # 1. Click at (100, 50) -> vector (50, 0) -> angle 0
    press_event = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(100.0, 50.0), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    picker.mousePressEvent(press_event)
    assert picker.angle() == 0
    assert 0 in emitted_angles
    
    # 2. Drag/move to (50, 100) -> vector (0, 50) -> angle 90
    move_event = QMouseEvent(QEvent.Type.MouseMove, QPointF(50.0, 100.0), Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    # Move events usually check buttons mask
    picker.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, QPointF(50.0, 100.0), Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    assert picker.angle() == 90
    assert 90 in emitted_angles


def test_text_effects_dialog_shadow_init(qapp):
    settings = {
        "enabled": True,
        "color": "#ff0000",
        "alpha": 200,
        "angle": 120,
        "distance": 5
    }
    
    dialog = TextEffectsDialog(TextEffectsDialog.MODE_SHADOW, settings)
    
    assert dialog.chk_enabled.isChecked() is True
    assert dialog.spin_alpha.value() == 200
    assert dialog.spin_angle.value() == 120
    assert dialog.angle_picker.angle() == 120
    assert dialog.spin_distance.value() == 5


def test_text_effects_dialog_shadow_sync(qapp):
    settings = {
        "enabled": True,
        "color": "#ff0000",
        "alpha": 200,
        "angle": 120,
        "distance": 5
    }
    
    dialog = TextEffectsDialog(TextEffectsDialog.MODE_SHADOW, settings)
    
    # Change spin box -> picker should sync
    dialog.spin_angle.setValue(180)
    assert dialog.angle_picker.angle() == 180
    
    # Change picker -> spin box should sync
    dialog.angle_picker.setAngle(270)
    # Trigger signal manually since we called setAngle programmatic
    dialog.angle_picker.angleChanged.emit(270)
    assert dialog.spin_angle.value() == 270


def test_text_effects_dialog_accept(qapp):
    settings = {
        "enabled": False,
        "color": "#00ff00",
        "alpha": 100,
        "angle": 45,
        "distance": 2
    }
    
    dialog = TextEffectsDialog(TextEffectsDialog.MODE_SHADOW, settings)
    
    dialog.chk_enabled.setChecked(True)
    dialog.spin_alpha.setValue(150)
    dialog.spin_angle.setValue(60)
    dialog.spin_distance.setValue(10)
    
    # Simulate Accept
    dialog._on_accept()
    
    result = dialog.get_result()
    assert result["enabled"] is True
    assert result["alpha"] == 150
    assert result["angle"] == 60
    assert result["distance"] == 10
