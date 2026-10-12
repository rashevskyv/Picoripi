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
from typing import Any, Deque, Dict, Iterable, Iterator, List, Optional, Set, Tuple

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QToolButton

import utils.constants as constants
from core.collab.client import RoomClient
from core.collab.comments_file import comments_path, merge_comment, read_room_comments, write_comments
from core.collab.roles import HOST, MODERATOR, allowed
from core.collab.server import JOURNAL_NAME, RoomServer
from core.i18n import tr
from core.progress_stats import _words as source_words
from ui.collab_markers import apply_markers, presence_line
from utils.atomic_io import atomic_write_json
from utils.logging_utils import log_debug, log_warning
from utils.thread_utils import WorkerThread, safe_shutdown_thread, single_shot

SUMMARY_EVERY_MS = 60_000
JOIN_SLICE_ROWS = 200                 # a join turn handles at most this many rows ...
JOIN_CLOCK_EVERY = 8                  # ... reads the clock every this many rows ...
JOIN_SLICE_SECONDS = 0.05             # ... and ends after about this long (one row may exceed it; see docs/DECISIONS.md D21)

REMOTE = "COLLAB_REMOTE"
DEFAULT_PORT = 8765
# Room events the window keeps: row edits and the roles, claims, comments and log. Presence and joins go to the list.
ROOM_EVENTS = {"edit", "snapshot", "join", "leave", "approved", "claim_granted", "claim_released", "claim_requested",
               "claim_denied", "role_set", "host_transferred", "kicked", "unbanned", "comment_added", "comment_resolved",
               "comment_deleted", "log"}
LOG_KEEP = 500


def settings_path() -> Path:
    """Name, port, last address, the participant token per name and the rooms the user saved (with their passwords,
    as the AI keys are kept). Read at call time: tests move SETTINGS_DIR."""
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


def saved_token(name: str) -> Optional[str]:
    """This computer's participant token for ``name`` (the room gives the same member back for it)."""
    tokens = load_settings().get("tokens")
    value = tokens.get(name) if isinstance(tokens, dict) else None
    return value if isinstance(value, str) and value else None


def remember_token(name: str, token: Optional[str]) -> None:
    """Keep the token of a new identity; written only when it changes (the join is on the UI thread)."""
    if not token or saved_token(name) == token:
        return
    tokens = dict(load_settings().get("tokens") or {})
    tokens[name] = token
    save_settings(tokens=tokens)


ENDPOINTS_KEY = "endpoints"


def load_endpoints() -> List[Dict[str, str]]:
    """The rooms the user chose to remember: ``[{name, address, password}]``; empty on a fresh profile.

    The password sits in this computer's collab.json in SETTINGS_DIR, next to the AI keys in settings.json. It is never
    written to the project folder, an export or a log, and nothing connects to a saved room by itself.
    """
    raw = load_settings().get(ENDPOINTS_KEY)
    if not isinstance(raw, list):
        return []
    return [{"name": str(e.get("name") or ""), "address": str(e["address"]), "password": str(e.get("password") or "")}
            for e in raw if isinstance(e, dict) and e.get("address")]


def remember_endpoint(name: str, address: str, password: str) -> None:
    endpoints = [e for e in load_endpoints() if e["address"] != address]
    endpoints.append({"name": name, "address": address, "password": password})
    save_settings(**{ENDPOINTS_KEY: endpoints})


def forget_endpoint(address: str) -> None:
    save_settings(**{ENDPOINTS_KEY: [e for e in load_endpoints() if e["address"] != address]})


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


# The events whose markers may sit on any block (claims, comments, joins and leaves, a whole snapshot).
_MARKED_EVENTS = {"snapshot", "join", "leave", "claim_granted", "claim_released", "claim_denied",
                  "comment_added", "comment_resolved", "comment_deleted"}


def _claim_mirror(claim: Dict[str, Any]) -> Dict[str, Any]:
    return {**claim, "keys": set(claim.get("keys") or [])}


def _comment_mirror(comment: Dict[str, Any]) -> Dict[str, Any]:
    keys = comment.get("keys")
    return {**comment, "keys": None if keys is None else set(keys)}


# The room events that change the mirror, and the handler method that applies each one.
_MIRROR = {
    "snapshot": "_mirror_snapshot", "join": "_mirror_join", "leave": "_mirror_leave",
    "approved": "_mirror_approved", "claim_granted": "_mirror_claim_granted",
    "claim_released": "_mirror_claim_released", "claim_requested": "_mirror_claim_requested",
    "claim_denied": "_mirror_claim_denied", "role_set": "_mirror_role_set",
    "host_transferred": "_mirror_host_transferred", "kicked": "_mirror_kicked", "unbanned": "_mirror_unbanned",
    "comment_added": "_mirror_comment_added", "comment_resolved": "_mirror_comment_resolved",
    "comment_deleted": "_mirror_comment_deleted", "log": "_mirror_log",
}


class CommentsFile(WorkerThread):
    """``comments.json`` read or written off the UI thread. ``comments`` None reads it, a list writes it.

    Owns nothing; WorkerThread keeps it alive until it finishes.
    """

    loaded = pyqtSignal(str, list)       # the room that wrote the file, and the comments it holds for this project

    def __init__(self, path: Path, fingerprint: str, room_id: str, comments: Optional[List[Dict[str, Any]]] = None):
        super().__init__()
        self.path, self.fingerprint, self.room_id, self.comments = path, fingerprint, room_id, comments

    def run(self) -> None:
        if self.comments is None:
            room_id, comments = read_room_comments(self.path, self.fingerprint)
            self.loaded.emit(room_id, comments)
            return
        try:
            write_comments(self.path, self.fingerprint, self.room_id, self.comments)
        except OSError as exc:                 # the room keeps working; the file is written at the next change
            log_debug(f"Collab: comments.json not written: {exc}")


def _comment_plain(comment: Dict[str, Any]) -> Dict[str, Any]:
    """A mirror comment as the file and the room send it (keys as a sorted list)."""
    keys = comment.get("keys")
    return {**comment, "keys": None if keys is None else sorted(keys)}


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
        self._block_keys: Dict[int, List[str]] = {}          # block index -> row keys, from _build_positions
        self._presence_since: Dict[str, float] = {}          # participant id -> when its row was last seen to change
        self._io_threads: List[Any] = []                     # comments.json readers and writers still running
        self._comments_writing = False                       # a comments.json write is running
        self._comments_again = False                         # a change came while a write ran: write again after it
        self._room_id = ""                                   # the room's id, from the join (written into the file)
        self._reset_mirror()

    def _reset_mirror(self) -> None:
        """What the room has said about roles, claims, comments and approvals (kept in step by the room's events)."""
        self.role: Optional[str] = None                      # this participant's role in the room
        self.members: Dict[str, Dict[str, Any]] = {}         # {id: {name, role, online, banned}}
        self.claims: Dict[str, Dict[str, Any]] = {}          # {cid: {cid, owner, name, scope, keys: set, online}}
        self.requests: Dict[str, Dict[str, Any]] = {}        # {rid: {rid, requester, name, scope, count}}
        self.comments: Dict[str, Dict[str, Any]] = {}        # {id: {... keys: set or None for the whole project}}
        self.approved: Set[str] = set()                      # row keys the room marked approved
        self.log: List[Dict[str, Any]] = []                  # moderator actions (the host sees them)
        self._room_text: Dict[str, str] = {}                 # the text the room holds per row key

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
        self._block_keys = {}
        for key, (block_idx, _string_idx) in self.positions.items():
            self._block_keys.setdefault(block_idx, []).append(key)

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
        room = self.server.room
        # The host is the member with the creation token. Whoever starts the room takes the host role, unless this
        # computer's saved token already is the room's host (a restart of the same room keeps the same host).
        token = saved_token(name)
        if not (token and room.is_host_token(token)):
            token = room.owner_token_plain or room.issue_owner_token(name)
        save_settings(name=name, port=self.server.port)
        self._connect(f"127.0.0.1:{self.server.port}", name, password, token=token)
        return self.server.port

    def join(self, address: str, password: str, name: str) -> None:
        self.leave()
        save_settings(name=name, address=address)
        self._connect(address, name, password, token=saved_token(name))

    def _connect(self, address: str, name: str, password: str, token: Optional[str] = None) -> None:
        self._build_positions()
        self.row_info, self.conflicts, self.participants = {}, {}, []
        self._applied_rev = {}
        self._reset_mirror()
        client = RoomClient(address, name, password, self.fingerprint(), token=token)
        generation = self._generation
        client.joined.connect(partial(self._on_joined, generation=generation))
        client.remote_events.connect(partial(self._on_remote_events, generation=generation))
        client.participants_changed.connect(self._on_participants)
        client.edits_done.connect(self._on_edits_done)
        client.edits_refused.connect(self._on_edits_refused)
        client.op_done.connect(self._on_op_done)
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
        self._reset_mirror()
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
        if not self.can_edit(key):
            self._refuse_local(block_idx, string_idx, key)
            return
        self.conflicts.pop(key, None)
        self.client.queue_edit(key, text or "", words=self._source_words(block_idx, string_idx))
        self._summary_dirty = True

    def can_edit(self, key: str) -> bool:
        """This participant's role may change text, and the row is not claimed by someone else (the room decides too)."""
        if self.client is None:
            return True
        if self.role is None or not allowed(self.role, "edit"):
            return False
        owner = self.claim_owner(key)
        return owner is None or owner == self._my_id()

    def _refuse_local(self, block_idx: int, string_idx: int, key: str) -> None:
        """A row this participant may not change: the room's text goes back in place, and the reason is shown."""
        room_text = self._room_text.get(key)
        if room_text is not None and self._current(block_idx, string_idx) != room_text:
            self._apply(block_idx, string_idx, room_text)
            self._refresh({block_idx})
        owner = self.claim_owner_name(key)
        self._status(tr('Claimed by {name}: the row stays as the room has it.', name=owner) if owner
                     else tr('Your role cannot change text in this room.'))

    def claim_owner(self, key: str) -> Optional[str]:
        """The member id that owns the most specific claim on ``key``, or None."""
        owner, size = None, None
        for claim in self.claims.values():
            if key in claim["keys"] and (size is None or len(claim["keys"]) < size):
                owner, size = claim["owner"], len(claim["keys"])
        return owner

    def claim_owner_name(self, key: str) -> Optional[str]:
        owner = self.claim_owner(key)
        return self.members.get(owner, {}).get("name") if owner else None

    def row_notes(self, key: str) -> Dict[str, Any]:
        """What the bar above the editor shows about one row: claim, open comments, approval, editability."""
        owner = self.claim_owner(key)
        return {
            "claimed_by": self.claim_owner_name(key),
            "claimed_by_me": owner is not None and owner == self._my_id(),
            "comments_open": sum(1 for c in self.comments.values()
                                 if not c["resolved"] and (c["keys"] is None or key in c["keys"])),
            "approved": key in self.approved,
            "editable": self.can_edit(key),
        }

    def _my_id(self) -> Optional[str]:
        return getattr(self.client, "participant_id", None) if self.client is not None else None

    def _source_words(self, block_idx: int, string_idx: int) -> int:
        try:
            return source_words(self.mw.data_store.data[block_idx][string_idx])
        except (IndexError, TypeError, KeyError):
            return 0

    def on_row_shown(self, block_idx: int, string_idx: int) -> None:
        """The editor shows this row: tell the room where this participant is, refresh the bar above the editor."""
        if self.client is not None and block_idx >= 0 and string_idx >= 0:
            self.client.set_presence(self._key(block_idx, string_idx))
            others = self.others_on(block_idx, string_idx)
            if others:                                    # a soft warning: nothing is locked
                self._status(tr('{names} is working here.', names=", ".join(others)))
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
        if getattr(self.client, "name", None):
            remember_token(self.client.name, data.get("token"))
        self.role = data.get("role")
        self.log = list(data.get("log") or [])
        self._room_id = str(data.get("room_id") or "")
        self._apply_state(data.get("state") or {})
        self._load_comments_file()
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
            self._mark_blocks({block_idx})                 # the room's markers go back on after the text (same turn)
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
            self._room_text[key] = row["text"]
            if row.get("approved"):
                self.approved.add(key)
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
        yield from self._mark_turns(set(self._block_keys))  # the room's markers on every block, one block per turn
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
        self._remote_pending.extend(event for event in events if event.get("type") in ROOM_EVENTS)
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
                        blocks = self._apply_event(event)
                    except Exception as exc:                # one bad event must not stall the others
                        failed.append((event.get("key") or event.get("type"), exc))
                        blocks = None
                    if blocks:
                        touched.update(blocks)
                    budget += 1
                    if self._turn_over(budget, turn_started) and self._remote_pending:
                        budget, turn_started = 0, time.perf_counter()
                        yield
                if failed:
                    log_warning(f"Collab: {len(failed)} room event(s) not applied; first: {failed[0][0]!r}: "
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
        self._room_text[key] = event["text"]
        self.approved.discard(key)
        self.row_info[key] = {"name": event.get("name", ""), "time": event.get("time")}
        self.conflicts.pop(key, None)
        if self._current(*position) == event["text"]:
            return None
        self._apply(*position, event["text"])
        self._summary_dirty = True
        return position[0]

    def _apply_event(self, event: Dict[str, Any]) -> Optional[Set[int]]:
        """Apply one room event; returns the blocks whose tree items it changed (or None).

        A claim, a comment or a join changes markers that may sit on any block, so it returns every block; each
        block's items are then refreshed in a turn of their own.
        """
        if event.get("type") == "edit":
            block_idx = self._apply_remote_edit(event)
            return {block_idx} if block_idx is not None else None
        if self.client is None:
            return None
        kind = event.get("type")
        method = _MIRROR.get(kind)
        if method is None:
            return None
        getattr(self, method)(event)
        return set(self._block_keys) if kind in _MARKED_EVENTS else None

    def _mark_turns(self, blocks: Set[int]) -> Iterator[None]:
        """Put the room's markers on each block's tree items, one block per turn (D21)."""
        for block_idx in sorted(blocks):
            yield
            self._mark_blocks({block_idx})

    def _mark_blocks(self, blocks: Iterable[int]) -> None:
        """Markers on the tree items of ``blocks``: who works there, the claim and the open comments."""
        updater = getattr(self.mw, "ui_updater", None)
        cache = getattr(updater, "_block_items_cache", None)
        if not cache or self.client is None:
            return
        me, now = self._my_id(), time.time()
        for block_idx in blocks:
            items = cache.get(block_idx) or []
            if not items:
                continue
            keys = set(self._block_keys.get(block_idx, ()))
            present = [p for p in self.participants if p.get("where") in keys and p.get("id") != me]
            claimed = [c for c in self.claims.values() if not c["keys"].isdisjoint(keys)]
            claim = claimed[0] if claimed else None
            comments = sum(1 for c in self.comments.values()
                           if not c["resolved"] and (c["keys"] is None or not c["keys"].isdisjoint(keys)))
            tooltip = []
            for person in present:
                minutes = int((now - self._presence_since.get(person["id"], now)) // 60)
                tooltip.append(presence_line(person["name"], minutes))
            if claim is not None:
                tooltip.append(tr('Claimed by {name}', name=claim["name"]) + ("" if claim.get("online") else tr(' (offline)')))
            if comments:
                tooltip.append(tr('{count} open comment(s)', count=comments))
            for item in items:
                apply_markers(item, present[0]["name"] if present else None, len(present) - 1,
                              claim["name"] if claim is not None else None,
                              claim is not None and not claim.get("online"), comments, "\n".join(tooltip))

    def _apply_state(self, state: Dict[str, Any]) -> None:
        """Replace the mirror of members, claims, requests and comments with what the room sent (join, snapshot)."""
        self.members = {m["id"]: {"name": m["name"], "role": m["role"], "online": m["online"], "banned": m["banned"]}
                        for m in state.get("members") or []}
        self.claims = {c["cid"]: _claim_mirror(c) for c in state.get("claims") or []}
        self.requests = {r["rid"]: dict(r) for r in state.get("requests") or []}
        self.comments = {c["id"]: _comment_mirror(c) for c in state.get("comments") or []}
        if self._my_id() in self.members:
            self.role = self.members[self._my_id()]["role"]

    def _mirror_snapshot(self, event: Dict[str, Any]) -> None:
        self._apply_state(event.get("state") or {})

    def _mirror_join(self, event: Dict[str, Any]) -> None:
        member = self.members.setdefault(event["by"], {"name": "?", "role": None, "banned": False})
        member.update(name=event.get("name", member["name"]), online=True)
        if event.get("role"):
            member["role"] = event["role"]

    def _mirror_leave(self, event: Dict[str, Any]) -> None:
        if event.get("by") in self.members:
            self.members[event["by"]]["online"] = False

    def _mirror_approved(self, event: Dict[str, Any]) -> None:
        (self.approved.add if event.get("approved") else self.approved.discard)(event["key"])

    def _mirror_claim_granted(self, event: Dict[str, Any]) -> None:
        claim = event["claim"]
        self.claims[claim["cid"]] = _claim_mirror(claim)
        if event.get("rid"):
            self.requests.pop(event["rid"], None)

    def _mirror_claim_released(self, event: Dict[str, Any]) -> None:
        self.claims.pop(event.get("cid"), None)

    def _mirror_claim_requested(self, event: Dict[str, Any]) -> None:
        request = event["request"]
        self.requests[request["rid"]] = dict(request)

    def _mirror_claim_denied(self, event: Dict[str, Any]) -> None:
        self.requests.pop(event.get("rid"), None)

    def _mirror_role_set(self, event: Dict[str, Any]) -> None:
        member = self.members.setdefault(event["member"], {"name": "?", "online": False, "banned": False})
        member["role"] = event["role"]
        if event["member"] == self._my_id():
            self.role = event["role"]

    def _mirror_host_transferred(self, event: Dict[str, Any]) -> None:
        new, old = event["to"], event["by"]
        for mid, role in ((new, HOST), (old, MODERATOR)):
            if mid in self.members:
                self.members[mid]["role"] = role
        if self._my_id() == new:
            self.role = HOST
        elif self._my_id() == old:
            self.role = MODERATOR

    def _mirror_kicked(self, event: Dict[str, Any]) -> None:
        if event.get("member") in self.members:
            self.members[event["member"]]["banned"] = True

    def _mirror_unbanned(self, event: Dict[str, Any]) -> None:
        if event.get("member") in self.members:
            self.members[event["member"]]["banned"] = False

    def _mirror_comment_added(self, event: Dict[str, Any]) -> None:
        comment = event["comment"]
        self.comments[comment["id"]] = _comment_mirror(comment)
        self._save_comments()

    def _mirror_comment_resolved(self, event: Dict[str, Any]) -> None:
        comment = self.comments.get(event.get("id"))
        if comment is not None:
            comment["resolved"] = ({"by": event.get("by"), "name": event.get("name"), "time": event.get("time")}
                                   if event.get("resolved") else None)
            self._save_comments()

    def _mirror_comment_deleted(self, event: Dict[str, Any]) -> None:
        if self.comments.pop(event.get("id"), None) is not None:
            self._save_comments()

    # ---- comments.json in the project folder (read and written off the UI thread) -----------------

    def _project_dir(self) -> Optional[Path]:
        project_dir = getattr(getattr(self.mw, "project_manager", None), "project_dir", None)
        return Path(project_dir) if project_dir else None

    def _load_comments_file(self) -> None:
        """Read the project's comments.json; what it holds is merged in when the worker reports (see below)."""
        folder = self._project_dir()
        if folder is None or self.client is None:
            return
        worker = CommentsFile(comments_path(folder), self.fingerprint(), self._room_id)
        worker.loaded.connect(self._on_comments_loaded)
        self._start_io(worker)

    def _on_comments_loaded(self, room_id: str, comments: List[Dict[str, Any]]) -> None:
        """Add the comments the file has and the window lacks; a resolution the file has later than the window's wins.

        A file written by this same room is not merged: the room is the authority for it (a comment the room deleted
        stays deleted). A file of another room (another host, or the project before a new room) is merged by id.
        """
        if self.client is None or not room_id or room_id == self._room_id:
            return
        changed = False
        for comment in comments:
            local = self.comments.get(comment["id"])
            if local is None:
                self.comments[comment["id"]] = _comment_mirror(comment)
                changed = True
            elif merge_comment(local, _comment_mirror(comment)):
                changed = True
        if changed:
            self._save_comments()

    def _save_comments(self) -> None:
        """Write the window's comments to the project's comments.json, one write at a time, in a worker."""
        folder = self._project_dir()
        if folder is None or self.client is None:
            return
        if self._comments_writing:
            self._comments_again = True                    # the newest state is written after the running write
            return
        self._comments_writing = True
        snapshot = [_comment_plain(c) for c in self.comments.values()]
        worker = CommentsFile(comments_path(folder), self.fingerprint(), self._room_id, snapshot)
        self._start_io(worker)

    def _start_io(self, worker: "CommentsFile") -> None:
        self._io_threads.append(worker)
        worker.finished.connect(partial(self._io_done, worker))
        worker.start()

    def _io_done(self, worker: "CommentsFile") -> None:
        if worker in self._io_threads:
            self._io_threads.remove(worker)
        if worker.comments is not None:                    # a write finished
            self._comments_writing = False
            if self._comments_again:
                self._comments_again = False
                self._save_comments()

    def _mirror_log(self, event: Dict[str, Any]) -> None:
        self.log.append(event["entry"])
        del self.log[:-LOG_KEEP]

    # ---- what this participant asks the room to do -------------------------------

    def _ask(self, kind: str, **fields: Any) -> Optional[str]:
        """Queue one operation for the room; its answer comes by ``op_done``. None when not in a room."""
        return self.client.queue_op(kind, **fields) if self.client is not None else None

    def keys_of_block(self, block_idx: int) -> List[str]:
        return list(self._block_keys.get(block_idx, []))

    def claim_id_of(self, key: str) -> Optional[str]:
        """The claim that covers ``key`` most specifically, or None (the claim the owner releases)."""
        best, size = None, None
        for cid, claim in self.claims.items():
            if key in claim["keys"] and (size is None or len(claim["keys"]) < size):
                best, size = cid, len(claim["keys"])
        return best

    def release_mine_in(self, keys: Set[str]) -> int:
        """Release this participant's claims that cover any of ``keys``; returns how many were released."""
        me = self._my_id()
        cids = [cid for cid, claim in self.claims.items() if claim["owner"] == me and not claim["keys"].isdisjoint(keys)]
        for cid in cids:
            self.release(cid)
        return len(cids)

    def resolve_open_in(self, keys: Set[str]) -> int:
        """Resolve the open comments whose scope covers any of ``keys``; returns how many."""
        cids = [cid for cid, c in self.comments.items()
                if not c["resolved"] and (c["keys"] is None or not c["keys"].isdisjoint(keys))]
        for cid in cids:
            self.resolve_comment(cid, True)
        return len(cids)

    def all_keys(self) -> List[str]:
        return list(self.positions)

    def claim(self, kind: str, label: str, keys: List[str]) -> Optional[str]:
        return self._ask("claim", scope={"kind": kind, "label": label}, keys=list(keys))

    def assign(self, target: str, kind: str, label: str, keys: List[str]) -> Optional[str]:
        return self._ask("assign", target=target, scope={"kind": kind, "label": label}, keys=list(keys))

    def release(self, cid: str) -> Optional[str]:
        return self._ask("release", cid=cid)

    def cancel_request(self, rid: str) -> Optional[str]:
        return self._ask("release", rid=rid)

    def decide(self, rid: str, approve: bool) -> Optional[str]:
        return self._ask("decide", rid=rid, approve=approve)

    def set_role(self, target: str, role: str) -> Optional[str]:
        return self._ask("role", target=target, role=role)

    def kick(self, target: str) -> Optional[str]:
        return self._ask("kick", target=target)

    def unban(self, target: str) -> Optional[str]:
        return self._ask("unban", target=target)

    def transfer_host(self, target: str) -> Optional[str]:
        return self._ask("transfer_host", target=target, confirm=True)

    def comment(self, kind: str, label: str, keys: List[str], text: str) -> Optional[str]:
        return self._ask("comment", scope={"kind": kind, "label": label},
                         keys=None if kind == "project" else list(keys), text=text)

    def resolve_comment(self, cid: str, resolved: bool) -> Optional[str]:
        return self._ask("comment_resolve", id=cid, resolved=resolved)

    def delete_comment(self, cid: str) -> Optional[str]:
        return self._ask("comment_delete", id=cid)

    def approve_row(self, key: str, approved: bool = True) -> Optional[str]:
        return self._ask("approve", key=key, approved=approved)

    def _on_op_done(self, op_id: str, kind: str, result: Dict[str, Any]) -> None:
        if "error" in result:
            message = tr('Not done: {reason}', reason=tr(str(result["error"])))
        elif result.get("refused"):
            message = tr('Your role does not allow this.')
        elif "requested" in result:
            message = tr('Request sent: the host or a moderator decides.')
        elif "granted" in result:
            message = tr('Claim granted.')
        else:
            message = tr('Done.')
        self.last_message = message
        self._status(message)
        self._refresh_bar()

    def _on_edits_refused(self, refused: Dict[str, Dict[str, Any]]) -> None:
        """The room refused some edits (a claim by someone else, or the role): the room's text goes back in place."""
        for key, info in refused.items():
            row = info.get("row") or {}
            room_text = row.get("text")
            if room_text is None or not row.get("rev"):   # a row the room does not hold keeps its local text
                continue
            self._room_text[key] = room_text
            position = self.positions.get(key)
            if position is not None and self._current(*position) != room_text:
                self._apply(*position, room_text)
                self._refresh({position[0]})
        if len(refused) == 1:
            key, info = next(iter(refused.items()))
            message = (tr('Claimed by {name}: your text was not sent.', name=info.get("owner") or "?")
                       if info.get("reason") == "claimed"
                       else tr('Your role cannot change text in this room.'))
        else:
            message = tr('{count} row(s) were not sent: your role or a claim does not allow it.', count=len(refused))
        self._status(message)
        self._refresh_bar()

    def _on_edits_done(self, accepted: Dict[str, int], conflicts: Dict[str, Dict[str, Any]]) -> None:
        name = self.client.name if self.client is not None else ""
        for key, rev in accepted.items():
            self.row_info[key] = {"name": name, "time": time.time()}
            self._applied_rev[key] = max(self._applied_rev.get(key, 0), int(rev or 0))
            position = self.positions.get(key)
            if position is not None:
                self._room_text[key] = self._current(*position)
        for key, theirs in conflicts.items():
            self._room_text[key] = theirs.get("text", "")
        if conflicts:
            self.conflicts.update(conflicts)
            self._status(tr('{count} row(s) were changed by someone else first: see the bar above the editor.',
                            count=len(conflicts)))
        self._refresh_bar()

    def _on_participants(self, participants: List[Dict[str, Any]]) -> None:
        if participants != self.participants:
            before = {p.get("id"): p.get("where") for p in self.participants}
            now, moved = time.time(), set()
            for person in participants:
                where = person.get("where")
                if before.get(person.get("id")) != where:           # moved, arrived or left a row: its blocks change
                    self._presence_since[person.get("id")] = now
                    for key in (before.get(person.get("id")), where):
                        position = self.positions.get(key) if key else None
                        if position is not None:
                            moved.add(position[0])
            present = {p.get("id") for p in participants}
            for pid, where in before.items():                        # left: the block it stood on changes too
                position = self.positions.get(where) if where and pid not in present else None
                if position is not None:
                    moved.add(position[0])
            self.participants = participants
            self._update_status_button()
            self._mark_blocks(moved)

    def _on_state(self, state: str) -> None:
        self.state = state
        self._update_status_button()

    def _on_refused(self, reason: str) -> None:
        # The room sends English on the wire; the window shows the translation of that text when there is one.
        self.last_message = tr('The room refused to let you in: {reason}', reason=tr(reason))
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
        me = self._my_id()
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
