"""All or nothing: a create or an open that fails leaves no project behind, and a start-up project that fails or hangs
gives way to the Project Manager instead of holding the start-up splash."""
import json
import time

from PyQt6.QtWidgets import QMessageBox

from core.project_library import build
from handlers.project_action import handler as handler_module
from handlers.project_action import session_mixin
from handlers.project_action.load_worker import ProjectLoadWorker
from plugins.base_game_rules import BaseGameRules
from ui.project_manager.wizard import ProjectWizard
from utils import app_mode
from main import MainWindow


class FailingUnpack(BaseGameRules):
    """A game whose unpack fails after it has started to write."""

    def get_source_roles(self):
        return [{"id": "base", "label": "Base game"}]

    def unpack_sources(self, sources, target_dir, progress, is_cancelled):
        with open(f"{target_dir}/partial.bin", "w", encoding="utf-8") as handle:
            handle.write("half written")
        raise OSError("the archive is damaged")


class FakeSplash:
    """The start-up splash as far as the main window uses it."""

    def __init__(self):
        self.closed = False

    def update_progress(self, value, message):
        pass

    def close(self):
        self.closed = True

    def deleteLater(self):
        pass


class HangingLoader(ProjectLoadWorker):
    """A project load that never finishes on its own: it runs until the host asks it to stop."""

    def run(self):
        while not self.isInterruptionRequested():
            time.sleep(0.01)
        self.finished_with_result.emit({})


class FailingLoader(ProjectLoadWorker):
    """A project load that fails at once."""

    def run(self):
        self.finished_with_result.emit({})


def _record_critical(monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda _parent, title, text, *a, **k: shown.append(text)))
    return shown


def _project_file(folder, name, plugin="plain_text"):
    folder.mkdir(parents=True)
    project_file = folder / "project.uiproj"
    project_file.write_text(json.dumps({"id": name, "name": name, "plugin_name": plugin, "blocks": []}),
                            encoding="utf-8")
    return str(project_file)


def _info(folder, entries_before):
    return {"directory": str(folder), "name": folder.name, "plugin": "plain_text", "description": "",
            "source_path": str(folder), "translation_path": str(folder / "translation"), "is_directory_mode": True,
            "auto_create_translations": True, "entries_before": entries_before}


def test_a_failed_unpack_removes_what_the_create_made(qtbot, tmp_path):
    base = tmp_path / "base.bin"
    base.write_bytes(b"base")
    folder = tmp_path / "Aria"
    wizard = ProjectWizard(None, lambda name: FailingUnpack(), lambda info: None)
    qtbot.addWidget(wizard)
    qtbot.waitUntil(lambda: wizard._game.count() > 0 or wizard._jobs == [], timeout=10000)
    wizard._game.addItem("Fake game", "fake")
    wizard._game.setCurrentIndex(wizard._game.count() - 1)
    wizard.add_paths([str(base)])
    qtbot.waitUntil(lambda: wizard._files_status.text() == "Files: 1", timeout=10000)
    wizard._name.setText("Aria")
    wizard._folder.setText(str(folder))

    wizard._create_clicked()

    qtbot.waitUntil(lambda: wizard._progress_text.text().startswith("Unpacking failed"), timeout=10000)
    assert not folder.exists()


def test_a_failed_unpack_keeps_what_was_in_the_folder_before(qtbot, tmp_path):
    base = tmp_path / "base.bin"
    base.write_bytes(b"base")
    folder = tmp_path / "Aria"
    folder.mkdir()
    (folder / "notes.txt").write_text("the user's notes", encoding="utf-8")
    wizard = ProjectWizard(None, lambda name: FailingUnpack(), lambda info: None)
    qtbot.addWidget(wizard)
    qtbot.waitUntil(lambda: wizard._game.count() > 0 or wizard._jobs == [], timeout=10000)
    wizard._game.addItem("Fake game", "fake")
    wizard._game.setCurrentIndex(wizard._game.count() - 1)
    wizard.add_paths([str(base)])
    qtbot.waitUntil(lambda: wizard._files_status.text() == "Files: 1", timeout=10000)
    wizard._name.setText("Aria")
    wizard._folder.setText(str(folder))

    wizard._create_clicked()

    qtbot.waitUntil(lambda: wizard._progress_text.text().startswith("Unpacking failed"), timeout=10000)
    assert sorted(entry.name for entry in folder.iterdir()) == ["notes.txt"]


def test_removing_new_entries_keeps_the_names_from_before(tmp_path):
    folder = tmp_path / "Aria"
    folder.mkdir()
    (folder / "keep.txt").write_text("kept", encoding="utf-8")
    before = build.entries_before(folder)
    (folder / "project.uiproj").write_text("{}", encoding="utf-8")
    (folder / "translation").mkdir()

    build.remove_new_entries(folder, before)

    assert sorted(entry.name for entry in folder.iterdir()) == ["keep.txt"]


def test_a_create_whose_project_does_not_open_registers_nothing_and_removes_its_files(qtbot, tmp_path, monkeypatch):
    """The populate fails after the create: the project is removed, not registered as the last one."""
    shown = _record_critical(monkeypatch)
    monkeypatch.setattr(session_mixin, "ProjectLoadWorker", FailingLoader)
    window = MainWindow()
    window.is_testing = True
    qtbot.addWidget(window)
    handler = window.project_action_handler
    folder = tmp_path / "Aria"
    window.last_opened_path = ""

    handler.finish_new_project(_info(folder, None))

    assert not (folder / "project.uiproj").exists()
    assert window.last_opened_path == ""
    assert str(folder / "project.uiproj") not in (window.recent_projects or [])
    assert shown and "did not open" in shown[-1]


def test_a_start_up_project_that_fails_to_load_is_forgotten_and_the_manager_opens(qtbot, tmp_path, monkeypatch):
    shown = _record_critical(monkeypatch)
    window = MainWindow()
    window.is_testing = True
    qtbot.addWidget(window)
    handler = window.project_action_handler
    opened = []
    monkeypatch.setattr(handler, "open_project_manager_action", lambda: opened.append(True))
    broken = tmp_path / "Broken" / "project.uiproj"
    broken.parent.mkdir()
    broken.write_text("{ not json", encoding="utf-8")
    window.last_opened_path = str(broken)
    window._startup_splash = FakeSplash()

    handler._open_recent_project(str(broken))

    assert window.last_opened_path == ""
    assert opened == [True]
    assert window._startup_splash is None
    assert shown and str(broken) in shown[-1]


def test_a_start_up_project_whose_load_hangs_is_cancelled_by_the_watchdog(qtbot, tmp_path, monkeypatch):
    shown = _record_critical(monkeypatch)
    monkeypatch.setattr(app_mode, "headless", False)   # the populate runs on its QThread, as in the app
    monkeypatch.setattr(session_mixin, "ProjectLoadWorker", HangingLoader)
    monkeypatch.setattr(handler_module, "STARTUP_STALL_MS", 300)
    window = MainWindow()
    window.is_testing = True
    qtbot.addWidget(window)
    handler = window.project_action_handler
    opened = []
    monkeypatch.setattr(handler, "open_project_manager_action", lambda: opened.append(True))
    project = _project_file(tmp_path / "Hung", "Hung")
    window.last_opened_path = project
    window._startup_splash = FakeSplash()

    handler._open_recent_project(project)

    qtbot.waitUntil(lambda: bool(shown), timeout=10000)
    assert "Loading stopped" in shown[-1]
    assert window.last_opened_path == ""
    assert opened == [True]
    assert window._startup_splash is None
