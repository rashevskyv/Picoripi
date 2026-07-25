"""Project-local additions and title overrides for the Story hierarchy."""

from __future__ import annotations

import uuid

from core.mempalace.story_timeline import StoryVirtualFolder, StoryVirtualProjection


METADATA_KEY = "manual_story_structures"


def _metadata(project) -> dict:
    metadata = getattr(project, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
        project.metadata = metadata
    value = metadata.setdefault(METADATA_KEY, {"version": 1, "nodes": []})
    if not isinstance(value, dict):
        value = {"version": 1, "nodes": []}
        metadata[METADATA_KEY] = value
    value.setdefault("version", 1)
    value.setdefault("nodes", [])
    return value


def add_manual_story_node(project, title: str, node_type: str, parent_id=None) -> str:
    node_id = f"manual:{uuid.uuid4().hex}"
    _metadata(project)["nodes"].append({
        "id": node_id,
        "title": str(title).strip(),
        "node_type": str(node_type).strip().casefold(),
        "parent_id": parent_id,
        "manual": True,
    })
    return node_id


def rename_story_node(project, node_id, title: str) -> None:
    nodes = _metadata(project)["nodes"]
    entry = next((node for node in nodes if str(node.get("id")) == str(node_id)), None)
    if entry is None:
        entry = {"id": node_id, "manual": False}
        nodes.append(entry)
    entry["title"] = str(title).strip()


def set_story_node_positions(project, positions) -> None:
    """Persist the exact parent and sibling order shown by the editor tree."""
    nodes = _metadata(project)["nodes"]
    by_id = {str(node.get("id")): node for node in nodes}
    for node_id, parent_id, order in positions:
        if node_id is None:
            continue
        key = str(node_id)
        entry = by_id.get(key)
        if entry is None:
            entry = {"id": node_id, "manual": False}
            nodes.append(entry)
            by_id[key] = entry
        entry["parent_id"] = parent_id
        entry["order"] = int(order)


def remove_story_nodes(project, node_ids, removed_paths=()) -> None:
    """Hide a Story subtree and detach rows explicitly assigned to it."""
    node_ids = [node_id for node_id in node_ids if node_id is not None]
    ids = {str(node_id) for node_id in node_ids}
    nodes = _metadata(project)["nodes"]
    by_id = {str(node.get("id")): node for node in nodes}
    for node_id in node_ids:
        key = str(node_id)
        entry = by_id.get(key)
        if entry is None:
            entry = {"id": node_id, "manual": False}
            nodes.append(entry)
            by_id[key] = entry
        entry["removed"] = True

    paths = [list(path or ()) for path in removed_paths if path]
    for block in getattr(project, "blocks", []) or []:
        assignments = getattr(block, "metadata", {}).get(
            "story_context_assignments", {}
        )
        for assignment in assignments.values():
            structure_id = assignment.get("structure_id")
            path = list(assignment.get("structure_path") or ())
            path_removed = any(path[:len(prefix)] == prefix for prefix in paths)
            if str(structure_id) in ids or path_removed:
                assignment["structure_id"] = "story:none"
                assignment["structure_path"] = []


def update_assigned_story_paths(project, old_path, new_path) -> None:
    """Keep manually assigned row paths aligned after an ancestor rename."""
    old_path = list(old_path or ())
    new_path = list(new_path or ())
    if not old_path:
        return
    for block in getattr(project, "blocks", []) or []:
        assignments = getattr(block, "metadata", {}).get("story_context_assignments", {})
        for assignment in assignments.values():
            path = list(assignment.get("structure_path") or ())
            if path[:len(old_path)] == old_path:
                assignment["structure_path"] = new_path + path[len(old_path):]


def apply_manual_story_structures(projection, project):
    """Return a projection with project-local additions and title overrides."""
    if not isinstance(projection, StoryVirtualProjection) or project is None:
        return projection
    metadata = getattr(project, "metadata", None)
    stored = metadata.get(METADATA_KEY) if isinstance(metadata, dict) else None
    nodes = list(stored.get("nodes", [])) if isinstance(stored, dict) else []
    if not nodes:
        return projection

    overrides = {str(node.get("id")): node for node in nodes}
    records = {}

    def collect(folder, parent_id=None, order=0):
        key = str(folder.id)
        records[key] = {
            "id": folder.id,
            "title": folder.title,
            "node_type": folder.node_type,
            "mappings": folder.mappings,
            "default_parent_id": parent_id,
            "default_order": order,
        }
        for child_order, child in enumerate(folder.children):
            collect(child, folder.id, child_order)

    for root_order, root in enumerate(projection.roots):
        collect(root, None, root_order)

    for order, node in enumerate(value for value in nodes if value.get("manual")):
        key = str(node.get("id"))
        records.setdefault(key, {
            "id": node.get("id"),
            "title": str(node.get("title") or "Untitled"),
            "node_type": str(node.get("node_type") or "chapter"),
            "mappings": (),
            "default_parent_id": node.get("parent_id"),
            "default_order": 1_000_000 + order,
        })

    active = {
        key: record for key, record in records.items()
        if not overrides.get(key, {}).get("removed")
    }
    children_by_parent = {}
    for key, record in active.items():
        entry = overrides.get(key, {})
        parent_id = (
            entry.get("parent_id")
            if "parent_id" in entry
            else record["default_parent_id"]
        )
        parent_key = None if parent_id is None else str(parent_id)
        if parent_key == key or parent_key not in active:
            parent_key = None
        order = entry.get("order", record["default_order"])
        children_by_parent.setdefault(parent_key, []).append((int(order), key))

    for siblings in children_by_parent.values():
        siblings.sort(key=lambda value: (
            value[0],
            str(overrides.get(value[1], {}).get(
                "title", active[value[1]]["title"]
            )).casefold(),
        ))

    def build(key, ancestry):
        if key in ancestry:
            return None
        record = active[key]
        entry = overrides.get(key, {})
        children = [
            child for child in (
                build(child_key, ancestry | {key})
                for _order, child_key in children_by_parent.get(key, ())
            )
            if child is not None
        ]
        return StoryVirtualFolder(
            record["id"],
            str(entry.get("node_type") or record["node_type"]),
            str(entry.get("title") or record["title"]),
            tuple(children),
            record["mappings"],
        )

    roots = [
        folder for folder in (
            build(key, set()) for _order, key in children_by_parent.get(None, ())
        )
        if folder is not None
    ]
    return StoryVirtualProjection(
        projection.document_id, tuple(roots), projection.speakers
    )
