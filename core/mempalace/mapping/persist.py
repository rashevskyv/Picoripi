"""Persist dialogue mappings and durable UI state."""

from __future__ import annotations

import sqlite3

from core.mempalace.mapping.models import (
    DialogueMappingInput,
    DialogueMappingRecord,
    DialogueMappingState,
    DialogueMappingUpsertResult,
)


def upsert_dialogue_mapping(
    conn: sqlite3.Connection,
    item: DialogueMappingInput,
    *,
    allow_locked_override: bool = False,
) -> DialogueMappingUpsertResult:
    """Upsert one mapping while preserving reviewed locked decisions by default."""
    existing = _find_mapping(conn, item.document_id, item.game_block_id, item.string_index)
    if existing and existing.locked and not allow_locked_override:
        return DialogueMappingUpsertResult(existing, True)

    _validate_target_node(conn, item.document_id, item.dialogue_node_id)
    reviewed_at = "CURRENT_TIMESTAMP" if item.reviewed_by else "NULL"
    conn.execute(
        f"""
        INSERT INTO story_dialogue_mappings (
            document_id, game_block_id, game_block_name, string_index,
            game_string_id, dialogue_node_id, source_text_snapshot,
            match_method, confidence, review_status, reviewed_by, reviewed_at,
            conflict_reason, locked
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, {reviewed_at}, ?, ?)
        ON CONFLICT(document_id, game_block_id, string_index) DO UPDATE SET
            game_block_name = excluded.game_block_name,
            game_string_id = excluded.game_string_id,
            dialogue_node_id = excluded.dialogue_node_id,
            source_text_snapshot = excluded.source_text_snapshot,
            match_method = excluded.match_method,
            confidence = excluded.confidence,
            review_status = excluded.review_status,
            reviewed_by = excluded.reviewed_by,
            reviewed_at = excluded.reviewed_at,
            conflict_reason = excluded.conflict_reason,
            locked = excluded.locked,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            item.document_id,
            item.game_block_id,
            item.game_block_name,
            item.string_index,
            item.game_string_id,
            item.dialogue_node_id,
            item.source_text_snapshot,
            item.match_method,
            item.confidence,
            item.review_status,
            item.reviewed_by,
            item.conflict_reason,
            int(item.locked),
        ),
    )
    mapping = _find_mapping(conn, item.document_id, item.game_block_id, item.string_index)
    return DialogueMappingUpsertResult(mapping, False)


def get_dialogue_mappings(
    conn: sqlite3.Connection,
    document_id: int,
    *,
    review_status: str | None = None,
) -> tuple[DialogueMappingRecord, ...]:
    query = f"SELECT {_MAPPING_COLUMNS} FROM story_dialogue_mappings WHERE document_id = ?"
    params: tuple = (document_id,)
    if review_status is not None:
        query += " AND review_status = ?"
        params += (review_status,)
    query += " ORDER BY game_block_id, string_index"
    return tuple(_record(row) for row in conn.execute(query, params).fetchall())


def get_dialogue_mapping_state(
    conn: sqlite3.Connection,
    document_id: int,
) -> DialogueMappingState:
    """Return durable search progress without rerunning the matcher."""
    mapping = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN review_status = 'matched' THEN 1 ELSE 0 END) AS automatic,
            SUM(CASE WHEN review_status IN ('approved', 'rejected') THEN 1 ELSE 0 END)
                AS reviewed,
            SUM(CASE WHEN review_status = 'needs_review' THEN 1 ELSE 0 END)
                AS needs_review
        FROM story_dialogue_mappings
        WHERE document_id = ?
        """,
        (document_id,),
    ).fetchone()
    relation = conn.execute(
        """
        SELECT COUNT(*)
        FROM story_dialogue_relations
        WHERE document_id = ? AND relation_status IN ('supported', 'approved')
        """,
        (document_id,),
    ).fetchone()
    return DialogueMappingState(
        total=int(mapping[0] or 0),
        automatic=int(mapping[1] or 0),
        reviewed=int(mapping[2] or 0),
        needs_review=int(mapping[3] or 0),
        context_links=int(relation[0] or 0),
    )


def _validate_target_node(
    conn: sqlite3.Connection,
    document_id: int,
    dialogue_node_id: int | None,
) -> None:
    if dialogue_node_id is None:
        return
    row = conn.execute(
        "SELECT document_id, node_type FROM story_nodes WHERE id = ?",
        (dialogue_node_id,),
    ).fetchone()
    if row != (document_id, "dialogue"):
        raise ValueError("dialogue_node_id must reference a dialogue node in the same document.")


_MAPPING_COLUMNS = (
    "id, document_id, game_block_id, game_block_name, string_index, game_string_id, "
    "dialogue_node_id, source_text_snapshot, match_method, confidence, review_status, "
    "reviewed_by, reviewed_at, conflict_reason, locked"
)


def _find_mapping(
    conn: sqlite3.Connection,
    document_id: int,
    game_block_id: str,
    string_index: int,
) -> DialogueMappingRecord | None:
    row = conn.execute(
        f"""
        SELECT {_MAPPING_COLUMNS} FROM story_dialogue_mappings
        WHERE document_id = ? AND game_block_id = ? AND string_index = ?
        """,
        (document_id, game_block_id, string_index),
    ).fetchone()
    return _record(row) if row else None


def _record(row) -> DialogueMappingRecord:
    values = list(row)
    values[-1] = bool(values[-1])
    return DialogueMappingRecord(*values)
