"""Working together: a real room server on 127.0.0.1 and real clients (no network mocks)."""
import json
import time

import pytest
import requests
from PyQt6.QtCore import QThread

from core.collab.client import RoomClient
from core.collab import server as room_module
from core.collab.server import Room, RoomServer
from core.data_state_processor import DataStateProcessor
from handlers import collab_handler as collab_module
from handlers.collab_handler import JOIN_SLICE_ROWS, CollabHandler
from test_core.test_translation_memory import _window

FP = "fingerprint-1"


@pytest.fixture
def room(tmp_path):
    server = RoomServer("secret", FP, port=0, host="127.0.0.1", journal=tmp_path / "room.json").start()
    yield server
    server.stop()


class FakeRoomClient(QThread):
    """A joined room client without a server: the handler checks ``client is None`` and ``has_pending``."""

    def stop(self) -> None:
        pass

    def set_summary(self, summary: dict) -> None:
        pass

    def has_pending(self, key: str) -> bool:
        return False

    def queue_edit(self, key: str, text: str, words: int = 0, seed: bool = False) -> None:
        pass


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


class TestRoomLimits:
    def test_the_progress_page_needs_the_room_token(self, room):
        base = f"http://127.0.0.1:{room.port}"
        assert requests.get(base + "/stats").status_code == 401
        token = requests.post(base + "/join", json={"name": "A", "password": "secret", "fingerprint": FP}).json()["token"]
        assert requests.get(base + "/stats", params={"token": "wrong"}).status_code == 401
        assert requests.get(base + "/stats", params={"token": "тест"}).status_code == 401    # not a server error
        page = requests.get(base + "/stats", params={"token": token})
        assert page.status_code == 200 and page.headers["Content-Type"].startswith("text/html")

    def test_the_event_list_is_bounded_and_a_poll_that_fell_behind_gets_every_row(self, monkeypatch):
        monkeypatch.setattr(room_module, "EVENT_LIMIT", 5)
        room = Room("secret", FP)
        pid = room.join("A", "secret", FP)["id"]
        before = room.seq
        for i in range(12):
            room.edit(pid, [{"key": f"k{i}", "text": f"t{i}", "base_rev": 0, "seed": False, "words": 0}])
        assert len(room.events) == 5
        recent = room.poll(pid, since=room.seq - 2, wait=0)
        assert [e["key"] for e in recent["events"]] == ["k10", "k11"]
        behind = room.poll(pid, since=before, wait=0)           # the oldest kept event is later than this
        assert all(e["type"] == "edit" for e in behind["events"])
        assert {e["key"]: e["text"] for e in behind["events"]} == {f"k{i}": f"t{i}" for i in range(12)}


class TestJoinInSlices:
    @staticmethod
    def _room_rows(handler, count):
        return {handler._key(0, i): {"text": f"UA {i}", "rev": 1, "name": "Olena", "time": 0.0} for i in range(count)}

    @staticmethod
    def _count_slices(monkeypatch, handler):
        """Records how many rows each UI-thread turn of the join applied."""
        applied, per_turn = {"n": 0}, []
        real_apply, real_turn = handler._apply, handler._join_slice

        def counting_apply(*args):
            applied["n"] += 1
            real_apply(*args)

        def counted_turn():
            start = applied["n"]
            real_turn()
            per_turn.append(applied["n"] - start)

        monkeypatch.setattr(handler, "_apply", counting_apply)
        monkeypatch.setattr(handler, "_join_slice", counted_turn)
        return per_turn

    def test_a_big_join_applies_its_rows_in_turns_of_at_most_a_slice(self, qtbot, tmp_path, monkeypatch):
        mw = _project_window(tmp_path, "slices", lines=[f"Source line {i}" for i in range(5000)])
        handler = mw.collab_handler
        handler._build_positions()
        per_turn = self._count_slices(monkeypatch, handler)
        handler._on_joined({"rows": self._room_rows(handler, 5000), "participants": []})
        assert sum(per_turn) == 0                              # the join itself returns before any row is applied
        qtbot.waitUntil(lambda: handler._join_plan is None, timeout=60000)
        assert sum(per_turn) == 5000
        assert max(per_turn) <= JOIN_SLICE_ROWS and len(per_turn) >= 5000 // JOIN_SLICE_ROWS
        assert handler._current(0, 4999) == "UA 4999"
        assert "Joined the room: 5000 row(s) taken from it" in handler.last_message

    def test_a_remote_edit_during_a_join_is_not_overwritten_by_the_older_room_text(self, qtbot, tmp_path):
        mw = _project_window(tmp_path, "superseded", lines=[f"Source {i}" for i in range(600)])
        handler = mw.collab_handler
        handler._build_positions()
        handler.client = FakeRoomClient()
        handler._on_joined({"rows": self._room_rows(handler, 600), "participants": []})
        handler._on_remote_events([{"type": "edit", "key": handler._key(0, 450), "text": "NEWER", "rev": 2,
                                    "name": "Ihor", "time": 1.0, "by": "someone"}])
        qtbot.waitUntil(lambda: not handler._turns, timeout=60000)   # the remote batch runs after the join
        assert handler._current(0, 450) == "NEWER"
        assert handler._current(0, 10) == "UA 10"

    def test_a_failing_remote_edit_does_not_stall_the_later_ones(self, qtbot, tmp_path, monkeypatch):
        mw = _project_window(tmp_path, "failing", lines=[f"S{i}" for i in range(5)])
        handler = mw.collab_handler
        handler._build_positions()
        handler.client = FakeRoomClient()
        warnings = []
        monkeypatch.setattr(collab_module, "log_warning", warnings.append)
        real_apply_edit = handler._apply_remote_edit
        bad_key = handler._key(0, 1)

        def failing_for_one_row(event):
            if event["key"] == bad_key:
                raise RuntimeError("boom")
            return real_apply_edit(event)

        monkeypatch.setattr(handler, "_apply_remote_edit", failing_for_one_row)
        handler._on_remote_events([{"type": "edit", "key": handler._key(0, i), "text": f"R{i}", "rev": 2,
                                    "name": "A", "time": 1.0} for i in range(5)])
        qtbot.waitUntil(lambda: not handler._turns, timeout=5000)
        assert [handler._current(0, i) for i in (0, 2, 3, 4)] == ["R0", "R2", "R3", "R4"]   # no stall after the failure
        assert handler._current(0, 1) == "S1"                  # the failing row is not written
        assert len(warnings) == 1 and bad_key in warnings[0]   # reported once, with its key
        assert handler._remote_turn is None

    def test_remote_edits_after_leave_or_from_an_old_room_are_not_applied(self, qtbot, tmp_path):
        mw = _project_window(tmp_path, "stale", lines=["S0", "S1"])
        handler = mw.collab_handler
        handler._build_positions()
        handler.client = FakeRoomClient()
        old_room = handler._generation
        handler._on_remote_events([{"type": "edit", "key": handler._key(0, 0), "text": "queued", "rev": 2,
                                    "name": "A", "time": 1.0}])
        handler.leave()                                        # the queued edit is dropped with the room
        assert not handler._remote_pending and not handler._turns
        handler.client = FakeRoomClient()                      # a new room: its own generation
        handler._on_remote_events([{"type": "edit", "key": handler._key(0, 0), "text": "stale", "rev": 3,
                                    "name": "B", "time": 2.0}], generation=old_room)
        handler.client = None
        handler._on_remote_events([{"type": "edit", "key": handler._key(0, 1), "text": "late", "rev": 4,
                                    "name": "B", "time": 3.0}])
        qtbot.waitUntil(lambda: not handler._turns, timeout=5000)
        assert handler._current(0, 0) == "S0" and handler._current(0, 1) == "S1"   # nothing written into the project
        assert not handler._remote_pending

    def test_two_overlapping_remote_batches_are_applied_in_order_and_a_stale_edit_is_not(self, qtbot, tmp_path,
                                                                                          monkeypatch):
        mw = _project_window(tmp_path, "overlap", lines=["Source"])
        handler = mw.collab_handler
        handler._build_positions()
        handler.client = FakeRoomClient()
        key = handler._key(0, 0)
        applied = []
        real_apply = handler._apply

        def recording_apply(*args):
            applied.append(args[2])
            real_apply(*args)

        monkeypatch.setattr(handler, "_apply", recording_apply)
        handler._on_remote_events([{"type": "edit", "key": key, "text": "first", "rev": 2, "name": "A", "time": 1.0}])
        handler._on_remote_events([{"type": "edit", "key": key, "text": "second", "rev": 3, "name": "B", "time": 2.0}])
        handler._on_remote_events([{"type": "edit", "key": key, "text": "stale", "rev": 2, "name": "C", "time": 3.0}])
        qtbot.waitUntil(lambda: not handler._turns, timeout=5000)
        assert applied == ["first", "second"]          # in arrival order; the older revision is never written
        assert handler._current(0, 0) == "second"
        handler._on_remote_events([{"type": "edit", "key": key, "text": "second", "rev": 3, "name": "B", "time": 2.0}])
        qtbot.waitUntil(lambda: not handler._turns, timeout=5000)
        assert applied == ["first", "second"]          # the same revision again is not applied twice

    def test_a_join_touching_100_blocks_refreshes_one_block_per_turn(self, qtbot, tmp_path, monkeypatch):
        class CountingUpdater:
            """Records each block tree refresh; the join calls only these two methods."""

            def __init__(self):
                self.refreshed = []

            def update_block_item_text_with_problem_count(self, block_idx):
                self.refreshed.append(block_idx)

            def update_text_views(self, *args, **kwargs):
                pass

        blocks = [[f"Source {b}-{r}" for r in range(3)] for b in range(100)]
        mw = _project_window(tmp_path, "blocks100", blocks=blocks)
        mw.ui_updater = counting = CountingUpdater()
        handler = mw.collab_handler
        handler._build_positions()
        rows = {handler._key(b, r): {"text": f"UA {b}-{r}", "rev": 1, "name": "Olena", "time": 0.0}
                for b in range(100) for r in range(3)}
        refreshes_per_turn = []
        real_turn = handler._join_slice

        def counted_turn():
            before = len(counting.refreshed)
            real_turn()
            refreshes_per_turn.append(len(counting.refreshed) - before)

        monkeypatch.setattr(handler, "_join_slice", counted_turn)
        handler._on_joined({"rows": rows, "participants": []})
        qtbot.waitUntil(lambda: handler._join_plan is None, timeout=60000)
        assert max(refreshes_per_turn) == 1                    # never more than one block refresh in a turn
        assert sorted(counting.refreshed) == list(range(100))  # every touched block refreshed once
        assert "Joined the room: 300 row(s) taken" in handler.last_message

    def test_leaving_the_room_stops_a_join_in_progress(self, qtbot, tmp_path, monkeypatch):
        mw = _project_window(tmp_path, "cancel", lines=[f"Source {i}" for i in range(2000)])
        handler = mw.collab_handler
        handler._build_positions()
        per_turn = self._count_slices(monkeypatch, handler)
        handler._on_joined({"rows": self._room_rows(handler, 2000), "participants": []})
        handler.leave()
        qtbot.waitUntil(lambda: not handler._join_tick_pending, timeout=5000)
        assert handler._join_plan is None and sum(per_turn) == 0


# ── two windows in one room ──────────────────────────────────────────

def _project_window(tmp_path, name, lines=("Hello", "Bye", "Yes"), blocks=None):
    folder = tmp_path / name
    folder.mkdir()
    mw = _window(folder, blocks if blocks is not None else [list(lines)])
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


# ── where the room listens ───────────────────────────────────────────

class TestWhereTheRoomListens:
    def test_a_room_listens_on_loopback_by_default(self):
        room = RoomServer("secret", FP, port=0)
        try:
            assert room.httpd.server_address[0] == "127.0.0.1"
        finally:
            room.httpd.server_close()

    def test_the_host_listens_on_loopback_until_other_computers_are_allowed(self, qtbot, tmp_path):
        mw = _project_window(tmp_path, "listen")
        try:
            mw.collab_handler.host(0, "pw", "Host")
            assert mw.collab_handler.server.httpd.server_address[0] == "127.0.0.1"
            mw.collab_handler.host(0, "pw", "Host", lan=True)
            assert mw.collab_handler.server.httpd.server_address[0] == "0.0.0.0"
        finally:
            mw.collab_handler.leave()

    def test_the_fingerprint_is_computed_in_one_pass_per_project(self, tmp_path, monkeypatch):
        mw = _project_window(tmp_path, "scan")
        handler = mw.collab_handler
        real_key, calls = handler._key, []

        def counting_key(block_idx, string_idx):
            calls.append((block_idx, string_idx))
            return real_key(block_idx, string_idx)

        monkeypatch.setattr(handler, "_key", counting_key)
        first = handler.fingerprint()
        handler._build_positions()
        assert handler.fingerprint() == first
        assert len(calls) == 3                      # the three rows of the window, one pass in all
        assert set(handler.positions.values()) == {(0, 0), (0, 1), (0, 2)}
