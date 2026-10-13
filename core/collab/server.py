"""Room server: a stdlib HTTP room that holds a project's shared translations, roles, claims and comments (JSON).

The room runs in one participant's Picoripi (``RoomServer`` inside the app) or on any computer without a window
(``python -m core.collab.server --headless ...``). Every participant talks to the room through
``core/collab/client.py``. The host is a role bound to a token, not to a computer: the first joiner that presents the
room's creation token becomes the host, and the host can transfer the role.

State changes are operations. Every change from a participant (an edit, a claim, a comment, a role, an approval)
goes through ``Room._apply_op``. An operation may carry ``seq``, the participant's sequence number: an operation
whose ``seq`` is not above the participant's high-water mark is a duplicate and changes nothing. Old clients
(``POST /edits``) send edits without ``seq``.

The room keeps the rows (text, revision, who, approval), the events (``seq``-numbered, read by long-poll on
``GET /events`` or ``GET /ops``), the members, the claims, the claim requests, the comments and a log of moderator
actions. The room journal (``collab_room.json``) and ``comments.json`` are written next to each other in the
project folder, atomically, a moment after a change. A journal from an earlier protocol still loads.

Permissions are one table, ``core/collab/roles.py``; the server asks it before every operation.

Server threads never touch Qt or the project data. Plain HTTP: use it on a LAN or over a VPN; the password is a
shared secret, not encryption. Tokens are stored as SHA-256 hashes. The room listens on 127.0.0.1 unless the host
allows other computers (``host="0.0.0.0"``).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import hmac
import json
import secrets
import sys
import threading
import time
from collections import OrderedDict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlparse

from core import progress_stats
from core.collab.roles import CLAIM_OWNERS, HOST, MODERATOR, TRANSLATOR, allowed
from utils.atomic_io import atomic_write_json
from utils.logging_utils import log_debug

PROTOCOL = 2
JOURNAL_NAME = "collab_room.json"    # in the project folder
COMMENTS_NAME = "comments.json"      # in the project folder, next to the journal
MAX_BODY = 16 * 1024 * 1024          # a whole project's translations at join
MAX_TEXT = 64 * 1024                  # one row
MAX_COMMENT = 4000
MAX_NAME = 64
MAX_OPS = 500                         # operations in one POST /ops
MAX_KEYS = 100_000                    # row keys in one scope (a claim, a comment)
POLL_WAIT = 1.0                       # seconds a poll waits for news
# ponytail: short poll keeps one client thread simple; abort-to-wake if traffic ever matters.
JOURNAL_DELAY = 2.0                   # seconds between journal writes while changes keep coming
PARTICIPANT_TIMEOUT = 30.0            # seconds without a poll before a participant is dropped
EVENT_LIMIT = 5000                    # events kept; a poll further behind gets a snapshot instead
LOG_LIMIT = 500                       # moderator actions kept
SEEN_OPS = 20_000                     # operations without seq remembered for dedupe; a restart forgets them
SCOPE_KINDS = ("project", "folder", "file", "block", "row", "virtual")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Room:
    """The room's state. Every public method takes the lock; nothing here knows about HTTP."""

    def __init__(self, password: str, fingerprint: Optional[str], journal: Optional[Path] = None,
                 owner_token: Optional[str] = None, owner_name: Optional[str] = None):
        self.password = password
        self.fingerprint = fingerprint          # None: a headless room with no journal waits for its host
        self.journal = journal
        self.room_id = secrets.token_hex(8)
        self.rows: Dict[str, Dict[str, Any]] = {}
        self.events: Deque[Dict[str, Any]] = deque(maxlen=EVENT_LIMIT)
        self.participants: Dict[str, Dict[str, Any]] = {}   # online sessions by member id
        self.members: Dict[str, Dict[str, Any]] = {}        # {id: {name, role, token_hash, banned, op_hw}}
        self.token_index: Dict[str, str] = {}               # token hash -> member id
        self.owner_hash: Optional[str] = None               # the creation token, until its first joiner takes it
        self.owner_name: Optional[str] = None
        self.owner_token_plain: Optional[str] = None        # kept in memory only, for the process that made it
        self.claims: Dict[str, Dict[str, Any]] = {}         # {cid: {cid, owner, scope, keys: set, order}}
        self.row_claim: Dict[str, str] = {}                 # row key -> cid of its most specific claim
        self.requests: Dict[str, Dict[str, Any]] = {}       # {rid: {rid, requester, scope, keys: set, time}}
        self.comments: Dict[str, Dict[str, Any]] = {}       # {id: {... keys: set or None for the project}}
        self.log: Deque[Dict[str, Any]] = deque(maxlen=LOG_LIMIT)
        self.seq = 0
        self._claim_order = 0
        self._seen_ops: "OrderedDict[Tuple[str, str], bool]" = OrderedDict()   # (member id, op_id) without seq
        self.closed = False
        # {name: {day: {rows, words, edits}}}: what each participant did, for the progress page.
        self.stats: Dict[str, Dict[str, Dict[str, int]]] = {}
        self.summary: Optional[Dict[str, Any]] = None
        self.cond = threading.Condition()
        self._journal_timer: Optional[threading.Timer] = None
        self._load_journal()
        if owner_token:
            self.set_owner_token(owner_token, owner_name)
        elif not self._has_host():
            self.issue_owner_token(owner_name)

    # ---- the creation token -------------------------------------------------

    def issue_owner_token(self, name: Optional[str] = None) -> str:
        """A new creation token: its first joiner becomes the host, and the previous host becomes a moderator."""
        return self.set_owner_token(secrets.token_urlsafe(24), name)

    def set_owner_token(self, token: str, name: Optional[str] = None) -> str:
        with self.cond:
            self.owner_hash = _hash(token)
            self.owner_token_plain = token
            self.owner_name = name or None
        return token

    def has_host(self) -> bool:
        with self.cond:
            return self._has_host()

    def is_host_token(self, token: str) -> bool:
        """True when ``token`` belongs to the member that is the host now."""
        with self.cond:
            mid = self.token_index.get(_hash(token))
            return mid is not None and self.members[mid]["role"] == HOST

    def _has_host(self) -> bool:
        return any(m["role"] == HOST for m in self.members.values())

    # ---- journal ----------------------------------------------------------------

    def _load_journal(self) -> None:
        if not self.journal or not self.journal.is_file():
            return
        try:
            data = json.loads(self.journal.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log_debug(f"Collab room: journal {self.journal} unreadable: {exc}")
            return
        if not isinstance(data, dict):
            return
        if self.fingerprint is None:
            self.fingerprint = data.get("fingerprint")
        if data.get("fingerprint") != self.fingerprint or not isinstance(data.get("rows"), dict):
            return
        self.rows = {k: v for k, v in data["rows"].items() if isinstance(v, dict) and isinstance(v.get("text"), str)}
        if isinstance(data.get("stats"), dict):
            self.stats = data["stats"]
        self.room_id = str(data.get("room_id") or self.room_id)
        self.seq = int(data.get("seq") or 0)
        for mid, member in (data.get("members") or {}).items():
            if isinstance(member, dict) and member.get("role") in ("host", "moderator", "reviewer", "translator", "observer"):
                self.members[mid] = {"name": str(member.get("name") or "?"), "role": member["role"],
                                     "token_hash": str(member.get("token_hash") or ""),
                                     "banned": bool(member.get("banned")), "op_hw": int(member.get("op_hw") or 0)}
                self.token_index[self.members[mid]["token_hash"]] = mid
        self.owner_hash = data.get("owner_hash") or None
        for claim in data.get("claims") or []:
            self._claim_order += 1
            self.claims[claim["cid"]] = {"cid": claim["cid"], "owner": claim["owner"], "scope": claim["scope"],
                                         "keys": set(claim["keys"]), "order": self._claim_order}
        for rid, req in ((r["rid"], r) for r in data.get("requests") or []):
            self.requests[rid] = {**req, "keys": set(req["keys"])}
        for comment in data.get("comments") or []:
            keys = comment.get("keys")
            self.comments[comment["id"]] = {**comment, "keys": set(keys) if keys is not None else None}
        self.log.extend(data.get("log") or [])
        self._reindex()

    def _snapshot(self) -> Dict[str, Any]:
        """The journal as a dict; called with the lock held. Row, claim and comment dicts are copied, not shared."""
        return {
            "protocol": PROTOCOL, "fingerprint": self.fingerprint, "room_id": self.room_id, "seq": self.seq,
            "rows": {k: dict(v) for k, v in self.rows.items()}, "stats": json.loads(json.dumps(self.stats)),
            "members": {mid: dict(m) for mid, m in self.members.items()}, "owner_hash": self.owner_hash,
            "claims": [self._claim_out(c) for c in self.claims.values()],
            "requests": [self._request_out(r, keys=True) for r in self.requests.values()],
            "comments": [self._comment_out(c) for c in self.comments.values()],
            "log": list(self.log),
        }

    def _schedule_journal(self) -> None:
        """Write the room soon; changes that keep coming are written together (called with the lock held)."""
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
            snapshot = self._snapshot()
        try:
            atomic_write_json(self.journal, snapshot, ensure_ascii=False)
            atomic_write_json(self.journal.parent / COMMENTS_NAME,
                              {"protocol": PROTOCOL, "fingerprint": snapshot["fingerprint"],
                               "room_id": snapshot["room_id"], "comments": snapshot["comments"]}, ensure_ascii=False)
        except OSError as exc:
            log_debug(f"Collab room: journal {self.journal} not written: {exc}")

    # ---- events, participants ------------------------------------------------

    def _event(self, kind: str, visible: Optional[str] = None, **fields: Any) -> None:
        """Append an event and wake the polls (called with the lock held). ``visible=HOST``: only the host gets it."""
        self.seq += 1
        event = {"seq": self.seq, "type": kind, "time": time.time(), **fields}
        if visible:
            event["visible"] = visible
        self.events.append(event)
        self.cond.notify_all()

    def _name(self, mid: Optional[str]) -> str:
        return self.members.get(mid or "", {}).get("name", "?")

    def _role(self, mid: Optional[str]) -> Optional[str]:
        return self.members.get(mid or "", {}).get("role")

    def _drop_silent(self) -> None:
        now = time.time()
        for pid, who in list(self.participants.items()):
            if now - who["seen"] > PARTICIPANT_TIMEOUT:
                del self.participants[pid]
                self._event("leave", by=pid, name=who["name"])

    def _public(self) -> List[Dict[str, Any]]:
        return [{"id": pid, "name": who["name"], "where": who.get("where"), "role": self._role(pid)}
                for pid, who in self.participants.items()]

    def join(self, name: str, password: str, fingerprint: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Join as ``name``. A known ``token`` returns the same member; the creation token makes a host.

        Raises ``PermissionError`` for a wrong password and ``ValueError`` for another project, a removed member or
        a name in use by someone online.
        """
        if not hmac.compare_digest(password.encode("utf-8"), self.password.encode("utf-8")):
            raise PermissionError("wrong password")
        with self.cond:
            self._drop_silent()
            is_owner = bool(token) and self.owner_hash is not None and hmac.compare_digest(_hash(token), self.owner_hash)
            if is_owner and self.fingerprint is None:
                self.fingerprint = fingerprint
            if self.fingerprint is None:
                raise ValueError("the room has no project yet: the host joins first")
            if fingerprint != self.fingerprint:
                raise ValueError("another project: the room works on different game text")
            mid = self.token_index.get(_hash(token)) if token else None
            if mid is not None and self.members[mid]["banned"]:
                raise ValueError("you were removed from this room")
            effective = (self.owner_name or name) if is_owner else name
            if any(pid != mid and who["name"] == effective for pid, who in self.participants.items()):
                raise ValueError("that name is in use in this room")
            if is_owner:
                token = self.owner_token_plain or token
                for old in self.members.values():
                    if old["role"] == HOST:
                        old["role"] = MODERATOR
                mid = secrets.token_hex(8)
                self.members[mid] = {"name": effective, "role": HOST, "token_hash": _hash(token), "banned": False,
                                     "op_hw": 0}
                self.token_index[_hash(token)] = mid
                self.owner_hash, self.owner_token_plain, self.owner_name = None, None, None
                self._log(mid, "host_created", to=effective)
            elif mid is None:
                token = secrets.token_urlsafe(24)
                mid = secrets.token_hex(8)
                self.members[mid] = {"name": name, "role": TRANSLATOR, "token_hash": _hash(token), "banned": False,
                                     "op_hw": 0}
                self.token_index[_hash(token)] = mid
            else:
                self.members[mid]["name"] = name
            member = self.members[mid]
            self.participants[mid] = {"name": member["name"], "seen": time.time(), "where": None}
            self._event("join", by=mid, name=member["name"], role=member["role"])
            self._schedule_journal()
            return {"id": mid, "token": token, "seq": self.seq, "rows": dict(self.rows),
                    "participants": self._public(), "role": member["role"], "room_id": self.room_id,
                    "op_hw": member["op_hw"], "state": self._state(),
                    "log": list(self.log) if member["role"] == HOST else []}

    def who(self, token: str) -> Optional[str]:
        """The member id of ``token`` while that member is online, or None."""
        with self.cond:              # request threads share the dicts with join, leave and the poll timeout
            mid = self.token_index.get(_hash(token))
            return mid if mid in self.participants else None

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
            return {"seq": self.seq, "events": self._events_since(since, self._role(pid)),
                    "participants": self._public(), "closed": self.closed}

    def _events_since(self, since: int, role: Optional[str] = None) -> List[Dict[str, Any]]:
        """The events after ``since``, newest last (called with the lock held).

        A client that fell further behind than the kept events gets every row as an ``edit`` and a ``snapshot`` of
        the members, claims, requests and comments: its state matches the room again, and nothing is lost silently.
        """
        oldest = self.events[0]["seq"] if self.events else self.seq + 1
        if oldest > since + 1:
            out: List[Dict[str, Any]] = [
                {"seq": self.seq, "type": "edit", "by": row.get("by", ""), "name": row.get("name", ""), "key": key,
                 "text": row["text"], "rev": row.get("rev", 0), "time": row.get("time"),
                 "approved": row.get("approved")}
                for key, row in self.rows.items()]
            out.append({"seq": self.seq, "type": "snapshot", "state": self._state()})
            return out
        out = []
        for event in reversed(self.events):                  # newest first: stop at the first one already seen
            if event["seq"] <= since:
                break
            out.append(event)
        out.reverse()
        if role != HOST:
            out = [e for e in out if e.get("visible") != HOST]
        return out

    # ---- rows (the edit path, shared by POST /edits and POST /ops) -----------

    def _row_out(self, key: str) -> Dict[str, Any]:
        row = self.rows.get(key)
        return dict(row) if row else {"text": "", "rev": 0, "by": "", "name": ""}

    def _edit_one(self, pid: str, edit: Dict[str, Any]) -> Tuple[str, Any]:
        """Apply one edit: returns ("accepted" | "same", rev), ("conflict", row) or ("refused", info). Lock held."""
        key, text, base = edit["key"], edit["text"], edit["base_rev"]
        role = self._role(pid)
        if role is None or not allowed(role, "edit"):
            return "refused", {"reason": "role", "row": self._row_out(key)}
        owner = self.row_claim.get(key)
        if owner is not None and self.claims[owner]["owner"] != pid:
            return "refused", {"reason": "claimed", "owner": self._name(self.claims[owner]["owner"]),
                               "row": self._row_out(key)}
        row = self.rows.get(key)
        current = row["rev"] if row else 0
        if base != current:
            return "conflict", self._row_out(key)
        if row and row["text"] == text:
            return "same", current
        name = self._name(pid)
        if not edit.get("seed"):
            self._count(name, first=not (row and row["text"].strip()), source_words=edit.get("words", 0))
        self.rows[key] = {"text": text, "rev": current + 1, "by": pid, "name": name, "time": time.time(),
                          "approved": None}
        self._event("edit", by=pid, name=name, key=key, text=text, rev=current + 1)
        return "accepted", current + 1

    def edit(self, pid: str, edits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Legacy batch (``POST /edits``): edits ``{key, text, base_rev}``; refused, conflicted and accepted apart."""
        accepted: Dict[str, int] = {}
        conflicts: Dict[str, Dict[str, Any]] = {}
        refused: Dict[str, Dict[str, Any]] = {}
        with self.cond:
            for edit in edits:
                status, value = self._edit_one(pid, edit)
                if status in ("accepted", "same"):
                    accepted[edit["key"]] = value
                elif status == "conflict":
                    conflicts[edit["key"]] = value
                else:
                    refused[edit["key"]] = value
            if accepted:
                self._schedule_journal()
        return {"accepted": accepted, "conflicts": conflicts, "refused": refused}

    def _count(self, name: str, first: bool, source_words: int) -> None:
        """One accepted edit by ``name`` today; a row translated for the first time also counts its source words."""
        day = self.stats.setdefault(name, {}).setdefault(_dt.date.today().isoformat(), {"rows": 0, "words": 0, "edits": 0})
        day["edits"] += 1
        if first:
            day["rows"] += 1
            day["words"] += max(0, int(source_words))

    # ---- operations (POST /ops) ----------------------------------------------

    def apply_ops(self, pid: str, ops: List[Any]) -> Dict[str, Dict[str, Any]]:
        """Apply a batch; returns {op_id: result}. Each result is ``ok``-shaped, ``duplicate``, ``error`` or a refusal."""
        results: Dict[str, Dict[str, Any]] = {}
        with self.cond:
            for index, op in enumerate(ops):
                op_id = op.get("op_id") if isinstance(op, dict) else None
                if not isinstance(op_id, str) or not op_id or len(op_id) > 64:
                    results[f"#{index}"] = {"error": "bad op id"}
                    continue
                results[op_id] = self._apply_op(pid, op)
        return results

    def _apply_op(self, pid: str, op: Dict[str, Any]) -> Dict[str, Any]:
        """One operation. A repeat is a no-op: with ``seq`` the member's high-water mark decides; without ``seq`` the
        ``op_id`` is remembered (the last SEEN_OPS, in memory). Lock held."""
        member = self.members.get(pid)
        if member is None:
            return {"error": "not a member"}
        seq = op.get("seq")
        if seq is not None:
            if isinstance(seq, bool) or not isinstance(seq, int) or seq <= 0:
                return {"error": "bad seq"}
            if seq <= member["op_hw"]:
                return {"duplicate": True}
            member["op_hw"] = seq
        else:
            seen = (pid, op["op_id"])
            if seen in self._seen_ops:
                return {"duplicate": True}
            self._seen_ops[seen] = True
            if len(self._seen_ops) > SEEN_OPS:
                self._seen_ops.popitem(last=False)
        method = _OPS.get(op.get("kind"))
        if method is None:
            return {"error": "unknown operation"}
        try:
            result = getattr(self, method)(pid, op)
        except ValueError as exc:
            return {"error": str(exc)}
        except Exception as exc:          # a field of the wrong type: this operation fails, the batch goes on
            log_debug(f"Collab room: operation {op.get('kind')!r} failed: {exc!r}")
            return {"error": "bad operation"}
        self._schedule_journal()
        return result

    def _op_edit(self, pid: str, op: Dict[str, Any]) -> Dict[str, Any]:
        status, value = self._edit_one(pid, _clean_edit(op))
        if status in ("accepted", "same"):
            return {"ok": True, "rev": value}
        return {"conflict": value} if status == "conflict" else {"refused": value}

    def _op_claim(self, pid: str, op: Dict[str, Any]) -> Dict[str, Any]:
        if not allowed(self._role(pid) or "", "claim"):
            return {"refused": {"reason": "role"}}
        scope, keys = _clean_scope(op.get("scope")), _clean_keys(op.get("keys"))
        if not keys:
            raise ValueError("nothing to claim")
        others = {self.claims[c]["owner"] for c in self._overlapping(keys)} - {pid}
        if others:
            rid = secrets.token_hex(6)
            self.requests[rid] = {"rid": rid, "requester": pid, "scope": scope, "keys": keys, "time": time.time()}
            self._event("claim_requested", by=pid, name=self._name(pid), request=self._request_out(self.requests[rid]))
            return {"requested": rid}
        return {"granted": self._grant(pid, scope, keys, actor=pid, displace=False)}

    def _op_decide(self, pid: str, op: Dict[str, Any]) -> Dict[str, Any]:
        if not allowed(self._role(pid) or "", "claim_decide"):
            return {"refused": {"reason": "role"}}
        rid = op.get("rid")
        request = self.requests.pop(rid, None) if isinstance(rid, str) else None
        if request is None:
            raise ValueError("no such request")
        if op.get("approve") is True:
            cid = self._grant(request["requester"], request["scope"], request["keys"], actor=pid, displace=True, rid=rid)
            if request["requester"] != pid:
                self._log(pid, "claim_approved", owner=request["requester"], scope=request["scope"])
            return {"granted": cid}
        self._event("claim_denied", by=pid, name=self._name(pid), rid=rid, requester=request["requester"])
        self._log(pid, "claim_denied", owner=request["requester"], scope=request["scope"])
        return {"ok": True}

    def _op_assign(self, pid: str, op: Dict[str, Any]) -> Dict[str, Any]:
        if not allowed(self._role(pid) or "", "assign"):
            return {"refused": {"reason": "role"}}
        target = op.get("target")
        member = self.members.get(target) if isinstance(target, str) else None
        if member is None or member["banned"] or member["role"] not in CLAIM_OWNERS:
            raise ValueError("that member cannot own a claim")
        scope, keys = _clean_scope(op.get("scope")), _clean_keys(op.get("keys"))
        if not keys:
            raise ValueError("nothing to assign")
        cid = self._grant(target, scope, keys, actor=pid, displace=True)
        self._log(pid, "claim_assigned", owner=target, scope=scope)
        return {"granted": cid}

    def _op_release(self, pid: str, op: Dict[str, Any]) -> Dict[str, Any]:
        """Take back a claim (its owner, or a host or moderator) or cancel a request (its requester)."""
        actor = self._role(pid) or ""
        rid = op.get("rid")
        if isinstance(rid, str) and rid in self.requests:
            request = self.requests[rid]
            if request["requester"] != pid and not allowed(actor, "claim_decide"):
                raise ValueError("not allowed")
            del self.requests[rid]
            self._event("claim_denied", by=pid, name=self._name(pid), rid=rid, requester=request["requester"])
            return {"ok": True}
        cid = op.get("cid")
        claim = self.claims.get(cid) if isinstance(cid, str) else None
        if claim is None:
            raise ValueError("no such claim")
        if claim["owner"] != pid and not allowed(actor, "claim_decide"):
            raise ValueError("not allowed")
        del self.claims[cid]
        self._reindex()
        taken = claim["owner"] != pid
        self._event("claim_released", by=pid, name=self._name(pid), cid=cid, owner=claim["owner"],
                    reason="taken away" if taken else "released")
        if taken:
            self._log(pid, "claim_taken_away", owner=claim["owner"], scope=claim["scope"])
        return {"ok": True}

    def _op_approve(self, pid: str, op: Dict[str, Any]) -> Dict[str, Any]:
        if not allowed(self._role(pid) or "", "approve"):
            return {"refused": {"reason": "role"}}
        key = op.get("key")
        if not isinstance(key, str):
            raise ValueError("bad key")
        row = self.rows.get(key)
        if row is None:
            raise ValueError("no such row")
        approved = op.get("approved") is not False
        row["approved"] = {"by": pid, "name": self._name(pid), "time": time.time()} if approved else None
        self._event("approved", by=pid, name=self._name(pid), key=key, approved=approved)
        return {"ok": True}

    def _op_comment(self, pid: str, op: Dict[str, Any]) -> Dict[str, Any]:
        text = op.get("text")
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_COMMENT:
            raise ValueError("a comment needs text up to 4000 characters")
        scope = _clean_scope(op.get("scope"))
        keys = None if scope["kind"] == "project" else _clean_keys(op.get("keys"))
        if keys is not None and not keys:
            raise ValueError("a comment needs a scope")
        cid = secrets.token_hex(6)
        self.comments[cid] = {"id": cid, "scope": scope, "keys": keys, "author": pid, "author_name": self._name(pid),
                              "time": time.time(), "text": text, "resolved": None}
        self._event("comment_added", by=pid, name=self._name(pid), comment=self._comment_out(self.comments[cid]))
        return {"comment": cid}

    def _op_comment_resolve(self, pid: str, op: Dict[str, Any]) -> Dict[str, Any]:
        comment = self._comment(op)
        actor = self._role(pid) or ""
        if not allowed(actor, "resolve_comment"):
            return {"refused": {"reason": "role"}}
        resolved = op.get("resolved") is not False
        resolved_by_other = comment["resolved"] is not None and comment["resolved"]["by"] != pid
        if not resolved and resolved_by_other and comment["author"] != pid and not allowed(actor, "reopen_any_comment"):
            return {"refused": {"reason": "role"}}
        comment["resolved"] = {"by": pid, "name": self._name(pid), "time": time.time()} if resolved else None
        self._event("comment_resolved", by=pid, name=self._name(pid), id=comment["id"], resolved=resolved)
        return {"ok": True}

    def _op_comment_delete(self, pid: str, op: Dict[str, Any]) -> Dict[str, Any]:
        comment = self._comment(op)
        if comment["author"] != pid:
            if not allowed(self._role(pid) or "", "delete_any_comment"):
                raise ValueError("not allowed")
            self._log(pid, "comment_deleted", author=comment["author"], scope=comment["scope"])
        del self.comments[comment["id"]]
        self._event("comment_deleted", by=pid, name=self._name(pid), id=comment["id"])
        return {"ok": True}

    def _op_role(self, pid: str, op: Dict[str, Any]) -> Dict[str, Any]:
        target, new = op.get("target"), op.get("role")
        member = self.members.get(target) if isinstance(target, str) else None
        if member is None or not allowed(self._role(pid) or "", "set_role", target=member["role"], new=new):
            raise ValueError("not allowed")
        previous, member["role"] = member["role"], new
        self._event("role_set", by=pid, name=self._name(pid), member=target, role=new, previous=previous)
        if target != pid:
            self._log(pid, "role_set", member=target, role=new, previous=previous)
        return {"ok": True}

    def _op_kick(self, pid: str, op: Dict[str, Any]) -> Dict[str, Any]:
        target = op.get("target")
        member = self.members.get(target) if isinstance(target, str) else None
        if member is None or target == pid or not allowed(self._role(pid) or "", "kick", target=member["role"]):
            raise ValueError("not allowed")
        member["banned"] = True
        self.participants.pop(target, None)
        self._event("kicked", by=pid, name=self._name(pid), member=target, target_name=member["name"])
        self._log(pid, "kicked", member=target, name=member["name"])
        return {"ok": True}

    def _op_unban(self, pid: str, op: Dict[str, Any]) -> Dict[str, Any]:
        target = op.get("target")
        member = self.members.get(target) if isinstance(target, str) else None
        if member is None or not member["banned"] or not allowed(self._role(pid) or "", "kick", target=member["role"]):
            raise ValueError("not allowed")
        member["banned"] = False
        self._event("unbanned", by=pid, name=self._name(pid), member=target)
        self._log(pid, "unbanned", member=target, name=member["name"])
        return {"ok": True}

    def _op_transfer_host(self, pid: str, op: Dict[str, Any]) -> Dict[str, Any]:
        target = op.get("target")
        member = self.members.get(target) if isinstance(target, str) else None
        if not allowed(self._role(pid) or "", "transfer_host") or member is None or member["banned"] or target == pid:
            raise ValueError("not allowed")
        if op.get("confirm") is not True:
            raise ValueError("the transfer needs confirmation")
        self.members[pid]["role"] = MODERATOR
        member["role"] = HOST
        self._event("host_transferred", by=pid, name=self._name(pid), to=target, to_name=member["name"])
        self._log(pid, "host_transferred", to=target, name=member["name"])
        return {"ok": True}

    def _comment(self, op: Dict[str, Any]) -> Dict[str, Any]:
        comment = self.comments.get(op.get("id")) if isinstance(op.get("id"), str) else None
        if comment is None:
            raise ValueError("no such comment")
        return comment

    # ---- claims ----------------------------------------------------------------

    def _overlapping(self, keys: Set[str]) -> List[str]:
        return [cid for cid, claim in self.claims.items() if not claim["keys"].isdisjoint(keys)]

    def _grant(self, owner: str, scope: Dict[str, str], keys: Set[str], actor: str, displace: bool,
               rid: Optional[str] = None) -> str:
        """A claim for ``owner``. ``displace``: the claims of everyone else on these rows are taken away first."""
        if displace:
            for cid in self._overlapping(keys):
                old = self.claims.pop(cid)
                self._event("claim_released", by=actor, name=self._name(actor), cid=cid, owner=old["owner"],
                            reason="reassigned")
        self._claim_order += 1
        cid = secrets.token_hex(6)
        self.claims[cid] = {"cid": cid, "owner": owner, "scope": scope, "keys": set(keys), "order": self._claim_order}
        self._reindex()
        self._event("claim_granted", by=actor, name=self._name(actor), rid=rid, claim=self._claim_out(self.claims[cid]))
        return cid

    def _reindex(self) -> None:
        """Map each row key to the most specific claim on it: the smallest scope, then the oldest (lock held)."""
        self.row_claim = {}
        for claim in sorted(self.claims.values(), key=lambda c: (len(c["keys"]), c["order"])):
            for key in claim["keys"]:
                self.row_claim.setdefault(key, claim["cid"])

    # ---- outgoing shapes ---------------------------------------------------------

    def _claim_out(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        return {"cid": claim["cid"], "owner": claim["owner"], "name": self._name(claim["owner"]),
                "scope": claim["scope"], "keys": sorted(claim["keys"]),
                "online": claim["owner"] in self.participants}

    def _request_out(self, request: Dict[str, Any], keys: bool = False) -> Dict[str, Any]:
        out = {"rid": request["rid"], "requester": request["requester"], "name": self._name(request["requester"]),
               "scope": request["scope"], "count": len(request["keys"])}
        if keys:
            out["keys"] = sorted(request["keys"])
        return out

    def _comment_out(self, comment: Dict[str, Any]) -> Dict[str, Any]:
        keys = comment["keys"]
        return {"id": comment["id"], "scope": comment["scope"], "keys": None if keys is None else sorted(keys),
                "author": comment["author"], "author_name": comment["author_name"], "time": comment["time"],
                "text": comment["text"], "resolved": comment["resolved"]}

    def _state(self) -> Dict[str, Any]:
        """Members, claims, requests and comments: what a joiner or a snapshot needs. Lock held."""
        return {
            "members": [{"id": mid, "name": m["name"], "role": m["role"], "online": mid in self.participants,
                         "banned": m["banned"]} for mid, m in self.members.items()],
            "claims": [self._claim_out(c) for c in self.claims.values()],
            "requests": [self._request_out(r) for r in self.requests.values()],
            "comments": [self._comment_out(c) for c in self.comments.values()],
        }

    def _log(self, actor: str, action: str, **detail: Any) -> None:
        """A moderator action, for the host's log (called with the lock held)."""
        entry = {"time": time.time(), "by": actor, "name": self._name(actor), "action": action, **detail}
        self.log.append(entry)
        self._event("log", visible=HOST, entry=entry)

    # ---- progress page and close -----------------------------------------------

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


_OPS = {
    "edit": "_op_edit", "claim": "_op_claim", "decide": "_op_decide", "release": "_op_release",
    "assign": "_op_assign", "approve": "_op_approve", "comment": "_op_comment",
    "comment_resolve": "_op_comment_resolve", "comment_delete": "_op_comment_delete", "role": "_op_role",
    "kick": "_op_kick", "unban": "_op_unban", "transfer_host": "_op_transfer_host",
}


def _clean_edit(edit: Any) -> Dict[str, Any]:
    """One edit, validated; raises ValueError on anything else."""
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
    return {"key": key, "text": text, "base_rev": base, "seed": edit.get("seed") is True, "words": words}


def _clean_edits(body: Any) -> List[Dict[str, Any]]:
    """The edits of a legacy request, validated; raises ValueError on anything else."""
    edits = body.get("edits") if isinstance(body, dict) else None
    if not isinstance(edits, list):
        raise ValueError("edits must be a list")
    return [_clean_edit(edit) for edit in edits]


def _clean_scope(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict) or value.get("kind") not in SCOPE_KINDS:
        raise ValueError("a scope needs a kind: project, folder, file, block, row or virtual")
    label = value.get("label", "")
    if not isinstance(label, str) or len(label) > 200:
        raise ValueError("bad scope label")
    return {"kind": value["kind"], "label": label}


def _clean_keys(value: Any) -> Set[str]:
    if not isinstance(value, list):
        raise ValueError("keys must be a list")
    if len(value) > MAX_KEYS:
        raise ValueError("too many rows in one scope")
    keys: Set[str] = set()
    for key in value:
        if not isinstance(key, str) or not key or len(key) > 1024:
            raise ValueError("bad key")
        keys.add(key)
    return keys


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
    server_version = "PicoripiRoom/2"
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
        if url.path not in ("/events", "/ops"):
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
            token = body.get("token") if isinstance(body.get("token"), str) else None
            try:
                self._send(200, self.room.join(name, str(body.get("password") or ""),
                                               str(body.get("fingerprint") or ""), token))
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
        elif path == "/ops":
            ops = body.get("ops") if isinstance(body, dict) else None
            if not isinstance(ops, list) or len(ops) > MAX_OPS:
                self._send(400, {"error": f"ops must be a list of at most {MAX_OPS}"})
                return
            if body.get("room_id") != self.room.room_id:
                self._send(409, {"error": "another room: the room was started again"})
                return
            self._send(200, {"results": self.room.apply_ops(pid, ops), "seq": self.room.seq})
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

    def __init__(self, password: str, fingerprint: Optional[str], port: int = 0, host: str = "127.0.0.1",
                 journal: Optional[Path] = None, owner_token: Optional[str] = None,
                 owner_name: Optional[str] = None):
        self.room = Room(password, fingerprint, journal, owner_token=owner_token, owner_name=owner_name)
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
        if self.thread.is_alive():        # shutdown() waits for serve_forever: an unstarted server would wait forever
            self.httpd.shutdown()
            self.thread.join(timeout=2)
        self.httpd.server_close()


# ---- headless entry point: python -m core.collab.server --headless ... ----------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m core.collab.server",
                                     description="Run a Picoripi work-together room without a window.")
    parser.add_argument("--headless", action="store_true", required=True, help="run without a window (the only mode)")
    parser.add_argument("--port", type=int, default=8765, help="port to listen on; 0 picks a free one")
    parser.add_argument("--host", default="127.0.0.1", help="address to listen on; 0.0.0.0 for other computers")
    parser.add_argument("--password-file", required=True, help="file whose first line is the room password")
    parser.add_argument("--project-dir", required=True, help="folder of the project: the journal lives here")
    parser.add_argument("--owner-name", default="", help="the host's name, used when the host first joins")
    parser.add_argument("--owner-token-file", default="",
                        help="file with the creation token; created with a new token if it does not exist")
    return parser.parse_args(argv)


def build_server(args: argparse.Namespace) -> Tuple[RoomServer, Optional[str]]:
    """The room for ``args``, unstarted; returns it with the creation token issued now (or None)."""
    lines = Path(args.password_file).read_text(encoding="utf-8").strip().splitlines()
    password = lines[0].strip() if lines else ""
    if not password:
        raise ValueError("the password file is empty")
    project_dir = Path(args.project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)
    owner_token = None
    token_file = Path(args.owner_token_file) if args.owner_token_file else None
    if token_file is not None and token_file.is_file():
        owner_token = token_file.read_text(encoding="utf-8").strip() or None
    server = RoomServer(password, None, port=args.port, host=args.host, journal=project_dir / JOURNAL_NAME,
                        owner_token=owner_token, owner_name=args.owner_name or None)
    issued = None
    if owner_token is None and server.room.owner_token_plain is not None:
        issued = server.room.owner_token_plain
        if token_file is not None:
            token_file.write_text(issued, encoding="utf-8")
            issued = None                  # the file holds it: do not print it
    return server, issued


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    server, issued = build_server(args)
    server.start()
    print(json.dumps({"port": server.port, "room_id": server.room.room_id, "owner_token": issued}), flush=True)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
