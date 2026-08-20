"""Every main-window button must explain itself, modifier-clicks included."""
import pytest
from PyQt6.QtWidgets import QMainWindow, QPushButton

from ui.builders.layout_builder import LayoutBuilder


@pytest.fixture
def built_window(qtbot):
    """Build the main layout on a bare window, without the full application."""
    window = QMainWindow()
    qtbot.addWidget(window)
    LayoutBuilder(window).build()
    return window


def test_every_button_has_a_tooltip(built_window):
    untipped = [
        button.text() or button.objectName() or repr(button)
        for button in built_window.findChildren(QPushButton)
        if not button.toolTip().strip()
    ]
    assert not untipped, f"buttons without a tooltip: {untipped}"


@pytest.mark.parametrize(
    "button_name, expected",
    [
        # Modifier-clicks that the handlers actually implement.
        ("auto_fix_button", ["Ctrl-click", "Shift-click", "Ctrl+Shift+A"]),
        ("ai_translate_button", ["Ctrl-click"]),
        ("ai_variation_button", ["Ctrl-click"]),
    ],
)
def test_modifier_alternatives_are_documented(built_window, button_name, expected):
    tooltip = getattr(built_window, button_name).toolTip()
    for phrase in expected:
        assert phrase in tooltip, f"{button_name} tooltip is missing '{phrase}'"
