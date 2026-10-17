"""The grid's details pane (the list's detail widget), the emulator lines, and the wizard's refused one-file create."""
import os

from PyQt6.QtWidgets import QLabel

from core.project_library import index, registry
from ui.project_manager.window import ProjectManagerDialog
from test_ui.test_project_manager.test_wizard_and_rows import _loader, _project


def _dialog(qtbot, root, targets, platform=None):
    project = _project(root / "root", "Aria", "p-aria")
    key = registry.project_key(project)
    registry.mutate(root, lambda reg: reg.add(project))
    index.merge(root, {key: {"counted_mtime": os.stat(project).st_mtime_ns, "targets": targets}})
    dialog = ProjectManagerDialog(None, str(root), [].append, lambda: None,
                                  lambda path, updates: None, lambda name, value: None, _loader)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog._loaded and key in dialog._items, timeout=5000)
    return dialog, key


def test_known_platforms_has_no_blank_line_unless_a_build_has_no_platform(qtbot, tmp_path):
    targets = [{"id": "patch", "label": "Patch", "platforms": ["switch"], "kind": "patch"}]
    dialog, _key = _dialog(qtbot, tmp_path / "a", targets)

    assert dialog._known_platforms() == ["switch"]


def test_known_platforms_keeps_the_blank_line_for_a_build_with_no_platform(qtbot, tmp_path):
    targets = [{"id": "patch", "label": "Patch", "platforms": [], "kind": "patch"}]
    dialog, _key = _dialog(qtbot, tmp_path / "b", targets)

    assert dialog._known_platforms() == [""]


def test_grid_shows_the_selected_project_in_the_same_details_as_the_list(qtbot, tmp_path):
    dialog, key = _dialog(qtbot, tmp_path / "c", [])
    dialog._set_mode("grid")
    assert dialog._grid_details.isHidden()

    dialog._grid_items[key].setSelected(True)

    shown = dialog._grid_details.widget()
    assert shown is not None and not dialog._grid_details.isHidden()
    texts = [label.text() for label in shown.findChildren(QLabel)]
    assert dialog._rows()[0]["path"] in texts

    dialog._grid_items[key].setSelected(False)

    assert dialog._grid_details.isHidden() and dialog._grid_details.widget() is None
