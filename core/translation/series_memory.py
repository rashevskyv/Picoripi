"""Series translation memory: what the other projects of a series translated, read from their own memory files.

Nothing is copied. Beside every series glossary a ``projects.json`` says which
projects share it and where each one's ``translation_memory.json`` is; a
project registers itself there when it opens and reads the others' files.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from core.translation.run_memory import normalize_source
from plugins.common.series_tags import neutral_key
from utils.atomic_io import atomic_write_json
from utils.logging_utils import log_debug

REGISTRY_NAME = "projects.json"
MEMORY_NAME = "translation_memory.json"


def source_hash(source: str) -> str:
    """The key of a source text in a translation memory: tags, case and spacing do not count."""
    return hashlib.sha1(normalize_source(source).encode("utf-8")).hexdigest()


def registry_path(series_file: Path) -> Path:
    """The ``projects.json`` beside a series glossary file."""
    return Path(series_file).parent / REGISTRY_NAME


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        log_debug(f"Series memory: cannot read {path}: {exc}")
        return None


def register_project(chain: Iterable[Path], project_name: str, memory_path: Path) -> None:
    """Record ``memory_path`` as the memory of ``project_name`` beside every series glossary of ``chain``.

    A tiny write, and only when the entry changes.
    """
    for series_file in chain:
        path = registry_path(series_file)
        registry = _read_json(path) if path.exists() else {}
        if not isinstance(registry, dict):
            registry = {}
        if registry.get(project_name) == str(memory_path):
            continue
        registry[project_name] = str(memory_path)
        try:
            atomic_write_json(path, registry, ensure_ascii=False, indent=1)
        except OSError as exc:
            log_debug(f"Series memory: cannot write {path}: {exc}")


def load_series_memory(chain: Iterable[Path], own_memory_path: Optional[Path]) -> Dict[str, List[Dict[str, str]]]:
    """``source hash -> [{source, translation, project}]`` from the other projects sharing a series glossary.

    Nearest level first; within a project the newest translation comes last,
    as in its own file. The project's own memory is left out.
    """
    memory: Dict[str, List[Dict[str, str]]] = {}
    seen: set = {Path(own_memory_path)} if own_memory_path else set()
    for series_file in chain:
        registry = _read_json(registry_path(series_file)) if registry_path(series_file).exists() else None
        if not isinstance(registry, dict):
            continue
        for project_name, memory_file in registry.items():
            path = Path(str(memory_file))
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            rows_by_hash = _read_json(path)
            if not isinstance(rows_by_hash, dict):
                continue
            for key, rows in rows_by_hash.items():
                if not isinstance(rows, list):
                    continue
                bucket = memory.setdefault(key, [])
                for row in rows:
                    if isinstance(row, dict) and isinstance(row.get("source"), str) and isinstance(row.get("translation"), str):
                        entry = {"source": row["source"], "translation": row["translation"], "project": str(project_name)}
                        # speaker and addressee say under whom the row was saved; rows saved before they existed have neither
                        # speaker_en is the speaker's own name: series rows of two games match by it (D45)
                        entry.update({k: str(row[k]) for k in ("speaker", "addressee", "speaker_en") if isinstance(row.get(k), str)})
                        # the tag kinds the row was saved with (plugins/common/series_tags.py): another game's syntax carries across
                        entry.update({k: row[k] for k in ("syntax", "tags", "neutral") if k in row})
                        bucket.append(entry)
    return memory


def index_neutral_rows(memory: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    """``neutral key -> rows``: the rows of ``load_series_memory`` that were saved with a neutral text (tag kinds).

    Built once per project load, from the same row objects; a row without tag kinds is not in the index.
    """
    index: Dict[str, List[Dict[str, Any]]] = {}
    for rows in memory.values():
        for row in rows:
            neutral = row.get("neutral")
            if isinstance(neutral, str):
                index.setdefault(neutral_key(neutral), []).append(row)
    return index


def index_source_positions(data: Any) -> Dict[str, List[tuple]]:
    """``source hash -> [(block_idx, string_idx), ...]``: where each source text sits in the project."""
    positions: Dict[str, List[tuple]] = {}
    if not isinstance(data, list):
        return positions
    for block_idx, block in enumerate(data):
        if not isinstance(block, list):
            continue
        for string_idx, source in enumerate(block):
            if isinstance(source, str) and normalize_source(source):
                positions.setdefault(source_hash(source), []).append((block_idx, string_idx))
    return positions
