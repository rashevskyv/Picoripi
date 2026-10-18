"""Give the rows of an older translation memory the context they were made under (D41, OPEN_ITEMS 4.2).

A row saved before D41 has no speaker, addressee or fold key, so a repeated text does not restore from it. This module
plans the rewrite of the rows from the saved translations (the position backup): a row with the same source and
translation as a saved position takes that position's context. The plan does not touch the input; the write keeps the
previous file as ``translation_memory.before_context.json`` (written once) and replaces the memory atomically.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from core.translation.series_memory import source_hash
from utils.atomic_io import atomic_write_json

BACKUP_NAME = "translation_memory.before_context.json"


# The context fields a memory row keeps. A context may carry more (``fold_legacy``, D46) that is only compared.
STORED_CONTEXT_KEYS = ("speaker", "addressee", "fold", "speaker_en")


def stored_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """The part of a context that a memory row keeps."""
    return {key: context[key] for key in STORED_CONTEXT_KEYS if key in context}


def same_context(row: Dict[str, Any], context: Optional[Dict[str, Any]]) -> bool:
    """Whether a memory row was made under ``context`` (its fold).

    A context of a plugin with a duplicate context (D46) also carries ``fold_legacy``: the fold a row saved
    before that context has. Such a row is the same context at its own place, so it still matches here.
    """
    if not context or not row.get("fold"):
        return False
    return row["fold"] in (context.get("fold"), context.get("fold_legacy"))


@dataclass(frozen=True)
class SavedPlace:
    """A string that has a saved translation: its place, source text and saved text."""

    block: int
    string: int
    source: str
    translation: str


@dataclass
class RebuildResult:
    """The planned memory, and what the plan changed."""

    memory: Dict[str, List[Dict[str, Any]]]
    updated: int = 0      # a legacy row took its context
    split: int = 0        # a further context of a legacy text got its own row
    tagged: int = 0       # a row got the tag kinds of its source
    missing: int = 0      # a saved place with no matching row (left as it is)
    cancelled: bool = False


def places_of(data: Sequence[Any], block_prefixes: Sequence[str], saved: Dict[str, str]) -> List[SavedPlace]:
    """The places with a saved translation. ``block_prefixes[b]`` is the saved-key prefix of block ``b``."""
    places: List[SavedPlace] = []
    for block_idx, block in enumerate(data):
        if not isinstance(block, list) or block_idx >= len(block_prefixes):
            continue
        prefix = block_prefixes[block_idx]
        for string_idx, source in enumerate(block):
            text = saved.get(f"{prefix}{string_idx}")
            if isinstance(source, str) and isinstance(text, str) and text.strip():
                places.append(SavedPlace(block_idx, string_idx, source, text))
    return places


def place_context(context_for: Callable[[int, int, str], Optional[Dict[str, str]]]) -> Callable[[SavedPlace], Optional[Dict[str, str]]]:
    """The manager's ``context_for(block, string, source)`` as the ``context_for(place)`` that ``plan_rebuild`` calls."""
    return lambda place: context_for(place.block, place.string, place.source)


def plan_rebuild(
    memory: Dict[str, List[Dict[str, Any]]],
    places: Sequence[SavedPlace],
    repeats: Callable[[str], bool],
    context_for: Callable[[SavedPlace], Optional[Dict[str, str]]],
    tag_fields_for: Callable[[str], Dict[str, Any]],
    should_cancel: Callable[[], bool] = lambda: False,
    report: Callable[[int, int], None] = lambda done, total: None,
) -> RebuildResult:
    """The memory with the context and tag kinds of ``places`` written into its rows; the input is not changed.

    ``repeats(source)``: the source text sits at more than one place (only then the context matters).
    ``context_for(place)``: ``{"speaker", "addressee", "fold"}`` of the place, or None.
    ``tag_fields_for(source)``: the tag kinds a row of the source keeps (``{}`` without a tag map).
    One row per context: a legacy row takes the first context, every further context gets its own row.
    """
    result = RebuildResult(memory=copy.deepcopy(memory))
    total = len(places)
    for done, place in enumerate(places):
        if should_cancel():
            result.cancelled = True
            return result
        report(done, total)
        rows = result.memory.get(source_hash(place.source), [])
        matches = [row for row in rows if row.get("source") == place.source and row.get("translation") == place.translation]
        if not matches:
            result.missing += 1
            continue
        tags = tag_fields_for(place.source)
        context = context_for(place) if repeats(place.source) else None
        if context is None:
            for row in matches:
                if tags and not row.get("tags"):
                    row.update(tags)
                    result.tagged += 1
            continue
        if any(same_context(row, context) for row in matches):
            continue
        saved = stored_context(context)
        legacy = [row for row in matches if not row.get("fold")]
        if legacy:
            legacy[0].update(saved)
            if tags and not legacy[0].get("tags"):
                legacy[0].update(tags)
            result.updated += 1
        else:
            rows.append({"source": place.source, "translation": place.translation, **saved, **tags})
            result.split += 1
    report(total, total)
    return result


def write_rebuilt(path: Path, memory: Dict[str, List[Dict[str, Any]]]) -> Path:
    """Write ``memory`` to ``path`` atomically. The previous file is kept as ``BACKUP_NAME`` beside it (once).

    Returns the backup path. A backup that already exists is kept: it is the memory before the first rebuild.
    """
    path = Path(path)
    backup = path.with_name(BACKUP_NAME)
    if path.is_file() and not backup.exists():
        temp = backup.with_name(backup.name + ".tmp")
        shutil.copyfile(path, temp)
        os.replace(temp, backup)
    atomic_write_json(path, memory, ensure_ascii=False, indent=1)
    return backup


def restore_backup(path: Path) -> bool:
    """Put the memory back from ``BACKUP_NAME`` (the backup is kept). False when there is no backup."""
    path = Path(path)
    backup = path.with_name(BACKUP_NAME)
    if not backup.is_file():
        return False
    temp = path.with_name(path.name + ".tmp")
    shutil.copyfile(backup, temp)
    os.replace(temp, path)
    return True


def load_memory(path: Path) -> Optional[Dict[str, List[Dict[str, Any]]]]:
    """The memory file as a dict, or None when it is missing or not one."""
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def counts_of(data: Sequence[Any]) -> Dict[str, int]:
    """How many places hold each source text (``repeats`` is ``count > 1``)."""
    counts: Dict[str, int] = {}
    for block in data:
        if isinstance(block, list):
            for source in block:
                if isinstance(source, str):
                    counts[source] = counts.get(source, 0) + 1
    return counts


def repeats_of(counts: Dict[str, int]) -> Callable[[str], bool]:
    """The ``repeats`` test of ``plan_rebuild`` for a count table."""
    return lambda source: counts.get(source, 0) > 1
