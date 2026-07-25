import json

import pytest

from core.mempalace_client import MemePalaceClient
from core.mempalace.timeline_ai_analyzer import parse_timeline_response


def _story_with_link(client):
    conn = client._get_connection()
    document_id = conn.execute(
        "INSERT INTO story_documents (source_path, source_hash, markup_format, markup_version) "
        "VALUES ('story.json', 'source', 'json', 1) RETURNING id"
    ).fetchone()[0]
    node_id = conn.execute(
        """INSERT INTO story_nodes (
               stable_id, document_id, node_type, order_index, text,
               start_line, end_line, origin, source_payload
           ) VALUES ('dialogue:one', ?, 'dialogue', 0, 'Hello', 0, 0,
                     'markup_studio', '{}') RETURNING id""",
        (document_id,),
    ).fetchone()[0]
    conn.execute(
        """INSERT INTO story_dialogue_relations (
               document_id, game_block_id, game_block_name, string_index,
               game_string_id, dialogue_node_id, source_text_snapshot,
               relation_method, score, game_coverage, primary_link,
               relation_status, locked
           ) VALUES (?, '7', 'Dialog', 3, 'game:7:3', ?, 'Hello',
                     'exact_or_contained', 1, 1, 1, 'supported', 0)""",
        (document_id, node_id),
    )
    conn.commit()
    return document_id, node_id


def test_semantic_timeline_is_resolved_by_physical_string(tmp_path):
    client = MemePalaceClient(project_dir=str(tmp_path))
    document_id, node_id = _story_with_link(client)

    assert client.replace_story_event_contexts(document_id, [{
        "dialogue_node_id": node_id,
        "event_order": 2,
        "event_title": "A warning",
        "summary": "The guard warns the hero.",
        "location": "Town gate",
        "participants": ["Guard", "Hero"],
        "interactions": ["Guard → Hero: warns him"],
        "previous_event": "Arrival",
        "next_event": "Entry",
    }], "hash") == 1

    event = client.get_story_event_for_game_string("7", 3)
    assert event.event_title == "A warning"
    assert event.participants == ("Guard", "Hero")
    assert event.interactions == ("Guard → Hero: warns him",)
    assert "Immediately before: Arrival" in event.to_prompt_text()
    assert client.get_story_events(document_id) == (event,)


def test_timeline_parser_requires_exact_dialogue_coverage():
    valid = json.dumps({"events": [{
        "event_title": "Meeting",
        "summary": "Two characters meet.",
        "location": "Square",
        "participants": ["A", "B"],
        "dialogue_ids": ["d00001", "d00002"],
    }]})
    assert parse_timeline_response(valid, {"d00001", "d00002"})[0]["location"] == "Square"

    with pytest.raises(ValueError, match="cover dialogue IDs exactly"):
        parse_timeline_response(valid, {"d00001", "d00002", "d00003"})
