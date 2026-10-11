"""The Project Manager window: what it shows from the registry and the cache, and the actions it sends."""
import json
from functools import partial

from core.project_library import index, registry
from ui.project_manager import window
from ui.project_manager.window import ProjectManagerDialog


def _project(root, name, project_id):
    folder = root / "games" / name / "picoripi"
    folder.mkdir(parents=True)
    project_file = folder / "project.uiproj"
    project_file.write_text(json.dumps({"id": project_id, "name": name, "blocks": [{}]}), encoding="utf-8")
    return str(project_file)


def _dialog(qtbot, settings, opened):
    dialog = ProjectManagerDialog(None, str(settings), opened.append, lambda: None)
    qtbot.addWidget(dialog)
    return dialog


def _section_titles(dialog):
    tree = dialog._tree
    return [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]


def test_empty_registry_shows_the_empty_state(qtbot, tmp_path):
    dialog = _dialog(qtbot, tmp_path, [])

    qtbot.waitUntil(lambda: dialog._loaded, timeout=5000)

    assert dialog._stack.currentWidget() is dialog._empty


def test_registry_projects_appear_with_last_opened_first(qtbot, tmp_path):
    first = _project(tmp_path / "root", "Aria", "p-aria")
    second = _project(tmp_path / "root", "Zelda", "p-zelda")
    registry.mutate(tmp_path, lambda reg: reg.add(first))
    registry.mutate(tmp_path, lambda reg: reg.touch_opened(second, project_id="p-zelda"))
    dialog = _dialog(qtbot, tmp_path, [])

    qtbot.waitUntil(lambda: len(dialog._scanned) == 2, timeout=5000)
    qtbot.waitUntil(lambda: dialog._tree.topLevelItemCount() > 0, timeout=5000)

    titles = _section_titles(dialog)
    assert titles[0].startswith("Last opened")
    assert dialog._stack.currentWidget() is dialog._tree
    assert dialog._items.keys() == {registry.project_key(first), registry.project_key(second)}


def test_cached_counts_show_in_the_row_before_the_scan_ends(qtbot, tmp_path):
    project = _project(tmp_path / "root", "Aria", "p-aria")
    registry.mutate(tmp_path, lambda reg: reg.add(project))
    index.merge(tmp_path, {registry.project_key(project): {
        "counts": {"lines": 1234, "needs_translation": 10, "translated": 4}}})
    dialog = _dialog(qtbot, tmp_path, [])

    qtbot.waitUntil(lambda: dialog._loaded, timeout=5000)
    row = dialog._rows()[0]

    assert row["lines"] == 1234
    assert row["translated"] == 40


def test_open_sends_the_path_and_closes_the_window(qtbot, tmp_path):
    project = _project(tmp_path / "root", "Aria", "p-aria")
    registry.mutate(tmp_path, lambda reg: reg.add(project))
    opened = []
    dialog = _dialog(qtbot, tmp_path, opened)
    qtbot.waitUntil(lambda: dialog._loaded, timeout=5000)

    dialog._open(project)

    assert opened == [project]


def test_removing_from_the_manager_keeps_the_project_file(qtbot, tmp_path):
    project = _project(tmp_path / "root", "Aria", "p-aria")
    registry.mutate(tmp_path, lambda reg: reg.add(project))
    dialog = _dialog(qtbot, tmp_path, [])
    qtbot.waitUntil(lambda: dialog._loaded, timeout=5000)

    dialog._mutate(partial(window._op_remove, path=project))

    qtbot.waitUntil(lambda: dialog._document["projects"] == [], timeout=5000)
    assert registry.read(tmp_path)["projects"] == []
    assert (tmp_path / "root" / "games" / "Aria" / "picoripi" / "project.uiproj").exists()


def test_import_creates_one_folder_per_series_and_adds_only_the_chosen_projects(tmp_path):
    first = _project(tmp_path / "root", "Aria", "p-aria")
    second = _project(tmp_path / "root", "Harmony", "p-harmony")
    chosen = [
        {"project_file": first, "series": "Castlevania", "platform": "DS", "project_id": "p-aria"},
        {"project_file": second, "series": "Castlevania", "platform": "", "project_id": "p-harmony"},
    ]

    registry.mutate(tmp_path, window._op_import, chosen[:1])

    document = registry.read(tmp_path)
    assert [f["name"] for f in document["folders"]] == ["Castlevania"]
    assert len(document["projects"]) == 1
    assert document["projects"][0]["platform"] == "DS"
    assert document["projects"][0]["folder_id"] == document["folders"][0]["id"]
