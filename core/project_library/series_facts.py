"""The series glossaries a project uses, and how many terms they hold: read by the Project Manager's scan for the details of
a project. Read only: the project file, the series glossaries and the folders above the project are never written."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Set

from core.glossary.series import linked_series_paths, series_chain
from core.project_library import plugin_facts
from core.translation.run_memory import normalize_source
from core.translation.series_fill import registered_memories
from core.translation.series_memory import MEMORY_NAME, source_hash
from utils.logging_utils import log_debug


def _name_of(path: Path) -> str:
    """``Pokemon`` for ``Pokemon/_glossary/glossary.json``; the file stem for any other file."""
    return path.parent.parent.name if path.parent.name == "_glossary" and path.parent.parent.name else path.stem


def _terms_of(path: Path) -> int:
    """The number of entries of a series glossary file (0 when it is not a list)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return 0
    return len(data) if isinstance(data, list) else 0


def _memory_keys(memories: Dict[str, Path], own: Path) -> Set[str]:
    """The source hashes that some other project of the series has a translation for (its memory file's keys)."""
    keys: Set[str] = set()
    for memory in memories.values():
        if memory == own or not memory.is_file():
            continue
        try:
            rows_by_hash = json.loads(memory.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if not isinstance(rows_by_hash, dict):
            continue
        for key, rows in rows_by_hash.items():
            if isinstance(rows, list) and any(isinstance(row, dict) and str(row.get("translation") or "").strip() for row in rows):
                keys.add(key)
    return keys


def reusable_texts(project_file: Path, memories: Dict[str, Path], own: Path) -> Optional[int]:
    """How many of the project's strings another project of the series has translated (same normalised text).

    Counts strings, not distinct texts. None when the project's strings cannot be read (plugin missing, file missing).
    """
    keys = _memory_keys(memories, own)
    if not keys:
        return 0
    try:
        strings = plugin_facts.project_block_strings(project_file)
    except Exception as error:  # the Project Manager shows a dash; the scan goes on
        log_debug(f"Series facts: strings of {project_file} not read: {error}")
        return None
    if strings is None:
        return None
    return sum(1 for _, _, source, _ in strings["blocks"] for text in source
               if isinstance(text, str) and normalize_source(text) and source_hash(text) in keys)


def _signature(project_file: Path, memories: Dict[str, Path], own: Path) -> str:
    """Changes when the project file or any other project's memory changes: the reusable count is then read again."""
    stat = project_file.stat()
    parts = [f"{stat.st_mtime_ns}:{stat.st_size}"]
    for name, memory in sorted(memories.items()):
        if memory != own and memory.is_file():
            state = memory.stat()
            parts.append(f"{name}:{state.st_mtime_ns}:{state.st_size}")
    return "|".join(parts)


def series_facts(project_file: str, cached: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """``{"files": [{"path", "name", "terms", "mtime_ns", "size"}], "terms": n, "link", "reusable", "signature"}``.

    ``link``: ``"linked"`` (the project names a series glossary), ``"folders"`` (found in the folders above) or
    ``"none"``. ``reusable``: the strings other projects of the series translated (None when not read).
    ``cached`` is the last answer. A file whose modification time and size are unchanged keeps its term count, so a
    chain that did not change is not read again; the reusable count is kept while ``signature`` is unchanged.
    """
    project_file = str(project_file)
    try:
        metadata = json.loads(Path(project_file).read_text(encoding="utf-8-sig")).get("metadata") or {}
    except (OSError, ValueError, AttributeError) as error:
        log_debug(f"Series facts: {project_file} not read: {error}")
        return {"files": [], "terms": 0, "link": "none", "reusable": None, "signature": ""}
    project_path = Path(project_file)
    previous = {entry.get("path"): entry for entry in (cached or {}).get("files") or [] if isinstance(entry, dict)}
    files: List[Dict[str, Any]] = []
    for path in series_chain(SimpleNamespace(metadata=metadata), project_path.parent):
        if not path.is_file():
            continue
        stat = path.stat()
        old = previous.get(str(path))
        reused = old is not None and old.get("mtime_ns") == stat.st_mtime_ns and old.get("size") == stat.st_size
        terms = int(old["terms"]) if reused and isinstance(old.get("terms"), int) else _terms_of(path)
        files.append({"path": str(path), "name": _name_of(path), "terms": terms,
                      "mtime_ns": stat.st_mtime_ns, "size": stat.st_size})
    own = project_path.parent / MEMORY_NAME
    memories = registered_memories(series_chain(SimpleNamespace(metadata=metadata), project_path.parent))
    signature = _signature(project_path, memories, own)
    if cached and cached.get("signature") == signature and "reusable" in cached:
        reusable = cached.get("reusable")
    else:
        reusable = reusable_texts(project_path, memories, own)
    if linked_series_paths(SimpleNamespace(metadata=metadata)):
        link = "linked"
    else:
        link = "folders" if files else "none"
    return {"files": files, "terms": sum(entry["terms"] for entry in files), "link": link,
            "reusable": reusable, "signature": signature}
