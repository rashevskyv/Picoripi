"""Workers stop when asked and leave nothing half-done behind (WP6 6.2)."""
import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.companion_sync import CompanionPullWorker, CompanionSyncClient, MergeResult
from dialogs.tag_alias_dialog import AliasUpdateWorker
from handlers.app_action_handler import AppActionHandler, SaveWorker
from handlers.project_action.load_worker import ProjectLoadWorker
from utils import thread_utils


def _response(payload, status=200):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload
    return response


REMOTE = {"glossary": [{"original": "Hyrule", "translation": "Гайрул"}], "updated_at": ""}


class TestCompanionClient:
    def _client_and_file(self, tmp_path):
        glossary = tmp_path / "glossary.json"
        glossary.write_text('[{"original": "Hyrule", "translation": "old"}]', encoding="utf-8")
        return CompanionSyncClient("http://server:8000", "token"), glossary

    def test_a_pull_cancelled_during_the_request_does_not_rewrite_the_glossary(self, tmp_path):
        client, glossary = self._client_and_file(tmp_path)
        before = glossary.read_bytes()

        with patch("requests.get", return_value=_response(REMOTE)):
            ok, _message, count = client.pull_project("P", glossary, cancelled=lambda: True)

        assert (ok, count) == (False, 0)
        assert glossary.read_bytes() == before and not glossary.with_suffix(".json.bak").exists()

    def test_the_same_pull_not_cancelled_writes_it(self, tmp_path):
        client, glossary = self._client_and_file(tmp_path)

        with patch("requests.get", return_value=_response(REMOTE)):
            ok, _message, count = client.pull_project("P", glossary)

        assert (ok, count) == (True, 1)
        assert json.loads(glossary.read_text(encoding="utf-8"))[0]["translation"] == "Гайрул"

    def test_a_sync_cancelled_during_the_request_neither_writes_nor_pushes(self, tmp_path):
        client, glossary = self._client_and_file(tmp_path)
        before = glossary.read_bytes()

        with patch("requests.get", return_value=_response(REMOTE)), patch("requests.post") as post:
            ok, *_rest = client.sync_project("P", glossary, cancelled=lambda: True)

        assert ok is False and glossary.read_bytes() == before
        post.assert_not_called()

    def test_a_cancelled_commit_neither_writes_nor_pushes(self, tmp_path):
        client, glossary = self._client_and_file(tmp_path)
        before = glossary.read_bytes()
        merge = MergeResult(merged_entries=[{"original": "Hyrule", "translation": "new"}], pulled_count=1, pushed_count=1, conflicts=[])

        with patch("requests.post") as post:
            ok, *_rest = client.commit_merge("P", glossary, merge, cancelled=lambda: True)

        assert ok is False and glossary.read_bytes() == before
        post.assert_not_called()

    def test_a_push_cancelled_before_the_request_sends_nothing(self, tmp_path):
        client, glossary = self._client_and_file(tmp_path)

        with patch("requests.post") as post:
            ok, _message, count = client.push_project("P", glossary, cancelled=lambda: True)

        assert (ok, count) == (False, 0)
        post.assert_not_called()

    def test_the_worker_hands_its_own_interruption_flag_to_the_client(self, tmp_path):
        client = MagicMock()
        client.pull_project.return_value = (True, "ok", 0)
        worker = CompanionPullWorker(client, "P", tmp_path / "glossary.json")

        worker.run()

        assert client.pull_project.call_args.kwargs["cancelled"] == worker.isInterruptionRequested


class _ProjectManager:
    def __init__(self):
        block = SimpleNamespace(metadata={}, source_file="a.txt", translation_file="a.txt", internal_key=None, name="a")
        self.project = SimpleNamespace(blocks=[block, block])
        self.paths_asked = []

    def clear_archive_cache(self):
        pass

    def get_absolute_path(self, path, **_kwargs):
        self.paths_asked.append(path)
        return "no-such-file"


def test_an_interrupted_project_load_reads_no_more_files_and_reports_an_empty_result(qtbot, monkeypatch):
    manager = _ProjectManager()
    worker = ProjectLoadWorker(manager, None)
    monkeypatch.setattr(worker, "isInterruptionRequested", lambda: True)
    results = []
    worker.finished_with_result.connect(results.append)

    worker.run()

    assert results == [{}] and manager.paths_asked == [] and worker.error_occurred is None


def test_an_interrupted_alias_update_reports_nothing(qtbot, monkeypatch):
    worker = AliasUpdateWorker({}, [["{a} one"], ["{a} two"]], [], "{a}", "[tag]")
    monkeypatch.setattr(worker, "isInterruptionRequested", lambda: True)
    results = []
    worker.finished_signal.connect(lambda *arguments: results.append(arguments))

    worker.run()

    assert results == []          # half-replaced data must not reach the data store


class _RunningSave(SaveWorker):
    def isRunning(self):
        return True


def test_a_second_save_is_refused_while_one_is_running(qtbot):
    window = MagicMock()
    handler = AppActionHandler(window, window.data_processor, window.ui_updater, window.current_game_rules)
    running = _RunningSave(window.data_processor, [])
    handler.save_worker = running
    outcomes = []

    with patch("handlers.app_action_handler.QProgressDialog") as progress_dialog:
        handler.perform_async_save_flow([], on_finished_callback=lambda *outcome: outcomes.append(outcome))

    assert handler.save_worker is running
    assert len(outcomes) == 1 and outcomes[0][0] is False and outcomes[0][2]
    progress_dialog.assert_not_called()
    window.state.set_active.assert_not_called()


class _SlowClient:
    """A Companion server that does not answer until the test lets it."""
    is_configured = True

    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.went_on_after_the_request = False

    def sync_project(self, *, cancelled, **_arguments):
        self.started.set()
        self.release.wait(10)
        if cancelled():
            return False, "cancelled", 0, 0, [], None
        self.went_on_after_the_request = True
        return True, "ok", 0, 0, [], None


def test_skipping_a_stuck_companion_sync_returns_at_once_and_kills_no_thread(qtbot, tmp_path):
    from components.companion.sync_dialog import CompanionSyncDialog

    thread_utils._parked.clear()
    client = _SlowClient()
    dialog = CompanionSyncDialog(client=client, project_name="P", glossary_path=tmp_path / "g.json", auto_start=False)
    qtbot.addWidget(dialog)
    dialog.start_sync()
    worker = dialog._worker
    try:
        assert client.started.wait(5)
        with patch.object(type(worker), "terminate") as terminate:
            began = time.monotonic()
            dialog._on_skip_clicked()
            waited = time.monotonic() - began

        terminate.assert_not_called()
        assert waited < 2.0                                   # the window is not held by the network
        assert thread_utils._parked == [(worker, worker)]     # the thread is kept until it ends
        assert dialog._worker is None and dialog.was_successful is False
    finally:
        client.release.set()
    qtbot.waitUntil(lambda: not thread_utils._parked, timeout=5000)
    assert client.went_on_after_the_request is False          # and it did nothing after being told to stop
