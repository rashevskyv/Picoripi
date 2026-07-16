"""Project-local Story Context assignments for game strings without script links."""

from __future__ import annotations

from typing import Any


METADATA_KEY = "story_context_assignments"


def project_block_for_data_index(mw: Any, block_idx: int):
    """Return the project block that owns one data-store block index."""
    manager = getattr(mw, "project_manager", None)
    project = getattr(manager, "project", None) if manager else None
    if project is None:
        return None
    project_idx = getattr(mw, "block_to_project_file_map", {}).get(block_idx, block_idx)
    try:
        return project.blocks[project_idx]
    except (IndexError, KeyError, TypeError):
        return None


def get_story_context_override(mw: Any, block_idx: int, string_idx: int) -> dict:
    """Return a copy of the manual Story Context assignment for one row."""
    block = project_block_for_data_index(mw, block_idx)
    if block is None:
        return {}
    value = block.metadata.get(METADATA_KEY, {}).get(str(string_idx), {})
    return dict(value) if isinstance(value, dict) else {}


def update_story_context_override(
    mw: Any,
    block_idx: int,
    string_idx: int,
    **changes: Any,
) -> bool:
    """Update selected override fields and remove the row entry when it becomes empty."""
    block = project_block_for_data_index(mw, block_idx)
    if block is None:
        return False
    assignments = block.metadata.setdefault(METADATA_KEY, {})
    key = str(string_idx)
    value = dict(assignments.get(key, {}))
    for field, new_value in changes.items():
        if new_value is None or new_value == "" or new_value == () or new_value == []:
            value.pop(field, None)
        else:
            value[field] = new_value
    if value:
        assignments[key] = value
    else:
        assignments.pop(key, None)
    if not assignments:
        block.metadata.pop(METADATA_KEY, None)
    return True


def iter_story_context_overrides(mw: Any):
    """Yield ``(data_block_idx, string_idx, assignment)`` for all manual rows."""
    manager = getattr(mw, "project_manager", None)
    project = getattr(manager, "project", None) if manager else None
    if project is None:
        return
    block_map = getattr(mw, "block_to_project_file_map", {})
    project_to_data = {project_idx: data_idx for data_idx, project_idx in block_map.items()}
    for project_idx, block in enumerate(project.blocks):
        data_idx = project_to_data.get(project_idx, project_idx)
        assignments = block.metadata.get(METADATA_KEY, {})
        if not isinstance(assignments, dict):
            continue
        for string_idx, value in assignments.items():
            if not isinstance(value, dict):
                continue
            try:
                yield data_idx, int(string_idx), dict(value)
            except (TypeError, ValueError):
                continue
