"""Load/save alignment inputs and persist relation choices."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sqlite3
import sys

from core.mempalace.alignment.models import GameMessage, MarkedDialogue
from core.mempalace.alignment.simulate import simulate


def load_dialogues(database: Path, document_id: int) -> list[MarkedDialogue]:
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    rows = connection.execute(
        """
        WITH RECURSIVE timeline(id, path) AS (
            SELECT id, printf('%012d', order_index) FROM story_nodes
            WHERE document_id = ? AND parent_id IS NULL
            UNION ALL
            SELECT child.id, timeline.path || '.' || printf('%012d', child.order_index)
            FROM story_nodes child JOIN timeline ON child.parent_id = timeline.id
            WHERE child.document_id = ?
        ), ancestors(dialogue_id, ancestor_id, distance) AS (
            SELECT id, parent_id, 1 FROM story_nodes
            WHERE document_id = ? AND node_type = 'dialogue' AND approved = 1
            UNION ALL
            SELECT ancestors.dialogue_id, parent.parent_id, ancestors.distance + 1
            FROM ancestors
            JOIN story_nodes parent ON parent.id = ancestors.ancestor_id
            WHERE parent.parent_id IS NOT NULL
        ), nearest_speaker AS (
            SELECT ancestors.dialogue_id, ancestors.ancestor_id AS speaker_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY ancestors.dialogue_id
                       ORDER BY ancestors.distance
                   ) AS proximity
            FROM ancestors
            JOIN story_nodes candidate ON candidate.id = ancestors.ancestor_id
            WHERE candidate.node_type = 'speaker' AND candidate.approved = 1
        )
        SELECT dialogue.id, dialogue.text, dialogue.start_line,
               COALESCE(speaker.title, speaker.text, 'Unknown speaker')
        FROM story_nodes dialogue
        JOIN timeline ON timeline.id = dialogue.id
        JOIN nearest_speaker ON nearest_speaker.dialogue_id = dialogue.id
            AND nearest_speaker.proximity = 1
        JOIN story_nodes speaker ON speaker.id = nearest_speaker.speaker_id
        WHERE dialogue.document_id = ?
          AND dialogue.node_type = 'dialogue'
          AND dialogue.approved = 1
        ORDER BY timeline.path
        """,
        (document_id, document_id, document_id, document_id),
    ).fetchall()
    connection.close()
    return [
        MarkedDialogue(row[0], order, row[1] or "", row[3], row[2])
        for order, row in enumerate(rows)
    ]


def load_messages(session_path: Path) -> list[GameMessage]:
    session = json.loads(session_path.read_text(encoding="utf-8"))
    block_names = session.get("block_names", {}) or {}
    messages = []
    for block_index, block in enumerate(session.get("data", [])):
        if not isinstance(block, list):
            continue
        block_name = str(block_names.get(str(block_index), block_index))
        for string_index, value in enumerate(block):
            text = str(value or "")
            if not text.strip():
                continue
            messages.append(GameMessage(
                len(messages),
                str(block_index),
                block_name,
                string_index,
                f"{block_name}_Str_{string_index}",
                text,
            ))
    return messages


def save_relations(
    connection: sqlite3.Connection,
    document_id: int,
    report: dict,
    messages: list[GameMessage],
) -> int:
    """Replace automatic relations while preserving locked manual decisions."""
    message_by_key = {
        (message.block_id, message.string_index): message for message in messages
    }
    savepoint = "mempalace_alignment_relations"
    connection.execute(f"SAVEPOINT {savepoint}")
    try:
        connection.execute(
            "DELETE FROM story_dialogue_relations WHERE document_id = ? AND locked = 0",
            (document_id,),
        )
        connection.execute(
            "DELETE FROM story_dialogue_mappings WHERE document_id = ? AND locked = 0",
            (document_id,),
        )
        inserted = 0
        relation_groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
        for relation in report.get("relations", ()):
            key = (str(relation["game_block_id"]), int(relation["string_index"]))
            message = message_by_key.get(key)
            if message is None:
                continue
            relation_groups[key].append(relation)
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO story_dialogue_relations (
                    document_id, game_block_id, game_block_name, string_index,
                    game_string_id, dialogue_node_id, source_text_snapshot,
                    relation_method, score, game_coverage, primary_link,
                    relation_status, locked
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'supported', 0)
                """,
                (
                    document_id,
                    message.block_id,
                    message.block_name,
                    message.string_index,
                    message.stable_id,
                    int(relation["dialogue_node_id"]),
                    message.text,
                    relation["method"],
                    float(relation["score"]),
                    float(relation["game_coverage"]),
                    int(bool(relation["primary"])),
                ),
            )
            inserted += int(cursor.rowcount > 0)
        for key, choices in relation_groups.items():
            message = message_by_key[key]
            primary = next((choice for choice in choices if choice["primary"]), None)
            if primary is None and all(
                choice["method"] == "exact_or_contained" for choice in choices
            ):
                # One reusable game resource can legitimately occur in several
                # marked contexts; exact relations do not require choosing one.
                continue
            selected = primary or max(choices, key=lambda choice: choice["score"])
            review_status = "matched" if primary is not None else "needs_review"
            method = (
                "exact_text"
                if selected["method"] == "exact_or_contained"
                else "fuzzy"
            )
            reason = None
            if primary is None:
                reason = (
                    f"{len(choices)} marked contexts remain after indexed alignment."
                )
            connection.execute(
                """
                INSERT OR IGNORE INTO story_dialogue_mappings (
                    document_id, game_block_id, game_block_name, string_index,
                    game_string_id, dialogue_node_id, source_text_snapshot,
                    match_method, confidence, review_status, conflict_reason, locked
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    document_id,
                    message.block_id,
                    message.block_name,
                    message.string_index,
                    message.stable_id,
                    int(selected["dialogue_node_id"]),
                    message.text,
                    method,
                    min(1.0, max(0.0, float(selected["score"]))),
                    review_status,
                    reason,
                ),
            )
        connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        return inserted
    except Exception:
        connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        raise


def lock_relation_choice(
    connection: sqlite3.Connection,
    document_id: int,
    game_block_id: str,
    string_index: int,
    dialogue_node_id: int | None,
) -> int:
    """Lock one chosen context, or reject every context when the text is not story."""
    if dialogue_node_id is None:
        cursor = connection.execute(
            """
            UPDATE story_dialogue_relations
            SET primary_link = 0, relation_status = 'rejected', locked = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE document_id = ? AND game_block_id = ? AND string_index = ?
            """,
            (document_id, game_block_id, string_index),
        )
    else:
        cursor = connection.execute(
            """
            UPDATE story_dialogue_relations
            SET primary_link = CASE WHEN dialogue_node_id = ? THEN 1 ELSE 0 END,
                relation_status = CASE
                    WHEN dialogue_node_id = ? THEN 'approved' ELSE 'rejected'
                END,
                locked = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE document_id = ? AND game_block_id = ? AND string_index = ?
            """,
            (
                dialogue_node_id,
                dialogue_node_id,
                document_id,
                game_block_id,
                string_index,
            ),
        )
    connection.commit()
    return cursor.rowcount


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--document-id", type=int, default=1)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--minimum-spoken-coverage", type=float)
    parser.add_argument("--gpu", choices=("auto", "on", "off"), default="auto")
    args = parser.parse_args()
    print("[1/4] Loading marked dialogue and game messages...", file=sys.stderr, flush=True)
    dialogues = load_dialogues(args.database, args.document_id)
    messages = load_messages(args.session)
    semantic_candidates = None
    accelerator = None
    if args.gpu != "off":
        print("[2/4] Retrieving CUDA candidates...", file=sys.stderr, flush=True)
        try:
            from core.mempalace.gpu_retrieval import retrieve_gpu_candidates

            semantic_candidates, accelerator = retrieve_gpu_candidates(
                dialogues, messages
            )
        except Exception as exc:
            if args.gpu == "on":
                raise
            accelerator = {"backend": "cpu_sparse", "gpu_fallback_reason": str(exc)}
    else:
        print("[2/4] CUDA retrieval disabled; using sparse candidates...", file=sys.stderr, flush=True)
    print("[3/4] Aligning and auditing candidate relations...", file=sys.stderr, flush=True)
    report = simulate(
        dialogues,
        messages,
        semantic_candidates=semantic_candidates,
        accelerator=accelerator,
    )
    print("[4/4] Alignment report ready.", file=sys.stderr, flush=True)
    print(json.dumps({
        key: value
        for key, value in report.items()
        if key not in {"relations", "uncovered"}
    }, indent=2))
    print("Worst uncovered marked blocks:")
    for item in report["uncovered"][:20]:
        print(
            f"  {item['coverage']:6.2f}% line {item['source_line']} "
            f"{item['speaker']}: {item['uncovered_text'][:140]}"
        )
    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if (
        args.minimum_spoken_coverage is not None
        and report["eligible_marked_dialogue"]["supported_relation_coverage"]
        < args.minimum_spoken_coverage
    ):
        return 1
    return 0
