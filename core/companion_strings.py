"""Translation rows with the Companion server: snapshot the project, pull phone edits, sort them, push the rows.

The server keeps per row ``translation`` (its text) and ``base`` (what the desktop pushed last); a row whose texts
differ was edited on the phone. A pulled edit is sorted against the text this PC has now:

* the PC text is still ``base``: the phone edit is taken (through ``DataStateProcessor``, see
  ``components/companion/strings_sync.py``);
* the PC text is the phone text: nothing to do;
* both changed, to different texts: a conflict. The user decides; until then the edit stays on the server.

Nothing here touches Qt or the project; the network calls run in a worker thread.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from core.companion_sync import CompanionSyncClient, _never
from core.i18n import tr
from utils.logging_utils import log_info

REMOTE = "COMPANION_REMOTE"      # the action type of a phone edit taken into the project
PUSH_TIMEOUT = 120               # seconds: a push carries every row of the project


@dataclass
class RowsSnapshot:
    """Copies of the project's rows, taken on the GUI thread, read in a worker."""

    data: List[List[Any]]
    edited_file: List[List[Any]]
    edited: Dict[Tuple[int, int], str]
    prefixes: List[str]
    names: Dict[str, str]

    def current(self, block: int, string: int) -> Optional[str]:
        """The row's text as ``DataStateProcessor.get_current_string_text`` gives it; None if the row is missing."""
        if not (0 <= block < len(self.data)) or not (0 <= string < len(self.data[block])):
            return None
        if (block, string) in self.edited:
            return self.edited[(block, string)]
        if block < len(self.edited_file) and string < len(self.edited_file[block]):
            value = self.edited_file[block][string]
            if value is not None:
                return str(value)
        value = self.data[block][string]
        return "" if value is None else str(value)

    def key(self, block: int, string: int) -> str:
        return f"{self.prefixes[block]}{string}"

    def rows(self) -> List[Dict[str, Any]]:
        out = []
        for block, strings in enumerate(self.data):
            for string, original in enumerate(strings):
                out.append({"key": self.key(block, string), "block": block, "string": string,
                            "original": "" if original is None else str(original),
                            "translation": self.current(block, string) or ""})
        return out

    def blocks(self) -> List[Dict[str, Any]]:
        return [{"block": block, "name": self.names.get(str(block)) or self.prefixes[block].split("::")[0]}
                for block in range(len(self.data))]


def take_snapshot(mw: Any) -> RowsSnapshot:
    """Copy what a push needs (GUI thread; list copies only, no per-row Python work)."""
    store = mw.data_store
    data = [list(b) if isinstance(b, list) else [] for b in (store.data or [])]
    edited_file = [list(b) if isinstance(b, list) else [] for b in (store.edited_file_data or [])]
    return RowsSnapshot(data, edited_file, dict(store.edited_data),
                        mw.saved_translations_manager.block_key_prefixes(len(data)), dict(store.block_names or {}))


@dataclass
class StringConflict:
    """A row changed both here and on the phone, to different texts."""

    key: str
    block: int
    string: int
    original: str
    pc: str
    phone: str


@dataclass
class SortedEdits:
    take: List[Tuple[int, int, str]] = field(default_factory=list)      # (block, string, phone text)
    conflicts: List[StringConflict] = field(default_factory=list)
    resolved: Dict[str, str] = field(default_factory=dict)              # key -> phone text decided on
    unknown: int = 0                                                    # rows this project does not have


def sort_phone_edits(pending: List[Dict[str, Any]], snapshot: RowsSnapshot) -> SortedEdits:
    """Sort pulled phone edits against the PC texts in ``snapshot`` (see the module docstring)."""
    out = SortedEdits()
    for row in pending:
        try:
            key, block, string = str(row["key"]), int(row["block"]), int(row["string"])
            phone, base = str(row["translation"]), str(row["base"])
        except (KeyError, TypeError, ValueError):
            out.unknown += 1
            continue
        pc = snapshot.current(block, string)
        if pc is None or snapshot.key(block, string) != key:
            out.unknown += 1                       # another project text: never applied blind
            continue
        if pc == phone:
            out.resolved[key] = phone
        elif pc == base:
            out.take.append((block, string, phone))
            out.resolved[key] = phone
        else:
            out.conflicts.append(StringConflict(key, block, string, str(row.get("original", "")), pc, phone))
    return out


def _error(resp: requests.Response) -> str:
    if resp.status_code == 401:
        return tr("Authentication failed: invalid token or PIN.")
    return tr("Server error {code}: {text}").format(code=resp.status_code, text=resp.text[:300])


def pull_phone_edits(client: CompanionSyncClient, project: str,
                     cancelled: Callable[[], bool] = _never) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """The rows edited on the phone and not taken yet."""
    try:
        resp = requests.get(f"{client.server_url}/api/strings/pull", headers=client._get_headers(),
                            params={"project": project}, timeout=client.timeout)
    except requests.exceptions.RequestException as exc:
        return False, tr("Failed to connect to companion server: {error}").format(error=exc), []
    if cancelled():
        return False, tr("Synchronization cancelled."), []
    if resp.status_code != 200:
        return False, _error(resp), []
    rows = resp.json().get("rows") or []
    return True, "", [r for r in rows if isinstance(r, dict)]


def push_rows(client: CompanionSyncClient, project: str, snapshot: RowsSnapshot, resolved: Dict[str, str],
              cancelled: Callable[[], bool] = _never) -> Tuple[bool, str, int]:
    """Send every row of the project; returns ``(ok, message, phone edits still open on the server)``."""
    if cancelled():
        return False, tr("Synchronization cancelled."), 0
    payload = {"project_name": project, "blocks": snapshot.blocks(), "rows": snapshot.rows(), "resolved": resolved}
    try:
        resp = requests.post(f"{client.server_url}/api/strings/push", headers=client._get_headers(), json=payload,
                             timeout=max(client.timeout, PUSH_TIMEOUT))
    except requests.exceptions.RequestException as exc:
        return False, tr("Failed to push to companion server: {error}").format(error=exc), 0
    if resp.status_code != 200:
        return False, _error(resp), 0
    data = resp.json()
    log_info(f"Companion strings: pushed {data.get('rows', 0)} rows of '{project}'")
    return True, "", int(data.get("pending", 0) or 0)
