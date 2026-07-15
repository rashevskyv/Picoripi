"""Normalize and synchronize Markup Studio hierarchy projects into SQLite."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
import sqlite3

from core.script_markup import HierarchyProject, HierarchyType, build_hierarchy_tree
from core.script_markup.hierarchy_markup import HierarchyMark


class StoryTimelineConflictError(RuntimeError):
    """Raised when source synchronization would remove a manual DB decision."""

    def __init__(
        self,
        source_stable_id: str,
        manual_stable_id: str,
        *,
        conflict_id: int | None = None,
    ) -> None:
        self.source_stable_id = source_stable_id
        self.manual_stable_id = manual_stable_id
        self.conflict_id = conflict_id
        super().__init__(str(self))

    def __str__(self) -> str:
        prefix = f"Conflict record #{self.conflict_id}: " if self.conflict_id else ""
        return (
            f"{prefix}cannot remove {self.source_stable_id!r}; manual node "
            f"{self.manual_stable_id!r} depends on it."
        )


@dataclass(frozen=True)
class StoryNode:
    stable_id: str
    parent_stable_id: str | None
    node_type: str
    order_index: int
    title: str | None
    text: str | None
    start_line: int
    end_line: int
    start_column: int | None
    end_column: int | None
    origin: str
    source_payload: str
    source_version: int


@dataclass(frozen=True)
class StoryTimelineSyncResult:
    document_id: int
    inserted_or_updated: int
    removed: int
    reference_items: int = 0
    reference_items_removed: int = 0


@dataclass(frozen=True)
class ReferenceItem:
    stable_id: str
    order_index: int
    name: str
    description: str
    start_line: int
    end_line: int
    origin: str
    source_payload: str
    source_version: int


@dataclass(frozen=True)
class ReferenceItemRecord:
    id: int
    stable_id: str
    document_id: int
    order_index: int
    name: str
    description: str
    start_line: int | None
    end_line: int | None


@dataclass(frozen=True)
class StoryNodeRecord:
    id: int
    stable_id: str
    document_id: int
    parent_id: int | None
    node_type: str
    order_index: int
    title: str | None
    text: str | None
    start_line: int | None
    end_line: int | None


@dataclass(frozen=True)
class StoryTimelinePosition:
    index: int
    total: int
    progress: float
    path: tuple[StoryNodeRecord, ...]


@dataclass(frozen=True)
class StorySyncConflictRecord:
    id: int
    document_id: int | None
    source_path: str
    source_hash: str
    conflict_type: str
    source_stable_id: str
    manual_stable_id: str
    details: str
    status: str
    created_at: str
    resolved_at: str | None


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


def sync_hierarchy_project(
    conn: sqlite3.Connection,
    project: HierarchyProject,
) -> StoryTimelineSyncResult:
    """Transactionally upsert one project and its normalized story tree."""
    nodes = normalize_hierarchy_project(project)
    reference_items = normalize_reference_items(project)
    savepoint = "mempalace_story_sync"
    conn.execute(f"SAVEPOINT {savepoint}")
    try:
        conn.execute(
            """
            INSERT INTO story_documents (
                source_path, source_hash, markup_format, markup_version
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(source_path) DO UPDATE SET
                source_hash = excluded.source_hash,
                markup_format = excluded.markup_format,
                markup_version = excluded.markup_version,
                imported_at = CURRENT_TIMESTAMP
            """,
            (project.source_path, project.source_hash, project.format, project.version),
        )
        document_id = conn.execute(
            "SELECT id FROM story_documents WHERE source_path = ?",
            (project.source_path,),
        ).fetchone()[0]

        wanted_reference_ids = {item.stable_id for item in reference_items}
        existing_reference_ids = {
            stable_id: row_id
            for row_id, stable_id in conn.execute(
                "SELECT id, stable_id FROM story_reference_items WHERE document_id = ?",
                (document_id,),
            )
        }
        stale_reference_ids = {
            stable_id: row_id
            for stable_id, row_id in existing_reference_ids.items()
            if stable_id not in wanted_reference_ids
        }
        for item in reference_items:
            conn.execute(
                """
                INSERT INTO story_reference_items (
                    stable_id, document_id, order_index, name, description,
                    start_line, end_line, origin, source_payload, source_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id, stable_id) DO UPDATE SET
                    order_index = excluded.order_index,
                    name = excluded.name,
                    description = excluded.description,
                    start_line = excluded.start_line,
                    end_line = excluded.end_line,
                    origin = excluded.origin,
                    source_payload = excluded.source_payload,
                    source_version = excluded.source_version
                """,
                (
                    item.stable_id, document_id, item.order_index, item.name,
                    item.description, item.start_line, item.end_line, item.origin,
                    item.source_payload, item.source_version,
                ),
            )

        wanted_ids = {node.stable_id for node in nodes}
        existing_imported = {
            stable_id: row_id
            for row_id, stable_id in conn.execute(
                """
                SELECT id, stable_id FROM story_nodes
                WHERE document_id = ? AND source_payload IS NOT NULL
                """,
                (document_id,),
            )
        }
        stale = {
            stable_id: row_id
            for stable_id, row_id in existing_imported.items()
            if stable_id not in wanted_ids
        }
        for stable_id, row_id in stale.items():
            manual_descendant = conn.execute(
                """
                WITH RECURSIVE descendants(id) AS (
                    SELECT id FROM story_nodes WHERE id = ?
                    UNION ALL
                    SELECT child.id FROM story_nodes child
                    JOIN descendants parent ON child.parent_id = parent.id
                )
                SELECT stable_id FROM story_nodes
                WHERE id IN descendants AND source_payload IS NULL
                LIMIT 1
                """,
                (row_id,),
            ).fetchone()
            if manual_descendant:
                raise StoryTimelineConflictError(stable_id, manual_descendant[0])

        node_ids: dict[str, int] = {}
        for node in nodes:
            conn.execute(
                """
                INSERT INTO story_nodes (
                    stable_id, document_id, parent_id, node_type, order_index,
                    title, text, start_line, end_line, start_column, end_column,
                    origin, approved, source_payload, source_version
                ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(document_id, stable_id) DO UPDATE SET
                    parent_id = NULL,
                    node_type = excluded.node_type,
                    order_index = excluded.order_index,
                    title = excluded.title,
                    text = excluded.text,
                    start_line = excluded.start_line,
                    end_line = excluded.end_line,
                    start_column = excluded.start_column,
                    end_column = excluded.end_column,
                    origin = excluded.origin,
                    approved = excluded.approved,
                    source_payload = excluded.source_payload,
                    source_version = excluded.source_version
                """,
                (
                    node.stable_id,
                    document_id,
                    node.node_type,
                    node.order_index,
                    node.title,
                    node.text,
                    node.start_line,
                    node.end_line,
                    node.start_column,
                    node.end_column,
                    node.origin,
                    node.source_payload,
                    node.source_version,
                ),
            )
            node_ids[node.stable_id] = conn.execute(
                "SELECT id FROM story_nodes WHERE document_id = ? AND stable_id = ?",
                (document_id, node.stable_id),
            ).fetchone()[0]

        for node in nodes:
            parent_id = node_ids.get(node.parent_stable_id)
            conn.execute(
                "UPDATE story_nodes SET parent_id = ? WHERE id = ?",
                (parent_id, node_ids[node.stable_id]),
            )

        for row_id in stale.values():
            conn.execute("DELETE FROM story_nodes WHERE id = ?", (row_id,))
        for row_id in stale_reference_ids.values():
            conn.execute("DELETE FROM story_reference_items WHERE id = ?", (row_id,))

        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        return StoryTimelineSyncResult(
            document_id,
            len(nodes),
            len(stale),
            len(reference_items),
            len(stale_reference_ids),
        )
    except Exception:
        conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        raise


def get_story_node(
    conn: sqlite3.Connection,
    document_id: int,
    stable_id: str,
) -> StoryNodeRecord | None:
    row = conn.execute(
        f"SELECT {_RECORD_COLUMNS} FROM story_nodes WHERE document_id = ? AND stable_id = ?",
        (document_id, stable_id),
    ).fetchone()
    return _record(row) if row else None


def get_story_document_id(conn: sqlite3.Connection, source_path: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM story_documents WHERE source_path = ?",
        (source_path,),
    ).fetchone()
    return row[0] if row else None


def get_reference_items(
    conn: sqlite3.Connection,
    document_id: int,
) -> tuple[ReferenceItemRecord, ...]:
    rows = conn.execute(
        """
        SELECT id, stable_id, document_id, order_index, name, description,
               start_line, end_line
        FROM story_reference_items
        WHERE document_id = ?
        ORDER BY order_index
        """,
        (document_id,),
    ).fetchall()
    return tuple(ReferenceItemRecord(*row) for row in rows)


def get_story_timeline(
    conn: sqlite3.Connection,
    document_id: int,
) -> tuple[StoryNodeRecord, ...]:
    return _story_timeline(conn, document_id)


def get_story_ancestors(
    conn: sqlite3.Connection,
    document_id: int,
    stable_id: str,
) -> tuple[StoryNodeRecord, ...]:
    rows = conn.execute(
        f"""
        WITH RECURSIVE chain(id, parent_id, depth) AS (
            SELECT id, parent_id, 0 FROM story_nodes
            WHERE document_id = ? AND stable_id = ?
            UNION ALL
            SELECT parent.id, parent.parent_id, chain.depth + 1
            FROM story_nodes parent
            JOIN chain ON parent.id = chain.parent_id
            WHERE parent.document_id = ?
        )
        SELECT {_QUALIFIED_RECORD_COLUMNS}
        FROM story_nodes node JOIN chain ON node.id = chain.id
        WHERE chain.depth > 0
        ORDER BY chain.depth DESC
        """,
        (document_id, stable_id, document_id),
    ).fetchall()
    return tuple(_record(row) for row in rows)


def get_story_descendants(
    conn: sqlite3.Connection,
    document_id: int,
    stable_id: str,
) -> tuple[StoryNodeRecord, ...]:
    rows = conn.execute(
        f"""
        WITH RECURSIVE tree(id, path, depth) AS (
            SELECT id, printf('%012d', order_index), 0 FROM story_nodes
            WHERE document_id = ? AND stable_id = ?
            UNION ALL
            SELECT child.id,
                   tree.path || '.' || printf('%012d', child.order_index),
                   tree.depth + 1
            FROM story_nodes child
            JOIN tree ON child.parent_id = tree.id
            WHERE child.document_id = ?
        )
        SELECT {_QUALIFIED_RECORD_COLUMNS}
        FROM story_nodes node JOIN tree ON node.id = tree.id
        WHERE tree.depth > 0
        ORDER BY tree.path
        """,
        (document_id, stable_id, document_id),
    ).fetchall()
    return tuple(_record(row) for row in rows)


def get_story_neighbors(
    conn: sqlite3.Connection,
    document_id: int,
    stable_id: str,
) -> tuple[StoryNodeRecord | None, StoryNodeRecord | None]:
    timeline = _story_timeline(conn, document_id)
    for index, node in enumerate(timeline):
        if node.stable_id == stable_id:
            previous = timeline[index - 1] if index else None
            next_node = timeline[index + 1] if index + 1 < len(timeline) else None
            return previous, next_node
    return None, None


def get_story_timeline_position(
    conn: sqlite3.Connection,
    document_id: int,
    stable_id: str,
) -> StoryTimelinePosition | None:
    timeline = _story_timeline(conn, document_id)
    for zero_based, node in enumerate(timeline):
        if node.stable_id == stable_id:
            index = zero_based + 1
            path = (*get_story_ancestors(conn, document_id, stable_id), node)
            structural_path = tuple(
                item for item in path if item.node_type in {"act", "chapter", "scene"}
            )
            return StoryTimelinePosition(
                index=index,
                total=len(timeline),
                progress=index / len(timeline),
                path=structural_path,
            )
    return None


def record_story_sync_conflict(
    conn: sqlite3.Connection,
    project: HierarchyProject,
    conflict: StoryTimelineConflictError,
) -> int:
    document_id = get_story_document_id(conn, project.source_path)
    existing = conn.execute(
        """
        SELECT id FROM story_sync_conflicts
        WHERE source_path = ? AND source_hash = ?
          AND source_stable_id = ? AND manual_stable_id = ? AND status = 'open'
        ORDER BY id DESC LIMIT 1
        """,
        (
            project.source_path,
            project.source_hash,
            conflict.source_stable_id,
            conflict.manual_stable_id,
        ),
    ).fetchone()
    if existing:
        return existing[0]
    return conn.execute(
        """
        INSERT INTO story_sync_conflicts (
            document_id, source_path, source_hash, conflict_type,
            source_stable_id, manual_stable_id, details
        ) VALUES (?, ?, ?, 'manual_descendant', ?, ?, ?)
        """,
        (
            document_id,
            project.source_path,
            project.source_hash,
            conflict.source_stable_id,
            conflict.manual_stable_id,
            str(conflict),
        ),
    ).lastrowid


def get_story_sync_conflicts(
    conn: sqlite3.Connection,
    source_path: str,
    *,
    status: str = "open",
) -> tuple[StorySyncConflictRecord, ...]:
    rows = conn.execute(
        """
        SELECT id, document_id, source_path, source_hash, conflict_type,
               source_stable_id, manual_stable_id, details, status,
               created_at, resolved_at
        FROM story_sync_conflicts
        WHERE source_path = ? AND status = ?
        ORDER BY id
        """,
        (source_path, status),
    ).fetchall()
    return tuple(StorySyncConflictRecord(*row) for row in rows)


def resolve_story_sync_conflict(conn: sqlite3.Connection, conflict_id: int) -> bool:
    result = conn.execute(
        """
        UPDATE story_sync_conflicts
        SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status = 'open'
        """,
        (conflict_id,),
    )
    return result.rowcount > 0


_RECORD_COLUMNS = (
    "id, stable_id, document_id, parent_id, node_type, order_index, title, text, "
    "start_line, end_line"
)
_QUALIFIED_RECORD_COLUMNS = ", ".join(
    f"node.{column.strip()}" for column in _RECORD_COLUMNS.split(",")
)


def _story_timeline(
    conn: sqlite3.Connection,
    document_id: int,
) -> tuple[StoryNodeRecord, ...]:
    rows = conn.execute(
        f"""
        WITH RECURSIVE timeline(id, path) AS (
            SELECT id, printf('%012d', order_index) FROM story_nodes
            WHERE document_id = ? AND parent_id IS NULL
            UNION ALL
            SELECT child.id,
                   timeline.path || '.' || printf('%012d', child.order_index)
            FROM story_nodes child
            JOIN timeline ON child.parent_id = timeline.id
            WHERE child.document_id = ?
        )
        SELECT {_QUALIFIED_RECORD_COLUMNS}
        FROM story_nodes node JOIN timeline ON node.id = timeline.id
        ORDER BY timeline.path
        """,
        (document_id, document_id),
    ).fetchall()
    return tuple(_record(row) for row in rows)


def _record(row) -> StoryNodeRecord:
    return StoryNodeRecord(*row)


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
    if mark.text.strip():
        return mark.text.strip()
    selected = lines[mark.start_line:mark.end_line + 1]
    if not selected:
        return ""
    if len(selected) == 1:
        start = mark.start_col or 0
        end = mark.end_col if mark.end_col is not None else len(selected[0])
        return selected[0][start:end].strip()
    if mark.start_col is not None:
        selected[0] = selected[0][mark.start_col:]
    if mark.end_col is not None:
        selected[-1] = selected[-1][:mark.end_col]
    return "\n".join(selected).strip()


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
