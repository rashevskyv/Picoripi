import json
from types import SimpleNamespace

from core.mempalace_client import MemePalaceClient
from core.mempalace.normalized_character_profiler import (
    chunk_character_dialogues,
    collect_character_dialogues,
    parse_character_profile,
)


def test_collects_dialogue_under_repeated_normalized_speaker_nodes():
    nodes = (
        SimpleNamespace(id=1, parent_id=None, node_type="chapter", title="One", text=None),
        SimpleNamespace(id=2, parent_id=1, node_type="speaker", title="Midna", text=None),
        SimpleNamespace(id=3, parent_id=2, node_type="dialogue", title=None, text="Move!"),
        SimpleNamespace(id=4, parent_id=1, node_type="speaker", title="Midna", text=None),
        SimpleNamespace(id=5, parent_id=4, node_type="dialogue", title=None, text="Listen."),
    )
    result = collect_character_dialogues(nodes)
    assert [item["text"] for item in result["Midna"]] == ["Move!", "Listen."]
    assert result["Midna"][0]["path"] == "One"


def test_character_profile_is_resolved_for_linked_game_string(tmp_path):
    client = MemePalaceClient(project_dir=str(tmp_path))
    conn = client._get_connection()
    document_id = conn.execute(
        "INSERT INTO story_documents (source_path, source_hash, markup_format, markup_version) "
        "VALUES ('story.json', 'source', 'json', 1) RETURNING id"
    ).fetchone()[0]
    speaker_id = conn.execute(
        """INSERT INTO story_nodes (
               stable_id, document_id, node_type, order_index, title, origin, source_payload
           ) VALUES ('speaker:midna', ?, 'speaker', 0, 'Midna', 'markup_studio', '{}')
           RETURNING id""",
        (document_id,),
    ).fetchone()[0]
    dialogue_id = conn.execute(
        """INSERT INTO story_nodes (
               stable_id, document_id, parent_id, node_type, order_index, text,
               origin, source_payload
           ) VALUES ('dialogue:one', ?, ?, 'dialogue', 0, 'Move!',
                     'markup_studio', '{}') RETURNING id""",
        (document_id, speaker_id),
    ).fetchone()[0]
    conn.execute(
        """INSERT INTO story_dialogue_relations (
               document_id, game_block_id, game_block_name, string_index,
               game_string_id, dialogue_node_id, source_text_snapshot,
               relation_method, score, game_coverage, primary_link,
               relation_status, locked
           ) VALUES (?, '2', 'Dialog', 4, 'game:2:4', ?, 'Move!',
                     'exact_or_contained', 1, 1, 1, 'supported', 0)""",
        (document_id, dialogue_id),
    )
    conn.commit()

    client.replace_character_profiles(document_id, [{
        "speaker_name": "Midna",
        "role": "Companion",
        "personality": "Sharp and impatient.",
        "speech_style": "Short imperatives.",
        "vocabulary": "Direct action verbs.",
        "relationships": "Teases the hero.",
        "address_and_grammar": "Informal address.",
        "translation_advice": "Keep commands compact.",
        "evidence_notes": "",
        "dialogue_count": 20,
    }], "hash")

    profiles = client.get_character_profiles_for_game_string("2", 4)
    assert len(profiles) == 1
    assert profiles[0].speaker_name == "Midna"
    assert "Translation direction: Keep commands compact." in profiles[0].to_prompt_text()


def test_character_profile_parser_validates_structured_ai_response():
    payload = {
        "is_character": True,
        "role": "Guide",
        "personality": "Impatient",
        "speech_style": "Direct",
        "vocabulary": "Imperatives",
        "relationships": "Protective",
        "address_and_grammar": "Informal",
        "translation_advice": "Prefer short commands",
        "evidence_notes": "Based on five lines",
    }
    assert parse_character_profile(json.dumps(payload))["speech_style"] == "Direct"


def test_character_dialogue_chunking_preserves_every_line():
    lines = [{"path": "Chapter", "text": f"Line {index}"} for index in range(137)]
    chunks = chunk_character_dialogues(lines)
    assert [line for chunk in chunks for line in chunk] == lines
    assert all(len(chunk) <= 60 for chunk in chunks)
