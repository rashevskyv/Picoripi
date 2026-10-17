"""The resource count of a project row: the worker's result, its failure and cancel, and the expanded row that shows it."""
import json
import os

from PyQt6.QtWidgets import QLabel

from core.i18n import tr
from core.project_library import index, registry, resources
from plugins.base_game_rules import BaseGameRules
from ui.project_manager.tasks import ResourceJob
from ui.project_manager.window import ProjectManagerDialog


class PlainGame(BaseGameRules):
    """A game with no build target: the row shows no action buttons, which keeps the test about resources."""


def _loader(name):
    return PlainGame()


def _project_with_files(root, name, project_id, files):
    """A project whose source folder holds ``files`` (name -> bytes); the project file sits in its own folder."""
    folder = root / "games" / name / "picoripi"
    folder.mkdir(parents=True)
    source = root / "games" / name / "source"
    source.mkdir(parents=True)
    for relative, data in files.items():
        (source / relative).parent.mkdir(parents=True, exist_ok=True)
        (source / relative).write_bytes(data)
    project_file = folder / "project.uiproj"
    project_file.write_text(json.dumps({"id": project_id, "name": name, "plugin_name": "plain", "blocks": [],
                                        "metadata": {"source_path": str(source), "translation_path": str(source)}}),
                            encoding="utf-8")
    return str(project_file)


def test_resource_job_counts_the_source_folder_on_a_worker(qtbot, tmp_path):
    project = _project_with_files(tmp_path, "Aria", "p-aria", {"menu.json": b"12345", "font.bfn": b"abc"})
    job = ResourceJob(project)

    with qtbot.waitSignal(job.done, timeout=10000) as blocker:
        job.start()

    counts = blocker.args[0]
    assert counts["text"] == {"files": 1, "bytes": 5}
    assert counts["font"] == {"files": 1, "bytes": 3}
    qtbot.waitUntil(lambda: job.isFinished(), timeout=5000)


def test_resource_job_reports_a_project_file_that_is_not_there(qtbot, tmp_path):
    job = ResourceJob(str(tmp_path / "gone" / "project.uiproj"))

    with qtbot.waitSignal(job.failed, timeout=10000):
        job.start()

    qtbot.waitUntil(lambda: job.isFinished(), timeout=5000)


def test_cancelled_resource_job_reports_nothing(qtbot, tmp_path, monkeypatch):
    project = _project_with_files(tmp_path, "Aria", "p-aria", {"a.json": b"x"})
    done, failed = [], []
    job = ResourceJob(project)
    job.done.connect(done.append)
    job.failed.connect(failed.append)

    def walk_that_is_cancelled(source, is_cancelled):
        job.requestInterruption()   # the user closes the window during the walk
        return None if is_cancelled() else {}

    monkeypatch.setattr(resources, "count_resources", walk_that_is_cancelled)
    job.start()

    qtbot.waitUntil(lambda: job.isFinished(), timeout=5000)

    assert done == [] and failed == []


def test_expanded_row_shows_the_resource_kinds_and_the_missing_translation_count(qtbot, tmp_path):
    project = _project_with_files(tmp_path, "Aria", "p-aria", {"menu.json": b"12345", "font.bfn": b"abc",
                                                              "title.png": b"12"})
    key = registry.project_key(project)
    registry.mutate(tmp_path, lambda reg: reg.add(project))
    index.merge(tmp_path, {key: {
        "counted_mtime": os.stat(project).st_mtime_ns,
        "missing_translations": 2,
        "targets": []}})
    dialog = ProjectManagerDialog(None, str(tmp_path), [].append, lambda: None,
                                  lambda path, updates: None, lambda name, value: None, _loader)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog._loaded and key in dialog._items, timeout=5000)

    item = dialog._items[key]
    item.setExpanded(True)
    detail = dialog._tree.itemWidget(item.child(0), 0)
    tree = dialog._resource_trees[key]
    qtbot.waitUntil(lambda: tree.topLevelItem(0).text(0) != tr("Counting the files..."), timeout=10000)

    rows = {tree.topLevelItem(i).text(0): tree.topLevelItem(i).text(1) for i in range(tree.topLevelItemCount())}
    assert rows == {"Text files": "1", "Font files": "1", "Texture files": "1", "Other files": "0"}
    attention = [label.text() for label in detail.findChildren(QLabel) if label.text().startswith("Needs attention")]
    assert "2 blocks have no translation file yet." in attention[0]


def test_expanded_row_names_the_files_the_wizard_took_by_role(qtbot, tmp_path):
    project = _project_with_files(tmp_path, "Aria", "p-aria", {"menu.json": b"1"})
    data = json.loads(open(project, encoding="utf-8").read())
    data["metadata"]["source_roles"] = {"base": "/games/aria.iso", "update": "/games/aria-update.nsp"}
    open(project, "w", encoding="utf-8").write(json.dumps(data))
    key = registry.project_key(project)
    registry.mutate(tmp_path, lambda reg: reg.add(project))
    card = {"source_roles": {"base": "/games/aria.iso", "update": "/games/aria-update.nsp"}}
    index.merge(tmp_path, {key: {"counted_mtime": os.stat(project).st_mtime_ns, "targets": [], "card": card}})
    dialog = ProjectManagerDialog(None, str(tmp_path), [].append, lambda: None,
                                  lambda path, updates: None, lambda name, value: None, _loader)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog._loaded and key in dialog._items, timeout=5000)

    item = dialog._items[key]
    item.setExpanded(True)
    detail = dialog._tree.itemWidget(item.child(0), 0)
    texts = [label.text() for label in detail.findChildren(QLabel)]

    assert "base: /games/aria.iso\nupdate: /games/aria-update.nsp" in texts
