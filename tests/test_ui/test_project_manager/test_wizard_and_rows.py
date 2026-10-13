"""The new-project wizard, the unpack job, and the expanded row of the Project Manager (targets, flags, emulator)."""
import json
import os

from PyQt6.QtWidgets import QCheckBox, QToolButton

from core.project_library import index, registry
from plugins.base_game_rules import BaseGameRules
from ui.project_manager import window
from ui.project_manager.tasks import UnpackJob
from ui.project_manager.window import ProjectManagerDialog
from ui.project_manager.wizard import ProjectWizard


class FakeGame(BaseGameRules):
    """An explicit fake game: two roles, a platform, one build target that writes one file."""

    def get_source_roles(self):
        return [{"id": "base", "label": "Base game"}, {"id": "update", "label": "Update"}]

    def get_platforms(self):
        return [{"id": "3ds", "label": "Nintendo 3DS"}]

    def get_build_targets(self):
        return [{"id": "patch", "label": "Patch", "platforms": [], "kind": "patch"}]

    def identify_source(self, path):
        return {"role": "update", "platform": "3ds"} if path.endswith("update.bin") else None

    def build_target(self, target_id, source_dir, translation_dir, output_dir, progress, is_cancelled):
        with open(os.path.join(output_dir, "patch.bin"), "w", encoding="utf-8") as handle:
            handle.write("built")
        return os.path.join(output_dir, "patch.bin")


def _loader(name):
    return FakeGame()


def _project(root, name, project_id):
    folder = root / "games" / name / "picoripi"
    folder.mkdir(parents=True)
    project_file = folder / "project.uiproj"
    project_file.write_text(json.dumps({"id": project_id, "name": name, "plugin_name": "fake", "blocks": []}),
                            encoding="utf-8")
    return str(project_file)


def _wait_for_plugins(qtbot, wizard):
    qtbot.waitUntil(lambda: wizard._game.count() > 0 or wizard._jobs == [], timeout=10000)
    wizard._game.addItem("Fake game", "fake")
    wizard._game.setCurrentIndex(wizard._game.count() - 1)


def test_wizard_reads_roles_and_creates_the_project_from_the_originals(qtbot, tmp_path):
    base = tmp_path / "base.bin"
    update = tmp_path / "update.bin"
    base.write_bytes(b"base")
    update.write_bytes(b"update")
    created = []
    wizard = ProjectWizard(None, _loader, created.append)
    qtbot.addWidget(wizard)
    _wait_for_plugins(qtbot, wizard)

    wizard.add_paths([str(base), str(update)])
    qtbot.waitUntil(lambda: wizard._files_status.text() == "Files: 2", timeout=10000)
    wizard._name.setText("Aria")
    wizard._folder.setText(str(tmp_path / "Aria"))
    wizard._create_clicked()
    qtbot.waitUntil(lambda: bool(created), timeout=10000)

    info = created[0]
    assert info["source_path"] == str(base)
    assert info["is_directory_mode"] is False
    assert info["translation_path"] == str(tmp_path / "Aria" / "translation" / "base.bin")
    assert info["metadata"]["source_roles"] == {"base": str(base), "update": str(update)}
    assert info["platform"] == "3ds"
    assert info["plugin"] == "fake"
    assert (tmp_path / "Aria" / "translation").is_dir()
    assert not [p for p in (tmp_path / "Aria").iterdir() if p.name.startswith(".unpack")]


def test_wizard_refuses_a_folder_that_already_holds_a_project(qtbot, tmp_path):
    wizard = ProjectWizard(None, _loader, lambda info: None)
    qtbot.addWidget(wizard)
    (tmp_path / "Aria").mkdir()
    (tmp_path / "Aria" / "project.uiproj").write_text("{}", encoding="utf-8")
    wizard._name.setText("Aria")
    wizard._folder.setText(str(tmp_path / "Aria"))

    assert wizard._problem() == "This folder already holds a project."


def test_wizard_needs_a_role_for_every_file_and_no_two_files_share_one(qtbot, tmp_path):
    first = tmp_path / "one.bin"
    second = tmp_path / "two.bin"
    first.write_bytes(b"1")
    second.write_bytes(b"2")
    wizard = ProjectWizard(None, _loader, lambda info: None)
    qtbot.addWidget(wizard)
    wizard._name.setText("Aria")
    wizard._folder.setText(str(tmp_path / "Aria"))
    wizard.add_paths([str(first), str(second)])
    qtbot.waitUntil(lambda: wizard._files_status.text() == "Files: 2", timeout=10000)
    # Both files start as the first role (base): the second one moves to the update role.
    wizard._files_tree.itemWidget(wizard._files_tree.topLevelItem(1), 1).setCurrentIndex(1)
    assert wizard._problem() == ""

    wizard._files_tree.itemWidget(wizard._files_tree.topLevelItem(0), 1).setCurrentIndex(1)

    assert wizard._problem() == "Two files have the same role. Give each file its own role."


def test_unpack_job_that_is_cancelled_leaves_only_the_project_folder(qtbot, tmp_path):
    project_dir = tmp_path / "Aria"
    job = UnpackJob("fake", {"base": "x"}, str(project_dir), _loader)
    cancelled, done = [], []
    job.cancelled.connect(lambda: cancelled.append(True))
    job.done.connect(done.append)
    job.isInterruptionRequested = lambda: True  # the user cancelled before the worker started

    job.run()

    assert cancelled == [True] and done == []
    assert not [p for p in project_dir.iterdir() if p.name.startswith(".unpack")]


def test_expanded_row_offers_targets_and_saves_flags_for_a_project_that_is_not_open(qtbot, tmp_path):
    project = _project(tmp_path / "root", "Aria", "p-aria")
    key = registry.project_key(project)
    registry.mutate(tmp_path, lambda reg: reg.add(project))
    index.merge(tmp_path, {key: {
        "counts": {"lines": 3, "needs_translation": 3, "translated": 1},
        "counted_mtime": os.stat(project).st_mtime_ns,
        "targets": [{"id": "patch", "label": "Patch", "platforms": [], "kind": "patch"}],
        "groups": {"Menu": {"blocks": 1, "lines": 3}}, "skipped": 0}})
    saved_flags, saved_settings = [], []
    dialog = ProjectManagerDialog(None, str(tmp_path), [].append, lambda: None,
                                  lambda path, updates: saved_flags.append((path, updates)),
                                  lambda name, value: saved_settings.append((name, value)), _loader)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog._loaded and key in dialog._items, timeout=5000)

    item = dialog._items[key]
    item.setExpanded(True)
    detail = dialog._tree.itemWidget(item.child(0), 0)
    buttons = {b.text(): b for b in detail.findChildren(QToolButton)}
    checks = {c.text(): c for c in detail.findChildren(QCheckBox)}

    assert buttons["Build mod"].isEnabled()
    assert buttons["Export mod"].isEnabled()
    assert not buttons["Run in emulator"].isEnabled()
    checks["Built"].setChecked(True)
    assert saved_flags == [(project, {"built": True})]


def test_run_in_emulator_needs_a_command_and_starts_it_detached(qtbot, tmp_path, monkeypatch):
    project = _project(tmp_path / "root", "Aria", "p-aria")
    key = registry.project_key(project)
    registry.mutate(tmp_path, lambda reg: reg.add(project))
    index.merge(tmp_path, {key: {
        "counted_mtime": os.stat(project).st_mtime_ns,
        "targets": [{"id": "patch", "label": "Patch", "platforms": [], "kind": "patch"}]}})
    dialog = ProjectManagerDialog(None, str(tmp_path), [].append, lambda: None,
                                  lambda path, updates: None, lambda name, value: None, _loader)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog._loaded and key in dialog._items, timeout=5000)

    started = []

    class FakeProcess:
        @staticmethod
        def startDetached(program, arguments):
            started.append([program, *arguments])
            return True, 42

    monkeypatch.setattr(window, "QProcess", FakeProcess)
    dialog._document["settings"] = {"emulator_command": '"emu" --load {path}'}

    dialog._on_action_done(key, "run", "/games/out dir/patch.bin")

    assert started == [["emu", "--load", "/games/out dir/patch.bin"]]
    assert dialog._action_text[key].startswith("Started the emulator")


def test_build_runs_the_plugin_target_into_the_project_build_folder(qtbot, tmp_path):
    project = _project(tmp_path / "root", "Aria", "p-aria")
    key = registry.project_key(project)
    registry.mutate(tmp_path, lambda reg: reg.add(project))
    index.merge(tmp_path, {key: {
        "counted_mtime": os.stat(project).st_mtime_ns,
        "targets": [{"id": "patch", "label": "Patch", "platforms": [], "kind": "patch"}]}})
    dialog = ProjectManagerDialog(None, str(tmp_path), [].append, lambda: None,
                                  lambda path, updates: None, lambda name, value: None, _loader)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog._loaded and key in dialog._items, timeout=5000)

    dialog._start_action(project, "patch", "build")

    qtbot.waitUntil(lambda: dialog._action_text.get(key, "").startswith("Built:"), timeout=10000)
    built = dialog._action_text[key].split("Built: ", 1)[1]
    assert built.endswith(os.path.join("build", "patch", "patch.bin"))
    assert os.path.isfile(built)
