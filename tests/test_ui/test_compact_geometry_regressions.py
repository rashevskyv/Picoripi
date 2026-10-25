"""Real widget geometry regressions for compact headers and menus."""
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QFont, QKeySequence
from PyQt6.QtWidgets import QApplication, QMainWindow, QMenu, QMenuBar, QWidget

from components.glossary.dialog import GlossaryDialog
from core.glossary_manager import GlossaryEntry
from core.data_store import AppDataStore
from ui.builders.layout_builder import LayoutBuilder
from ui.themes import DARK_THEME_STYLESHEET, LIGHT_THEME_STYLESHEET


def _glossary(qtbot):
    entry = GlossaryEntry(original="Ordon", translation="Ордон", notes="Description")
    dialog = GlossaryDialog(
        parent=None,
        entries=[entry],
        occurrence_map={},
        jump_callback=lambda occurrence: None,
        ai_variation_callback=lambda glossary_entry: None,
    )
    qtbot.addWidget(dialog)
    dialog.resize(1000, 760)
    dialog.show()
    qtbot.waitExposed(dialog)
    return dialog


def _header_widget_rect(widget, pane):
    return QRect(widget.mapTo(pane, QPoint(0, 0)), widget.size())


def _layout_widgets(layout):
    widgets = []
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item.widget() is not None:
            widgets.append(item.widget())
        elif item.layout() is not None:
            widgets.extend(_layout_widgets(item.layout()))
    return widgets


def _assert_header_fits(pane, header_layout):
    pane_rect = pane.rect()
    visible_children = _layout_widgets(header_layout)
    visible_children = [widget for widget in visible_children if widget is not None and not widget.isHidden()]
    assert visible_children
    for widget in visible_children:
        rect = _header_widget_rect(widget, pane)
        assert rect.left() >= pane_rect.left()
        assert rect.top() >= pane_rect.top()
        assert rect.right() <= pane_rect.right() + 1
        assert rect.bottom() <= pane_rect.bottom()


def _assert_sections_do_not_overlap(dialog):
    panes = (dialog._notes_pane, dialog._ai_notes_pane, dialog._occurrences_pane)
    rects = [QRect(pane.mapTo(dialog._lower_detail_splitter, QPoint(0, 0)), pane.size()) for pane in panes]
    for index, rect in enumerate(rects):
        for sibling in rects[index + 1:]:
            assert not rect.intersects(sibling)


def test_collapsed_glossary_headers_resize_after_live_font_and_theme_changes(qtbot, tmp_path, monkeypatch):
    from utils import constants
    monkeypatch.setattr(constants, "SETTINGS_FILE_PATH", tmp_path / "settings.json")
    app = QApplication.instance()
    old_font, old_stylesheet = app.font(), app.styleSheet()
    dialog = _glossary(qtbot)
    dialog.resize(1400, 760)
    sections = (
        ("notes", dialog._notes_pane, dialog._notes_pane.layout().itemAt(0).layout(), dialog._notes_collapse_button),
        ("ai_notes", dialog._ai_notes_pane, dialog._ai_notes_pane.layout().itemAt(0).layout(), dialog._ai_notes_collapse_button),
        ("occurrences", dialog._occurrences_pane, dialog._occurrences_pane.layout().itemAt(0).layout(), dialog._occ_collapse_button),
    )
    try:
        for name, pane, header, button in sections:
            dialog._set_section_collapsed(name, True)
            qtbot.waitUntil(lambda: pane.height() >= pane.minimumSizeHint().height())
            app.setStyleSheet(DARK_THEME_STYLESHEET)
            app.setFont(QFont(old_font.family(), 20))
            for widget in _layout_widgets(header):
                widget.setFont(app.font())
            qtbot.waitUntil(lambda: pane.height() >= pane.minimumSizeHint().height())
            _assert_header_fits(pane, header)
            _assert_sections_do_not_overlap(dialog)
            app.setStyleSheet(LIGHT_THEME_STYLESHEET)
            app.setFont(QFont(old_font.family(), 10))
            for widget in _layout_widgets(header):
                widget.setFont(app.font())
            qtbot.waitUntil(lambda: pane.height() >= pane.minimumSizeHint().height())
            _assert_header_fits(pane, header)
            _assert_sections_do_not_overlap(dialog)
            dialog._set_section_collapsed(name, False)
    finally:
        app.setFont(old_font)
        app.setStyleSheet(old_stylesheet)


def test_glossary_collapsed_sections_stay_compact_and_description_text_fits(qtbot, tmp_path, monkeypatch):
    from utils import constants
    monkeypatch.setattr(constants, "SETTINGS_FILE_PATH", tmp_path / "settings.json")
    app = QApplication.instance()
    old_font, old_stylesheet = app.font(), app.styleSheet()
    dialog = _glossary(qtbot)
    dialog.resize(840, 520)
    dialog.show()
    qtbot.waitExposed(dialog)
    try:
        for name in ("notes", "ai_notes", "occurrences"):
            dialog._set_section_collapsed(name, True)
        app.setFont(QFont("Segoe UI", 20))
        notes_header = dialog._notes_pane.layout().itemAt(0).layout()
        panes = (dialog._notes_pane, dialog._ai_notes_pane, dialog._occurrences_pane)
        headers = tuple(pane.layout().itemAt(0).layout() for pane in panes)
        for header in headers:
            for widget in _layout_widgets(header):
                if not widget.isHidden():
                    widget.setFont(app.font())
        qtbot.waitUntil(lambda: dialog._lower_detail_splitter.sizes() == [pane.minimumSizeHint().height() for pane in panes])
        assert dialog._notes_pane.width() >= notes_header.sizeHint().width(), (
            dialog._notes_pane.width(), notes_header.sizeHint().width(),
            [(widget.text() if hasattr(widget, "text") else type(widget).__name__, widget.sizeHint().width()) for widget in _layout_widgets(notes_header)],
        )
        assert dialog._profiled_checkbox.text() == "Profiled via AI"
        assert "speech profile" in dialog._profiled_checkbox.toolTip().lower()
        assert dialog._notes_variation_button.isVisible()
        for widget in _layout_widgets(notes_header):
            if not widget.isHidden():
                assert widget.width() >= widget.sizeHint().width()

        actual_sizes = dialog._lower_detail_splitter.sizes()
        expected_sizes = [pane.minimumSizeHint().height() for pane in panes]
        assert actual_sizes == expected_sizes
        _assert_sections_do_not_overlap(dialog)
    finally:
        app.setFont(old_font)
        app.setStyleSheet(old_stylesheet)


def test_editor_controls_fit_large_font_and_keep_headers_aligned(qtbot):
    app = QApplication.instance()
    old_font, old_stylesheet = app.font(), app.styleSheet()
    window = QMainWindow()
    qtbot.addWidget(window)
    window.data_store = AppDataStore()
    window.game_dialog_max_width_pixels = 300
    window.show_multiple_spaces_as_dots = False
    window.space_dot_color_hex = "#888888"
    window.newline_display_symbol = "¶"
    LayoutBuilder(window).build()
    window.resize(1500, 900)
    window.show()
    qtbot.waitExposed(window)
    try:
        app.setStyleSheet(DARK_THEME_STYLESHEET)
        app.setFont(QFont(old_font.family(), 20))
        for control in window.right_header_container.findChildren(QWidget):
            control.setFont(app.font())
        window.right_header_container.layout().activate()
        window.right_header_container.updateGeometry()
        qtbot.waitUntil(lambda: window.right_header_container.height() >= window.right_header_container.sizeHint().height())
        controls = (
            window.navigate_down_button, window.navigate_up_button,
            window.ai_translate_button, window.ai_variation_button, window.auto_fix_button,
            window.font_combobox, window.width_spinbox, window.apply_width_button,
        )
        for control in controls:
            assert control.height() >= control.sizeHint().height(), (control, control.sizeHint(), control.size())
            assert window.right_header_container.rect().contains(
                QRect(control.mapTo(window.right_header_container, QPoint(0, 0)), control.size())
            )
        tab_h = window.source_tab_widget.tabBar().sizeHint().height()
        assert window.left_header_container.height() + tab_h == window.right_header_container.height()
    finally:
        app.setFont(old_font)
        app.setStyleSheet(old_stylesheet)


def test_themed_menu_bar_and_popup_actions_have_room_for_labels_and_shortcuts(qtbot):
    app = QApplication.instance()
    old_font, old_stylesheet = app.font(), app.styleSheet()
    window = QMainWindow()
    qtbot.addWidget(window)
    bar = QMenuBar(window)
    menu = QMenu("File", bar)
    open_action = menu.addAction("Open Project")
    open_action.setShortcut(QKeySequence("Ctrl+O"))
    disabled_action = menu.addAction("Unavailable")
    disabled_action.setEnabled(False)
    nested = menu.addMenu("Recent Projects")
    nested.addAction("Example")
    bar.addMenu(menu)
    window.setMenuBar(bar)
    window.resize(600, 300)
    window.show()
    qtbot.waitExposed(window)
    try:
        app.setFont(QFont(old_font.family(), 18))
        for stylesheet in (DARK_THEME_STYLESHEET, LIGHT_THEME_STYLESHEET):
            app.setStyleSheet(stylesheet)
            bar.updateGeometry()
            qtbot.waitUntil(lambda: bar.height() >= bar.sizeHint().height())
            action_rect = bar.actionGeometry(bar.actions()[0])
            assert action_rect.width() >= bar.fontMetrics().horizontalAdvance("File")
            assert action_rect.height() >= bar.fontMetrics().height()
            menu.popup(window.mapToGlobal(QPoint(30, bar.height())))
            qtbot.waitUntil(lambda: menu.isVisible())
            for action in menu.actions():
                rect = menu.actionGeometry(action)
                assert rect.height() >= menu.fontMetrics().height()
                assert menu.rect().contains(rect)
            assert open_action.shortcut().toString() == "Ctrl+O"
            assert not disabled_action.isEnabled()
            assert menu.actions()[2].menu() is nested
            assert nested.actions()
            menu.hide()
    finally:
        app.setFont(old_font)
        app.setStyleSheet(old_stylesheet)
