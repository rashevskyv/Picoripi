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


def _event(title, ids, **extra):
    return {"event_title": title, "summary": "", "location": "",
            "participants": [], "dialogue_ids": ids, **extra}


def test_a_line_claimed_twice_stays_with_the_first_event():
    """The model repeats a line across neighbouring events; that is a slip.

    Failing the whole pass over it threw away an analysis of thousands of lines
    and reported "missing=[], unknown=[]", which named nothing at all.
    """
    payload = json.dumps({"events": [
        _event("Arrival", ["d00001", "d00002"]),
        _event("Warning", ["d00002", "d00003"]),
    ]})

    events = parse_timeline_response(payload, {"d00001", "d00002", "d00003"})

    assert [e["dialogue_ids"] for e in events] == [["d00001", "d00002"], ["d00003"]]


def test_an_event_whose_lines_all_belong_earlier_is_dropped():
    payload = json.dumps({"events": [
        _event("Arrival", ["d00001", "d00002"]),
        _event("Repeat", ["d00001"]),
    ]})

    events = parse_timeline_response(payload, {"d00001", "d00002"})

    assert [e["event_title"] for e in events] == ["Arrival"]


def test_a_repeat_never_hides_a_line_the_ai_missed():
    """Deduplicating must not turn incomplete coverage into a silent pass."""
    payload = json.dumps({"events": [
        _event("Arrival", ["d00001", "d00001"]),
    ]})

    with pytest.raises(ValueError, match="missing=\\['d00002'\\]"):
        parse_timeline_response(payload, {"d00001", "d00002"})


def test_story_timeline_worker_chunking_and_retry(tmp_path):
    from unittest.mock import MagicMock
    from core.mempalace.timeline_ai_analyzer import StoryTimelineAIAnalyzerWorker

    client = MemePalaceClient(project_dir=str(tmp_path))
    document_id, node_id = _story_with_link(client)

    ai_provider = MagicMock()
    call_count = 0

    def mock_translate(messages, session=None, settings_override=None):
        nonlocal call_count
        call_count += 1
        assert settings_override is not None
        assert settings_override.get("timeout") == 300
        # Fail on first attempt to test retry
        if call_count == 1:
            raise TimeoutError("Simulated timeout")
        resp = MagicMock()
        resp.text = json.dumps({
            "events": [{
                "event_title": "Hero Arrives",
                "summary": "Arrival in town",
                "location": "Town gate",
                "participants": ["Hero"],
                "interactions": [],
                "dialogue_ids": ["d00001"],
            }]
        })
        return resp

    ai_provider.translate = mock_translate

    worker = StoryTimelineAIAnalyzerWorker(
        client=client,
        ai_provider=ai_provider,
        document_id=document_id,
        target_lang="Ukrainian",
    )

    results = []
    worker.finished.connect(lambda ok, msg: results.append((ok, msg)))
    worker.run()

    assert len(results) == 1
    assert results[0][0] is True
    assert "Built 1 story events" in results[0][1]
    assert call_count == 2  # 1 fail + 1 retry success
