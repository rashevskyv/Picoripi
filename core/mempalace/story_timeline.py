"""Normalize and synchronize Markup Studio hierarchy projects into SQLite."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
import sqlite3

from core.script_markup import (
    HierarchyProject,
    HierarchyType,
    build_hierarchy_tree,
    mark_text,
)
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
class StoryVirtualMapping:
    """One physical game string exposed through a derived story folder."""

    game_block_id: str
    game_string_id: str
    string_index: int


@dataclass(frozen=True)
class StoryVirtualFolder:
    """A selectable Act, Chapter, or Scene in the main project tree."""

    id: int
    node_type: str
    title: str
    children: tuple["StoryVirtualFolder", ...]
    mappings: tuple[StoryVirtualMapping, ...]


@dataclass(frozen=True)
class StoryVirtualSpeaker:
    """A selectable speaker folder derived from marked script ancestry."""

    name: str
    mappings: tuple[StoryVirtualMapping, ...]


@dataclass(frozen=True)
class StoryVirtualProjection:
    """Read-only projection of saved story context for the translation UI."""

    document_id: int | None
    roots: tuple[StoryVirtualFolder, ...]
    speakers: tuple[StoryVirtualSpeaker, ...]


def story_virtual_projection_to_dict(projection: StoryVirtualProjection) -> dict:
    """Serialize a virtual Story projection for durable project sessions."""
    def mapping_to_dict(mapping: StoryVirtualMapping) -> dict:
        return {
            "game_block_id": mapping.game_block_id,
            "game_string_id": mapping.game_string_id,
            "string_index": mapping.string_index,
        }

    def folder_to_dict(folder: StoryVirtualFolder) -> dict:
        return {
            "id": folder.id,
            "node_type": folder.node_type,
            "title": folder.title,
            "children": [folder_to_dict(child) for child in folder.children],
            "mappings": [mapping_to_dict(mapping) for mapping in folder.mappings],
        }

    return {
        "document_id": projection.document_id,
        "roots": [folder_to_dict(folder) for folder in projection.roots],
        "speakers": [
            {
                "name": speaker.name,
                "mappings": [mapping_to_dict(mapping) for mapping in speaker.mappings],
            }
            for speaker in projection.speakers
        ],
    }


def story_virtual_projection_from_dict(value: dict) -> StoryVirtualProjection | None:
    """Restore a virtual Story projection from a session-safe dictionary."""
    if not isinstance(value, dict):
        return None

    def mapping_from_dict(mapping: dict) -> StoryVirtualMapping:
        return StoryVirtualMapping(
            game_block_id=str(mapping.get("game_block_id", "")),
            game_string_id=str(mapping.get("game_string_id", "")),
            string_index=int(mapping.get("string_index", -1)),
        )

    def folder_from_dict(folder: dict) -> StoryVirtualFolder:
        return StoryVirtualFolder(
            id=int(folder["id"]),
            node_type=str(folder.get("node_type", "chapter")),
            title=str(folder.get("title", "")),
            children=tuple(folder_from_dict(child) for child in folder.get("children", [])),
            mappings=tuple(mapping_from_dict(mapping) for mapping in folder.get("mappings", [])),
        )

    try:
        return StoryVirtualProjection(
            document_id=value.get("document_id"),
            roots=tuple(folder_from_dict(folder) for folder in value.get("roots", [])),
            speakers=tuple(
                StoryVirtualSpeaker(
                    name=str(speaker.get("name", "")),
                    mappings=tuple(
                        mapping_from_dict(mapping)
                        for mapping in speaker.get("mappings", [])
                    ),
                )
                for speaker in value.get("speakers", [])
            ),
        )
    except (KeyError, TypeError, ValueError):
        return None


@dataclass(frozen=True)
class StoryStringContext:
    """Saved virtual destinations for one physical game string."""

    structure_id: int | None
    structure_path: tuple[str, ...]
    speaker_name: str | None


def story_stable_id_for_mark(mark: HierarchyMark) -> str:
    """Return the normalized story id used when a hierarchy mark is imported."""
    return _stable_id(mark, _story_node_type(mark))


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
