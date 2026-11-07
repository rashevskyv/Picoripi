"""Build ROM shows a progress window with Cancel and opens the result's folder when the build is done."""
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QMainWindow, QProgressDialog, QStatusBar

from ui.main_window.actions import settings_mixin
from ui.main_window.actions.settings_mixin import MainWindowSettingsActionsMixin


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


def test_progress_reaches_the_dialog(qtbot):
    actions = _actions(qtbot)
    actions._build_progress(42, "Writing the package")
    assert actions._build_dialog.value() == 42
    assert actions._build_dialog.labelText() == "Writing the package"


def test_done_opens_the_folder_and_closes_the_dialog(qtbot, tmp_path, monkeypatch):
    opened, shown = [], []
    monkeypatch.setattr(settings_mixin.QMessageBox, "information", lambda *args: shown.append(args[2]))
    monkeypatch.setattr("PyQt6.QtGui.QDesktopServices.openUrl", lambda url: opened.append(url))
    result = tmp_path / "game (UA).nup"
    result.write_bytes(b"x")
    actions = _actions(qtbot)
    actions._build_done(str(result))
    assert opened == [QUrl.fromLocalFile(str(tmp_path))]
    assert actions._build_dialog is None and actions._build_job is None
    assert shown and str(result) in shown[0]


def test_failure_closes_the_dialog_without_opening_a_folder(qtbot, monkeypatch):
    opened, shown = [], []
    monkeypatch.setattr(settings_mixin.QMessageBox, "critical", lambda *args: shown.append(args[2]))
    monkeypatch.setattr("PyQt6.QtGui.QDesktopServices.openUrl", lambda url: opened.append(url))
    actions = _actions(qtbot)
    actions._build_ended("Build failed", "disk full", True)
    assert opened == [] and actions._build_dialog is None
    assert shown == ["Build failed\n\ndisk full"]
