"""The Project Manager's scan: the card, icon and string counts of each project, with the cache rules.

The window runs this in a child process (``core/project_library/scan_child.py``), so the parsing never holds the
window's interpreter. Each step reports one small event (a dict); the window updates the row the event names.

Cache rules, one entry per project key in ``project_index.json``:
- ``card``: reused while the project file keeps its modification time and size.
- ``counts`` or ``count_error``: reused while ``plugin_facts.input_signature`` is unchanged. Any change to the project
  file, the plugin's config, its Python files (the parser), the shared ``common`` plugin files, the Picoripi version, or
  a source or translation file a block names starts a recount.
- ``icon``: reused while its ``want`` is unchanged: the user's ``picoripi/icon.png`` (size and modification time), or,
  without one, the project file and plugin. The PNG lives in ``<data folder>/pm_icons``.
A cache entry is never trusted across a changed signature; a missing entry is simply computed.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from core.project_library import index, plugin_facts
from core.project_library.cards import fallback_name, read_card
from core.project_library.icons import ICON_SIZE, scale_image_bytes, scale_image_file
from core.project_library.plugin_facts import default_load_rules
from core.project_library.series_facts import series_facts
from utils.logging_utils import log_debug

ICON_FILE_NAME = "icon.png"  # beside project.uiproj, inside the project's picoripi folder
ICON_CACHE_NAME = "pm_icons"
FLUSH_CARDS = 25  # cards written to the index per save
FLUSH_SECONDS = 2.0  # counts written at least this often

Emit = Callable[[Dict[str, Any]], None]
Cancelled = Callable[[], bool]
LoadRules = Callable[[str], Any]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stat_pair(path: Path) -> Optional[List[int]]:
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return [stat.st_mtime_ns, stat.st_size]


def _card_for(project_file: str, cached: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The card of a project: the cached one while the file is unchanged, else read again."""
    try:
        stat = os.stat(project_file)
    except OSError:
        return {"missing": True, "issues": ["project_file_missing"], "name": fallback_name(project_file)}
    if cached and cached.get("mtime_ns") == stat.st_mtime_ns and cached.get("size") == stat.st_size:
        return cached
    try:
        return read_card(project_file)
    except (OSError, ValueError) as exc:
        return {"issues": ["unreadable"], "error": str(exc), "name": fallback_name(project_file)}


def _icon_want(project_dir: Path, card: Dict[str, Any]) -> List[Any]:
    """What the icon depends on. A user's icon.png wins over the plugin's icon."""
    user = _stat_pair(project_dir / ICON_FILE_NAME)
    if user is not None:
        return ["user", user]
    return ["plugin", card.get("mtime_ns"), card.get("size"), card.get("plugin", "")]


def _icon_step(key: str, project_file: str, card: Dict[str, Any], cached: Optional[Dict[str, Any]],
               icon_dir: Path, rules_of: Callable[[str], Any]) -> Optional[Dict[str, Any]]:
    """The icon entry of a project when it changed, else None. Writes the scaled PNG atomically."""
    project_dir = Path(project_file).parent
    want = _icon_want(project_dir, card)
    if cached and cached.get("want") == want and (not cached.get("file") or Path(cached["file"]).is_file()):
        return None
    target = icon_dir / (hashlib.sha1(key.encode("utf-8")).hexdigest() + ".png")
    source, stored = "none", ""
    if want[0] == "user":
        if scale_image_file(project_dir / ICON_FILE_NAME, target, ICON_SIZE):
            source, stored = "user", str(target)
    else:
        data = _plugin_icon(card, project_dir, rules_of)
        if data and scale_image_bytes(data, target, ICON_SIZE):
            source, stored = "plugin", str(target)
    if not stored and target.exists():
        target.unlink()
    return {"want": want, "file": stored, "source": source}


def _plugin_icon(card: Dict[str, Any], project_dir: Path, rules_of: Callable[[str], Any]) -> Optional[bytes]:
    """The plugin's icon for a project, or None. The hook is optional; a failing plugin gives no icon."""
    plugin = str(card.get("plugin") or "")
    if not plugin or "plugin_missing" in card.get("issues", []):
        return None
    try:
        rules = rules_of(plugin)
    except Exception as exc:  # the counts report the missing plugin; an icon just stays generated
        log_debug(f"Project icon: plugin {plugin} not loaded: {exc}")
        return None
    hook = getattr(rules, "project_icon", None)
    if not callable(hook):
        return None
    try:
        data = hook(str(project_dir))
    except Exception as exc:  # a plugin's bug must not stop the scan
        log_debug(f"Project icon: plugin {plugin} failed: {exc}")
        return None
    return bytes(data) if isinstance(data, (bytes, bytearray)) and data else None


def _count_fields(project_file: str, signature: str, load_rules: LoadRules,
                  is_cancelled: Cancelled) -> Tuple[Optional[Dict[str, Any]], str]:
    """The count entry of a project and its outcome: counted, plugin_missing, failed; None entry when cancelled."""
    stamp = _now()
    try:
        result = plugin_facts.count_project(project_file, load_rules, is_cancelled)
    except plugin_facts.PluginMissing:
        return {"counts": None, "count_error": plugin_facts.PLUGIN_MISSING, "signature": signature,
                "counted_at": stamp}, "plugin_missing"
    except Exception as exc:  # one broken project must not stop the others
        return {"counts": None, "count_error": str(exc), "signature": signature, "counted_at": stamp}, "failed"
    if result is None:
        return None, "cancelled"
    return {"counts": result["counts"], "targets": result["targets"], "skipped": result["skipped"],
            "groups": result["groups"], "missing_translations": result["missing_translations"],
            "signature": signature, "counted_at": stamp}, "counted"


class _Batch:
    """Index writes, held back and written in groups, so the disk is not written once per project."""

    def __init__(self, directory: str):
        self._directory = directory
        self._pending: Dict[str, Dict[str, Any]] = {}
        self._since = time.monotonic()

    def add(self, key: str, fields: Dict[str, Any]) -> None:
        self._pending.setdefault(key, {}).update(fields)

    def due(self, size: int) -> bool:
        return len(self._pending) >= size or time.monotonic() - self._since >= FLUSH_SECONDS

    def flush(self) -> None:
        if self._pending:
            index.merge(self._directory, self._pending)
        self._pending = {}
        self._since = time.monotonic()


def run(data_dir: str, projects: Iterable[Tuple[str, str]], emit: Emit, is_cancelled: Cancelled,
        load_rules: LoadRules = default_load_rules) -> Dict[str, int]:
    """Scan ``projects`` (``(project key, project file)`` pairs). Returns the totals that the ``done`` event carries.

    Phase 1 reads every card (a ``card`` event each), then each project's icon and input signature (a ``checked``
    event each, ``done`` = projects checked so far). Phase 2 counts only the projects whose signature changed, so a
    second start with nothing changed does no parsing of string content.
    """
    targets = list(projects)
    cache = index.read(data_dir)
    icon_dir = Path(data_dir) / ICON_CACHE_NAME
    icon_dir.mkdir(parents=True, exist_ok=True)
    loaded: Dict[str, Any] = {}

    def rules_of(plugin: str) -> Any:
        if plugin not in loaded:
            loaded[plugin] = load_rules(plugin)
        return loaded[plugin]

    started = time.monotonic()
    batch = _Batch(data_dir)
    stale: List[Tuple[str, str, str, Dict[str, Any]]] = []
    totals = {"counted": 0, "plugin_missing": 0, "failed": 0}
    cancelled = False
    # Every card first: a card is one small JSON file, so the whole list has its names (and search finds them) in
    # about a second; the icons and the signatures (a stat of every file a block names) come after.
    cards: List[Tuple[str, str, Dict[str, Any]]] = []
    for key, project_file in targets:
        if is_cancelled():
            cancelled = True
            break
        cached = cache.get(key) or {}
        card = _card_for(project_file, cached.get("card"))
        if card is not cached.get("card"):
            batch.add(key, {"card": card})
        series = series_facts(project_file, cached.get("series_glossaries"))
        if series != cached.get("series_glossaries"):
            batch.add(key, {"series_glossaries": series})
        emit({"event": "card", "key": key, "card": card, "series": series})
        cards.append((key, project_file, card))
    batch.flush()
    for position, (key, project_file, card) in enumerate(cards):
        if is_cancelled():
            cancelled = True
            break
        emit({"event": "checked", "done": position + 1})
        cached = cache.get(key) or {}
        icon = _icon_step(key, project_file, card, cached.get("icon"), icon_dir, rules_of)
        if icon is not None:
            batch.add(key, {"icon": icon})
            emit({"event": "icon", "key": key, "file": icon["file"], "source": icon["source"]})
        if batch.due(FLUSH_CARDS):
            batch.flush()
        if "plugin_missing" in card.get("issues", []):
            totals["plugin_missing"] += 1
        if card.get("missing") or "unreadable" in card.get("issues", []) or "plugin_missing" in card.get("issues", []):
            continue
        try:
            signature = plugin_facts.input_signature(project_file)
        except (OSError, ValueError):
            continue
        if cached.get("signature") == signature and ("counts" in cached or "count_error" in cached):
            continue
        stale.append((key, project_file, signature, card))
    batch.flush()
    emit({"event": "plan", "total": len(targets), "stale": len(stale)})

    if not cancelled:
        for position, (key, project_file, signature, card) in enumerate(stale):
            if is_cancelled():
                cancelled = True
                break
            emit({"event": "progress", "done": position, "total": len(stale),
                  "name": card.get("name") or fallback_name(project_file)})
            fields, outcome = _count_fields(project_file, signature, rules_of, is_cancelled)
            if fields is None:
                cancelled = True
                break
            totals[outcome] = totals.get(outcome, 0) + 1
            batch.add(key, fields)
            emit({"event": "counts", "key": key, "fields": fields})
            if batch.due(5):
                batch.flush()
        batch.flush()
    summary = {"total": len(targets), "stale": len(stale), **totals, "cancelled": cancelled,
               "seconds": round(time.monotonic() - started, 2)}
    emit({"event": "done", **summary})
    return summary


def encode(event: Dict[str, Any]) -> str:
    """One protocol line: JSON with no newline inside it."""
    return json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
