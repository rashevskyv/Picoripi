"""Room server: one participant's Picoripi serves the room the others join (stdlib HTTP, JSON).

The host chooses a port and a password and tells the others the address. Every
participant, the host included, talks to the room through ``core/collab/client.py``.
The room keeps, per row key, the current text, its revision and who wrote it, and
a feed of events (``edit``, ``presence``, ``join``, ``leave``) that clients read by
long-poll. An edit sent against an old revision is refused with the current text,
so nobody overwrites anybody without seeing it. The rows are written to a journal
in the host's project folder, so a restarted room keeps them. The room also counts,
per participant and day, the rows they translated first, the source words of those
rows and their edits, and serves a progress page at ``/stats``
(``core/progress_stats.py``) from those counts and the project summary a client posts. The page needs the room
token in its query (``?token=``).

Server threads never touch Qt or the project data. Plain HTTP: use it on a LAN or
over a VPN; the password is a shared secret, not encryption. The room listens on 127.0.0.1 unless the host
allows other computers (``host="0.0.0.0"``).
"""
from __future__ import annotations

import datetime as _dt
import hmac
import json
import secrets
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from core import progress_stats
from utils.atomic_io import atomic_write_json
from utils.logging_utils import log_debug

PROTOCOL = 1
MAX_BODY = 16 * 1024 * 1024          # a whole project's translations at join
MAX_TEXT = 64 * 1024                  # one row
MAX_NAME = 64
POLL_WAIT = 1.0                       # seconds a poll waits for news
# ponytail: short poll keeps one client thread simple; abort-to-wake if traffic ever matters.
JOURNAL_DELAY = 2.0                   # seconds between journal writes while edits keep coming
PARTICIPANT_TIMEOUT = 30.0            # seconds without a poll before a participant is dropped
EVENT_LIMIT = 5000                    # events kept; a poll further behind gets every row as an edit instead


class Room:
    """The room's state. Every method takes the lock; nothing here knows about HTTP."""

    def __init__(self, password: str, fingerprint: str, journal: Optional[Path] = None):
        self.password = password
        self.fingerprint = fingerprint
        self.journal = journal
        self.rows: Dict[str, Dict[str, Any]] = {}
        self.events: Deque[Dict[str, Any]] = deque(maxlen=EVENT_LIMIT)
        self.participants: Dict[str, Dict[str, Any]] = {}
        self.seq = 0
        self.closed = False
        # {name: {day: {rows, words, edits}}}: what each participant did, for the progress page.
        self.stats: Dict[str, Dict[str, Dict[str, int]]] = {}
        self.summary: Optional[Dict[str, Any]] = None
        self.cond = threading.Condition()
        self._journal_timer: Optional[threading.Timer] = None
        self._load_journal()

    # ── journal ─────────────────────────────────────────────────────────

    def _load_journal(self) -> None:
        if not self.journal or not self.journal.is_file():
            return
        try:
            data = json.loads(self.journal.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log_debug(f"Collab room: journal {self.journal} unreadable: {exc}")
            return
        if isinstance(data, dict) and data.get("fingerprint") == self.fingerprint and isinstance(data.get("rows"), dict):
            self.rows = {k: v for k, v in data["rows"].items() if isinstance(v, dict) and isinstance(v.get("text"), str)}
            if isinstance(data.get("stats"), dict):
                self.stats = data["stats"]

    def _schedule_journal(self) -> None:
        """Write the rows soon; edits that keep coming are written together (called with the lock held)."""
        if not self.journal or self._journal_timer is not None or self.closed:
            return
        timer = threading.Timer(JOURNAL_DELAY, self.write_journal)
        timer.daemon = True
        self._journal_timer = timer
        timer.start()

    def write_journal(self) -> None:
        with self.cond:
            self._journal_timer = None
            if not self.journal:
                return
            snapshot = {"protocol": PROTOCOL, "fingerprint": self.fingerprint, "rows": dict(self.rows),
                        "stats": json.loads(json.dumps(self.stats))}
        try:
            atomic_write_json(self.journal, snapshot, ensure_ascii=False)
        except OSError as exc:
            log_debug(f"Collab room: journal {self.journal} not written: {exc}")

    # ── participants and events ────────────────────────────────────────

    def _event(self, kind: str, **fields: Any) -> None:
        """Append an event and wake the polls (called with the lock held)."""
        self.seq += 1
        self.events.append({"seq": self.seq, "type": kind, "time": time.time(), **fields})
        self.cond.notify_all()

    def _drop_silent(self) -> None:
        now = time.time()
        for pid, who in list(self.participants.items()):
            if now - who["seen"] > PARTICIPANT_TIMEOUT:
                del self.participants[pid]
                self._event("leave", by=pid, name=who["name"])

    def _public(self) -> List[Dict[str, Any]]:
        return [{"id": pid, "name": who["name"], "where": who.get("where")} for pid, who in self.participants.items()]

    def join(self, name: str, password: str, fingerprint: str) -> Dict[str, Any]:
        if not hmac.compare_digest(password.encode("utf-8"), self.password.encode("utf-8")):
            raise PermissionError("wrong password")
        if fingerprint != self.fingerprint:
            raise ValueError("another project: the room works on different game text")
        with self.cond:
            self._drop_silent()
            pid = secrets.token_hex(8)
            token = secrets.token_urlsafe(24)
            self.participants[pid] = {"name": name, "token": token, "seen": time.time(), "where": None}
            self._event("join", by=pid, name=name)
            return {"id": pid, "token": token, "seq": self.seq, "rows": dict(self.rows), "participants": self._public()}

    def who(self, token: str) -> Optional[str]:
        """The participant id of ``token``, or None."""
        with self.cond:                   # request threads share the dict with join, leave and the poll timeout
            for pid, who in self.participants.items():
                if hmac.compare_digest(who["token"].encode("utf-8"), token.encode("utf-8")):
                    return pid
        return None

    def leave(self, pid: str) -> None:
        with self.cond:
            who = self.participants.pop(pid, None)
            if who:
                self._event("leave", by=pid, name=who["name"])

    def presence(self, pid: str, where: Any) -> None:
        with self.cond:
            who = self.participants.get(pid)
            if who is None or who.get("where") == where:
                return
            who["where"] = where
            self._event("presence", by=pid, name=who["name"], where=where)

    def poll(self, pid: str, since: int, wait: float = POLL_WAIT) -> Dict[str, Any]:
        deadline = time.time() + wait
        with self.cond:
            while not self.closed and self.seq <= since and time.time() < deadline:
                self.cond.wait(max(0.0, deadline - time.time()))
            if pid in self.participants:
                self.participants[pid]["seen"] = time.time()
            self._drop_silent()
            return {"seq": self.seq, "events": self._events_since(since), "participants": self._public(),
                    "closed": self.closed}

    def _events_since(self, since: int) -> List[Dict[str, Any]]:
        """The events after ``since``, newest last (called with the lock held).

        A client that fell further behind than the kept events gets every row as an ``edit``: its
        rows then match the room again, and nothing is lost silently.
        """
        oldest = self.events[0]["seq"] if self.events else self.seq + 1
        if oldest > since + 1:
            return [{"seq": self.seq, "type": "edit", "by": row.get("by", ""), "name": row.get("name", ""), "key": key,
                     "text": row["text"], "rev": row.get("rev", 0), "time": row.get("time")}
                    for key, row in self.rows.items()]
        out: List[Dict[str, Any]] = []
        for event in reversed(self.events):                  # newest first: stop at the first one already seen
            if event["seq"] <= since:
                break
            out.append(event)
        out.reverse()
        return out

    def edit(self, pid: str, edits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply edits ``{key, text, base_rev}``; one whose ``base_rev`` is not the row's revision is refused."""
        accepted: Dict[str, int] = {}
        conflicts: Dict[str, Dict[str, Any]] = {}
        with self.cond:
            name = self.participants.get(pid, {}).get("name", "?")
            for edit in edits:
                key, text, base = edit["key"], edit["text"], edit["base_rev"]
                row = self.rows.get(key)
                current = row["rev"] if row else 0
                if base != current:
                    conflicts[key] = dict(row) if row else {"text": "", "rev": 0, "by": "", "name": ""}
                    continue
                if row and row["text"] == text:
                    accepted[key] = current
                    continue
                if not edit.get("seed"):
                    self._count(name, first=not (row and row["text"].strip()), source_words=edit.get("words", 0))
                self.rows[key] = {"text": text, "rev": current + 1, "by": pid, "name": name, "time": time.time()}
                accepted[key] = current + 1
                self._event("edit", by=pid, name=name, key=key, text=text, rev=current + 1)
            if accepted:
                self._schedule_journal()
        return {"accepted": accepted, "conflicts": conflicts}

    def _count(self, name: str, first: bool, source_words: int) -> None:
        """One accepted edit by ``name`` today; a row translated for the first time also counts its source words."""
        day = self.stats.setdefault(name, {}).setdefault(_dt.date.today().isoformat(), {"rows": 0, "words": 0, "edits": 0})
        day["edits"] += 1
        if first:
            day["rows"] += 1
            day["words"] += max(0, int(source_words))

    def set_summary(self, summary: Dict[str, Any]) -> None:
        with self.cond:
            self.summary = summary

    def stats_page(self) -> str:
        with self.cond:
            summary = self.summary or {"project": "", "generated": time.time(), "rows_total": 0, "rows_done": 0,
                                       "words_total": 0, "words_done": 0, "blocks": []}
            board = progress_stats.leaderboard(json.loads(json.dumps(self.stats)))
        return progress_stats.render_html(summary, summary.get("history") or {}, board, refresh_seconds=30)

    def close(self) -> None:
        with self.cond:
            self.closed = True
            timer, self._journal_timer = self._journal_timer, None
            self.cond.notify_all()
        if timer is not None:
            timer.cancel()
        self.write_journal()


def _clean_edits(body: Any) -> List[Dict[str, Any]]:
    """The edits of a request, validated; raises ValueError on anything else."""
    edits = body.get("edits") if isinstance(body, dict) else None
    if not isinstance(edits, list):
        raise ValueError("edits must be a list")
    out = []
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("an edit must be an object")
        key, text, base = edit.get("key"), edit.get("text"), edit.get("base_rev", 0)
        if not isinstance(key, str) or not key or len(key) > 1024:
            raise ValueError("bad key")
        if not isinstance(text, str) or len(text) > MAX_TEXT:
            raise ValueError("bad text")
        if not isinstance(base, int) or isinstance(base, bool) or base < 0:
            raise ValueError("bad base_rev")
        words = edit.get("words", 0)
        if not isinstance(words, int) or isinstance(words, bool) or not 0 <= words <= 100000:
            raise ValueError("bad words")
        out.append({"key": key, "text": text, "base_rev": base, "seed": edit.get("seed") is True, "words": words})
    return out


def _int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("a count must be a non-negative integer")
    return value


def _clean_summary(body: Any) -> Dict[str, Any]:
    """A project summary as ``core.progress_stats.summarize`` makes it, validated; raises ValueError otherwise."""
    if not isinstance(body, dict):
        raise ValueError("summary must be an object")
    out = {field: _int(body.get(field, 0)) for field in ("rows_total", "rows_done", "words_total", "words_done")}
    out["project"] = str(body.get("project") or "")[:200]
    out["generated"] = time.time()
    blocks = body.get("blocks") or []
    if not isinstance(blocks, list) or len(blocks) > 100000:
        raise ValueError("bad blocks")
    out["blocks"] = [{"name": str(b.get("name") or "")[:200], "total": _int(b.get("total", 0)),
                      "done": _int(b.get("done", 0)), "words": _int(b.get("words", 0))}
                     for b in blocks if isinstance(b, dict)]
    history = body.get("history") or {}
    if not isinstance(history, dict) or len(history) > 5000:
        raise ValueError("bad history")
    out["history"] = {str(day)[:10]: {"rows_done": _int(v.get("rows_done", 0)), "words_done": _int(v.get("words_done", 0))}
                      for day, v in history.items() if isinstance(v, dict)}
    return out


class _Handler(BaseHTTPRequestHandler):
    server_version = "PicoripiRoom/1"
    room: Room  # set on the subclass made per server

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - BaseHTTPRequestHandler's name
        pass

    def _send(self, status: int, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except OSError:
            pass

    def _body(self) -> Any:
        length = int(self.headers.get("Content-Length") or 0)
        if length < 0 or length > MAX_BODY:
            raise ValueError("request too large")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _participant(self) -> Optional[str]:
        token = self.headers.get("X-Room-Token") or ""
        pid = self.room.who(token) if token else None
        if pid is None:
            self._send(401, {"error": "not in the room"})
        return pid

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        url = urlparse(self.path)
        if url.path == "/hello":
            self._send(200, {"protocol": PROTOCOL, "app": "picoripi-room"})
            return
        if url.path in ("/stats", "/"):
            # Counts and names only, no text. A browser cannot send the room token as a header, so it comes in the query.
            token = (parse_qs(url.query).get("token") or [""])[0]
            if self.room.who(token) is None:
                self._send(401, {"error": "not in the room"})
                return
            data = self.room.stats_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except OSError:
                pass
            return
        if url.path != "/events":
            self._send(404, {"error": "not found"})
            return
        pid = self._participant()
        if pid is None:
            return
        try:
            since = int((parse_qs(url.query).get("since") or ["0"])[0])
        except ValueError:
            self._send(400, {"error": "bad since"})
            return
        self._send(200, self.room.poll(pid, since))

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        path = urlparse(self.path).path
        try:
            body = self._body()
        except (ValueError, UnicodeDecodeError) as exc:
            self._send(400, {"error": str(exc)})
            return
        if path == "/join":
            name = str(body.get("name") or "").strip()[:MAX_NAME] if isinstance(body, dict) else ""
            if not name:
                self._send(400, {"error": "a name is needed"})
                return
            try:
                self._send(200, self.room.join(name, str(body.get("password") or ""), str(body.get("fingerprint") or "")))
            except PermissionError as exc:
                self._send(401, {"error": str(exc)})
            except ValueError as exc:
                self._send(409, {"error": str(exc)})
            return
        pid = self._participant()
        if pid is None:
            return
        if path == "/edits":
            try:
                edits = _clean_edits(body)
            except ValueError as exc:
                self._send(400, {"error": str(exc)})
                return
            self._send(200, self.room.edit(pid, edits))
        elif path == "/presence":
            where = body.get("where") if isinstance(body, dict) else None
            if where is not None and not (isinstance(where, str) and len(where) <= 1024):
                self._send(400, {"error": "bad where"})
                return
            self.room.presence(pid, where)
            self._send(200, {})
        elif path == "/summary":
            try:
                self.room.set_summary(_clean_summary(body))
            except (ValueError, AttributeError) as exc:
                self._send(400, {"error": str(exc)})
                return
            self._send(200, {})
        elif path == "/leave":
            self.room.leave(pid)
            self._send(200, {})
        else:
            self._send(404, {"error": "not found"})


class RoomServer:
    """The room on ``host:port`` in a daemon thread; ``stop()`` returns within a second."""

    def __init__(self, password: str, fingerprint: str, port: int = 0, host: str = "127.0.0.1",
                 journal: Optional[Path] = None):
        self.room = Room(password, fingerprint, journal)
        handler = type("RoomHandler", (_Handler,), {"room": self.room})
        self.httpd = ThreadingHTTPServer((host, port), handler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.2},
                                       name="collab-room", daemon=True)

    @property
    def port(self) -> int:
        return self.httpd.server_address[1]

    def start(self) -> "RoomServer":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.room.close()                 # wakes every poll first, so shutdown does not wait for one
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
