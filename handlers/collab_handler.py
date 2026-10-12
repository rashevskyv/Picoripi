"""Working together in a room: host or join, send this participant's edits, apply the others', show who is where.

The host's Picoripi runs ``core/collab/server.py`` and joins it like everyone else
(``127.0.0.1``). Rows are named by the saved-translations key (file, block key,
string index), so every participant must open the same game text; the room checks
that with a fingerprint of the source rows. A local edit reaches the room through
``DataStateProcessor.update_edited_data`` (``on_local_edit``); a remote one is
applied through the same call with ``action_type="COLLAB_REMOTE"``, which is not
sent back and not put on the undo stack.
"""
from __future__ import annotations

import hashlib
import json
import socket
import time
from functools import partial
from pathlib import Path
from collections import deque
from typing import Any, Deque, Dict, Iterator, List, Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QToolButton

import utils.constants as constants
from core.collab.client import RoomClient
from core.collab.server import RoomServer
from core.i18n import tr
from core.progress_stats import _words as source_words
from utils.atomic_io import atomic_write_json
from utils.logging_utils import log_debug, log_warning
from utils.thread_utils import WorkerThread, safe_shutdown_thread, single_shot

SUMMARY_EVERY_MS = 60_000
JOIN_SLICE_ROWS = 200                 # a join turn handles at most this many rows ...
JOIN_CLOCK_EVERY = 8                  # ... reads the clock every this many rows ...
JOIN_SLICE_SECONDS = 0.05             # ... and ends after about this long (one row may exceed it; see docs/DECISIONS.md D21)

REMOTE = "COLLAB_REMOTE"
JOURNAL_NAME = "collab_room.json"
DEFAULT_PORT = 8765


def settings_path() -> Path:
    """Name, port and last address (never the password); read at call time: tests move SETTINGS_DIR."""
    return constants.SETTINGS_DIR / "collab.json"


def load_settings() -> Dict[str, Any]:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(**values: Any) -> None:
    data = {**load_settings(), **values}
    try:
        atomic_write_json(settings_path(), data, ensure_ascii=False, indent=1)
    except OSError as exc:
        log_debug(f"Collab: settings not saved: {exc}")


_LAN_ADDRESSES: List[str] = []


def lan_addresses() -> List[str]:
    """This computer's IPv4 addresses other than loopback (what the others type to join).

    Asked for only when other computers are allowed, and looked up once per process.
    ponytail: a network change after the first lookup shows in the invitation after a restart of Picoripi.
    """
    if not _LAN_ADDRESSES:
        found = set()
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                found.add(info[4][0])
        except OSError:
            pass
        _LAN_ADDRESSES.extend(sorted(a for a in found if not a.startswith("127.")))
    return list(_LAN_ADDRESSES)


class LanLookup(WorkerThread):
    """``lan_addresses()`` off the UI thread: name lookup can wait for DNS. Owns nothing; WorkerThread keeps it alive."""

    found = pyqtSignal(list)

    def run(self) -> None:
        self.found.emit(lan_addresses())


def ensure_collab_handler(main_window: Any) -> "CollabHandler":
    """The window's room handler, made on first use with its status-bar button."""
    handler = getattr(main_window, "collab_handler", None)
    if handler is None:
        handler = CollabHandler(main_window)
        main_window.collab_handler = handler
        bar = getattr(main_window, "statusBar", None)
        if bar is not None and hasattr(bar, "addPermanentWidget"):
            button = QToolButton(main_window)
            button.setAutoRaise(True)
            button.setToolTip(tr('Work together: who is in the room. Click to open the window.'))
            button.clicked.connect(main_window.actions.open_collab)
            bar.addPermanentWidget(button)
            handler.status_button = button
            handler._update_status_button()
    return handler


class CollabHandler(QObject):
    """The room of this window: one at a time."""

    def __init__(self, main_window: Any):
        super().__init__(main_window if isinstance(main_window, QObject) else None)
        self.mw = main_window
        self.server: Optional[RoomServer] = None
        self.client: Optional[RoomClient] = None
        self.state = "off"
        self.participants: List[Dict[str, Any]] = []
        self.row_info: Dict[str, Dict[str, Any]] = {}       # key -> {name, time}: who changed it last
        self.conflicts: Dict[str, Dict[str, Any]] = {}      # key -> theirs + "mine"
        self.positions: Dict[str, Tuple[int, int]] = {}
        self._scan_cache: Optional[Tuple[tuple, Tuple[str, Dict[str, Tuple[int, int]]]]] = None
        self.last_message = ""
        self.status_button: Optional[QToolButton] = None
        self._summary_dirty = False
        self._summary_worker = None
        self._join_plan: Optional[Iterator[None]] = None     # the join's turns (None when no join runs)
        self._join_tick_pending = False
        self._turns: Deque[Iterator[None]] = deque()         # turns in order: the join, then remote batches
        self._remote_pending: Deque[Dict[str, Any]] = deque()  # remote edits not applied yet, oldest first
        self._remote_turn: Optional[Iterator[None]] = None
        self._applied_rev: Dict[str, int] = {}               # per row key: newest revision applied or sent here
        self._generation = 0                                 # counts the rooms: bumped by leave(), see _on_remote_events

    # ── project identity ───────────────────────────────────────────────

    def _key(self, block_idx: int, string_idx: int) -> str:
        return self.mw.saved_translations_manager._get_string_unique_key(block_idx, string_idx)

    def _rows(self):
        data = getattr(self.mw.data_store, "data", None) or []
        for block_idx, block in enumerate(data):
            if isinstance(block, list):
                for string_idx, source in enumerate(block):
                    yield block_idx, string_idx, source

    def _scan(self) -> Tuple[str, Dict[str, Tuple[int, int]]]:
        """The fingerprint and the row positions, from one pass over the rows, cached per project.

        The cache is keyed on the row list, its length and the plugin: source rows do not change while a room runs.
        ponytail: a project reloaded into the same list object keeps the old cache; reload creates a new list.
        """
        store = self.mw.data_store
        plugin = str(getattr(self.mw, "active_game_plugin", ""))
        token = (id(getattr(store, "data", None)), len(getattr(store, "data", None) or []), plugin)
        if self._scan_cache is not None and self._scan_cache[0] == token:
            return self._scan_cache[1]
        digest = hashlib.sha256(str(plugin).encode("utf-8"))
        positions: Dict[str, Tuple[int, int]] = {}
        for block_idx, string_idx, source in self._rows():
            key = self._key(block_idx, string_idx)
            digest.update(f"\x00{key}\x01{source}".encode("utf-8"))
            positions[key] = (block_idx, string_idx)
        result = (digest.hexdigest(), positions)
        self._scan_cache = (token, result)
        return result

    def fingerprint(self) -> str:
        """The plugin and every row's key and source text: two participants on different text are refused."""
        return self._scan()[0]

    def _build_positions(self) -> None:
        self.positions = self._scan()[1]

    # ── start and stop ─────────────────────────────────────────────────

    def project_open(self) -> bool:
        return bool(getattr(self.mw.data_store, "data", None))

    def host(self, port: int, password: str, name: str, bind: Optional[str] = None, lan: bool = False) -> int:
        """Start the room on ``port`` and join it; returns the port (0 picks a free one).

        Only this computer can reach the room unless ``lan`` is true: then every network interface listens.
        ``bind`` overrides that choice (tests pin a loopback address).
        """
        self.leave()
        if bind is None:
            bind = "0.0.0.0" if lan else "127.0.0.1"
        project_dir = getattr(getattr(self.mw, "project_manager", None), "project_dir", None)
        journal = Path(project_dir) / JOURNAL_NAME if project_dir else None
        self.server = RoomServer(password, self.fingerprint(), port=port, host=bind, journal=journal).start()
        save_settings(name=name, port=self.server.port)
        self._connect(f"127.0.0.1:{self.server.port}", name, password)
        return self.server.port

    def join(self, address: str, password: str, name: str) -> None:
        self.leave()
        save_settings(name=name, address=address)
        self._connect(address, name, password)

    def _connect(self, address: str, name: str, password: str) -> None:
        self._build_positions()
        self.row_info, self.conflicts, self.participants = {}, {}, []
        self._applied_rev = {}
        client = RoomClient(address, name, password, self.fingerprint())
        generation = self._generation
        client.joined.connect(partial(self._on_joined, generation=generation))
        client.remote_events.connect(partial(self._on_remote_events, generation=generation))
        client.participants_changed.connect(self._on_participants)
        client.edits_done.connect(self._on_edits_done)
        client.state_changed.connect(self._on_state)
        client.refused.connect(self._on_refused)
        self.client = client
        client.start()

    def leave(self) -> None:
        """Leave the room (and stop it, when this window hosts it); returns within a few seconds."""
        self._generation += 1                              # events still in flight from that room are dropped
        self._join_plan = None
        self._turns.clear()
        self._remote_turn = None
        self._remote_pending.clear()
        client, self.client = self.client, None
        if client is not None:
            client.stop()
            safe_shutdown_thread(client, client, timeout_ms=3000)
        server, self.server = self.server, None
        if server is not None:
            server.stop()
        self.participants, self.conflicts = [], {}
        self._on_state("off")

    @property
    def active(self) -> bool:
        return self.client is not None

    # ── this participant's edits ───────────────────────────────────────

    def on_local_edit(self, block_idx: int, string_idx: int, text: str, action_type: str) -> None:
        """Called by ``update_edited_data`` for every edit; queues it unless it came from the room."""
        if self.client is None or action_type == REMOTE:
            return
        key = self._key(block_idx, string_idx)
        self.conflicts.pop(key, None)
        self.client.queue_edit(key, text or "", words=self._source_words(block_idx, string_idx))
        self._summary_dirty = True

    def _source_words(self, block_idx: int, string_idx: int) -> int:
        try:
            return source_words(self.mw.data_store.data[block_idx][string_idx])
        except (IndexError, TypeError, KeyError):
            return 0

    def on_row_shown(self, block_idx: int, string_idx: int) -> None:
        """The editor shows this row: tell the room where this participant is, refresh the bar above the editor."""
        if self.client is not None and block_idx >= 0 and string_idx >= 0:
            self.client.set_presence(self._key(block_idx, string_idx))
        bar = getattr(self.mw, "collab_row_bar", None)
        if bar is not None:
            bar.refresh(block_idx, string_idx)

    # ── what the room sends ────────────────────────────────────────────

    def _current(self, block_idx: int, string_idx: int) -> str:
        text, _ = self.mw.data_processor.get_current_string_text(block_idx, string_idx)
        return text or ""

    def _apply(self, block_idx: int, string_idx: int, text: str) -> None:
        self.mw.data_processor.update_edited_data(block_idx, string_idx, text, action_type=REMOTE, skip_ui_refresh=True)

    def _refresh(self, blocks) -> None:
        updater = getattr(self.mw, "ui_updater", None)
        if updater is None:
            return
        for block_idx in blocks:
            updater.update_block_item_text_with_problem_count(block_idx)
        store = self.mw.data_store
        if getattr(store, "physical_block_idx", -1) in blocks:
            updater.update_text_views()

    def _on_joined(self, data: Dict[str, Any], generation: Optional[int] = None) -> None:
        """Take the room's rows and share the rows the room lacks, in turns (see ``_join_work``)."""
        if generation is not None and (generation != self._generation or self.client is None):
            return                                         # the rows of a room that was left
        self._join_plan = self._join_work(data)
        self._turns.append(self._join_plan)
        self.participants = data.get("participants") or []
        self._schedule_join_slice()

    def _schedule_join_slice(self) -> None:
        if self._turns and not self._join_tick_pending:
            self._join_tick_pending = True
            single_shot(0, self, self._join_slice)

    def _join_slice(self) -> None:
        """Run the next turn of the queue: one step of the join or of a remote batch."""
        self._join_tick_pending = False
        if not self._turns:
            return                                         # the room was left
        turn = self._turns[0]
        try:
            next(turn)
        except StopIteration:
            self._turns.popleft()
            if turn is self._join_plan:
                self._join_plan = None
        except Exception as exc:                           # a failed turn is dropped, the queue goes on
            log_warning(f"Collab: a room turn failed and was dropped: {exc!r}")
            self._turns.popleft()
            if turn is self._join_plan:
                self._join_plan = None
        self._schedule_join_slice()

    @staticmethod
    def _turn_over(rows_done: int, turn_started: float) -> bool:
        if rows_done >= JOIN_SLICE_ROWS:
            return True
        return rows_done % JOIN_CLOCK_EVERY == 0 and time.perf_counter() - turn_started >= JOIN_SLICE_SECONDS

    def _refresh_turns(self, touched: set) -> Iterator[None]:
        """Refresh the touched blocks' tree items, one block per turn; then the editor, if its block was touched."""
        updater = getattr(self.mw, "ui_updater", None)
        for block_idx in sorted(touched):
            yield                                          # each block's tree refresh is a turn of its own (D21)
            if updater is not None:
                updater.update_block_item_text_with_problem_count(block_idx)
        if updater is not None and getattr(self.mw.data_store, "physical_block_idx", -1) in touched:
            yield                                          # the editor's text views: a turn of their own
            updater.update_text_views()

    def _join_work(self, data: Dict[str, Any]) -> Iterator[None]:
        """The join as a generator: yields when a turn is full (rows or time). Each row is checked when it is reached."""
        taken, shared, budget = 0, 0, 0
        turn_started = time.perf_counter()
        touched: set = set()
        room_rows = data.get("rows") or {}
        for key, row in room_rows.items():
            self.row_info[key] = {"name": row.get("name", ""), "time": row.get("time")}
            self._applied_rev[key] = max(self._applied_rev.get(key, 0), int(row.get("rev", 0) or 0))
            position = self.positions.get(key)
            if position is not None and self._current(*position) != row["text"]:
                if position in self.mw.data_store.edited_data:
                    self.conflicts[key] = {**row, "mine": self._current(*position)}
                else:
                    self._apply(*position, row["text"])
                    taken += 1
                    touched.add(position[0])
            budget += 1
            if self._turn_over(budget, turn_started):
                budget, turn_started = 0, time.perf_counter()
                yield
        for key, (block_idx, string_idx) in list(self.positions.items()):
            if key in room_rows:
                continue
            if self.client is None:
                return
            source = self.mw.data_store.data[block_idx][string_idx]
            text = self._current(block_idx, string_idx)
            if text and text != source:
                self.client.queue_edit(key, text, words=self._source_words(block_idx, string_idx), seed=True)
                shared += 1
            budget += 1
            if self._turn_over(budget, turn_started):
                budget, turn_started = 0, time.perf_counter()
                yield
        yield from self._refresh_turns(touched)
        self.last_message = tr('Joined the room: {taken} row(s) taken from it, {shared} shared, {conflicts} conflict(s).',
                               taken=taken, shared=shared, conflicts=len(self.conflicts))
        self._status(self.last_message)
        self._refresh_bar()
        self._summary_dirty = True
        self._send_summary()

    def _send_summary(self) -> None:
        """Count the project in a worker and give the room the result; again every minute while edits happen."""
        if self.client is None:
            return
        if self._summary_dirty and (self._summary_worker is None or self._summary_worker.isFinished()):
            from handlers.progress_handler import start_progress_worker
            self._summary_dirty = False
            self._summary_worker = start_progress_worker(self.mw, self._on_summary)
        single_shot(SUMMARY_EVERY_MS, self, self._send_summary)

    def _on_summary(self, summary: dict, history: dict) -> None:
        if self.client is not None:
            self.client.set_summary({**summary, "history": history})

    def _on_remote_events(self, events: List[Dict[str, Any]], generation: Optional[int] = None) -> None:
        """Queue the others' edits; they are applied in turns, in arrival order, behind any batch still running.

        ``generation`` is the room the events came from (the client's, when connected). Events from a room that was
        left, or that is not joined, are dropped: nothing from an old room is written into the project.
        """
        if generation is None:
            generation = self._generation
        if self.client is None or generation != self._generation:
            return
        self._remote_pending.extend(event for event in events if event.get("type") == "edit")
        if self._remote_turn is None and self._remote_pending:
            self._start_remote_work()

    def _start_remote_work(self) -> None:
        self._remote_turn = self._remote_work(self._generation)
        self._turns.append(self._remote_turn)
        self._schedule_join_slice()

    def _remote_work(self, generation: int) -> Iterator[None]:
        """Apply the queued remote edits, JOIN_SLICE_ROWS per turn; then refresh the blocks they touched, one per turn.

        One edit that fails does not stop the others: the failure is logged once per batch, with its key. Edits that
        arrive while a turn waits are taken by the outer loop: nothing is dropped, nothing runs twice. The ``finally``
        clears the batch's own marker, and restarts a batch if edits were left behind by an exception.
        """
        try:
            while self._remote_pending and generation == self._generation:
                touched: set = set()
                failed: List[Any] = []
                budget, turn_started = 0, time.perf_counter()
                while self._remote_pending and generation == self._generation:
                    event = self._remote_pending.popleft()
                    try:
                        block_idx = self._apply_remote_edit(event)
                    except Exception as exc:                # one bad edit must not stall the others
                        failed.append((event.get("key"), exc))
                        block_idx = None
                    if block_idx is not None:
                        touched.add(block_idx)
                    budget += 1
                    if self._turn_over(budget, turn_started) and self._remote_pending:
                        budget, turn_started = 0, time.perf_counter()
                        yield
                if failed:
                    log_warning(f"Collab: {len(failed)} remote edit(s) not applied; first: row {failed[0][0]!r}: "
                                f"{failed[0][1]!r}")
                yield from self._refresh_turns(touched)
                self._refresh_bar()
        finally:
            if generation == self._generation:
                self._remote_turn = None
                if self._remote_pending:
                    self._start_remote_work()

    def _apply_remote_edit(self, event: Dict[str, Any]) -> Optional[int]:
        """Apply one remote edit if it is newer than what this participant has; returns the block it changed.

        A row is never written twice with the same revision, and an older revision cannot overwrite a newer one. A row
        with an unsent local edit is left alone: the server decides that conflict.
        """
        if self.client is None:
            return None                                    # not joined: nothing from a room is written
        key = event["key"]
        rev = int(event.get("rev", 0) or 0)
        if rev <= self._applied_rev.get(key, 0):
            return None
        position = self.positions.get(key)
        if position is None:
            return None
        if self.client.has_pending(key):
            return None                                    # our unsent text meets it on the server as a conflict
        self._applied_rev[key] = rev
        self.row_info[key] = {"name": event.get("name", ""), "time": event.get("time")}
        self.conflicts.pop(key, None)
        if self._current(*position) == event["text"]:
            return None
        self._apply(*position, event["text"])
        self._summary_dirty = True
        return position[0]

    def _on_edits_done(self, accepted: Dict[str, int], conflicts: Dict[str, Dict[str, Any]]) -> None:
        name = self.client.name if self.client is not None else ""
        for key, rev in accepted.items():
            self.row_info[key] = {"name": name, "time": time.time()}
            self._applied_rev[key] = max(self._applied_rev.get(key, 0), int(rev or 0))
        if conflicts:
            self.conflicts.update(conflicts)
            self._status(tr('{count} row(s) were changed by someone else first: see the bar above the editor.',
                            count=len(conflicts)))
        self._refresh_bar()

    def _on_participants(self, participants: List[Dict[str, Any]]) -> None:
        if participants != self.participants:
            self.participants = participants
            self._update_status_button()

    def _on_state(self, state: str) -> None:
        self.state = state
        self._update_status_button()

    def _on_refused(self, reason: str) -> None:
        self.last_message = tr('The room refused to let you in: {reason}', reason=reason)
        self._status(self.last_message)
        self.leave()

    # ── conflicts ──────────────────────────────────────────────────────

    def take_theirs(self, key: str) -> None:
        theirs = self.conflicts.pop(key, None)
        position = self.positions.get(key)
        if theirs and position:
            self._apply(*position, theirs.get("text", ""))
            self._refresh({position[0]})
        self._refresh_bar()

    def keep_mine(self, key: str) -> None:
        mine = self.conflicts.pop(key, None)
        position = self.positions.get(key)
        if mine and position and self.client is not None:
            if self._current(*position) != mine["mine"]:
                self._apply(*position, mine["mine"])
                self._refresh({position[0]})
            self.client.queue_edit(key, mine["mine"])
        self._refresh_bar()

    # ── where everybody is ─────────────────────────────────────────────

    def describe(self, key: Optional[str]) -> str:
        """``Block name, line N`` for a row key."""
        position = self.positions.get(key or "")
        if position is None:
            return tr('nowhere yet')
        names = getattr(self.mw.data_store, "block_names", {}) or {}
        return tr('{block}, line {line}', block=names.get(str(position[0]), f"#{position[0]}"), line=position[1] + 1)

    def jump_to(self, key: Optional[str]) -> None:
        position = self.positions.get(key or "")
        undo = getattr(self.mw, "undo_manager", None)
        if position and undo is not None:
            undo._navigate_to(*position)

    def others_on(self, block_idx: int, string_idx: int) -> List[str]:
        key = self._key(block_idx, string_idx)
        me = self.client.participant_id if self.client is not None else None
        return [p["name"] for p in self.participants if p.get("where") == key and p.get("id") != me]

    # ── status ─────────────────────────────────────────────────────────

    def _status(self, message: str) -> None:
        bar = getattr(self.mw, "statusBar", None)
        if bar is not None and hasattr(bar, "showMessage"):
            bar.showMessage(message, 8000)

    def _refresh_bar(self) -> None:
        bar = getattr(self.mw, "collab_row_bar", None)
        store = getattr(self.mw, "data_store", None)
        if bar is not None and store is not None:
            bar.refresh(getattr(store, "physical_block_idx", -1), getattr(store, "current_string_idx", -1))

    def status_text(self) -> str:
        if self.state == "off":
            return tr('Room: off')
        if self.state == "connected":
            return tr('Room: {count} here', count=len(self.participants))
        return tr('Room: connecting…')

    def _update_status_button(self) -> None:
        if self.status_button is not None:
            self.status_button.setText(self.status_text())
