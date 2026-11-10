"""Build ROM builds every target of the plugin in one run: one progress window with Cancel, one result, and the
result's folder opens when the run is done."""
from types import SimpleNamespace

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtWidgets import QLabel, QMainWindow, QProgressDialog, QPushButton, QStatusBar

from ui.main_window.actions import settings_mixin
from ui.main_window.actions.settings_mixin import MainWindowSettingsActionsMixin
from ui.project_manager import tasks


class _Actions(MainWindowSettingsActionsMixin):
    def __init__(self, mw):
        self.mw = mw


def _actions(qtbot):
    mw = QMainWindow()
    qtbot.addWidget(mw)
    mw.statusBar = QStatusBar(mw)
    actions = _Actions(mw)
    actions._build_job = object()
    actions._build_dialog = QProgressDialog("", "Cancel", 0, 100, mw)
    return actions


def test_progress_reaches_the_dialog_with_the_time_passed_and_left(qtbot, monkeypatch):
    actions = _actions(qtbot)
    clock = iter([100.0, 160.0])
    monkeypatch.setattr(settings_mixin.time, "monotonic", lambda: next(clock))
    actions._build_progress_dialog("Build ROM", lambda: None).close()
    actions._build_dialog = QProgressDialog("", "Cancel", 0, 100, actions.mw)
    actions._build_progress(25, "Writing the package")
    assert actions._build_dialog.value() == 25
    assert actions._build_dialog.labelText() == "Writing the package · 1:00 passed, about 3:00 left"


class _Job(QObject):
    """Stands in for ActionJob: the test emits its signals."""
    progress = pyqtSignal(int, str)
    done = pyqtSignal(str)
    published = pyqtSignal(str)
    cancelled = pyqtSignal()
    failed = pyqtSignal(str)
    started = []

    def __init__(self, project_file, target_id, load_rules, export_to="", publish_description=None):
        super().__init__()
        self.target = target_id
        self.publish = publish_description
        self.interrupted = False

    def start(self):
        _Job.started.append(self)

    def requestInterruption(self):
        self.interrupted = True


def _run(qtbot, tmp_path, monkeypatch, targets, publish=None):
    """A main window with a project of ``targets``; Build ROM pressed. Returns (actions, opened, shown).

    ``publish`` names the targets that carry a publish entry."""
    opened, shown = [], []
    for name in ("information", "critical"):
        monkeypatch.setattr(settings_mixin.QMessageBox, name, lambda *args, n=name: shown.append((n, args[2])))
    monkeypatch.setattr("PyQt6.QtGui.QDesktopServices.openUrl", lambda url: opened.append(url))
    monkeypatch.setattr(tasks, "ActionJob", _Job)
    _Job.started = []
    actions = _actions(qtbot)
    actions._build_job = None
    mw = actions.mw
    mw.project_manager = SimpleNamespace(project_file_path=str(tmp_path / "project.uiproj"))
    entry = {"repo": "https://example.invalid/r.git", "branch": "main", "game": "G", "post": "p", "files_root": "files"}
    mw.current_game_rules = SimpleNamespace(get_build_targets=lambda: [
        {"id": t, "label": t.upper(), **({"publish": entry} if t in (publish or ()) else {})} for t in targets])
    mw.data_store = SimpleNamespace(unsaved_changes=False)
    actions.build_rom()
    return actions, opened, shown


def test_a_target_that_publishes_asks_first_and_the_jobs_get_the_description(qtbot, tmp_path, monkeypatch):
    actions, opened, shown = _run(qtbot, tmp_path, monkeypatch, ["iso", "bluewake"], publish=["iso"])
    assert _Job.started == []                       # nothing builds until the question is answered
    dialog = actions._publish_dialog
    qtbot.addWidget(dialog)
    assert any("ISO" in label.text() for label in dialog.findChildren(QLabel))   # names what publishes
    dialog.description_edit.setPlainText("New dialogues")
    dialog.accept()
    assert [(job.target, job.publish) for job in _Job.started] == [("iso", "New dialogues")]
    _Job.started[0].published.emit("Published v3 (abc1234) to r. The Telegram message was sent.")
    _Job.started[0].done.emit(str(tmp_path / "build" / "iso" / "game.iso"))
    _Job.started[1].done.emit(str(tmp_path / "build" / "bluewake" / "GZLE01.iso"))
    assert len(shown) == 1 and "Published v3" in shown[0][1] and "game.iso" in shown[0][1]


def test_an_unchecked_publish_box_builds_without_publishing(qtbot, tmp_path, monkeypatch):
    actions, opened, shown = _run(qtbot, tmp_path, monkeypatch, ["iso"], publish=["iso"])
    dialog = actions._publish_dialog
    qtbot.addWidget(dialog)
    dialog.publish_check.setChecked(False)
    dialog.accept()
    assert [(job.target, job.publish) for job in _Job.started] == [("iso", None)]


def test_cancelling_the_question_builds_nothing(qtbot, tmp_path, monkeypatch):
    actions, opened, shown = _run(qtbot, tmp_path, monkeypatch, ["iso"], publish=["iso"])
    dialog = actions._publish_dialog
    qtbot.addWidget(dialog)
    dialog.reject()
    assert _Job.started == [] and getattr(actions, "_build_run", None) is None


def test_build_rom_builds_every_target_one_after_another_without_asking(qtbot, tmp_path, monkeypatch):
    actions, opened, shown = _run(qtbot, tmp_path, monkeypatch, ["nup", "hookshot"])
    assert [job.target for job in _Job.started] == ["nup"]
    _Job.started[0].progress.emit(50, "Writing")
    assert actions._build_dialog.value() == 25          # half of the first of two targets
    assert "NUP (1/2): Writing" in actions._build_dialog.labelText()
    _Job.started[0].done.emit(str(tmp_path / "build" / "nup" / "game.nup"))
    assert [job.target for job in _Job.started] == ["nup", "hookshot"]
    _Job.started[1].done.emit(str(tmp_path / "build" / "hookshot"))
    assert opened == [QUrl.fromLocalFile(str(tmp_path / "build"))]
    assert len(shown) == 1 and shown[0][0] == "information"
    assert "game.nup" in shown[0][1] and "hookshot" in shown[0][1]
    assert actions._build_dialog is None and actions._build_job is None


def test_a_failed_target_is_reported_and_the_next_one_still_builds(qtbot, tmp_path, monkeypatch):
    actions, opened, shown = _run(qtbot, tmp_path, monkeypatch, ["nup", "hookshot"])
    _Job.started[0].failed.emit("disk full")
    _Job.started[1].done.emit(str(tmp_path / "build" / "hookshot"))
    assert shown[0][0] == "critical"
    assert "NUP failed: disk full" in shown[0][1] and "hookshot" in shown[0][1]
    assert opened == [QUrl.fromLocalFile(str(tmp_path / "build"))]


def test_cancel_stops_the_run(qtbot, tmp_path, monkeypatch):
    actions, opened, shown = _run(qtbot, tmp_path, monkeypatch, ["nup", "hookshot"])
    actions._build_dialog.findChild(QPushButton).click()
    assert _Job.started[0].interrupted
    _Job.started[0].cancelled.emit()
    assert len(_Job.started) == 1 and opened == []
    assert shown == [("information", "Build cancelled")]


def test_one_target_opens_its_own_folder(qtbot, tmp_path, monkeypatch):
    result = tmp_path / "build" / "iso" / "game (UA).iso"
    result.parent.mkdir(parents=True)
    result.write_bytes(b"x")
    actions, opened, shown = _run(qtbot, tmp_path, monkeypatch, ["iso"])
    _Job.started[0].done.emit(str(result))
    assert opened == [QUrl.fromLocalFile(str(result.parent))]
    assert shown and str(result) in shown[0][1]


def test_failure_closes_the_dialog_without_opening_a_folder(qtbot, monkeypatch):
    opened, shown = [], []
    monkeypatch.setattr(settings_mixin.QMessageBox, "critical", lambda *args: shown.append(args[2]))
    monkeypatch.setattr("PyQt6.QtGui.QDesktopServices.openUrl", lambda url: opened.append(url))
    actions = _actions(qtbot)
    actions._build_ended("Build failed", "disk full", True)
    assert opened == [] and actions._build_dialog is None
    assert shown == ["Build failed\n\ndisk full"]


def test_progress_window_is_not_resizable(qtbot):
    actions = _actions(qtbot)
    cancelled = []
    dialog = actions._build_progress_dialog("Build ROM", lambda: cancelled.append(True))
    qtbot.addWidget(dialog)
    actions._build_dialog = dialog
    assert dialog.minimumSize() == dialog.maximumSize()
    actions._build_progress(10, "A much longer step text than the first label had")
    assert dialog.minimumSize() == dialog.maximumSize()
    dialog.findChild(QPushButton).click()
    assert cancelled == [True]
