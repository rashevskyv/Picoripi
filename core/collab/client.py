"""Room client: one worker thread that joins a room, sends this participant's operations and reads the others'.

Edits are queued by row key from the UI thread (the latest text of a row wins, so typing does not become one
request per key). Other operations (claims, comments, roles, approvals) are queued with ``queue_op``. The worker
sends them to ``POST /ops`` in batches, each with a sequence number that goes on from the room's high-water mark,
so a batch sent twice (a lost reply) is applied once. The worker keeps the revisions of the rows itself.

The participant token is kept by the caller (the handler saves it) and given back in ``joined``. A kicked or
restarted participant joins again with the same token and gets the same member back.

Everything the UI needs arrives by signal: ``joined``, ``remote_events``, ``edits_done``, ``edits_refused``,
``op_done``, ``participants_changed``, ``state_changed``, ``refused``.
"""
from __future__ import annotations

import threading
import uuid
from typing import Any, Dict, List, Optional

import requests
from PyQt6.QtCore import pyqtSignal

from core.translation.transport import AbortableSession
from utils.logging_utils import log_debug, log_warning
from utils.thread_utils import WorkerThread

REQUEST_TIMEOUT = 10.0        # longer than the server's poll wait
RECONNECT_MS = 2000


class RoomClient(WorkerThread):
    """Joins ``address`` (``host:port``) as ``name`` and keeps the room in step until stopped."""

    joined = pyqtSignal(dict)            # {id, token, role, rows, participants, state, log, ...}
    remote_events = pyqtSignal(list)     # events by the others (and this participant's non-edit events)
    participants_changed = pyqtSignal(list)
    edits_done = pyqtSignal(dict, dict)  # accepted {key: rev}, conflicts {key: {theirs..., "mine": text}}
    edits_refused = pyqtSignal(dict)     # refused {key: {reason, owner, row, "mine": text}}
    op_done = pyqtSignal(str, str, dict)  # op id, kind, the room's answer
    state_changed = pyqtSignal(str)      # "connecting" | "connected" | "reconnecting" | "off"
    refused = pyqtSignal(str)            # wrong password, another project, removed: the worker stops

    def __init__(self, address: str, name: str, password: str, fingerprint: str, token: Optional[str] = None):
        super().__init__()
        address = address.strip()
        self.base_url = address if address.startswith("http") else f"http://{address}"
        self.name, self.password, self.fingerprint = name, password, fingerprint
        self.participant_id: Optional[str] = None
        self.role: Optional[str] = None
        self._token: Optional[str] = token or None
        self._joined = False
        self._room_id: Optional[str] = None
        self._seq = 0                                  # the event cursor
        self._next_seq = 1                             # the next operation's sequence number
        self._revs: Dict[str, int] = {}
        self._lock = threading.Lock()
        self._pending: Dict[str, Dict[str, Any]] = {}  # edits not yet sent, by row key
        self._ops: List[Dict[str, Any]] = []           # other operations not yet sent
        self._in_flight: List[Dict[str, Any]] = []     # sent (or about to be) and not answered: sent again as is
        self._summary: Optional[Dict[str, Any]] = None
        self._presence: Optional[str] = None
        self._presence_sent: Optional[str] = None
        self._session = AbortableSession()

    # ---- from the UI thread -------------------------------------------------------

    def queue_edit(self, key: str, text: str, words: int = 0, seed: bool = False) -> None:
        """Send ``text`` for row ``key``; ``words`` = the row's source words (for the progress page);
        ``seed`` = sharing a translation made before the room (not counted to anyone)."""
        with self._lock:
            previous = self._pending.get(key)
            self._pending[key] = {"text": text, "words": words, "seed": seed and (previous is None or previous["seed"])}

    def queue_op(self, kind: str, **fields: Any) -> str:
        """Send an operation (``claim``, ``comment``, ``role``, ...); returns its id, reported by ``op_done``."""
        op_id = uuid.uuid4().hex
        with self._lock:
            self._ops.append({"op_id": op_id, "kind": kind, **fields})
        return op_id

    def set_summary(self, summary: Dict[str, Any]) -> None:
        """The project's progress summary for the room's progress page; sent with the next round."""
        with self._lock:
            self._summary = summary

    def has_pending(self, key: str) -> bool:
        with self._lock:
            return key in self._pending or any(op.get("key") == key for op in self._in_flight)

    def set_presence(self, where: Optional[str]) -> None:
        with self._lock:
            self._presence = where

    def stop(self) -> None:
        """Ask the worker to leave; closes the request in flight at once."""
        self.requestInterruption()
        self._session.abort()

    # ---- the worker ----------------------------------------------------------------

    @property
    def token(self) -> str:
        """This participant's room token (the progress page takes it in its query; the handler stores it)."""
        return self._token or ""

    def _post(self, path: str, body: Dict[str, Any], timeout: float = REQUEST_TIMEOUT) -> requests.Response:
        headers = {"X-Room-Token": self._token} if self._token else {}
        return self._session.post(self.base_url + path, json=body, headers=headers, timeout=timeout)

    def _join(self) -> bool:
        self.state_changed.emit("connecting" if self.participant_id is None else "reconnecting")
        body: Dict[str, Any] = {"name": self.name, "password": self.password, "fingerprint": self.fingerprint}
        if self._token:
            body["token"] = self._token
        reply = self._post("/join", body)
        if reply.status_code in (401, 409, 400):
            self.refused.emit(str(reply.json().get("error") or reply.status_code))
            return False
        reply.raise_for_status()
        data = reply.json()
        self.participant_id, self._token, self._seq = data["id"], data["token"], data["seq"]
        self.role, self._room_id = data["role"], data["room_id"]
        self._next_seq = max(self._next_seq, int(data.get("op_hw") or 0) + 1)
        self._revs = {key: row.get("rev", 0) for key, row in data["rows"].items()}
        self._presence_sent = None
        self._joined = True
        self.joined.emit(data)
        self.state_changed.emit("connected")
        return True

    def _flush(self) -> None:
        with self._lock:
            if not self._in_flight:                    # new operations wait until the last batch is answered
                pending, self._pending = self._pending, {}
                queued, self._ops = self._ops, []
                batch = [{"op_id": uuid.uuid4().hex, "kind": "edit", "key": key, "text": edit["text"],
                          "base_rev": self._revs.get(key, 0), "words": edit["words"], "seed": edit["seed"]}
                         for key, edit in pending.items()] + queued
                for op in batch:
                    op["seq"] = self._next_seq
                    self._next_seq += 1
                self._in_flight = batch
            batch = list(self._in_flight)
            presence = self._presence
            summary, self._summary = self._summary, None
        if batch:
            reply = self._post("/ops", {"room_id": self._room_id, "ops": batch})
            if reply.status_code == 409:               # the room was started again: nothing of this batch counts
                with self._lock:
                    self._in_flight = []
                self.refused.emit(str(reply.json().get("error") or "another room"))
                self.requestInterruption()
                return
            reply.raise_for_status()
            results = reply.json().get("results") or {}
            with self._lock:
                self._in_flight = []
            self._answer(batch, results)
        if presence != self._presence_sent:
            self._post("/presence", {"where": presence}).raise_for_status()
            self._presence_sent = presence
        if summary is not None:
            self._post("/summary", summary).raise_for_status()

    def _answer(self, batch: List[Dict[str, Any]], results: Dict[str, Dict[str, Any]]) -> None:
        """Apply the room's answers: row revisions, conflicts, refusals, and the other operations' answers."""
        accepted: Dict[str, int] = {}
        conflicts: Dict[str, Dict[str, Any]] = {}
        refused: Dict[str, Dict[str, Any]] = {}
        for op in batch:
            result = results.get(op["op_id"])
            if result is None or "error" in result:
                log_warning(f"RoomClient: operation {op['kind']} not applied: {(result or {}).get('error', 'no answer')}")
                if op["kind"] != "edit":
                    self.op_done.emit(op["op_id"], op["kind"], result or {"error": "no answer"})
                continue
            if op["kind"] != "edit":
                self.op_done.emit(op["op_id"], op["kind"], result)
                continue
            key = op["key"]
            if result.get("ok"):
                self._revs[key] = result["rev"]
                accepted[key] = result["rev"]
            elif "conflict" in result:
                theirs = result["conflict"]
                self._revs[key] = theirs.get("rev", 0)
                conflicts[key] = {**theirs, "mine": op["text"]}
            elif "refused" in result:
                info = result["refused"]
                if isinstance(info.get("row"), dict):
                    self._revs[key] = info["row"].get("rev", self._revs.get(key, 0))
                refused[key] = {**info, "mine": op["text"]}
        if accepted or conflicts:
            self.edits_done.emit(accepted, conflicts)
        if refused:
            self.edits_refused.emit(refused)

    def _poll(self) -> None:
        headers = {"X-Room-Token": self._token or ""}
        reply = self._session.get(f"{self.base_url}/events", params={"since": self._seq}, headers=headers,
                                  timeout=REQUEST_TIMEOUT)
        if reply.status_code == 401:
            self._joined = False                        # dropped (asleep, host restarted): join again, same token
            return
        reply.raise_for_status()
        data = reply.json()
        self._seq = data["seq"]
        others = []
        for event in data["events"]:
            if event["type"] == "edit":
                self._revs[event["key"]] = event["rev"]
                if event.get("by") == self.participant_id:
                    continue                            # our own edit is already in the row
            others.append(event)
        if others:
            self.remote_events.emit(others)
        self.participants_changed.emit(data["participants"])

    def _sleep(self, ms: int) -> None:
        for _ in range(ms // 100):
            if self.isInterruptionRequested():
                return
            self.msleep(100)

    def run(self) -> None:
        try:
            while not self.isInterruptionRequested():
                try:
                    if not self._joined and not self._join():
                        return
                    self._flush()
                    self._poll()
                except (requests.RequestException, ValueError, KeyError) as exc:
                    if self.isInterruptionRequested():
                        break
                    log_debug(f"RoomClient: {exc}")
                    self._joined = False
                    self.state_changed.emit("reconnecting")
                    self._sleep(RECONNECT_MS)
        finally:
            if self._joined and self._token:
                try:
                    fresh = AbortableSession()                 # the main one may be aborted already
                    fresh.post(self.base_url + "/leave", json={}, headers={"X-Room-Token": self._token}, timeout=1)
                except requests.RequestException:
                    pass
