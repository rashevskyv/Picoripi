"""Closing the Project Manager: with no project open the window quits Picoripi (as File > Exit does); with one open it returns."""
from types import SimpleNamespace

from PyQt6.QtCore import Qt

from handlers.project_action import library_mixin
from handlers.project_action.library_mixin import LibraryMixin
from ui.project_manager import window
from ui.project_manager.window import ProjectManagerDialog


def _no_scan_child(monkeypatch):
    monkeypatch.setattr(window.ScanProcess, "start", lambda self, data_dir, projects: True)


def _dialog(qtbot, settings, on_closed, opened=None):
    dialog = ProjectManagerDialog(None, str(settings), (opened if opened is not None else []).append,
                                  lambda: None, lambda project_file, updates: None, lambda name, value: None,
                                  on_closed=on_closed)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(lambda: dialog._loaded, timeout=5000)
    return dialog


def _mixin(project):
    """A stand-in main window: its ``close`` records a quit, ``project_manager.project`` is the open project."""
    closes = []
    mixin = LibraryMixin()
    mixin.mw = SimpleNamespace(project_manager=SimpleNamespace(project=project), close=lambda: closes.append(1))
    return mixin, closes


def test_the_close_button_calls_on_closed_once(qtbot, tmp_path, monkeypatch):
    _no_scan_child(monkeypatch)
    calls = []
    dialog = _dialog(qtbot, tmp_path, lambda: calls.append(1))

    dialog.close()

    assert not dialog.isVisible()
    assert calls == [1]


def test_esc_calls_on_closed_once(qtbot, tmp_path, monkeypatch):
    _no_scan_child(monkeypatch)
    calls = []
    dialog = _dialog(qtbot, tmp_path, lambda: calls.append(1))

    qtbot.keyClick(dialog, Qt.Key.Key_Escape)

    assert not dialog.isVisible()
    assert calls == [1]


def test_opening_a_project_from_the_manager_does_not_call_on_closed(qtbot, tmp_path, monkeypatch):
    _no_scan_child(monkeypatch)
    calls = []
    opened = []
    dialog = _dialog(qtbot, tmp_path, lambda: calls.append(1), opened)

    dialog._open(str(tmp_path / "Aria" / "project.uiproj"))

    assert opened == [str(tmp_path / "Aria" / "project.uiproj")]
    assert not dialog.isVisible()
    assert calls == []


def test_after_an_open_the_next_close_still_calls_on_closed(qtbot, tmp_path, monkeypatch):
    _no_scan_child(monkeypatch)
    calls = []
    dialog = _dialog(qtbot, tmp_path, lambda: calls.append(1))
    dialog._open(str(tmp_path / "Aria" / "project.uiproj"))
    dialog.show()

    dialog.close()

    assert calls == [1]


def test_closing_with_no_project_open_quits_through_the_main_window_close(qtbot, tmp_path, monkeypatch):
    mixin, closes = _mixin(project=None)

    mixin._project_manager_closed()

    assert closes == [1]


def test_closing_with_a_project_open_only_returns_to_it(qtbot, tmp_path, monkeypatch):
    mixin, closes = _mixin(project=object())

    mixin._project_manager_closed()

    assert closes == []


def test_the_manager_is_built_with_the_quit_rule(qtbot, tmp_path, monkeypatch):
    """The mixin hands its rule to the window; the window itself does not know about the main window."""
    seen = {}

    class FakeDialog:
        def __init__(self, parent, library_dir, open_project, new_project, save_flags, save_setting, **kwargs):
            seen.update(kwargs)

        def show(self):
            pass

        def raise_(self):
            pass

        def activateWindow(self):
            pass

    monkeypatch.setattr(library_mixin, "ProjectManagerDialog", FakeDialog)
    mixin, _closes = _mixin(project=None)
    mixin.mw.project_manager_dialog = None
    mixin.open_project_manager_action()

    assert seen["on_closed"] == mixin._project_manager_closed
