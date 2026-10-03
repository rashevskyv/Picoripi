"""REVIEW_QUEUE WP6 6.2/6.3: Companion push, pull, test, conflicts, exit and skip against the real server.

The real Companion server (companion/server, FastAPI) runs in-process under uvicorn on 127.0.0.1; a server
that accepts and never answers is a listening socket nobody accepts from. The desktop side is the real
MainWindow, glossary window, Settings dialog and sync dialogs; message boxes and menus are answered by a
timer the way a user would click them.
"""
import asyncio
import socket
import threading
import time

import pytest
import requests
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QProgressDialog, QPushButton

from test_review._rq_wp1_6_helpers import main_window, make_plain_project, open_project  # noqa: F401
from utils import thread_utils

uvicorn = pytest.importorskip("uvicorn")
pytest.importorskip("fastapi")

TOKEN = "rq-pin"
PROJECT = "RQ"


# ------------------------------------------------------------------------- servers

class _PushDelay:
    """ASGI wrapper: holds /api/sync/push for ``seconds`` so the window can be watched while it pushes."""

    def __init__(self, app):
        self.app = app
        self.seconds = 0.0

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("path") == "/api/sync/push" and self.seconds:
            await asyncio.sleep(self.seconds)
        await self.app(scope, receive, send)


class CompanionServer:
    def __init__(self, data_dir):
        from companion.server.main import create_app

        self.app = _PushDelay(create_app(data_dir=data_dir, auth_token=TOKEN))
        self.server = uvicorn.Server(uvicorn.Config(self.app, host="127.0.0.1", port=0, log_level="warning",
                                                    lifespan="off"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started:
            assert time.monotonic() < deadline, "the Companion server did not start"
            time.sleep(0.01)
        self.url = f"http://127.0.0.1:{self.server.servers[0].sockets[0].getsockname()[1]}"

    def stop(self):
        self.server.should_exit = True
        self.thread.join(5)

    # what the phone does
    def headers(self):
        return {"Authorization": f"Bearer {TOKEN}"}

    def glossary(self):
        response = requests.get(f"{self.url}/api/sync/pull", params={"project": PROJECT}, headers=self.headers(), timeout=5)
        return {e["original"]: e for e in response.json().get("glossary", []) if not e.get("deleted_at")} \
            if response.status_code == 200 else {}

    def phone_edit(self, original, translation):
        response = requests.put(f"{self.url}/api/glossary/entry", params={"project": PROJECT}, headers=self.headers(),
                                json={"original": original, "translation": translation}, timeout=5)
        assert response.status_code == 200, response.text


@pytest.fixture
def companion(tmp_path):
    server = CompanionServer(tmp_path / "companion_data")
    yield server
    server.stop()


class SilentServer:
    """Accepts connections (the kernel does) and never answers. ``close()`` resets every waiting request."""

    def __init__(self):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(16)
        self.url = f"http://127.0.0.1:{self.sock.getsockname()[1]}"

    def close(self):
        self.sock.close()


@pytest.fixture
def silent_server(qtbot):
    server = SilentServer()
    yield server
    server.close()      # the parked requests fail now instead of after the client's timeout
    qtbot.waitUntil(lambda: not thread_utils._parked, timeout=10000)


def refused_url():
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return f"http://127.0.0.1:{port}"


# ------------------------------------------------------------------------- the user

class User:
    """Watches the screen every 15 ms; answers message boxes, picks menu entries, presses buttons on request."""

    def __init__(self):
        self.boxes = []          # (title, text) of every message box seen
        self.menu_choice = None  # text fragment of the menu entry to pick
        self.plans = []          # [(predicate(widget) -> bool, action(widget))], each run once
        self.samples = []        # what the sync dialog showed, while it was open
        self.timer = QTimer()
        self.timer.timeout.connect(self._look)
        self.timer.start(15)

    def stop(self):
        self.timer.stop()

    def when(self, predicate, action):
        self.plans.append((predicate, action))

    def _look(self):
        from components.companion.sync_dialog import CompanionSyncDialog

        for widget in QApplication.topLevelWidgets():
            if not widget.isVisible():
                continue
            if isinstance(widget, QMessageBox):
                self.boxes.append((widget.windowTitle(), widget.text()))
                widget.done(0)
            elif isinstance(widget, QMenu) and self.menu_choice:
                action = next((a for a in widget.actions() if self.menu_choice in a.text()), None)
                if action is not None:
                    self.menu_choice = None
                    widget.setActiveAction(action)
                    QTest.keyClick(widget, Qt.Key.Key_Return)
            elif isinstance(widget, CompanionSyncDialog):
                bar = widget._progress_bar
                self.samples.append((time.monotonic(), bar.minimum(), bar.maximum(), widget._status_label.text()))
            for plan in list(self.plans):
                if plan[0](widget):
                    self.plans.remove(plan)
                    plan[1](widget)


@pytest.fixture
def user():
    watcher = User()
    yield watcher
    watcher.stop()


def configure(mw, url, auto_sync):
    for key, value in (("companion_server_url", url), ("companion_api_token", TOKEN), ("companion_auto_sync", auto_sync)):
        mw.settings_manager.set(key, value)
        setattr(mw, key, value)


def project_window(mw, tmp_path, monkeypatch, qtbot, terms=(("Hello", "Привіт"), ("World", "Світ"))):
    project = make_plain_project(tmp_path, {"a": ["Hello there", "World"]}, name=PROJECT)
    open_project(mw, project, monkeypatch, qtbot)
    manager = mw.translation_handler.glossary_handler.glossary_manager
    for original, translation in terms:
        manager.add_entry(original, translation, "")
    return manager


def open_glossary_window(mw, qtbot):
    handler = mw.translation_handler.glossary_handler
    handler.show_glossary_dialog()
    qtbot.waitUntil(lambda: handler.dialog is not None and handler.dialog.isVisible(), timeout=10000)
    return handler.dialog


def companion_menu(dialog, user, entry, qtbot):
    user.menu_choice = entry
    seen_before = len(user.boxes)
    dialog._companion_sync_button.click()
    qtbot.waitUntil(lambda: len(user.boxes) > seen_before, timeout=10000)
    return user.boxes[-1]


# ------------------------------------------------------------------------- 6.3 glossary window and Settings

def test_glossary_window_push_and_test_connection_reach_the_real_server(main_window, companion, user, qtbot, tmp_path, monkeypatch):  # noqa: F811
    project_window(main_window, tmp_path, monkeypatch, qtbot)
    configure(main_window, companion.url, auto_sync=False)
    dialog = open_glossary_window(main_window, qtbot)
    # A loopback push can finish inside one 15 ms look of the user, so record every show() instead of polling.
    import components.companion.background_call as background_call
    progress_seen = []

    class RecordingProgress(QProgressDialog):
        def show(self):
            if "Companion" in self.labelText():
                progress_seen.append(self.labelText())
            super().show()

    monkeypatch.setattr(background_call, "QProgressDialog", RecordingProgress)

    title, text = companion_menu(dialog, user, "Push Glossary", qtbot)
    assert progress_seen, "no progress window while pushing"
    assert (title, text) == ("Companion Sync", "✓ Successfully pushed 2 terms to Companion server.")
    assert {k: v["translation"] for k, v in companion.glossary().items()} == {"Hello": "Привіт", "World": "Світ"}

    title, text = companion_menu(dialog, user, "Test Server Connection", qtbot)
    assert (title, text) == ("Companion Server", "✓ Connection successful! Found 1 project(s) on server.")


def test_glossary_window_pull_brings_the_phone_edit_into_the_glossary_and_the_view(main_window, companion, user, qtbot, tmp_path, monkeypatch):  # noqa: F811
    manager = project_window(main_window, tmp_path, monkeypatch, qtbot)
    configure(main_window, companion.url, auto_sync=False)
    dialog = open_glossary_window(main_window, qtbot)
    companion_menu(dialog, user, "Push Glossary", qtbot)
    companion.phone_edit("Hello", "Вітаю")

    title, text = companion_menu(dialog, user, "Pull Reviewed Glossary", qtbot)

    assert title == "Companion Sync" and text.startswith("✓ Successfully pulled")
    assert manager.get_entry("Hello").translation == "Вітаю"                     # the glossary
    assert any(e.original == "Hello" and e.translation == "Вітаю" for e in dialog._all_entries)   # the view


def test_settings_test_connection_reports_success_and_a_wrong_token(main_window, companion, qtbot):  # noqa: F811
    from ui.settings_dialog import SettingsDialog

    settings = SettingsDialog(main_window)
    qtbot.addWidget(settings)
    settings.companion_url_edit.setText(companion.url)
    for token, expected in ((TOKEN, "✓ Connection successful! Found 0 project(s) on server."),
                            ("wrong", "✗ Authentication failed: invalid token or PIN.")):
        settings.companion_token_edit.setText(token)
        settings.test_companion_btn.click()
        assert settings.companion_status_label.text() == "Connecting..."
        qtbot.waitUntil(lambda: settings.companion_status_label.text() == expected, timeout=10000)


def test_settings_test_connection_to_a_silent_server_cancels_at_once(main_window, silent_server, qtbot):  # noqa: F811
    from ui.settings_dialog import SettingsDialog

    settings = SettingsDialog(main_window)
    qtbot.addWidget(settings)
    settings.companion_url_edit.setText(silent_server.url)
    settings.companion_token_edit.setText(TOKEN)
    settings.test_companion_btn.click()
    progress = settings.findChild(QProgressDialog)
    qtbot.waitUntil(lambda: progress.isVisible(), timeout=5000)
    QTest.qWait(200)                                   # the request is out and hangs

    started = time.monotonic()
    progress.findChild(QPushButton).click()            # Cancel
    assert time.monotonic() - started < 1.0
    assert not progress.isVisible()
    QTest.qWait(100)
    assert settings.companion_status_label.text() == "Connecting..."      # no late result


# ------------------------------------------------------------------------- 6.3 conflicts

def test_a_conflict_is_resolved_and_the_sync_window_finishes_with_counts_while_it_pushes(main_window, companion, user, qtbot, tmp_path, monkeypatch):  # noqa: F811
    from components.companion.conflict_dialog import CompanionConflictDialog

    manager = project_window(main_window, tmp_path, monkeypatch, qtbot)
    configure(main_window, companion.url, auto_sync=True)
    handler = main_window.translation_handler.glossary_handler

    open_glossary_window(main_window, qtbot)            # the first sync uploads the glossary
    assert set(companion.glossary()) == {"Hello", "World"}
    handler.dialog.close()

    companion.phone_edit("Hello", "Вітаю (телефон)")     # the same term, on the phone ...
    handler._handle_glossary_entry_update("Hello", "Привіт (ПК)", "")    # ... and on the desktop (the window's edit path)
    assert manager.get_entry("Hello").translation == "Привіт (ПК)"

    resolved = []

    def keep_local(conflicts):
        resolved.append([(c.original, c.local_entry.get("translation"), c.remote_entry.get("translation"))
                         for c in conflicts.conflicts])
        next(b for b in conflicts.findChildren(QPushButton) if b.text() == "Keep All Local (PC)").click()
        conflicts.accept()

    user.when(lambda w: isinstance(w, CompanionConflictDialog), keep_local)
    companion.app.seconds = 0.6                          # the commit's push takes a while
    open_glossary_window(main_window, qtbot)

    assert resolved == [[("Hello", "Привіт (ПК)", "Вітаю (телефон)")]]
    # After the resolution the window went back to its busy bar and kept repainting during the push ...
    pushing = [s for s in user.samples if s[3] == "Pushing local updates to Companion server…"]
    assert len(pushing) >= 10 and all((s[1], s[2]) == (0, 0) for s in pushing)
    # ... and finished with the counts.
    assert any(s[3] == "✓ Synchronized successfully: 0 pulled, 1 pushed." for s in user.samples)
    assert companion.glossary()["Hello"]["translation"] == "Привіт (ПК)"
    assert manager.get_entry("Hello").translation == "Привіт (ПК)"


def test_terms_pulled_on_glossary_open_survive_reopening_the_glossary_window(main_window, companion, user, qtbot, tmp_path, monkeypatch):  # noqa: F811
    manager = project_window(main_window, tmp_path, monkeypatch, qtbot)
    configure(main_window, companion.url, auto_sync=True)
    handler = main_window.translation_handler.glossary_handler
    open_glossary_window(main_window, qtbot)            # uploads the glossary
    handler.dialog.close()
    companion.phone_edit("Hello", "Вітаю")
    from components.companion.conflict_dialog import CompanionConflictDialog

    def take_remote(conflicts):     # the edit lands within 2 s of the upload: the user keeps the phone's version
        next(b for b in conflicts.findChildren(QPushButton) if b.text() == "Keep All Remote (Companion)").click()
        conflicts.accept()

    user.when(lambda w: isinstance(w, CompanionConflictDialog), take_remote)
    open_glossary_window(main_window, qtbot)            # pulls the phone's edit
    assert manager.get_entry("Hello").translation == "Вітаю"
    handler.dialog.close()
    configure(main_window, companion.url, auto_sync=False)   # e.g. working offline from here on

    dialog = open_glossary_window(main_window, qtbot)
    assert manager.get_entry("Hello").translation == "Вітаю"
    assert any(e.original == "Hello" and e.translation == "Вітаю" for e in dialog._all_entries)


# ------------------------------------------------------------------------- 6.2 / 6.3 exit and skip

def _close(mw, qtbot):
    mw.is_testing = False                 # the real application's close path, Companion sync included
    started = time.monotonic()
    mw.close()
    elapsed = time.monotonic() - started
    mw.is_testing = True                  # the fixture's second close must not sync again
    return elapsed


def _sync_dialog(widget, closing):
    from components.companion.sync_dialog import CompanionSyncDialog
    return isinstance(widget, CompanionSyncDialog) and widget.is_closing == closing


def test_exit_with_the_server_off_shows_the_error_and_close_anyway_closes(main_window, user, qtbot, tmp_path, monkeypatch):  # noqa: F811
    project_window(main_window, tmp_path, monkeypatch, qtbot)
    configure(main_window, refused_url(), auto_sync=True)
    seen = {}

    def close_anyway(dialog):
        seen["title"], seen["status"] = dialog.windowTitle(), dialog._status_label.text()
        dialog._skip_button.click()

    user.when(lambda w: _sync_dialog(w, True) and w._skip_button.text() == "Close Anyway", close_anyway)
    elapsed = _close(main_window, qtbot)

    assert seen["title"] == "Closing Picoripi — Synchronizing Glossary…"
    assert seen["status"].startswith("✗ Failed to sync with Companion server")
    assert elapsed < 8 and not main_window.isVisible()


def test_exit_with_a_silent_server_closes_by_itself_after_the_cap(main_window, silent_server, user, qtbot, tmp_path, monkeypatch):  # noqa: F811
    import components.companion.sync_dialog as sync_dialog

    monkeypatch.setattr(sync_dialog, "CLOSING_CAP_MS", 600)   # 6 s in the product; the mechanism is the same
    project_window(main_window, tmp_path, monkeypatch, qtbot)
    configure(main_window, silent_server.url, auto_sync=True)
    shown = []
    user.when(lambda w: _sync_dialog(w, True), lambda w: shown.append(w.windowTitle()))

    elapsed = _close(main_window, qtbot)

    assert shown == ["Closing Picoripi — Synchronizing Glossary…"]
    assert 0.5 < elapsed < 3                         # the cap, not the client's 6 s timeout
    assert not any("Error" in title or "Failed" in title for title, _ in user.boxes)


def test_exit_skip_and_close_leaves_at_once(main_window, silent_server, user, qtbot, tmp_path, monkeypatch):  # noqa: F811
    project_window(main_window, tmp_path, monkeypatch, qtbot)
    configure(main_window, silent_server.url, auto_sync=True)
    user.when(lambda w: _sync_dialog(w, True) and w._worker is not None and w._skip_button.text() == "Skip & Close",
              lambda w: w._skip_button.click())

    elapsed = _close(main_window, qtbot)

    assert elapsed < 2.5            # the cap is 6 s; Skip did not wait for it
    assert not main_window.isVisible()


def test_sync_to_a_silent_server_then_skip_closes_at_once_and_the_glossary_opens(main_window, silent_server, user, qtbot, tmp_path, monkeypatch):  # noqa: F811
    project_window(main_window, tmp_path, monkeypatch, qtbot)
    configure(main_window, silent_server.url, auto_sync=True)
    skipped = []

    def skip(dialog):
        skipped.append(time.monotonic())
        dialog._skip_button.click()

    user.when(lambda w: _sync_dialog(w, False) and w._worker is not None
              and w._skip_button.text() == "Skip & Work Offline", skip)

    dialog = open_glossary_window(main_window, qtbot)

    assert skipped and time.monotonic() - skipped[0] < 2.0      # the sync window let go at once ...
    assert dialog.isVisible()                                    # ... and the editor went on to the glossary
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start(10)
    QTest.qWait(300)
    timer.stop()
    assert len(ticks) >= 10                                      # the event loop is not blocked by the hung request
