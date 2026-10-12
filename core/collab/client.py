"""Room client: one worker thread that joins a room, sends this participant's edits and reads the others'.

Edits are queued by row key from the UI thread (the latest text of a row wins, so
typing does not become one request per key) and sent with the revision the client
last saw for that row. The worker keeps those revisions itself. Everything the UI
needs arrives by signal: ``joined``, ``remote_events``, ``edits_done``,
``state_changed``, ``refused``.
"""
from __future__ import annotations

import threading
from typing import Any, Dict, Optional

import requests
from PyQt6.QtCore import pyqtSignal

from core.translation.transport import AbortableSession
from utils.logging_utils import log_debug
from utils.thread_utils import WorkerThread

REQUEST_TIMEOUT = 10.0        # longer than the server's poll wait
RECONNECT_MS = 2000


class RoomClient(WorkerThread):
    """Joins ``address`` (``host:port``) as ``name`` and keeps the room in step until stopped."""

    joined = pyqtSignal(dict)            # {id, rows, participants}
    remote_events = pyqtSignal(list)     # events by the others
    participants_changed = pyqtSignal(list)
    edits_done = pyqtSignal(dict, dict)  # accepted {key: rev}, conflicts {key: {theirs..., "mine": text}}
    state_changed = pyqtSignal(str)      # "connecting" | "connected" | "reconnecting"
    refused = pyqtSignal(str)            # wrong password, another project: the worker stops

    def __init__(self, address: str, name: str, password: str, fingerprint: str):
        super().__init__()
        address = address.strip()
        self.base_url = address if address.startswith("http") else f"http://{address}"
        self.name, self.password, self.fingerprint = name, password, fingerprint
        self.participant_id: Optional[str] = None
        self._token: Optional[str] = None
        self._seq = 0
        self._revs: Dict[str, int] = {}
        self._lock = threading.Lock()
        self._pending: Dict[str, Dict[str, Any]] = {}
        self._summary: Optional[Dict[str, Any]] = None
        self._presence: Optional[str] = None
        self._presence_sent: Optional[str] = None
        self._session = AbortableSession()

    # ── from the UI thread ─────────────────────────────────────────────

    def queue_edit(self, key: str, text: str, words: int = 0, seed: bool = False) -> None:
        """Send ``text`` for row ``key``; ``words`` = the row's source words (for the progress page);
        ``seed`` = sharing a translation made before the room (not counted to anyone)."""
        with self._lock:
            previous = self._pending.get(key)
            self._pending[key] = {"text": text, "words": words, "seed": seed and (previous is None or previous["seed"])}

    def set_summary(self, summary: Dict[str, Any]) -> None:
        """The project's progress summary for the room's progress page; sent with the next round."""
        with self._lock:
            self._summary = summary

    def has_pending(self, key: str) -> bool:
        with self._lock:
            return key in self._pending

    def set_presence(self, where: Optional[str]) -> None:
        with self._lock:
            self._presence = where

    def stop(self) -> None:
        """Ask the worker to leave; closes the request in flight at once."""
        self.requestInterruption()
        self._session.abort()

    # ── the worker ─────────────────────────────────────────────────────

    def _post(self, path: str, body: Dict[str, Any], timeout: float = REQUEST_TIMEOUT) -> requests.Response:
        headers = {"X-Room-Token": self._token} if self._token else {}
        return self._session.post(self.base_url + path, json=body, headers=headers, timeout=timeout)

    def _join(self) -> bool:
        self.state_changed.emit("connecting" if self.participant_id is None else "reconnecting")
        reply = self._post("/join", {"name": self.name, "password": self.password, "fingerprint": self.fingerprint})
        if reply.status_code in (401, 409, 400):
            self.refused.emit(str(reply.json().get("error") or reply.status_code))
            return False
        reply.raise_for_status()
        data = reply.json()
        self.participant_id, self._token, self._seq = data["id"], data["token"], data["seq"]
        self._revs = {key: row.get("rev", 0) for key, row in data["rows"].items()}
        self._presence_sent = None
        self.joined.emit(data)
        self.state_changed.emit("connected")
        return True

    def _flush(self) -> None:
        with self._lock:
            pending, self._pending = self._pending, {}
            presence = self._presence
            summary, self._summary = self._summary, None
        if pending:
            edits = [{"key": k, "text": e["text"], "base_rev": self._revs.get(k, 0), "words": e["words"], "seed": e["seed"]}
                     for k, e in pending.items()]
            try:
                reply = self._post("/edits", {"edits": edits})
                reply.raise_for_status()
            except Exception:
                with self._lock:                       # keep them for the next try; newer typing wins
                    for key, edit in pending.items():
                        self._pending.setdefault(key, edit)
                raise
            result = reply.json()
            self._revs.update(result.get("accepted") or {})
            conflicts = {}
            for key, theirs in (result.get("conflicts") or {}).items():
                self._revs[key] = theirs.get("rev", 0)
                conflicts[key] = {**theirs, "mine": pending[key]["text"]}
            self.edits_done.emit(result.get("accepted") or {}, conflicts)
        if presence != self._presence_sent:
            self._post("/presence", {"where": presence}).raise_for_status()
            self._presence_sent = presence
        if summary is not None:
            self._post("/summary", summary).raise_for_status()

    def _poll(self) -> None:
        headers = {"X-Room-Token": self._token or ""}
        reply = self._session.get(f"{self.base_url}/events", params={"since": self._seq}, headers=headers,
                                  timeout=REQUEST_TIMEOUT)
        if reply.status_code == 401:
            self._token = None                          # dropped (asleep, host restarted): join again
            return
        reply.raise_for_status()
        data = reply.json()
        self._seq = data["seq"]
        others = []
        for event in data["events"]:
            if event["type"] == "edit":
                self._revs[event["key"]] = event["rev"]
            if event.get("by") != self.participant_id:
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
                    if self._token is None and not self._join():
                        return
                    self._flush()
                    self._poll()
                except (requests.RequestException, ValueError, KeyError) as exc:
                    if self.isInterruptionRequested():
                        break
                    log_debug(f"RoomClient: {exc}")
                    self._token = None
                    self.state_changed.emit("reconnecting")
                    self._sleep(RECONNECT_MS)
        finally:
            if self._token:
                try:
                    fresh = AbortableSession()                 # the main one may be aborted already
                    fresh.post(self.base_url + "/leave", json={}, headers={"X-Room-Token": self._token}, timeout=1)
                except requests.RequestException:
                    pass
