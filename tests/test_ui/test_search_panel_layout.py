"""Search panel layout and the theme icons it relies on."""
from __future__ import annotations

import re
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from components.search_panel import SearchPanelWidget
from ui.themes import stylesheet


def test_theme_icon_urls_point_at_existing_files():
    for dark in (True, False):
        urls = re.findall(r'url\("([^"]+)"\)', stylesheet(dark))
        assert any(u.endswith("chevron-down.svg") or u.endswith("chevron-down-light.svg") for u in urls)
        for url in urls:
            assert Path(url).is_file(), url


def test_buttons_keep_label_width_and_close_button_gets_icon(qtbot):
    app = QApplication.instance()
    old = app.styleSheet()
    app.setStyleSheet(stylesheet(dark=False))
    try:
        panel = SearchPanelWidget(None)
        qtbot.addWidget(panel)
        panel.resize(1600, panel.sizeHint().height())
        panel.show()
        qtbot.waitExposed(panel)

        for button in (panel.find_previous_button, panel.find_next_button, panel.advanced_button):
            assert button.width() == max(button.minimumWidth(), button.sizeHint().width())
        assert panel.search_query_edit.width() > 3 * panel.advanced_button.width()
        assert not panel.close_search_panel_button.icon().isNull()
    finally:
        app.setStyleSheet(old)
