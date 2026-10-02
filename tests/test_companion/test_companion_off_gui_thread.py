"""No Companion request runs on the GUI thread (WP6 6.3)."""
import threading
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QDialog, QProgressDialog, QPushButton, QWidget

from components.companion.background_call import run_companion_call
from components.companion.sync_dialog import CompanionSyncDialog
from core.companion_sync import ConflictRecord, MergeResult, sync_push_on_close
from utils import thread_utils


def test_a_call_runs_in_another_thread_and_its_result_arrives_on_the_gui_thread(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    gui_thread = QThread.currentThread()
    seen = {}

    def call(cancelled):
        seen["call_thread"] = QThread.currentThread()
        return True, "pong", cancelled()

    def on_result(result):
        seen["result"] = result
        seen["result_thread"] = QThread.currentThread()

    run_companion_call(parent, call, on_result)
    qtbot.waitUntil(lambda: "result" in seen, timeout=5000)

    assert seen["result"] == (True, "pong", False)
    assert seen["call_thread"] != gui_thread and seen["result_thread"] == gui_thread
    assert not parent.findChild(QProgressDialog).isVisible()
    qtbot.waitUntil(lambda: not thread_utils._running, timeout=5000)


def test_a_call_that_raises_reports_none_instead_of_hanging_the_progress_window(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    results = []

    def call(_cancelled):
        raise RuntimeError("the server sent nonsense")

    run_companion_call(parent, call, results.append)
    qtbot.waitUntil(lambda: results == [None], timeout=5000)
    qtbot.waitUntil(lambda: not thread_utils._running, timeout=5000)


def test_cancelling_returns_at_once_and_the_result_is_dropped(qtbot):
    thread_utils._parked.clear()
    parent = QWidget()
    qtbot.addWidget(parent)
    started, release = threading.Event(), threading.Event()
    results, cancelled_seen = [], []

    def call(cancelled):
        started.set()
        release.wait(10)
        cancelled_seen.append(cancelled())
        return True, "too late", 0

    run_companion_call(parent, call, results.append)
    try:
        assert started.wait(5)
        parent.findChild(QProgressDialog).findChild(QPushButton).click()      # the Cancel button
        assert len(thread_utils._parked) == 1 and not thread_utils._running
    finally:
        release.set()
    qtbot.waitUntil(lambda: not thread_utils._parked, timeout=5000)

    assert cancelled_seen == [True] and results == []


class _ConflictingClient:
    """The first sync reports a conflict; the commit records the thread it ran in."""
    is_configured = True

    def __init__(self):
        self.commit_thread = None
        self.merge = MergeResult(merged_entries=[], pulled_count=0, pushed_count=0, conflicts=[])

    def sync_project(self, **_arguments):
        conflict = MagicMock(spec=ConflictRecord)
        return True, "conflicts", 0, 0, [conflict], self.merge

    def commit_merge(self, *, on_status, cancelled, **_arguments):
        self.commit_thread = QThread.currentThread()
        on_status("committing")
        return True, "Synchronized", 1, 2, [], None


def test_a_resolved_merge_is_committed_in_the_worker_not_in_the_window(qtbot, tmp_path):
    client = _ConflictingClient()
    dialog = CompanionSyncDialog(
        client=client, project_name="P", glossary_path=tmp_path / "g.json", auto_start=False, auto_close_ms=0
    )
    qtbot.addWidget(dialog)
    resolver = MagicMock()
    resolver.return_value.exec.return_value = QDialog.DialogCode.Accepted
    resolver.return_value.get_resolutions.return_value = {}

    with patch("components.companion.sync_dialog.CompanionConflictDialog", resolver), \
         patch("components.companion.sync_dialog.apply_conflict_resolutions", return_value=client.merge):
        dialog.start_sync()
        qtbot.waitUntil(lambda: dialog.was_successful, timeout=5000)

    assert client.commit_thread is not None and client.commit_thread != QThread.currentThread()
    assert (dialog.terms_pulled, dialog.terms_pushed) == (1, 2)


class _SilentClient:
    is_configured = True

    def __init__(self):
        self.started, self.release = threading.Event(), threading.Event()

    def sync_project(self, *, cancelled, **_arguments):
        self.started.set()
        self.release.wait(10)
        return False, "cancelled" if cancelled() else "late", 0, 0, [], None


def test_on_exit_a_silent_server_is_given_up_on_after_the_cap(qtbot, tmp_path):
    thread_utils._parked.clear()
    client = _SilentClient()
    dialog = CompanionSyncDialog(
        client=client, project_name="P", glossary_path=tmp_path / "g.json", auto_start=False, is_closing=True
    )
    qtbot.addWidget(dialog)
    dialog._closing_cap.setInterval(50)
    try:
        dialog.start_sync()
        assert client.started.wait(5)
        qtbot.waitUntil(lambda: dialog._worker is None, timeout=5000)      # the cap fired and skipped
        assert dialog.result() == QDialog.DialogCode.Rejected and dialog.was_successful is False
    finally:
        client.release.set()
    qtbot.waitUntil(lambda: not thread_utils._parked, timeout=5000)


def test_without_the_closing_mode_there_is_no_cap(qtbot, tmp_path):
    dialog = CompanionSyncDialog(client=MagicMock(is_configured=False), project_name="P",
                                 glossary_path=tmp_path / "g.json", auto_start=False)
    qtbot.addWidget(dialog)

    dialog.start_sync()

    assert not dialog._closing_cap.isActive()


class _Window(QWidget):
    is_testing = False
    settings_manager = None


def test_on_close_with_a_window_the_sync_never_falls_back_to_a_blocking_call(qtbot, tmp_path):
    window = _Window()
    qtbot.addWidget(window)
    client = MagicMock(is_configured=True)

    with patch("core.companion_sync.get_companion_client_from_mw", return_value=client), \
         patch("core.companion_sync.resolve_project_glossary_info", return_value=("P", tmp_path / "g.json", None)), \
         patch("components.companion.sync_dialog.CompanionSyncDialog", side_effect=RuntimeError("no display")):
        assert sync_push_on_close(window) is False

    client.sync_project.assert_not_called()


def test_settings_that_hold_no_address_start_no_client():
    from core.companion_sync import get_companion_client_from_mw

    window = MagicMock()        # every setting it returns is an object, not a string

    assert get_companion_client_from_mw(window) is None
