"""Normalize Markup Studio hierarchy projects into story nodes / reference items."""

from __future__ import annotations

from collections import defaultdict
import json

from core.script_markup import (
    HierarchyProject,
    HierarchyType,
    build_hierarchy_tree,
    mark_text,
)
from core.script_markup.hierarchy_markup import HierarchyMark
from core.mempalace.timeline.models import ReferenceItem, StoryNode


def story_stable_id_for_mark(mark: HierarchyMark) -> str:
    """Return the normalized story id used when a hierarchy mark is imported."""
    return _stable_id(mark, _story_node_type(mark))

_SKIPPED_TYPES = {
    HierarchyType.GLOSSARY,
    HierarchyType.BREAKER,
    HierarchyType.IGNORE,
    HierarchyType.UNMARKED,
    HierarchyType.ITEM,
    HierarchyType.ITEM_DESCRIPTION,
}

def normalize_reference_items(project: HierarchyProject) -> tuple[ReferenceItem, ...]:
    """Build non-dialogue catalogue records from Item -> Item Description nodes."""
    lines = project.raw_text.splitlines()
    root = build_hierarchy_tree(project.approved_marks)
    items: list[ReferenceItem] = []

    def visit(node) -> None:
        mark = node.mark
        if mark is not None and mark.type_id == HierarchyType.ITEM:
            descriptions = [
                _marked_text(child.mark, lines)
                for child in node.children
                if child.mark is not None
                and child.mark.type_id == HierarchyType.ITEM_DESCRIPTION
            ]
            descriptions = [value for value in descriptions if value]
            end_line = max(
                [mark.end_line]
                + [
                    child.mark.end_line
                    for child in node.children
                    if child.mark is not None
                    and child.mark.type_id == HierarchyType.ITEM_DESCRIPTION
                ]
            )
            payload = json.dumps(
                {
                    "item": _mark_payload(mark),
                    "descriptions": [
                        _mark_payload(child.mark)
                        for child in node.children
                        if child.mark is not None
                        and child.mark.type_id == HierarchyType.ITEM_DESCRIPTION
                    ],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            items.append(ReferenceItem(
                stable_id=_stable_id(mark, "item"),
                order_index=len(items),
                name=_marked_text(mark, lines),
                description="\n".join(descriptions),
                start_line=mark.start_line,
                end_line=end_line,
                origin=mark.origin,
                source_payload=payload,
                source_version=project.version,
            ))
        for child in node.children:
            visit(child)

    visit(root)
    return tuple(items)

def normalize_hierarchy_project(project: HierarchyProject) -> tuple[StoryNode, ...]:
    """Convert approved hierarchy marks into a deterministic flat story tree."""
    lines = project.raw_text.splitlines()
    depth_stack: dict[int, StoryNode] = {}
    sibling_counts: defaultdict[str | None, int] = defaultdict(int)
    nodes: list[StoryNode] = []

    for mark in project.approved_marks:
        if mark.type_id in _SKIPPED_TYPES:
            continue

        node_type = _story_node_type(mark)
        content = _marked_text(mark, lines)
        stable_id = _stable_id(mark, node_type)
        parent = next(
            (depth_stack[depth] for depth in range(mark.depth - 1, -1, -1) if depth in depth_stack),
            None,
        )
        parent_stable_id = parent.stable_id if parent else None
        order_index = sibling_counts[parent_stable_id]
        sibling_counts[parent_stable_id] += 1

        title = None
        text = None
        if node_type in {"act", "chapter", "scene"}:
            title = mark.label.strip() or content
        elif node_type == "speaker":
            title = content or mark.label.strip()
        else:
            text = content

        payload = json.dumps(
            {
                "start_line": mark.start_line,
                "end_line": mark.end_line,
                "start_col": mark.start_col,
                "end_col": mark.end_col,
                "depth": mark.depth,
                "type_id": mark.type_id,
                "text": mark.text,
                "label": mark.label,
                "description": mark.description,
                "order": mark.order,
                "origin": mark.origin,
                "approved": mark.approved,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        node = StoryNode(
            stable_id=stable_id,
            parent_stable_id=parent_stable_id,
            node_type=node_type,
            order_index=order_index,
            title=title or None,
            text=text or None,
            start_line=mark.start_line,
            end_line=mark.end_line,
            start_column=mark.start_col,
            end_column=mark.end_col,
            origin=mark.origin,
            source_payload=payload,
            source_version=project.version,
        )
        nodes.append(node)
        depth_stack[mark.depth] = node
        for depth in tuple(depth_stack):
            if depth > mark.depth:
                del depth_stack[depth]

    return tuple(nodes)

def _story_node_type(mark: HierarchyMark) -> str:
    if mark.type_id == HierarchyType.STRUCTURE:
        return {0: "act", 1: "chapter"}.get(mark.depth, "scene")
    return {
        HierarchyType.SPEAKER: "speaker",
        HierarchyType.TEXT: "dialogue",
        HierarchyType.ACTION: "action",
        HierarchyType.CONTEXT: "context",
        HierarchyType.NARRATOR: "narrator",
    }.get(mark.type_id, "context")

def _stable_id(mark: HierarchyMark, node_type: str) -> str:
    start_col = "" if mark.start_col is None else str(mark.start_col)
    end_col = "" if mark.end_col is None else str(mark.end_col)
    return (
        f"{node_type}:{mark.depth}:{mark.start_line}:{start_col}:"
        f"{mark.end_line}:{end_col}:{mark.order}"
    )

def _marked_text(mark: HierarchyMark, lines: list[str]) -> str:
    # Markup Studio keeps ``mark.text`` as editing/history metadata.  After a
    # mark is moved or the raw script is edited that cache may describe the old
    # range.  The canonical renderer already knows which node types may use an
    # explicit value (assigned speakers/headings) and which must be read from
    # the current source range.  Reuse it here so MemPalace can never combine
    # fresh coordinates with stale dialogue text.
    return mark_text(mark, lines).strip()

def _mark_payload(mark: HierarchyMark) -> dict:
    return {
        "start_line": mark.start_line,
        "end_line": mark.end_line,
        "start_col": mark.start_col,
        "end_col": mark.end_col,
        "depth": mark.depth,
        "type_id": mark.type_id,
        "text": mark.text,
        "label": mark.label,
        "description": mark.description,
        "order": mark.order,
        "origin": mark.origin,
        "approved": mark.approved,
    }
