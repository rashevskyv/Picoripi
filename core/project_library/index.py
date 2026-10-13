"""The cached project index (``project_index.json``): the last card and string counts of each project."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from core.project_library import plugin_facts
from core.project_library.cards import count_strings
from utils.atomic_io import atomic_write_json
from utils.logging_utils import log_warning

INDEX_FILE_NAME = "project_index.json"
SCHEMA_VERSION = 1

# Writers from several worker threads take turns; a read-modify-write must not interleave.
_lock = threading.Lock()


def index_path(directory: str | os.PathLike) -> Path:
    return Path(directory) / INDEX_FILE_NAME


def _read_entries(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        entries = raw.get("entries") if isinstance(raw, dict) else None
        if not isinstance(entries, dict):
            raise ValueError("no entries object")
        return entries
    except (OSError, ValueError) as exc:
        aside = path.with_name(path.name + ".unreadable")
        try:
            os.replace(path, aside)
        except OSError:
            pass
        log_warning(f"Project index set aside as {aside.name}: {exc}")
        return {}


def read(directory: str | os.PathLike) -> Dict[str, Dict[str, Any]]:
    """All cached entries, keyed by ``project_key``."""
    with _lock:
        return _read_entries(index_path(directory))


def merge(directory: str | os.PathLike, updates: Dict[str, Dict[str, Any]]) -> None:
    """Set the given fields of each entry (by key); other fields and entries stay. Writes the file atomically."""
    if not updates:
        return
    path = index_path(directory)
    with _lock:
        entries = _read_entries(path)
        for key, fields in updates.items():
            entries.setdefault(key, {}).update(fields)
        atomic_write_json(path, {"version": SCHEMA_VERSION, "entries": entries}, indent=2, ensure_ascii=False)


def stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def record_counts(directory: str | os.PathLike, key: str, original: Any, translated_file: Any,
                  edited: Dict[Any, Any], project_file: str | os.PathLike | None = None) -> Dict[str, int]:
    """Count the strings of a project from data in memory and store the counts. Runs on a worker thread.

    With ``project_file`` the entry also stores the input signature of the files on disk, so the next scan keeps
    these counts while the saved files are unchanged. The counts come from memory: they are the saved state
    when this runs after a save.
    """
    counts = count_strings(original, translated_file, edited)
    fields: Dict[str, Any] = {"counts": counts, "counted_at": stamp(), "count_error": None}
    if project_file is not None:
        try:
            fields["signature"] = plugin_facts.input_signature(project_file)
        except (OSError, ValueError):
            fields["signature"] = None  # the next scan recounts
    merge(directory, {key: fields})
    return counts
