import sqlite3

import pytest

from core.mempalace.story_timeline import (
    StoryTimelineConflictError,
    normalize_hierarchy_project,
    normalize_reference_items,
)
from core.mempalace_client import MemePalaceClient
from core.script_markup import (
    HIERARCHY_FORMAT_VERSION,
    HIERARCHY_PROJECT_FORMAT,
    HierarchyType,
    default_type_definitions,
    parse_hierarchy_project,
)


def _project(*, include_dialogue=True, source_hash="hash-one"):
    definitions = default_type_definitions()
    marks = [
        {"start_line": 0, "end_line": 4, "depth": 0, "type_id": HierarchyType.STRUCTURE, "text": "Act I", "order": 1, "origin": "manual", "approved": True},
        {"start_line": 1, "end_line": 4, "depth": 1, "type_id": HierarchyType.STRUCTURE, "text": "Chapter One", "order": 2, "origin": "manual", "approved": True},
        {"start_line": 2, "end_line": 4, "depth": 2, "type_id": HierarchyType.STRUCTURE, "text": "Scene One", "order": 3, "origin": "manual", "approved": True},
        {"start_line": 3, "end_line": 3, "depth": 3, "type_id": HierarchyType.SPEAKER, "text": "MIDNA", "order": 4, "origin": "manual", "approved": True},
    ]
    if include_dialogue:
        marks.append(
            {"start_line": 4, "end_line": 4, "depth": 4, "type_id": HierarchyType.TEXT, "text": "Hello.", "order": 5, "origin": "manual", "approved": True}
        )
    payload = {
        "format": HIERARCHY_PROJECT_FORMAT,
        "version": HIERARCHY_FORMAT_VERSION,
        "source_path": "C:/scripts/raw.txt",
        "raw_text": "Act I\nChapter One\nScene One\nMIDNA\nHello.\n",
        "type_definitions": [
            {
                "type_id": definition.type_id,
                "label": definition.label,
                "description": definition.description,
                "color": definition.color,
            }
            for definition in definitions.values()
        ],
        "hierarchy_marks": marks,
    }
    return parse_hierarchy_project(
        payload,
        source_path="C:/project/script_markup_project.json",
        source_hash=source_hash,
    )


def _reference_project(*, include_item=True, source_hash="reference-one"):
    definitions = default_type_definitions()
    marks = [
        {"start_line": 0, "end_line": 2, "depth": 0, "type_id": HierarchyType.STRUCTURE, "text": "Collection Screen", "order": 1, "origin": "manual", "approved": True},
    ]
    if include_item:
        marks.extend([
            {"start_line": 1, "end_line": 1, "depth": 4, "type_id": HierarchyType.ITEM, "order": 2, "origin": "manual", "approved": True},
            {"start_line": 2, "end_line": 2, "depth": 5, "type_id": HierarchyType.ITEM_DESCRIPTION, "order": 3, "origin": "manual", "approved": True},
        ])
    payload = {
        "format": HIERARCHY_PROJECT_FORMAT,
        "version": HIERARCHY_FORMAT_VERSION,
        "source_path": "C:/scripts/items.txt",
        "raw_text": "Collection Screen\nWallet\nA wallet from your childhood.\n",
        "type_definitions": [
            {
                "type_id": definition.type_id,
                "label": definition.label,
                "description": definition.description,
                "color": definition.color,
            }
            for definition in definitions.values()
        ],
        "hierarchy_marks": marks,
    }
    return parse_hierarchy_project(
        payload,
        source_path="C:/project/items_markup_project.json",
        source_hash=source_hash,
    )


def test_normalize_hierarchy_project_preserves_order_and_parentage():
    nodes = normalize_hierarchy_project(_project())

    assert [node.node_type for node in nodes] == [
        "act", "chapter", "scene", "speaker", "dialogue"
    ]
    assert [node.order_index for node in nodes] == [0, 0, 0, 0, 0]
    assert nodes[0].parent_stable_id is None
    assert [node.parent_stable_id for node in nodes[1:]] == [
        node.stable_id for node in nodes[:-1]
    ]
    assert nodes[0].title == "Act I"
    assert nodes[-1].text == "Hello."


def test_reference_item_context_uses_containing_structure(tmp_path):
    client = MemePalaceClient(project_dir=str(tmp_path))
    result = client.sync_story_timeline(_reference_project())

    context = client.get_reference_item_context(result.document_id, "Wallet")

    assert context is not None
    assert context.structure_path == ("Collection Screen",)
    assert context.structure_id is not None


def test_normalize_dialogue_reads_current_source_range_not_stale_cached_text():
    project = _project()
    payload = {
        "format": project.format,
        "version": project.version,
        "source_path": project.raw_source_path,
        "raw_text": "Act I\nChapter One\nScene One\nLETTER\nAbout Mail Delivery\n",
        "type_definitions": [
            {
                "type_id": definition.type_id,
                "label": definition.label,
                "description": definition.description,
                "color": definition.color,
            }
            for definition in project.type_definitions
        ],
        "hierarchy_marks": [
            {
                "start_line": mark.start_line,
                "end_line": mark.end_line,
                "depth": mark.depth,
                "type_id": mark.type_id,
                "text": (
                    "Part of the Mirror of Twilight"
                    if mark.type_id == HierarchyType.TEXT else mark.text
                ),
                "label": mark.label,
                "description": mark.description,
                "color": mark.color,
                "order": mark.order,
                "start_col": mark.start_col,
                "end_col": mark.end_col,
                "origin": mark.origin,
                "approved": mark.approved,
            }
            for mark in project.hierarchy_marks
        ],
    }
    moved = parse_hierarchy_project(payload, source_path=project.source_path)

    nodes = normalize_hierarchy_project(moved)

    assert nodes[-2].title == "LETTER"
    assert nodes[-1].text == "About Mail Delivery"


def test_item_catalog_is_stored_separately_from_story_dialogue(tmp_path):
    project = _reference_project()

    assert [node.node_type for node in normalize_hierarchy_project(project)] == ["act"]
    references = normalize_reference_items(project)
    assert [(item.name, item.description) for item in references] == [
        ("Wallet", "A wallet from your childhood."),
    ]

    client = MemePalaceClient(project_dir=str(tmp_path))
    first = client.sync_story_timeline(project)
    stored = client.get_reference_items(first.document_id)
    assert [(item.name, item.description) for item in stored] == [
        ("Wallet", "A wallet from your childhood."),
    ]
    assert (first.inserted_or_updated, first.reference_items) == (1, 1)
    assert client._get_connection().execute(
        "SELECT COUNT(*) FROM story_nodes WHERE document_id = ? AND node_type IN ('speaker', 'dialogue')",
        (first.document_id,),
    ).fetchone()[0] == 0

    second = client.sync_story_timeline(
        _reference_project(include_item=False, source_hash="reference-two")
    )
    assert second.reference_items_removed == 1
    assert client.get_reference_items(first.document_id) == ()


def test_sync_story_timeline_is_idempotent_and_preserves_row_ids(tmp_path):
    client = MemePalaceClient(project_dir=str(tmp_path))
    project = _project()

    first = client.sync_story_timeline(project)
    conn = client._get_connection()
    first_ids = dict(conn.execute(
        "SELECT stable_id, id FROM story_nodes WHERE document_id = ?",
        (first.document_id,),
    ))
    second = client.sync_story_timeline(project)
    second_ids = dict(conn.execute(
        "SELECT stable_id, id FROM story_nodes WHERE document_id = ?",
        (second.document_id,),
    ))

    assert first.document_id == second.document_id
    assert first_ids == second_ids
    assert second.inserted_or_updated == 5
    assert second.removed == 0


def test_sync_story_timeline_removes_only_stale_imported_nodes(tmp_path):
    client = MemePalaceClient(project_dir=str(tmp_path))
    first = client.sync_story_timeline(_project())

    result = client.sync_story_timeline(
        _project(include_dialogue=False, source_hash="hash-two")
    )
    conn = client._get_connection()
    rows = conn.execute(
        "SELECT node_type FROM story_nodes WHERE document_id = ? ORDER BY id",
        (first.document_id,),
    ).fetchall()

    assert result.document_id == first.document_id
    assert result.removed == 1
    assert [row[0] for row in rows] == ["act", "chapter", "scene", "speaker"]
    assert conn.execute(
        "SELECT source_hash FROM story_documents WHERE id = ?",
        (first.document_id,),
    ).fetchone()[0] == "hash-two"


def test_sync_story_timeline_rolls_back_when_manual_child_would_be_lost(tmp_path):
    client = MemePalaceClient(project_dir=str(tmp_path))
    first = client.sync_story_timeline(_project())
    conn = client._get_connection()
    dialogue_id = conn.execute(
        "SELECT id FROM story_nodes WHERE document_id = ? AND node_type = 'dialogue'",
        (first.document_id,),
    ).fetchone()[0]
    conn.execute(
        """
        INSERT INTO story_nodes (
            stable_id, document_id, parent_id, node_type, order_index,
            text, origin, approved, source_payload, source_version
        ) VALUES ('manual-note', ?, ?, 'context', 0, 'Keep', 'manual', 1, NULL, 1)
        """,
        (first.document_id, dialogue_id),
    )
    conn.commit()

    with pytest.raises(StoryTimelineConflictError, match="manual-note") as raised:
        client.sync_story_timeline(
            _project(include_dialogue=False, source_hash="hash-two")
        )

    assert raised.value.conflict_id is not None
    conflicts = client.get_story_sync_conflicts(_project().source_path)
    assert len(conflicts) == 1
    assert conflicts[0].id == raised.value.conflict_id
    assert conflicts[0].conflict_type == "manual_descendant"
    assert conflicts[0].manual_stable_id == "manual-note"
    assert conflicts[0].status == "open"
    assert conn.execute(
        "SELECT source_hash FROM story_documents WHERE id = ?",
        (first.document_id,),
    ).fetchone()[0] == "hash-one"
    assert conn.execute(
        "SELECT COUNT(*) FROM story_nodes WHERE document_id = ?",
        (first.document_id,),
    ).fetchone()[0] == 6

    with pytest.raises(StoryTimelineConflictError) as repeated:
        client.sync_story_timeline(
            _project(include_dialogue=False, source_hash="hash-two")
        )
    assert repeated.value.conflict_id == raised.value.conflict_id
    assert len(client.get_story_sync_conflicts(_project().source_path)) == 1
    assert client.resolve_story_sync_conflict(raised.value.conflict_id)
    assert client.get_story_sync_conflicts(_project().source_path) == ()
    assert len(client.get_story_sync_conflicts(
        _project().source_path, status="resolved"
    )) == 1


def test_story_timeline_rejects_duplicate_manual_stable_id(tmp_path):
    client = MemePalaceClient(project_dir=str(tmp_path))
    result = client.sync_story_timeline(_project())
    conn = client._get_connection()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO story_nodes (
                stable_id, document_id, node_type, order_index, source_version
            ) VALUES (?, ?, 'context', 0, 1)
            """,
            (next(iter(normalize_hierarchy_project(_project()))).stable_id, result.document_id),
        )


def test_story_timeline_query_api_returns_paths_neighbors_and_position(tmp_path):
    client = MemePalaceClient(project_dir=str(tmp_path))
    result = client.sync_story_timeline(_project())
    normalized = normalize_hierarchy_project(_project())
    act, chapter, scene, speaker, dialogue = normalized

    stored_dialogue = client.get_story_node(result.document_id, dialogue.stable_id)
    assert stored_dialogue is not None
    assert stored_dialogue.text == "Hello."
    assert [node.stable_id for node in client.get_story_ancestors(
        result.document_id, dialogue.stable_id
    )] == [act.stable_id, chapter.stable_id, scene.stable_id, speaker.stable_id]
    assert [node.stable_id for node in client.get_story_descendants(
        result.document_id, act.stable_id
    )] == [chapter.stable_id, scene.stable_id, speaker.stable_id, dialogue.stable_id]

    previous, next_node = client.get_story_neighbors(result.document_id, dialogue.stable_id)
    assert previous.stable_id == speaker.stable_id
    assert next_node is None
    previous, next_node = client.get_story_neighbors(result.document_id, act.stable_id)
    assert previous is None
    assert next_node.stable_id == chapter.stable_id

    position = client.get_story_timeline_position(result.document_id, dialogue.stable_id)
    assert (position.index, position.total, position.progress) == (5, 5, 1.0)
    assert [node.node_type for node in position.path] == ["act", "chapter", "scene"]


def test_story_virtual_projection_uses_normalized_hierarchy_and_active_relations(tmp_path):
    client = MemePalaceClient(project_dir=str(tmp_path))
    result = client.sync_story_timeline(_project())
    dialogue = normalize_hierarchy_project(_project())[-1]
    stored_dialogue = client.get_story_node(result.document_id, dialogue.stable_id)
    conn = client._get_connection()
    relation_values = (
        result.document_id, "1", "zel_01", 1, "zel_01_Str_1",
        stored_dialogue.id, "Hello.", "exact_or_contained", 1.0, 1.0,
    )
    conn.execute(
        """
        INSERT INTO story_dialogue_relations (
            document_id, game_block_id, game_block_name, string_index,
            game_string_id, dialogue_node_id, source_text_snapshot,
            relation_method, score, game_coverage, relation_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'supported')
        """,
        relation_values,
    )
    conn.execute(
        """
        INSERT INTO story_dialogue_relations (
            document_id, game_block_id, game_block_name, string_index,
            game_string_id, dialogue_node_id, source_text_snapshot,
            relation_method, score, game_coverage, relation_status
        ) VALUES (?, '0', 'zel_00', 0, 'zel_00_Str_0', ?, 'No',
                  'manual', 1.0, 1.0, 'rejected')
        """,
        (result.document_id, stored_dialogue.id),
    )
    conn.commit()

    projection = client.get_story_virtual_projection()

    assert projection.document_id == result.document_id
    act = projection.roots[0]
    chapter = act.children[0]
    scene = chapter.children[0]
    assert [act.title, chapter.title, scene.title] == [
        "Act I", "Chapter One", "Scene One"
    ]
    assert [(m.game_block_id, m.string_index) for m in scene.mappings] == [("1", 1)]
    assert [(speaker.name, len(speaker.mappings)) for speaker in projection.speakers] == [
        ("MIDNA", 1)
    ]
    assert client.get_story_speakers_for_game_string("1", 1) == ("MIDNA",)
    assert client.get_story_speakers_for_game_string("0", 0) == ()
    target = client.get_story_navigation_target("1", 1)
    assert target is not None
    assert target.stable_id == dialogue.stable_id
    assert client.get_story_navigation_target("0", 0) is None
    contexts = client.get_story_string_contexts("1", 1)
    assert len(contexts) == 1
    assert contexts[0].structure_path == ("Act I", "Chapter One", "Scene One")
    assert contexts[0].structure_id == scene.id
    assert contexts[0].speaker_name == "MIDNA"
    mappings = client.get_story_mappings_for_node(result.document_id, dialogue.stable_id)
    assert [(mapping.game_block_id, mapping.string_index) for mapping in mappings] == [("1", 1)]
    assert client.get_story_document_source_path(result.document_id) == _project().source_path
