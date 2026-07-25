"""Semantic story events attached to normalized marked-dialogue nodes."""

from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3
from typing import Iterable


@dataclass(frozen=True)
class StoryEventContext:
    document_id: int
    dialogue_node_id: int
    stable_id: str
    event_order: int
    event_title: str
    summary: str
    location: str
    participants: tuple[str, ...]
    previous_event: str
    next_event: str
    source_hash: str
    interactions: tuple[str, ...] = ()

    def to_prompt_text(self) -> str:
        parts = [f"Timeline Event: {self.event_title}"]
        if self.summary:
            parts.append(f"What is happening: {self.summary}")
        if self.location:
            parts.append(f"Location: {self.location}")
        if self.participants:
            parts.append("Participants: " + ", ".join(self.participants))
        if self.interactions:
            parts.append("Interaction in this event: " + "; ".join(self.interactions))
        if self.previous_event:
            parts.append(f"Immediately before: {self.previous_event}")
        if self.next_event:
            parts.append(f"Immediately after: {self.next_event}")
        return "\n".join(parts)


def replace_story_event_contexts(
    conn: sqlite3.Connection,
    document_id: int,
    contexts: Iterable[dict],
    source_hash: str,
) -> int:
    rows = list(contexts)
    with conn:
        conn.execute(
            "DELETE FROM story_timeline_contexts WHERE document_id = ?",
            (document_id,),
        )
        conn.executemany(
            """
            INSERT INTO story_timeline_contexts (
                document_id, dialogue_node_id, event_order, event_title, summary,
                location, participants_json, previous_event, next_event, source_hash,
                interactions_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    document_id,
                    int(row["dialogue_node_id"]),
                    int(row["event_order"]),
                    str(row["event_title"]),
                    str(row.get("summary") or ""),
                    str(row.get("location") or ""),
                    json.dumps(row.get("participants") or [], ensure_ascii=False),
                    str(row.get("previous_event") or ""),
                    str(row.get("next_event") or ""),
                    source_hash,
                    json.dumps(row.get("interactions") or [], ensure_ascii=False),
                )
                for row in rows
            ],
        )
    return len(rows)


def get_story_event_for_game_string(
    conn: sqlite3.Connection,
    game_block_id: str,
    string_index: int,
    document_id: int | None = None,
) -> StoryEventContext | None:
    if document_id is None:
        row = conn.execute(
            "SELECT id FROM story_documents ORDER BY imported_at DESC, id DESC LIMIT 1"
        ).fetchone()
        document_id = row[0] if row else None
    if document_id is None:
        return None
    row = conn.execute(
        """
        SELECT context.document_id, context.dialogue_node_id, node.stable_id,
               context.event_order, context.event_title, context.summary,
               context.location, context.participants_json, context.previous_event,
               context.next_event, context.source_hash, context.interactions_json
        FROM story_timeline_contexts context
        JOIN story_nodes node ON node.id = context.dialogue_node_id
        WHERE context.document_id = ? AND context.dialogue_node_id = COALESCE(
            (SELECT dialogue_node_id FROM story_dialogue_relations
             WHERE document_id = ? AND game_block_id = ? AND string_index = ?
               AND relation_status IN ('supported', 'approved')
             ORDER BY primary_link DESC, locked DESC, score DESC, id LIMIT 1),
            (SELECT dialogue_node_id FROM story_dialogue_mappings
             WHERE document_id = ? AND game_block_id = ? AND string_index = ?
               AND dialogue_node_id IS NOT NULL
             ORDER BY locked DESC, confidence DESC, id LIMIT 1)
        )
        """,
        (document_id, document_id, str(game_block_id), int(string_index),
         document_id, str(game_block_id), int(string_index)),
    ).fetchone()
    return _record(row) if row else None


def get_story_events(
    conn: sqlite3.Connection, document_id: int
) -> tuple[StoryEventContext, ...]:
    rows = conn.execute(
        """
        SELECT context.document_id, MIN(context.dialogue_node_id), MIN(node.stable_id),
               context.event_order, context.event_title, context.summary,
               context.location, context.participants_json, context.previous_event,
               context.next_event, context.source_hash, context.interactions_json
        FROM story_timeline_contexts context
        JOIN story_nodes node ON node.id = context.dialogue_node_id
        WHERE context.document_id = ?
        GROUP BY context.event_order, context.event_title, context.summary,
                 context.location, context.participants_json,
                 context.previous_event, context.next_event, context.source_hash,
                 context.interactions_json
        ORDER BY context.event_order
        """,
        (document_id,),
    ).fetchall()
    return tuple(_record(row) for row in rows)


def _record(row) -> StoryEventContext:
    try:
        participants = tuple(str(item) for item in json.loads(row[7]) if str(item).strip())
    except (TypeError, ValueError, json.JSONDecodeError):
        participants = ()
    try:
        interactions = tuple(
            str(item) for item in json.loads(row[11]) if str(item).strip()
        )
    except (IndexError, TypeError, ValueError, json.JSONDecodeError):
        interactions = ()
    return StoryEventContext(
        int(row[0]), int(row[1]), str(row[2]), int(row[3]), str(row[4]),
        str(row[5]), str(row[6]), participants, str(row[8]), str(row[9]), str(row[10]),
        interactions,
    )
