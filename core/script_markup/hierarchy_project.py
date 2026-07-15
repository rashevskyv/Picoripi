"""Validated, UI-independent import contract for hierarchy markup projects."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .hierarchy_ai_jobs import HIERARCHY_FORMAT_VERSION, HIERARCHY_PROJECT_FORMAT
from .hierarchy_markup import HierarchyMark, HierarchyType, HierarchyTypeDefinition


class HierarchyProjectError(ValueError):
    """Raised when a hierarchy project does not satisfy the import contract."""


class HierarchyImportStatus(str, Enum):
    """Persistent source state shown by MemPalace Builder."""

    NOT_IMPORTED = "Not imported"
    UP_TO_DATE = "Up to date"
    SOURCE_CHANGED = "Source changed"
    IMPORT_ERROR = "Import error"


@dataclass(frozen=True)
class HierarchyProject:
    """A validated snapshot of ``script_markup_project.json``."""

    format: str
    version: int
    source_path: str
    raw_source_path: str
    source_hash: str
    raw_text: str
    type_definitions: tuple[HierarchyTypeDefinition, ...]
    hierarchy_marks: tuple[HierarchyMark, ...]
    unapproved_marks: tuple[HierarchyMark, ...]

    @property
    def approved_marks(self) -> tuple[HierarchyMark, ...]:
        return tuple(mark for mark in self.hierarchy_marks if mark.approved)

    def node_counts(self) -> dict[str, int]:
        """Return stable user-facing counts for approved importable nodes."""

        counts: Counter[str] = Counter()
        for mark in self.approved_marks:
            if mark.type_id == HierarchyType.STRUCTURE:
                counts[{0: "act", 1: "chapter", 2: "scene"}.get(mark.depth, "structure")] += 1
            elif mark.type_id == HierarchyType.SPEAKER:
                counts["speaker"] += 1
            elif mark.type_id == HierarchyType.TEXT:
                counts["dialogue"] += 1
            elif mark.type_id == HierarchyType.GLOSSARY:
                counts["glossary"] += 1
            elif mark.type_id == HierarchyType.ITEM:
                counts["item"] += 1
            elif mark.type_id == HierarchyType.ITEM_DESCRIPTION:
                counts["item_description"] += 1
        return {
            key: counts[key]
            for key in (
                "act", "chapter", "scene", "structure", "speaker", "dialogue",
                "glossary", "item", "item_description",
            )
        }


def _require_object(value: Any, field: str) -> dict:
    if not isinstance(value, dict):
        raise HierarchyProjectError(f"{field} must be an object.")
    return value


def _require_list(value: Any, field: str) -> list:
    if not isinstance(value, list):
        raise HierarchyProjectError(f"{field} must be an array.")
    return value


def _require_string(value: Any, field: str, *, allow_empty: bool = True) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        suffix = " a non-empty string" if not allow_empty else " a string"
        raise HierarchyProjectError(f"{field} must be{suffix}.")
    return value


def _require_int(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise HierarchyProjectError(f"{field} must be an integer >= {minimum}.")
    return value


def _optional_int(value: Any, field: str) -> int | None:
    if value is None:
        return None
    return _require_int(value, field)


def _parse_type_definitions(items: Any) -> tuple[HierarchyTypeDefinition, ...]:
    definitions: list[HierarchyTypeDefinition] = []
    seen: set[str] = set()
    for index, raw in enumerate(_require_list(items, "type_definitions")):
        item = _require_object(raw, f"type_definitions[{index}]")
        type_id = _require_string(item.get("type_id"), f"type_definitions[{index}].type_id", allow_empty=False)
        if type_id in seen:
            raise HierarchyProjectError(f"Duplicate type definition: {type_id}.")
        seen.add(type_id)
        definitions.append(HierarchyTypeDefinition(
            type_id=type_id,
            label=_require_string(item.get("label"), f"type_definitions[{index}].label", allow_empty=False),
            description=_require_string(item.get("description"), f"type_definitions[{index}].description"),
            color=_require_string(item.get("color"), f"type_definitions[{index}].color", allow_empty=False),
        ))
    if not definitions:
        raise HierarchyProjectError("type_definitions must not be empty.")
    return tuple(definitions)


def _parse_marks(items: Any, type_ids: set[str], raw_text: str) -> tuple[HierarchyMark, ...]:
    marks: list[HierarchyMark] = []
    line_count = len(raw_text.splitlines())
    for index, raw in enumerate(_require_list(items, "hierarchy_marks")):
        item = _require_object(raw, f"hierarchy_marks[{index}]")
        prefix = f"hierarchy_marks[{index}]"
        start = _require_int(item.get("start_line"), f"{prefix}.start_line")
        end = _require_int(item.get("end_line"), f"{prefix}.end_line")
        if end < start:
            raise HierarchyProjectError(f"{prefix}.end_line must be >= start_line.")
        if line_count == 0 or end >= line_count:
            raise HierarchyProjectError(f"{prefix} points outside raw_text ({line_count} lines).")
        type_id = _require_string(item.get("type_id"), f"{prefix}.type_id", allow_empty=False)
        if type_id not in type_ids:
            raise HierarchyProjectError(f"{prefix}.type_id references unknown type {type_id!r}.")
        approved = item.get("approved")
        if not isinstance(approved, bool):
            raise HierarchyProjectError(f"{prefix}.approved must be a boolean.")
        origin = _require_string(item.get("origin"), f"{prefix}.origin", allow_empty=False)
        start_col = _optional_int(item.get("start_col"), f"{prefix}.start_col")
        end_col = _optional_int(item.get("end_col"), f"{prefix}.end_col")
        if start_col is not None and end_col is not None and end_col < start_col:
            raise HierarchyProjectError(f"{prefix}.end_col must be >= start_col.")
        marks.append(HierarchyMark(
            start_line=start,
            end_line=end,
            depth=_require_int(item.get("depth"), f"{prefix}.depth"),
            type_id=type_id,
            text=_require_string(item.get("text", ""), f"{prefix}.text"),
            label=_require_string(item.get("label", ""), f"{prefix}.label"),
            description=_require_string(item.get("description", ""), f"{prefix}.description"),
            color=_require_string(item.get("color", ""), f"{prefix}.color"),
            order=_require_int(item.get("order", 0), f"{prefix}.order"),
            start_col=start_col,
            end_col=end_col,
            origin=origin,
            approved=approved,
        ))
    return tuple(sorted(marks, key=lambda mark: (mark.start_line, mark.depth, mark.order)))


def parse_hierarchy_project(
    payload: Any,
    *,
    source_path: str = "",
    source_hash: str = "",
) -> HierarchyProject:
    """Validate an already decoded hierarchy project payload."""

    data = _require_object(payload, "project")
    project_format = _require_string(data.get("format"), "format", allow_empty=False)
    if project_format != HIERARCHY_PROJECT_FORMAT:
        raise HierarchyProjectError(
            f"Unsupported format {project_format!r}; expected {HIERARCHY_PROJECT_FORMAT!r}."
        )
    version = _require_int(data.get("version"), "version", minimum=1)
    if version != HIERARCHY_FORMAT_VERSION:
        raise HierarchyProjectError(
            f"Unsupported hierarchy project version {version}; supported version is {HIERARCHY_FORMAT_VERSION}."
        )
    raw_text = _require_string(data.get("raw_text"), "raw_text")
    definitions = _parse_type_definitions(data.get("type_definitions"))
    marks = _parse_marks(data.get("hierarchy_marks"), {item.type_id for item in definitions}, raw_text)
    return HierarchyProject(
        format=project_format,
        version=version,
        source_path=source_path or str(data.get("source_path") or ""),
        raw_source_path=str(data.get("source_path") or ""),
        source_hash=source_hash,
        raw_text=raw_text,
        type_definitions=definitions,
        hierarchy_marks=marks,
        unapproved_marks=tuple(mark for mark in marks if not mark.approved),
    )


def load_hierarchy_project(path: str | Path) -> HierarchyProject:
    """Read and validate a hierarchy project without any UI dependency."""

    project_path = Path(path)
    try:
        raw_bytes = project_path.read_bytes()
    except OSError as exc:
        raise HierarchyProjectError(f"Could not read hierarchy project: {exc}") from exc
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HierarchyProjectError(f"Invalid UTF-8 JSON: {exc}") from exc
    return parse_hierarchy_project(
        payload,
        source_path=str(project_path.resolve()),
        source_hash=hashlib.sha256(raw_bytes).hexdigest(),
    )


def hierarchy_import_status(
    project: HierarchyProject | None,
    *,
    imported_path: str = "",
    imported_hash: str = "",
    imported_version: int | None = None,
) -> HierarchyImportStatus:
    """Compare a validated source snapshot with persisted import metadata."""

    if project is None or not imported_path or not imported_hash or imported_version is None:
        return HierarchyImportStatus.NOT_IMPORTED
    selected_path = os.path.normcase(os.path.abspath(project.source_path))
    saved_path = os.path.normcase(os.path.abspath(imported_path))
    if selected_path != saved_path:
        return HierarchyImportStatus.NOT_IMPORTED
    if project.source_hash != imported_hash or project.version != imported_version:
        return HierarchyImportStatus.SOURCE_CHANGED
    return HierarchyImportStatus.UP_TO_DATE
