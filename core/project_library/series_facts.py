"""The series glossaries a project uses, and how many terms they hold: read by the Project Manager's scan for the details of
a project. Read only: the project file, the series glossaries and the folders above the project are never written."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from core.glossary.series import series_chain
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


def series_facts(project_file: str, cached: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """``{"files": [{"path", "name", "terms", "mtime_ns", "size"}], "terms": n}`` for the project's series chain.

    ``cached`` is the last answer. A file whose modification time and size are unchanged keeps its term count, so a
    chain that did not change is not read again.
    """
    project_file = str(project_file)
    try:
        metadata = json.loads(Path(project_file).read_text(encoding="utf-8-sig")).get("metadata") or {}
    except (OSError, ValueError, AttributeError) as error:
        log_debug(f"Series facts: {project_file} not read: {error}")
        return {"files": [], "terms": 0}
    previous = {entry.get("path"): entry for entry in (cached or {}).get("files") or [] if isinstance(entry, dict)}
    files: List[Dict[str, Any]] = []
    for path in series_chain(SimpleNamespace(metadata=metadata), Path(project_file).parent):
        if not path.is_file():
            continue
        stat = path.stat()
        old = previous.get(str(path))
        reused = old is not None and old.get("mtime_ns") == stat.st_mtime_ns and old.get("size") == stat.st_size
        terms = int(old["terms"]) if reused and isinstance(old.get("terms"), int) else _terms_of(path)
        files.append({"path": str(path), "name": _name_of(path), "terms": terms,
                      "mtime_ns": stat.st_mtime_ns, "size": stat.st_size})
    return {"files": files, "terms": sum(entry["terms"] for entry in files)}
