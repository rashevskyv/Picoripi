"""Under the Ukrainian locale every visible English string of the Project Manager has a uk.json entry.

The walk reads the widgets as they show: labels, buttons, combo items, headers, rows, the detail pane, the progress
strip, the placeholder and tooltips, the add menu. Project data (names, series, platform, plugin id) is listed
explicitly in ``DATA_TEXT``; anything else with English letters must be a UI string with a translation.
"""
import json
import re
from pathlib import Path

from PyQt6.QtWidgets import (QAbstractButton, QComboBox, QLabel, QLineEdit, QListWidget, QToolButton, QTreeWidget,
                             QWidget)

from core import i18n
from core.project_library import registry
from main import install_qt_translator
from ui.project_manager import window
from ui.project_manager.window import ProjectManagerDialog

UK_PATH = Path(i18n.LOCALES_DIR) / "uk.json"
# Project data the fixture writes: a folder name, a series, a platform, a plugin id. Not UI text.
DATA_TEXT = {"Aria", "Zelda", "GBA", "plain_text"}
ENGLISH = re.compile(r"[A-Za-z]")


def _uk_keys():
    return json.loads(UK_PATH.read_text(encoding="utf-8"))


def _project(root, series, name):
    folder = root / series / name / "picoripi"
    folder.mkdir(parents=True)
    project_file = folder / "project.uiproj"
    project_file.write_text(json.dumps({"id": name, "name": name, "blocks": []}), encoding="utf-8")
    return str(project_file)


def _texts(tree_or_list):
    """Every text of a tree or list, the items in every row."""
    if isinstance(tree_or_list, QTreeWidget):
        headers = [tree_or_list.headerItem().text(column) for column in range(tree_or_list.columnCount())]
        items = []

        def walk(item):
            for column in range(tree_or_list.columnCount()):
                items.append(item.text(column))
                items.append(item.toolTip(column))
            for child in range(item.childCount()):
                walk(item.child(child))

        for index in range(tree_or_list.topLevelItemCount()):
            walk(tree_or_list.topLevelItem(index))
        return headers + items
    return [tree_or_list.item(index).text() for index in range(tree_or_list.count())]


def _visible_strings(dialog):
    """The (text, widget) pairs the dialog shows now."""
    found = [(dialog.windowTitle(), dialog)]
    for widget in dialog.findChildren(QWidget):
        if not widget.isVisibleTo(dialog):
            continue
        if isinstance(widget, (QLabel, QAbstractButton)):
            found.append((widget.text(), widget))
        if isinstance(widget, QComboBox):
            found.extend((widget.itemText(index), widget) for index in range(widget.count()))
        if isinstance(widget, QLineEdit):
            found.append((widget.placeholderText(), widget))
        if isinstance(widget, (QTreeWidget, QListWidget)):
            found.extend((text, widget) for text in _texts(widget))
        if widget.toolTip():
            found.append((widget.toolTip(), widget))
    for button in dialog.findChildren(QToolButton):  # the menus of the buttons are not shown until opened
        if button.menu() is not None:
            found.extend((action.text(), button) for action in button.menu().actions() if action.text())
    return [(text, widget) for text, widget in found if text]


def _ui_part(text):
    """The text without the project data in it: a progress line or a grid cell carries a project name."""
    for data in DATA_TEXT:
        text = text.replace(data, " ")
    return text


def _english_without_translation(texts, uk):
    """The English UI strings left on screen, with the reason when uk.json has no entry for the text.

    A path is project data and is skipped. Each line of a multi-line text is checked on its own.
    """
    failures = []
    for text, widget in texts:
        if "/" in text or "\\" in text:
            continue
        for line in _ui_part(text).splitlines():
            if not ENGLISH.search(line):
                continue
            reason = "no uk.json key" if text not in uk else "uk.json entry is still English"
            where = type(widget).__name__ if widget is not None else "-"
            failures.append(f"{text!r} on {where}: {reason}")
    return sorted(set(failures))


def test_every_visible_project_manager_string_has_a_ukrainian_entry(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(window.ScanProcess, "start", lambda self, data_dir, projects: True)
    root = tmp_path / "root"
    aria = _project(root, "Zelda", "Aria")
    registry.mutate(tmp_path, lambda reg: reg.add(aria, platform="GBA"))
    i18n.init("uk")
    try:
        dialog = ProjectManagerDialog(None, str(tmp_path), lambda path: None, lambda: None,
                                      lambda project_file, updates: None, lambda name, value: None)
        qtbot.addWidget(dialog)
        dialog.show()
        qtbot.waitUntil(lambda: dialog._loaded, timeout=5000)
        key = registry.project_key(aria)
        dialog._on_scan_event({"event": "card", "key": key, "card": {
            "name": "Aria", "plugin": "plain_text", "issues": ["source_missing"]}})
        qtbot.waitUntil(lambda: key in dialog._items and dialog._items[key].text(0) == "Aria", timeout=5000)
        dialog._items[key].setExpanded(True)  # the detail pane: flags, buttons, the attention line
        dialog._on_scan_event({"event": "plan", "total": 1, "stale": 1})
        dialog._on_scan_event({"event": "progress", "done": 0, "total": 1, "name": "Aria"})
        qtbot.waitUntil(lambda: dialog._strip.isVisible(), timeout=2000)
        texts = _visible_strings(dialog)  # the list, the strip and the detail pane
        dialog._set_mode("grid")
        texts += _visible_strings(dialog)
        dialog._search.setText("zzz")  # the no-match page
        dialog._render()
        texts += _visible_strings(dialog)
        dialog._search.setText("")
        dialog._render()
        uk = _uk_keys()

        failures = _english_without_translation(texts, uk)

        assert failures == []
        seen = {text for text, _widget in texts}
        assert {i18n.tr("Search projects"), i18n.tr("Status"), i18n.tr("No project matches this search.")} <= seen
    finally:
        i18n.init("en")


def test_the_walk_sees_the_list_headers_in_ukrainian(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(window.ScanProcess, "start", lambda self, data_dir, projects: True)
    i18n.init("uk")
    try:
        dialog = ProjectManagerDialog(None, str(tmp_path), lambda path: None, lambda: None,
                                      lambda project_file, updates: None, lambda name, value: None)
        qtbot.addWidget(dialog)
        dialog.show()
        qtbot.waitUntil(lambda: dialog._loaded, timeout=5000)
        headers = [dialog._tree.headerItem().text(column) for column in range(dialog._tree.columnCount())]

        assert headers[0] == i18n.tr("Project name")
        assert headers[0] != "Project name"
        assert dialog.windowTitle() == i18n.tr("Project Manager") != "Project Manager"
    finally:
        i18n.init("en")


def test_the_walk_catches_an_english_string_with_no_entry(qtbot):
    """The walk itself: a string with no uk.json entry is reported."""
    uk = _uk_keys()
    fake = [("Definitely not translated here", None), ("Aria", None), ("—", None), ("Opens", None)]

    failures = _english_without_translation(fake, uk)

    assert len(failures) == 2  # project data and a symbol pass; an English string with no key fails, and so does one
    assert any("Definitely not translated here" in f and "no uk.json key" in f for f in failures)  # that has a key
    assert any("'Opens'" in f and "still English" in f for f in failures)


def test_the_qt_standard_buttons_follow_the_language(qtbot):
    from PyQt6.QtWidgets import QApplication, QDialogButtonBox
    translator = install_qt_translator("uk")
    try:
        assert translator is not None
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)  # Qt's Ukrainian file has "Cancel"
        button = box.button(QDialogButtonBox.StandardButton.Cancel)
        assert button.text() != "Cancel"
        assert re.search("[Ѐ-ӿ]", button.text())
    finally:
        if translator is not None:
            QApplication.instance().removeTranslator(translator)
