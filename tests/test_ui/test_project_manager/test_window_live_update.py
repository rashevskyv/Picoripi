"""The window while a scan runs: rows change in place (scroll and selection kept), the progress strip, the icon actions.

Scan events are fed to the window directly (the scan child is covered in test_scan.py); the icon files are real.
"""
import json
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage

from core.project_library import registry
from core.project_library.icons import USER_ICON_MAX
from core.project_library.scan import ICON_FILE_NAME
from ui.project_manager import window
from ui.project_manager.window import ProjectManagerDialog, series_of


def _project(root, name):
    folder = root / "games" / name / "picoripi"
    folder.mkdir(parents=True)
    project_file = folder / "project.uiproj"
    project_file.write_text(json.dumps({"id": name, "name": name, "plugin_name": "plain_text", "blocks": []}),
                            encoding="utf-8")
    return str(project_file)


def _dialog(qtbot, settings):
    dialog = ProjectManagerDialog(None, str(settings), lambda path: None, lambda: None,
                                  lambda project_file, updates: None, lambda name, value: None)
    qtbot.addWidget(dialog)
    return dialog


def _counts_event(key, translated):
    return {"event": "counts", "key": key, "fields": {
        "counts": {"lines": 10, "needs_translation": 10, "translated": translated}, "targets": [], "skipped": 0,
        "groups": {}, "signature": f"sig-{key}-{translated}", "counted_at": "2026-10-13T19:00:00"}}


def test_updates_while_scrolled_keep_the_scroll_position_and_the_rows(qtbot, tmp_path):
    projects = [_project(tmp_path / "root", f"Game {number:02d}") for number in range(60)]
    registry.mutate(tmp_path, lambda reg: [reg.add(path) for path in projects])
    dialog = _dialog(qtbot, tmp_path)
    dialog.resize(900, 300)
    dialog.show()
    qtbot.waitUntil(lambda: len(dialog._items) == 60, timeout=10000)
    bar = dialog._tree.verticalScrollBar()
    qtbot.waitUntil(lambda: bar.maximum() > 0, timeout=5000)
    bar.setValue(bar.maximum() // 2)
    scrolled = bar.value()
    items_before = dict(dialog._items)
    keys = [registry.project_key(path) for path in projects]

    for key in keys[::-1]:  # the rows arrive in the reverse of their order
        dialog._on_scan_event(_counts_event(key, 3))
    qtbot.wait(400)  # the render is debounced; let it run

    assert bar.value() == scrolled
    assert all(dialog._items[key] is items_before[key] for key in keys)


def test_the_progress_strip_shows_the_count_and_hides_when_done(qtbot, tmp_path):
    dialog = _dialog(qtbot, tmp_path)
    dialog.show()
    dialog._on_scan_event({"event": "plan", "total": 191, "stale": 40})
    assert dialog._strip.isVisible()

    dialog._on_scan_event({"event": "progress", "done": 2, "total": 40, "name": "Pokémon Emerald"})

    text = dialog._strip_label.text()
    assert "Scanning 153 of 191" in text
    assert "Pokémon Emerald" in text
    assert dialog._strip_bar.value() == 153
    dialog._on_scan_event({"event": "done", "total": 191, "counted": 40, "plugin_missing": 0, "failed": 0,
                           "seconds": 1.0, "stale": 40})
    assert not dialog._strip.isVisible()


def test_a_plan_with_nothing_to_count_shows_no_strip(qtbot, tmp_path):
    dialog = _dialog(qtbot, tmp_path)
    dialog.show()
    dialog._on_scan_event({"event": "plan", "total": 5, "stale": 0})

    assert not dialog._strip.isVisible()


def test_set_icon_copies_a_scaled_png_into_the_project_folder(qtbot, tmp_path, monkeypatch):
    project = _project(tmp_path / "root", "Aria")
    registry.mutate(tmp_path, lambda reg: reg.add(project))
    picture = tmp_path / "picture.png"
    big = QImage(900, 600, QImage.Format.Format_ARGB32)
    big.fill(Qt.GlobalColor.blue)
    assert big.save(str(picture), "PNG")
    dialog = _dialog(qtbot, tmp_path)
    dialog.show()
    qtbot.waitUntil(lambda: len(dialog._items) == 1, timeout=10000)
    row = dialog._rows()[0]
    monkeypatch.setattr(window.QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(picture), ""))

    dialog._icon_clicked(row)

    target = Path(project).parent / ICON_FILE_NAME
    qtbot.waitUntil(lambda: row["key"] in dialog._icon_images, timeout=10000)
    stored = QImage(str(target))
    assert not stored.isNull()
    assert max(stored.width(), stored.height()) == USER_ICON_MAX
    assert not any(p.name.endswith(".tmp") for p in target.parent.iterdir())


def test_clear_icon_removes_only_the_icon_file(qtbot, tmp_path, monkeypatch):
    project = _project(tmp_path / "root", "Aria")
    registry.mutate(tmp_path, lambda reg: reg.add(project))
    icon = Path(project).parent / ICON_FILE_NAME
    image = QImage(64, 64, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.green)
    assert image.save(str(icon), "PNG")
    dialog = _dialog(qtbot, tmp_path)
    dialog.show()
    qtbot.waitUntil(lambda: len(dialog._items) == 1, timeout=10000)
    monkeypatch.setattr(window.QMessageBox, "question", lambda *args, **kwargs: window.QMessageBox.StandardButton.Yes)

    dialog._clear_icon_clicked(dialog._rows()[0])

    qtbot.waitUntil(lambda: not icon.exists(), timeout=10000)
    assert Path(project).exists()


def test_series_comes_from_the_folder_layout_with_or_without_a_platform_folder():
    assert series_of("E:/Emulators/RomHacking/Ace Attorney/Trilogy/3DS/picoripi/project.uiproj") == "Ace Attorney"
    assert series_of("E:/Emulators/RomHacking/Animal Crossing/Happy Home Designer/picoripi/project.uiproj") == "Animal Crossing"
