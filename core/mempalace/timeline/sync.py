"""Synchronize hierarchy projects into SQLite and manage sync conflicts."""

from __future__ import annotations

import sqlite3

from core.script_markup import HierarchyProject
from core.mempalace.timeline.models import (
    StorySyncConflictRecord,
    StoryTimelineConflictError,
    StoryTimelineSyncResult,
)
from core.mempalace.timeline.normalize import (
    normalize_hierarchy_project,
    normalize_reference_items,
)
from core.mempalace.timeline.queries import get_story_document_id


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
        previous_document = conn.execute(
            "SELECT id, source_hash FROM story_documents WHERE source_path = ?",
            (project.source_path,),
        ).fetchone()
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
        if previous_document and previous_document[1] != project.source_hash:
            # Semantic summaries describe the old source snapshot. They can be
            # rebuilt without disturbing normalized nodes or reviewed mappings.
            conn.execute(
                "DELETE FROM story_timeline_contexts WHERE document_id = ?",
                (document_id,),
            )
            conn.execute(
                "DELETE FROM story_character_profiles WHERE document_id = ?",
                (document_id,),
            )

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
