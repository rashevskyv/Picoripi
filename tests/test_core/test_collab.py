"""Working together: a real room server on 127.0.0.1 and real clients (no network mocks)."""
import json
import time

import pytest
import requests

from core.collab.client import RoomClient
from core.collab.server import RoomServer
from core.data_state_processor import DataStateProcessor
from handlers.collab_handler import CollabHandler
from test_core.test_translation_memory import _window

FP = "fingerprint-1"


@pytest.fixture
def room(tmp_path):
    server = RoomServer("secret", FP, port=0, host="127.0.0.1", journal=tmp_path / "room.json").start()
    yield server
    server.stop()


def _client(qtbot, server, name, password="secret", fingerprint=FP):
    client = RoomClient(f"127.0.0.1:{server.port}", name, password, fingerprint)
    return client


def _stop(client):
    client.stop()
    client.wait(5000)


class TestServer:
    def test_wrong_password_and_another_project_are_refused(self, qtbot, room):
        for password, fingerprint in (("nope", FP), ("secret", "other")):
            client = _client(qtbot, room, "Olena", password, fingerprint)
            with qtbot.waitSignal(client.refused, timeout=5000) as refused:
                client.start()
            client.wait(5000)
            assert refused.args[0] in ("wrong password", "another project: the room works on different game text")

    def test_an_edit_reaches_the_other_participant_but_not_its_author(self, qtbot, room):
        a, b = _client(qtbot, room, "A"), _client(qtbot, room, "B")
        seen_a, seen_b = [], []
        a.remote_events.connect(seen_a.extend)
        b.remote_events.connect(seen_b.extend)
        for client in (a, b):
            with qtbot.waitSignal(client.joined, timeout=5000):
                client.start()
        try:
            a.queue_edit("f::b::1", "Привіт")
            qtbot.waitUntil(lambda: any(e["type"] == "edit" for e in seen_b), timeout=5000)
            edit = next(e for e in seen_b if e["type"] == "edit")
            assert (edit["key"], edit["text"], edit["name"], edit["rev"]) == ("f::b::1", "Привіт", "A", 1)
            time.sleep(1.5)
            assert not any(e["type"] == "edit" for e in seen_a)
        finally:
            _stop(a)
            _stop(b)

    def test_an_edit_against_an_old_revision_is_refused_with_the_current_text(self, room):
        base = f"http://127.0.0.1:{room.port}"
        tokens = [requests.post(base + "/join", json={"name": n, "password": "secret", "fingerprint": FP}).json()["token"]
                  for n in ("A", "B")]

        def edit(token, text, base_rev):
            return requests.post(base + "/edits", headers={"X-Room-Token": token},
                                 json={"edits": [{"key": "k", "text": text, "base_rev": base_rev}]}).json()

        assert edit(tokens[0], "A's text", 0) == {"accepted": {"k": 1}, "conflicts": {}}
        stale = edit(tokens[1], "B's text", 0)
        assert stale["accepted"] == {} and stale["conflicts"]["k"]["text"] == "A's text"
        assert stale["conflicts"]["k"]["name"] == "A" and stale["conflicts"]["k"]["rev"] == 1
        assert edit(tokens[1], "B's text", 1)["accepted"] == {"k": 2}

    def test_bad_requests_are_refused(self, room):
        base = f"http://127.0.0.1:{room.port}"
        assert requests.get(base + "/events?since=0").status_code == 401
        token = requests.post(base + "/join", json={"name": "A", "password": "secret", "fingerprint": FP}).json()["token"]
        headers = {"X-Room-Token": token}
        assert requests.post(base + "/edits", headers=headers, json={"edits": "x"}).status_code == 400
        assert requests.post(base + "/edits", headers=headers,
                             json={"edits": [{"key": "k", "text": 5, "base_rev": 0}]}).status_code == 400
        assert requests.post(base + "/join", json={"name": "", "password": "secret", "fingerprint": FP}).status_code == 400
        assert requests.post(base + "/join", data="not json", headers={"Content-Type": "application/json"}).status_code == 400

    def test_stop_returns_quickly_while_a_poll_waits(self, tmp_path):
        server = RoomServer("secret", FP, port=0, host="127.0.0.1").start()
        base = f"http://127.0.0.1:{server.port}"
        token = requests.post(base + "/join", json={"name": "A", "password": "secret", "fingerprint": FP}).json()["token"]
        import threading
        poller = threading.Thread(target=lambda: requests.get(base + "/events?since=99",
                                                              headers={"X-Room-Token": token}, timeout=5))
        poller.start()
        time.sleep(0.2)
        started = time.monotonic()
        server.stop()
        assert time.monotonic() - started < 2.0
        poller.join(5)

    def test_the_journal_keeps_the_rows_for_a_restarted_room(self, tmp_path):
        journal = tmp_path / "room.json"
        server = RoomServer("secret", FP, port=0, host="127.0.0.1", journal=journal).start()
        base = f"http://127.0.0.1:{server.port}"
        token = requests.post(base + "/join", json={"name": "A", "password": "secret", "fingerprint": FP}).json()["token"]
        requests.post(base + "/edits", headers={"X-Room-Token": token},
                      json={"edits": [{"key": "k", "text": "Так", "base_rev": 0}]})
        server.stop()
        assert json.loads(journal.read_text(encoding="utf-8"))["rows"]["k"]["text"] == "Так"

        again = RoomServer("secret", FP, port=0, host="127.0.0.1", journal=journal).start()
        try:
            joined = requests.post(f"http://127.0.0.1:{again.port}/join",
                                   json={"name": "B", "password": "secret", "fingerprint": FP}).json()
            assert joined["rows"]["k"]["text"] == "Так" and joined["rows"]["k"]["rev"] == 1
        finally:
            again.stop()
        other = RoomServer("secret", "another project", port=0, host="127.0.0.1", journal=journal)
        assert other.room.rows == {}
        other.httpd.server_close()


# ── two windows in one room ──────────────────────────────────────────

def _project_window(tmp_path, name):
    folder = tmp_path / name
    folder.mkdir()
    mw = _window(folder, [["Hello", "Bye", "Yes"]])
    mw.data_processor = DataStateProcessor(mw)
    mw.active_game_plugin = "plain_text"
    mw.statusBar = None
    mw.collab_handler = CollabHandler(mw)
    return mw


@pytest.fixture
def pair(tmp_path, qtbot):
    a, b = _project_window(tmp_path, "a"), _project_window(tmp_path, "b")
    yield a, b
    for mw in (a, b):
        mw.collab_handler.leave()


def _wait_joined(qtbot, mw):
    qtbot.waitUntil(lambda: mw.collab_handler.state == "connected", timeout=5000)


class TestTwoWindows:
    def test_the_host_shares_its_rows_and_an_edit_in_one_window_appears_in_the_other(self, qtbot, pair):
        a, b = pair
        a.data_processor.update_edited_data(0, 0, "Привіт")             # done before the room exists
        port = a.collab_handler.host(0, "pw", "Host", bind="127.0.0.1")
        _wait_joined(qtbot, a)
        qtbot.waitUntil(lambda: bool(a.collab_handler.row_info), timeout=5000)  # the host's row reached the room
        b.collab_handler.join(f"127.0.0.1:{port}", "pw", "Guest")
        _wait_joined(qtbot, b)
        qtbot.waitUntil(lambda: b.data_processor.get_current_string_text(0, 0)[0] == "Привіт", timeout=5000)
        assert "Joined the room: 1 row(s) taken from it" in b.collab_handler.last_message

        a.undo_manager.record_action.reset_mock()
        b.data_processor.update_edited_data(0, 1, "Бувай")
        qtbot.waitUntil(lambda: a.data_processor.get_current_string_text(0, 1)[0] == "Бувай", timeout=5000)
        assert a.collab_handler.row_info[a.collab_handler._key(0, 1)]["name"] == "Guest"
        a.undo_manager.record_action.assert_not_called()                 # another participant's edit is not undoable here
        qtbot.waitUntil(lambda: len(a.collab_handler.participants) == 2, timeout=5000)

    def test_an_unsaved_local_row_that_differs_from_the_room_becomes_a_conflict(self, qtbot, pair):
        a, b = pair
        a.data_processor.update_edited_data(0, 2, "Так")
        port = a.collab_handler.host(0, "pw", "Host", bind="127.0.0.1")
        _wait_joined(qtbot, a)
        qtbot.waitUntil(lambda: bool(a.collab_handler.row_info), timeout=5000)
        b.data_processor.update_edited_data(0, 2, "Атож")
        b.collab_handler.join(f"127.0.0.1:{port}", "pw", "Guest")
        _wait_joined(qtbot, b)
        key = b.collab_handler._key(0, 2)
        qtbot.waitUntil(lambda: key in b.collab_handler.conflicts, timeout=5000)
        assert b.data_processor.get_current_string_text(0, 2)[0] == "Атож"   # nothing overwritten silently
        assert b.collab_handler.conflicts[key]["text"] == "Так"

        b.collab_handler.keep_mine(key)
        qtbot.waitUntil(lambda: a.data_processor.get_current_string_text(0, 2)[0] == "Атож", timeout=5000)
