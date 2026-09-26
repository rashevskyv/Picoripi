"""Tests for QToolTip theme styling and scoped button stylesheet isolation."""
from __future__ import annotations

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QToolTip

from components.glossary.dialog import GlossaryDialog
from ui.main_window.main_window_ui_handler import MainWindowUIHandler
from ui.themes import DARK_THEME_STYLESHEET, LIGHT_THEME_STYLESHEET


def test_stylesheets_define_qtooltip_rules():
    """Verify that both dark and light stylesheets explicitly define QToolTip styling."""
    assert "QToolTip" in DARK_THEME_STYLESHEET
    assert "#2E2E2E" in DARK_THEME_STYLESHEET
    assert "#E0E0E0" in DARK_THEME_STYLESHEET
    assert "#505050" in DARK_THEME_STYLESHEET

    assert "QToolTip" in LIGHT_THEME_STYLESHEET
    assert "#F8F9FA" in LIGHT_THEME_STYLESHEET
    assert "#212529" in LIGHT_THEME_STYLESHEET
    assert "#CED4DA" in LIGHT_THEME_STYLESHEET


def test_dark_theme_tooltip_palette_and_rendering(qtbot):
    """Verify dark theme tooltip has dark background and light text without whiteout."""
    app = QApplication.instance()
    MainWindowUIHandler.apply_theme(app, "dark")

    btn = QPushButton("Test Button")
    qtbot.addWidget(btn)
    btn.setToolTip("Dark Theme Tooltip")
    btn.show()

    QToolTip.showText(QPoint(100, 100), "Dark Theme Tooltip", btn)
    QApplication.processEvents()

    tip_label = None
    for top in app.topLevelWidgets():
        if isinstance(top, QLabel) and top.text() == "Dark Theme Tooltip":
            tip_label = top
            break

    assert tip_label is not None, "Tooltip label widget not found"
    assert tip_label.palette().color(tip_label.foregroundRole()).name().lower() == "#e0e0e0"
    assert tip_label.palette().color(tip_label.backgroundRole()).name().lower() == "#2e2e2e"

    pixmap = tip_label.grab()
    img = pixmap.toImage()
    white_count = sum(
        1
        for x in range(img.width())
        for y in range(img.height())
        if img.pixelColor(x, y).name().lower() == "#ffffff"
    )
    # The tooltip interior should not be washed out in white
    assert white_count == 0
    QToolTip.hideText()


def test_light_theme_tooltip_palette_and_rendering(qtbot):
    """Verify light theme tooltip has light background and dark text."""
    app = QApplication.instance()
    MainWindowUIHandler.apply_theme(app, "light")

    btn = QPushButton("Test Button")
    qtbot.addWidget(btn)
    btn.setToolTip("Light Theme Tooltip")
    btn.show()

    QToolTip.showText(QPoint(100, 100), "Light Theme Tooltip", btn)
    QApplication.processEvents()

    tip_label = None
    for top in app.topLevelWidgets():
        if isinstance(top, QLabel) and top.text() == "Light Theme Tooltip":
            tip_label = top
            break

    assert tip_label is not None, "Tooltip label widget not found"
    assert tip_label.palette().color(tip_label.foregroundRole()).name().lower() == "#212529"
    assert tip_label.palette().color(tip_label.backgroundRole()).name().lower() == "#f8f9fa"
    QToolTip.hideText()

    # Restore dark theme for subsequent tests
    MainWindowUIHandler.apply_theme(app, "dark")


def test_glossary_dialog_buttons_do_not_leak_white_text_to_tooltips(qtbot):
    """Verify that styled buttons in GlossaryDialog do not cause white text on white tooltips."""
    app = QApplication.instance()
    MainWindowUIHandler.apply_theme(app, "dark")

    dlg = GlossaryDialog(
        parent=None,
        entries=[],
        occurrence_map={},
        jump_callback=lambda x: None,
        build_callback=lambda: None,
        force_retranslate_callback=lambda: None,
        ai_classify_callback=lambda: None,
        clear_callback=lambda: None,
        global_replace_callback=lambda a, b: None,
    )
    qtbot.addWidget(dlg)
    dlg.show()
    QApplication.processEvents()

    buttons_to_test = [
        dlg._global_replace_button,
        dlg._build_button,
        dlg._retranslate_button,
        dlg._ai_classify_button,
        dlg._clear_button,
    ]

    for btn in buttons_to_test:
        tip = btn.toolTip() or "Test Tooltip"
        QToolTip.showText(QPoint(100, 100), tip, btn)
        QApplication.processEvents()

        tip_label = None
        for top in app.topLevelWidgets():
            if isinstance(top, QLabel) and top.text() == tip:
                tip_label = top
                break

        assert tip_label is not None, f"Tooltip label for button {btn.text()} not found"
        text_color = tip_label.palette().color(tip_label.foregroundRole()).name().lower()
        bg_color = tip_label.palette().color(tip_label.backgroundRole()).name().lower()

        # Must NOT be white text on white background
        assert not (text_color == "#ffffff" and bg_color == "#ffffff"), (
            f"Button '{btn.text()}' has white text on white background tooltip!"
        )
        assert text_color == "#e0e0e0", f"Unexpected text color {text_color} for button {btn.text()}"
        assert bg_color == "#2e2e2e", f"Unexpected background color {bg_color} for button {btn.text()}"

        pixmap = tip_label.grab()
        img = pixmap.toImage()
        white_pixels = sum(
            1
            for x in range(img.width())
            for y in range(img.height())
            if img.pixelColor(x, y).name().lower() == "#ffffff"
        )
        assert white_pixels == 0, f"Button '{btn.text()}' tooltip contains whiteout pixels"

    QToolTip.hideText()
