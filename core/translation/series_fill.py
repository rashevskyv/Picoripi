"""Series glossary terms written into the other projects of a series (D45, item 1).

A project that is not open cannot take a term in its editor. Its term goes into its backup, ``saved_translations.json``,
which its Restore action reads. Only a string the project does not translate yet is written: the translation file is
read first (``plugin_facts.project_block_strings``), so a translation the owner already made is never offered a
replacement. The first write keeps a copy of the backup (``saved_translations.before_terms.json``). Writes are atomic.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from core.glossary.term_fill import FILL, build_term_table, plan_fills
from core.project_library import plugin_facts
from core.translation.series_memory import REGISTRY_NAME, source_hash
from plugins.common.tag_logic import TAG_STATUS_OK, compare_tags
from utils.atomic_io import atomic_write_json
from utils.logging_utils import log_warning

SAVED_NAME = "saved_translations.json"
BEFORE_NAME = "saved_translations.before_terms.json"


def registered_memories(chain: Iterable[Path]) -> Dict[str, Path]:
    """``project name -> translation memory file`` of every project registered beside the series glossaries of ``chain``."""
    found: Dict[str, Path] = {}
    for series_file in chain:
        path = Path(series_file).parent / REGISTRY_NAME
        if not path.is_file():
            continue
        try:
            registry = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            log_warning(f"Series fill: cannot read {path}: {exc}")
            continue
        if not isinstance(registry, dict):
            continue
        for name, memory in registry.items():
            if isinstance(memory, str):
                found.setdefault(str(name), Path(memory))
    return found


def project_file_in(project_dir: Path) -> Optional[Path]:
    """The ``.uiproj`` of a project folder (the first in name order), or None."""
    files = sorted(Path(project_dir).glob("*.uiproj"))
    return files[0] if files else None


def saved_key(source_file: str, internal_key: str, index: int) -> str:
    """The key of one string in ``saved_translations.json``: the same form ``SavedTranslationsManager`` writes."""
    return f"{source_file}::{internal_key}::{index}"


def write_backup(project_dir: Path, entries: Dict[str, str]) -> Dict[str, int]:
    """Add ``entries`` to the project's ``saved_translations.json`` where the key is absent or empty.

    Returns ``{"written": n, "kept": n}``: an existing non-empty entry is kept, never replaced.
    """
    path = Path(project_dir) / SAVED_NAME
    saved: Dict[str, Any] = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"cannot read {path}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ValueError(f"{path} is not an object")
        saved = loaded
    to_write = {key: text for key, text in entries.items() if not str(saved.get(key) or "").strip()}
    counts = {"written": len(to_write), "kept": len(entries) - len(to_write)}
    if not to_write:
        return counts
    if path.is_file() and not (Path(project_dir) / BEFORE_NAME).exists():
        shutil.copy2(path, Path(project_dir) / BEFORE_NAME)
    saved.update(to_write)
    atomic_write_json(path, saved, ensure_ascii=False, indent=4)
    return counts


def fill_project(project_dir: Path, entries: List[Tuple[str, str]], should_cancel: Callable[[], bool]) -> Dict[str, Any]:
    """Plan the series terms for one project and write its untranslated lines into the backup.

    ``entries``: the series glossary ``(term, translation)`` pairs. The tag kinds are the project's own plugin's.
    Returns ``{"status": ...}`` and, when done, the counts per fill status plus ``refused`` (tags) and the width note.
    """
    project_file = project_file_in(project_dir)
    if project_file is None:
        return {"status": "no project file"}
    strings = plugin_facts.project_block_strings(project_file, is_cancelled=should_cancel)
    if strings is None:
        return {"status": "cancelled"}
    rules = plugin_facts.default_load_rules(strings["plugin"])
    getter = getattr(rules, "get_series_tag_map", None)
    tag_map = getter() if callable(getter) else None
    table = build_term_table(entries, tag_map)
    wanted = {source_hash(term) for term, _ in table.by_key.values()}
    wanted |= {source_hash(pairs[0][0]) for pairs in table.conflicts.values()}
    if not wanted:
        return {"status": "no terms"}
    rows: List[Tuple[int, int, str, str, bool]] = []
    keys: List[str] = []
    for source_file, internal_key, source, translation in strings["blocks"]:
        if should_cancel():
            return {"status": "cancelled"}
        for index, text in enumerate(source):
            if not isinstance(text, str) or source_hash(text) not in wanted:
                continue
            current = translation[index] if translation and index < len(translation) and isinstance(translation[index], str) else ""
            translated = bool(current.strip()) and current.strip() != text.strip()
            # block_idx of a row is its position in ``keys``: the row list is the caller's, not the editor's
            rows.append((len(keys), 0, text, current, translated))
            keys.append(saved_key(source_file, internal_key, index))
    fills = plan_fills(table, rows, tag_map)
    by_status: Dict[str, int] = {}
    refused = 0
    to_write: Dict[str, str] = {}
    for fill in fills:
        by_status[fill.status] = by_status.get(fill.status, 0) + 1
        if fill.status != FILL:
            continue
        if compare_tags(fill.translation, fill.source)[0] != TAG_STATUS_OK:
            refused += 1
            continue
        to_write[keys[fill.block_idx]] = fill.translation
    counts = write_backup(project_dir, to_write)
    return {"status": "done", "planned": len(fills), "by_status": by_status, "refused_tags": refused,
            "written": counts["written"], "kept": counts["kept"], "width_checked": False}
