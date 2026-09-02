"""Read story timeline / virtual projection / reference queries from SQLite."""

from __future__ import annotations

from collections import defaultdict
import sqlite3

from core.mempalace.timeline.models import (
    ReferenceItemRecord,
    StoryNodeRecord,
    StoryStringContext,
    StoryTimelinePosition,
    StoryVirtualFolder,
    StoryVirtualMapping,
    StoryVirtualProjection,
    StoryVirtualSpeaker,
)


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

def get_story_virtual_projection(
    conn: sqlite3.Connection,
    document_id: int | None = None,
) -> StoryVirtualProjection:
    """Project saved story relations into selectable UI folders without duplicating data."""
    if document_id is None:
        row = conn.execute(
            "SELECT id FROM story_documents ORDER BY imported_at DESC, id DESC LIMIT 1"
        ).fetchone()
        document_id = row[0] if row else None
    if document_id is None:
        return StoryVirtualProjection(None, (), ())

    timeline = _story_timeline(conn, document_id)
    if not timeline:
        return StoryVirtualProjection(document_id, (), ())

    nodes = {node.id: node for node in timeline}
    timeline_order = {node.id: index for index, node in enumerate(timeline)}
    structural_types = {"act", "chapter", "scene"}
    structural_nodes = [node for node in timeline if node.node_type in structural_types]

    parent_structure: dict[int, int | None] = {}
    for node in structural_nodes:
        parent_id = node.parent_id
        while parent_id is not None and nodes[parent_id].node_type not in structural_types:
            parent_id = nodes[parent_id].parent_id
        parent_structure[node.id] = parent_id

    relation_rows = conn.execute(
        """
        SELECT game_block_id, game_string_id, string_index, dialogue_node_id
        FROM story_dialogue_relations
        WHERE document_id = ? AND relation_status IN ('supported', 'approved')
        """,
        (document_id,),
    ).fetchall()
    relation_rows.sort(key=lambda row: (timeline_order.get(row[3], len(timeline)), row[0], row[2]))

    structure_mappings: dict[int, list[StoryVirtualMapping]] = defaultdict(list)
    structure_seen: dict[int, set[tuple[str, int]]] = defaultdict(set)
    speaker_mappings: dict[str, list[StoryVirtualMapping]] = defaultdict(list)
    speaker_seen: dict[str, set[tuple[str, int]]] = defaultdict(set)

    for block_id, string_id, string_index, dialogue_id in relation_rows:
        if dialogue_id not in nodes:
            continue
        mapping = StoryVirtualMapping(str(block_id), str(string_id), int(string_index))
        mapping_key = (mapping.game_block_id, mapping.string_index)
        speaker_name = None
        current = nodes[dialogue_id]
        visited: set[int] = set()
        while current.id not in visited:
            visited.add(current.id)
            if current.node_type in structural_types:
                if mapping_key not in structure_seen[current.id]:
                    structure_seen[current.id].add(mapping_key)
                    structure_mappings[current.id].append(mapping)
            elif current.node_type == "speaker" and speaker_name is None:
                speaker_name = (current.title or current.text or "").strip()
            if current.parent_id is None or current.parent_id not in nodes:
                break
            current = nodes[current.parent_id]
        if speaker_name and mapping_key not in speaker_seen[speaker_name]:
            speaker_seen[speaker_name].add(mapping_key)
            speaker_mappings[speaker_name].append(mapping)

    children_by_parent: dict[int | None, list[StoryNodeRecord]] = defaultdict(list)
    for node in structural_nodes:
        children_by_parent[parent_structure[node.id]].append(node)

    def build_folder(node: StoryNodeRecord) -> StoryVirtualFolder:
        return StoryVirtualFolder(
            id=node.id,
            node_type=node.node_type,
            title=(node.title or node.text or node.node_type.title()).strip(),
            children=tuple(build_folder(child) for child in children_by_parent[node.id]),
            mappings=tuple(structure_mappings[node.id]),
        )

    roots = tuple(build_folder(node) for node in children_by_parent[None])
    speakers = tuple(
        StoryVirtualSpeaker(name, tuple(speaker_mappings[name]))
        for name in sorted(speaker_mappings, key=str.casefold)
    )
    return StoryVirtualProjection(document_id, roots, speakers)

def get_story_speakers_for_game_string(
    conn: sqlite3.Connection,
    game_block_id: str,
    string_index: int,
    document_id: int | None = None,
) -> tuple[str, ...]:
    """Return only normalized speaker ancestors for one physical game string."""
    if document_id is None:
        row = conn.execute(
            "SELECT id FROM story_documents ORDER BY imported_at DESC, id DESC LIMIT 1"
        ).fetchone()
        document_id = row[0] if row else None
    if document_id is None:
        return ()
    rows = conn.execute(
        """
        WITH RECURSIVE ancestors(relation_id, node_id, parent_id, depth) AS (
            SELECT relation.id, dialogue.id, dialogue.parent_id, 0
            FROM story_dialogue_relations relation
            JOIN story_nodes dialogue ON dialogue.id = relation.dialogue_node_id
            WHERE relation.document_id = ?
              AND relation.game_block_id = ?
              AND relation.string_index = ?
              AND relation.relation_status IN ('supported', 'approved')
            UNION ALL
            SELECT ancestors.relation_id, parent.id, parent.parent_id,
                   ancestors.depth + 1
            FROM ancestors
            JOIN story_nodes parent ON parent.id = ancestors.parent_id
        )
        SELECT COALESCE(NULLIF(TRIM(speaker.title), ''), TRIM(speaker.text)) AS name,
               MIN(ancestors.depth) AS nearest_depth,
               MIN(speaker.order_index) AS story_order
        FROM ancestors
        JOIN story_nodes speaker ON speaker.id = ancestors.node_id
        WHERE speaker.node_type = 'speaker' AND speaker.approved = 1
        GROUP BY name
        HAVING name IS NOT NULL AND name != ''
        ORDER BY nearest_depth, story_order, name COLLATE NOCASE
        """,
        (document_id, str(game_block_id), int(string_index)),
    ).fetchall()
    return tuple(row[0] for row in rows)

def get_story_navigation_target(
    conn: sqlite3.Connection,
    game_block_id: str,
    string_index: int,
    document_id: int | None = None,
) -> StoryNodeRecord | None:
    """Return the best saved marked-script node for one physical game string."""
    if document_id is None:
        row = conn.execute(
            "SELECT id FROM story_documents ORDER BY imported_at DESC, id DESC LIMIT 1"
        ).fetchone()
        document_id = row[0] if row else None
    if document_id is None:
        return None
    row = conn.execute(
        f"""
        SELECT {_QUALIFIED_RECORD_COLUMNS}
        FROM story_nodes node
        WHERE node.id = COALESCE(
            (
                SELECT relation.dialogue_node_id
                FROM story_dialogue_relations relation
                WHERE relation.document_id = ?
                  AND relation.game_block_id = ?
                  AND relation.string_index = ?
                  AND relation.relation_status IN ('supported', 'approved')
                ORDER BY relation.primary_link DESC, relation.locked DESC,
                         relation.score DESC, relation.id
                LIMIT 1
            ),
            (
                SELECT mapping.dialogue_node_id
                FROM story_dialogue_mappings mapping
                WHERE mapping.document_id = ?
                  AND mapping.game_block_id = ?
                  AND mapping.string_index = ?
                  AND mapping.dialogue_node_id IS NOT NULL
                ORDER BY mapping.locked DESC, mapping.confidence DESC, mapping.id
                LIMIT 1
            )
        )
        """,
        (
            document_id, str(game_block_id), int(string_index),
            document_id, str(game_block_id), int(string_index),
        ),
    ).fetchone()
    return _record(row) if row else None

def get_story_string_contexts(
    conn: sqlite3.Connection,
    game_block_id: str,
    string_index: int,
    document_id: int | None = None,
) -> tuple[StoryStringContext, ...]:
    """Return the structure path and role attached to every saved relation."""
    if document_id is None:
        row = conn.execute(
            "SELECT id FROM story_documents ORDER BY imported_at DESC, id DESC LIMIT 1"
        ).fetchone()
        document_id = row[0] if row else None
    if document_id is None:
        return ()
    dialogue_ids = conn.execute(
        """
        SELECT dialogue_node_id
        FROM story_dialogue_relations
        WHERE document_id = ? AND game_block_id = ? AND string_index = ?
          AND relation_status IN ('supported', 'approved')
        ORDER BY primary_link DESC, locked DESC, score DESC, id
        """,
        (document_id, str(game_block_id), int(string_index)),
    ).fetchall()
    timeline = {node.id: node for node in _story_timeline(conn, document_id)}
    result: list[StoryStringContext] = []
    seen = set()
    for (dialogue_id,) in dialogue_ids:
        node = timeline.get(dialogue_id)
        structures: list[StoryNodeRecord] = []
        speaker = None
        visited = set()
        while node is not None and node.id not in visited:
            visited.add(node.id)
            if node.node_type in {"act", "chapter", "scene"}:
                structures.append(node)
            elif node.node_type == "speaker" and speaker is None:
                speaker = (node.title or node.text or "").strip() or None
            node = timeline.get(node.parent_id)
        structures.reverse()
        structure_id = structures[-1].id if structures else None
        path = tuple((item.title or item.text or item.node_type.title()).strip() for item in structures)
        key = (structure_id, path, speaker)
        if key not in seen:
            seen.add(key)
            result.append(StoryStringContext(structure_id, path, speaker))
    return tuple(result)

def get_story_mappings_for_node(
    conn: sqlite3.Connection,
    document_id: int,
    stable_id: str,
) -> tuple[StoryVirtualMapping, ...]:
    """Return physical strings linked to a node or any of its descendants."""
    rows = conn.execute(
        """
        WITH RECURSIVE descendants(id) AS (
            SELECT id FROM story_nodes WHERE document_id = ? AND stable_id = ?
            UNION ALL
            SELECT child.id FROM story_nodes child
            JOIN descendants parent ON child.parent_id = parent.id
        )
        SELECT relation.game_block_id, relation.game_string_id, relation.string_index
        FROM story_dialogue_relations relation
        JOIN descendants ON descendants.id = relation.dialogue_node_id
        WHERE relation.document_id = ?
          AND relation.relation_status IN ('supported', 'approved')
        ORDER BY relation.primary_link DESC, relation.locked DESC,
                 relation.score DESC, relation.id
        """,
        (document_id, stable_id, document_id),
    ).fetchall()
    result = []
    seen = set()
    for block_id, string_id, string_index in rows:
        key = (str(block_id), int(string_index))
        if key in seen:
            continue
        seen.add(key)
        result.append(StoryVirtualMapping(str(block_id), str(string_id), int(string_index)))
    return tuple(result)

def get_reference_item_context(
    conn: sqlite3.Connection, document_id: int, item_name: str
) -> StoryStringContext | None:
    """Return the nearest structural location containing a reference item."""
    reference = conn.execute(
        """SELECT start_line, end_line FROM story_reference_items
           WHERE document_id = ? AND name = ? COLLATE NOCASE LIMIT 1""",
        (document_id, item_name),
    ).fetchone()
    if not reference or reference[0] is None:
        return None
    start_line, end_line = int(reference[0]), int(reference[1] or reference[0])
    timeline = _story_timeline(conn, document_id)
    nodes = {node.id: node for node in timeline}
    candidates = [
        node for node in timeline
        if node.node_type in {"act", "chapter", "scene"}
        and node.start_line is not None and node.end_line is not None
        and node.start_line <= start_line and node.end_line >= end_line
    ]
    if not candidates:
        return None
    deepest = min(candidates, key=lambda node: (node.end_line - node.start_line, -node.order_index))
    structures = []
    current = deepest
    while current is not None:
        if current.node_type in {"act", "chapter", "scene"}:
            structures.append(current)
        current = nodes.get(current.parent_id)
    structures.reverse()
    path = tuple((node.title or node.text or node.node_type.title()).strip() for node in structures)
    return StoryStringContext(deepest.id, path, None)

def get_story_document_source_path(
    conn: sqlite3.Connection,
    document_id: int | None = None,
) -> str:
    """Return the saved Markup Studio project path for a story document."""
    if document_id is None:
        row = conn.execute(
            "SELECT source_path FROM story_documents "
            "ORDER BY imported_at DESC, id DESC LIMIT 1"
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT source_path FROM story_documents WHERE id = ?",
            (int(document_id),),
        ).fetchone()
    return str(row[0]) if row and row[0] else ""

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
