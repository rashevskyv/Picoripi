import pytest

from core.mempalace.dialogue_mapping import (
    DialogueMappingCancelled,
    DialogueMappingInput,
    GameString,
    canonicalize_dialogue_text,
)
from core.mempalace_client import MemePalaceClient


def _database_with_story_nodes(tmp_path):
    client = MemePalaceClient(project_dir=str(tmp_path))
    conn = client._get_connection()
    document_id = conn.execute(
        """
        INSERT INTO story_documents (
            source_path, source_hash, markup_format, markup_version
        ) VALUES ('project.json', 'hash', 'hierarchy', 1)
        """
    ).lastrowid
    scene_id = conn.execute(
        """
        INSERT INTO story_nodes (
            stable_id, document_id, node_type, order_index, title
        ) VALUES ('scene:1', ?, 'scene', 0, 'Scene')
        """,
        (document_id,),
    ).lastrowid
    dialogue_id = conn.execute(
        """
        INSERT INTO story_nodes (
            stable_id, document_id, parent_id, node_type, order_index, text
        ) VALUES ('dialogue:1', ?, ?, 'dialogue', 0, 'Hello')
        """,
        (document_id, scene_id),
    ).lastrowid
    conn.commit()
    return client, document_id, scene_id, dialogue_id


def _mapping(document_id, dialogue_id, **changes):
    values = {
        "document_id": document_id,
        "game_block_id": "12",
        "game_block_name": "zel_00",
        "string_index": 7,
        "game_string_id": "zel_00:7",
        "source_text_snapshot": "Hello",
        "dialogue_node_id": dialogue_id,
        "match_method": "exact_text",
        "confidence": 1.0,
        "review_status": "matched",
    }
    values.update(changes)
    return DialogueMappingInput(**values)


def test_dialogue_mapping_targets_exact_dialogue_node(tmp_path):
    client, document_id, _scene_id, dialogue_id = _database_with_story_nodes(tmp_path)

    result = client.upsert_dialogue_mapping(_mapping(document_id, dialogue_id))

    assert not result.preserved_locked_mapping
    assert result.mapping.dialogue_node_id == dialogue_id
    assert result.mapping.match_method == "exact_text"
    assert result.mapping.confidence == 1.0
    assert client.get_dialogue_mappings(document_id) == (result.mapping,)


def test_dialogue_mapping_preserves_locked_manual_decision(tmp_path):
    client, document_id, _scene_id, dialogue_id = _database_with_story_nodes(tmp_path)
    manual = client.upsert_dialogue_mapping(_mapping(
        document_id,
        dialogue_id,
        match_method="manual",
        review_status="approved",
        reviewed_by="translator",
        locked=True,
    )).mapping

    automatic = client.upsert_dialogue_mapping(_mapping(
        document_id,
        None,
        match_method="unmatched",
        confidence=0.0,
        review_status="unmatched",
    ))

    assert automatic.preserved_locked_mapping
    assert automatic.mapping == manual
    assert automatic.mapping.reviewed_at is not None


def test_dialogue_mapping_allows_explicit_locked_override(tmp_path):
    client, document_id, _scene_id, dialogue_id = _database_with_story_nodes(tmp_path)
    client.upsert_dialogue_mapping(_mapping(
        document_id, dialogue_id, match_method="manual",
        review_status="approved", locked=True,
    ))

    result = client.upsert_dialogue_mapping(
        _mapping(
            document_id,
            None,
            match_method="unmatched",
            confidence=0.0,
            review_status="unmatched",
            locked=False,
        ),
        allow_locked_override=True,
    )

    assert not result.preserved_locked_mapping
    assert result.mapping.dialogue_node_id is None
    assert not result.mapping.locked


def test_dialogue_mapping_rejects_non_dialogue_target(tmp_path):
    client, document_id, scene_id, _dialogue_id = _database_with_story_nodes(tmp_path)

    with pytest.raises(ValueError, match="dialogue node"):
        client.upsert_dialogue_mapping(_mapping(document_id, scene_id))


def test_dialogue_mapping_filters_review_queue(tmp_path):
    client, document_id, _scene_id, dialogue_id = _database_with_story_nodes(tmp_path)
    client.upsert_dialogue_mapping(_mapping(
        document_id,
        dialogue_id,
        review_status="needs_review",
        confidence=0.72,
        match_method="fuzzy",
    ))

    queue = client.get_dialogue_mappings(document_id, review_status="needs_review")

    assert len(queue) == 1
    assert queue[0].game_string_id == "zel_00:7"
    assert queue[0].confidence == 0.72


def test_matcher_prefers_exact_identifier_over_text(tmp_path):
    client, document_id, _scene_id, dialogue_id = _database_with_story_nodes(tmp_path)
    conn = client._get_connection()
    conn.execute(
        "UPDATE story_nodes SET text = '[zel_00_Str_7]: Different wording' WHERE id = ?",
        (dialogue_id,),
    )
    conn.commit()

    summary = client.match_game_strings(document_id, [GameString(
        block_id="0",
        block_name="zel_00",
        string_index=7,
        stable_id="zel_00_Str_7",
        text="Game text does not need to match",
    )])

    mapping = client.get_dialogue_mappings(document_id)[0]
    assert summary.exact_id == 1
    assert mapping.dialogue_node_id == dialogue_id
    assert mapping.review_status == "matched"


def test_matcher_uses_unique_normalized_exact_text(tmp_path):
    client, document_id, _scene_id, dialogue_id = _database_with_story_nodes(tmp_path)

    summary = client.match_game_strings(document_id, [GameString(
        block_id="0",
        block_name="zel_00",
        string_index=7,
        stable_id="zel_00_Str_7",
        text="  HELLO  ",
    )])

    mapping = client.get_dialogue_mappings(document_id)[0]
    assert summary.exact_text == 1
    assert mapping.dialogue_node_id == dialogue_id
    assert mapping.match_method == "exact_text"


def test_matcher_sends_repeated_exact_text_to_review(tmp_path):
    client, document_id, scene_id, _dialogue_id = _database_with_story_nodes(tmp_path)
    conn = client._get_connection()
    conn.execute(
        "UPDATE story_nodes SET text = 'Hello there' WHERE stable_id = 'dialogue:1'"
    )
    conn.execute(
        """
        INSERT INTO story_nodes (
            stable_id, document_id, parent_id, node_type, order_index, text
        ) VALUES ('dialogue:2', ?, ?, 'dialogue', 1, 'Hello there')
        """,
        (document_id, scene_id),
    )
    conn.commit()

    summary = client.match_game_strings(document_id, [GameString(
        block_id="0", block_name="zel_00", string_index=7,
        stable_id="zel_00_Str_7", text="Hello there",
    )])

    mapping = client.get_dialogue_mappings(document_id)[0]
    assert summary.needs_review == 1
    assert mapping.dialogue_node_id is None
    assert mapping.review_status == "needs_review"
    assert "repeated" in mapping.conflict_reason


def test_matcher_excludes_repeated_short_text_from_review(tmp_path):
    client, document_id, scene_id, _dialogue_id = _database_with_story_nodes(tmp_path)
    conn = client._get_connection()
    conn.execute("UPDATE story_nodes SET text = 'Yes' WHERE stable_id = 'dialogue:1'")
    conn.execute(
        """
        INSERT INTO story_nodes (
            stable_id, document_id, parent_id, node_type, order_index, text
        ) VALUES ('dialogue:yes-2', ?, ?, 'dialogue', 1, 'Yes')
        """,
        (document_id, scene_id),
    )
    conn.commit()

    summary = client.match_game_strings(document_id, [GameString(
        "0", "zel_00", 7, "zel_00_Str_7", "Yes"
    )])

    mapping = client.get_dialogue_mappings(document_id)[0]
    assert summary.needs_review == 0
    assert summary.unmatched == 1
    assert mapping.review_status == "unmatched"
    assert "intentionally skipped" in mapping.conflict_reason


def test_matcher_skips_unique_generic_short_reply(tmp_path):
    client, document_id, _scene_id, _dialogue_id = _database_with_story_nodes(tmp_path)
    conn = client._get_connection()
    conn.execute("UPDATE story_nodes SET text = 'OK' WHERE stable_id = 'dialogue:1'")
    conn.commit()

    summary = client.match_game_strings(document_id, [GameString(
        "0", "zel_00", 7, "zel_00_Str_7", "OK"
    )])

    mapping = client.get_dialogue_mappings(document_id)[0]
    assert summary.exact_text == 0
    assert summary.unmatched == 1
    assert mapping.dialogue_node_id is None
    assert mapping.review_status == "unmatched"


def test_matcher_ignores_unapproved_dialogue_nodes(tmp_path):
    client, document_id, scene_id, dialogue_id = _database_with_story_nodes(tmp_path)
    conn = client._get_connection()
    unapproved_id = conn.execute(
        """
        INSERT INTO story_nodes (
            stable_id, document_id, parent_id, node_type, order_index, text, approved
        ) VALUES ('dialogue:unapproved', ?, ?, 'dialogue', 1, 'Hello', 0)
        """,
        (document_id, scene_id),
    ).lastrowid
    conn.commit()

    summary = client.match_game_strings(document_id, [GameString(
        "0", "zel_00", 7, "zel_00_Str_7", "Hello"
    )])

    mapping = client.get_dialogue_mappings(document_id)[0]
    assert summary.exact_text == 1
    assert mapping.dialogue_node_id == dialogue_id
    assert mapping.dialogue_node_id != unapproved_id


def test_matcher_resolves_repeated_text_from_previous_marked_dialogue(tmp_path):
    client, document_id, scene_id, dialogue_id = _database_with_story_nodes(tmp_path)
    conn = client._get_connection()
    conn.execute("DELETE FROM story_nodes WHERE id = ?", (dialogue_id,))
    link_id = conn.execute(
        "INSERT INTO story_nodes (stable_id, document_id, parent_id, node_type, order_index, title) "
        "VALUES ('speaker:link', ?, ?, 'speaker', 0, 'LINK')",
        (document_id, scene_id),
    ).lastrowid
    midna_id = conn.execute(
        "INSERT INTO story_nodes (stable_id, document_id, parent_id, node_type, order_index, title) "
        "VALUES ('speaker:midna', ?, ?, 'speaker', 1, 'MIDNA')",
        (document_id, scene_id),
    ).lastrowid
    for stable_id, parent_id, order_index, text in (
        ("dialogue:link-before", link_id, 0, "The gate is closed."),
        ("dialogue:link-repeat", link_id, 1, "I understand."),
        ("dialogue:midna-before", midna_id, 0, "Listen carefully."),
        ("dialogue:midna-repeat", midna_id, 1, "I understand."),
    ):
        conn.execute(
            "INSERT INTO story_nodes (stable_id, document_id, parent_id, node_type, order_index, text) "
            "VALUES (?, ?, ?, 'dialogue', ?, ?)",
            (stable_id, document_id, parent_id, order_index, text),
        )
    conn.commit()

    summary = client.match_game_strings(document_id, [
        GameString("0", "zel_00", 0, "zel_00_Str_0", "Listen carefully."),
        GameString("0", "zel_00", 1, "zel_00_Str_1", "I understand."),
    ])

    mapping = client.get_dialogue_mappings(document_id)[1]
    parent_title = conn.execute(
        "SELECT parent.title FROM story_nodes dialogue "
        "JOIN story_nodes parent ON parent.id = dialogue.parent_id "
        "WHERE dialogue.id = ?",
        (mapping.dialogue_node_id,),
    ).fetchone()[0]
    assert summary.needs_review == 0
    assert mapping.review_status == "matched"
    assert mapping.match_method == "exact_text"
    assert "previous marked dialogue context" in mapping.conflict_reason
    assert parent_title == "MIDNA"


def test_matcher_resolves_repeated_text_from_next_marked_dialogue(tmp_path):
    client, document_id, scene_id, dialogue_id = _database_with_story_nodes(tmp_path)
    conn = client._get_connection()
    conn.execute("DELETE FROM story_nodes WHERE id = ?", (dialogue_id,))
    link_id = conn.execute(
        "INSERT INTO story_nodes (stable_id, document_id, parent_id, node_type, order_index, title) "
        "VALUES ('speaker:link', ?, ?, 'speaker', 0, 'LINK')",
        (document_id, scene_id),
    ).lastrowid
    midna_id = conn.execute(
        "INSERT INTO story_nodes (stable_id, document_id, parent_id, node_type, order_index, title) "
        "VALUES ('speaker:midna', ?, ?, 'speaker', 1, 'MIDNA')",
        (document_id, scene_id),
    ).lastrowid
    expected_id = None
    for stable_id, parent_id, order_index, text in (
        ("dialogue:link-repeat", link_id, 0, "I understand."),
        ("dialogue:link-after", link_id, 1, "Then open the gate."),
        ("dialogue:midna-repeat", midna_id, 0, "I understand."),
        ("dialogue:midna-after", midna_id, 1, "Now follow me."),
    ):
        node_id = conn.execute(
            "INSERT INTO story_nodes (stable_id, document_id, parent_id, node_type, order_index, text) "
            "VALUES (?, ?, ?, 'dialogue', ?, ?)",
            (stable_id, document_id, parent_id, order_index, text),
        ).lastrowid
        if stable_id == "dialogue:midna-repeat":
            expected_id = node_id
    conn.commit()

    summary = client.match_game_strings(document_id, [
        GameString("0", "zel_00", 0, "zel_00_Str_0", "I understand."),
        GameString("0", "zel_00", 1, "zel_00_Str_1", "Now follow me."),
    ])

    mapping = client.get_dialogue_mappings(document_id)[0]
    assert summary.needs_review == 0
    assert mapping.dialogue_node_id == expected_id
    assert "next marked dialogue context" in mapping.conflict_reason


def test_matcher_does_not_use_neighbor_from_another_game_block(tmp_path):
    client, document_id, scene_id, dialogue_id = _database_with_story_nodes(tmp_path)
    conn = client._get_connection()
    conn.execute("UPDATE story_nodes SET text = 'Listen carefully.' WHERE id = ?", (dialogue_id,))
    conn.execute(
        "INSERT INTO story_nodes (stable_id, document_id, parent_id, node_type, order_index, text) "
        "VALUES ('dialogue:repeat-1', ?, ?, 'dialogue', 1, 'I understand.')",
        (document_id, scene_id),
    )
    conn.execute(
        "INSERT INTO story_nodes (stable_id, document_id, parent_id, node_type, order_index, text) "
        "VALUES ('dialogue:repeat-2', ?, ?, 'dialogue', 2, 'I understand.')",
        (document_id, scene_id),
    )
    conn.commit()

    summary = client.match_game_strings(document_id, [
        GameString("block-a", "zel_00", 0, "zel_00_Str_0", "Listen carefully."),
        GameString("block-b", "zel_01", 1, "zel_01_Str_1", "I understand."),
    ])

    repeated = client.get_dialogue_mappings(
        document_id, review_status="needs_review"
    )[0]
    assert summary.needs_review == 1
    assert repeated.dialogue_node_id is None


def test_matcher_proposes_fuzzy_candidate_but_requires_review(tmp_path):
    client, document_id, _scene_id, dialogue_id = _database_with_story_nodes(tmp_path)
    conn = client._get_connection()
    conn.execute(
        "UPDATE story_nodes SET text = 'Welcome to Hyrule Castle!' WHERE id = ?",
        (dialogue_id,),
    )
    conn.commit()

    summary = client.match_game_strings(document_id, [GameString(
        block_id="0", block_name="zel_00", string_index=7,
        stable_id="zel_00_Str_7", text="Welcome to the Hyrule Castle!",
    )])

    mapping = client.get_dialogue_mappings(document_id)[0]
    assert summary.needs_review == 1
    assert mapping.dialogue_node_id == dialogue_id
    assert mapping.match_method == "fuzzy"
    assert 0.82 <= mapping.confidence < 1.0
    assert "margin" in mapping.conflict_reason


def test_matcher_ignores_presentation_punctuation_for_exact_match(tmp_path):
    client, document_id, _scene_id, dialogue_id = _database_with_story_nodes(tmp_path)
    conn = client._get_connection()
    conn.execute(
        "UPDATE story_nodes SET text = 'Welcome to Hyrule Castle!' WHERE id = ?",
        (dialogue_id,),
    )
    conn.commit()

    summary = client.match_game_strings(document_id, [GameString(
        "0", "zel_00", 7, "zel_00_Str_7", "Welcome to Hyrule Castle."
    )])

    mapping = client.get_dialogue_mappings(document_id)[0]
    assert summary.exact_text == 1
    assert summary.needs_review == 0
    assert mapping.review_status == "matched"
    assert mapping.match_method == "exact_text"
    assert mapping.confidence == 1.0


def test_matcher_maps_multiple_game_strings_into_one_marked_dialogue_block(tmp_path):
    client, document_id, _scene_id, dialogue_id = _database_with_story_nodes(tmp_path)
    conn = client._get_connection()
    conn.execute(
        "UPDATE story_nodes SET text = ? WHERE id = ?",
        (
            "Tell me... Do you ever feel a strange sadness as dusk falls?\n"
            "They say it is the only time when our world intersects with theirs.",
            dialogue_id,
        ),
    )
    conn.commit()

    summary = client.match_game_strings(document_id, [
        GameString(
            "0", "zel_00", 0, "zel_00_Str_0",
            "Tell me... Do you ever feel a strange sadness as dusk falls?",
        ),
        GameString(
            "0", "zel_00", 1, "zel_00_Str_1",
            "They say it is the only time when our world intersects with theirs.",
        ),
    ])

    mappings = client.get_dialogue_mappings(document_id)
    assert summary.exact_text == 2
    assert summary.located_dialogues == 1
    assert [mapping.dialogue_node_id for mapping in mappings] == [dialogue_id, dialogue_id]


def test_matcher_ignores_bmg_control_tags_inside_game_text(tmp_path):
    client, document_id, _scene_id, dialogue_id = _database_with_story_nodes(tmp_path)
    conn = client._get_connection()
    conn.execute(
        "UPDATE story_nodes SET text = 'The Master Sword has awakened!' WHERE id = ?",
        (dialogue_id,),
    )
    conn.commit()

    summary = client.match_game_strings(document_id, [GameString(
        "0", "zel_00", 0, "zel_00_Str_0",
        "The {escape:255:000001}Master Sword{escape:255:000000} has awakened!",
    )])

    mapping = client.get_dialogue_mappings(document_id)[0]
    assert summary.exact_text == 1
    assert mapping.dialogue_node_id == dialogue_id


def test_matcher_infers_stable_tag_equivalent_from_marked_context(tmp_path):
    client, document_id, _scene_id, dialogue_id = _database_with_story_nodes(tmp_path)
    conn = client._get_connection()
    conn.execute(
        "UPDATE story_nodes SET text = ? WHERE id = ?",
        (
            "Young Master Link, what is the trouble? "
            "Tell me, Master Link, have you thought about what I told you?",
            dialogue_id,
        ),
    )
    conn.commit()

    summary = client.match_game_strings(document_id, [
        GameString(
            "0", "zel_00", 0, "zel_00_Str_0",
            "Young Master {escape:0:0000}... What is the trouble?",
        ),
        GameString(
            "0", "zel_00", 1, "zel_00_Str_1",
            "Tell me, Master {escape:0:0000}... Have you thought about what I told you?",
        ),
    ])

    mappings = client.get_dialogue_mappings(document_id)
    assert summary.exact_text == 2
    assert summary.inferred_tag_equivalents == (("{escape:0:0000}", "link"),)
    assert [mapping.dialogue_node_id for mapping in mappings] == [dialogue_id, dialogue_id]


def test_matcher_fuzzy_matches_one_message_inside_larger_speaker_paragraph(tmp_path):
    client, document_id, _scene_id, dialogue_id = _database_with_story_nodes(tmp_path)
    conn = client._get_connection()
    conn.execute(
        "UPDATE story_nodes SET text = ? WHERE id = ?",
        (
            "You have traveled a very long way. "
            "Welcome back to the ancient kingdom of Hyrule. "
            "The princess is waiting for you in the tower.",
            dialogue_id,
        ),
    )
    conn.commit()

    summary = client.match_game_strings(document_id, [GameString(
        "0", "zel_00", 0, "zel_00_Str_0",
        "Welcome to the ancient kingdom of Hyrule!",
    )])

    mapping = client.get_dialogue_mappings(document_id)[0]
    assert summary.needs_review == 1
    assert mapping.dialogue_node_id == dialogue_id
    assert mapping.match_method == "fuzzy"


def test_matcher_normalizes_line_breaks_for_exact_text(tmp_path):
    client, document_id, _scene_id, dialogue_id = _database_with_story_nodes(tmp_path)
    conn = client._get_connection()
    conn.execute(
        "UPDATE story_nodes SET text = 'Hello\nthere' WHERE id = ?",
        (dialogue_id,),
    )
    conn.commit()

    summary = client.match_game_strings(document_id, [GameString(
        "0", "zel_00", 7, "zel_00_Str_7", "Hello there"
    )])

    assert summary.exact_text == 1


def test_matcher_records_no_match_without_inventing_candidate(tmp_path):
    client, document_id, _scene_id, _dialogue_id = _database_with_story_nodes(tmp_path)

    summary = client.match_game_strings(document_id, [GameString(
        "0", "zel_00", 7, "zel_00_Str_7", "Completely unrelated sentence"
    )])

    mapping = client.get_dialogue_mappings(document_id)[0]
    assert summary.unmatched == 1
    assert mapping.dialogue_node_id is None
    assert mapping.match_method == "unmatched"
    assert mapping.conflict_reason == "No sufficiently strong candidate."


def test_text_normalization_retains_placeholders_and_tags():
    tagged = canonicalize_dialogue_text("Hello   {PLAYER} [color=red]")

    assert tagged == "hello {player} [color=red]"
    assert tagged != canonicalize_dialogue_text("Hello")


def test_matcher_cancellation_rolls_back_whole_batch(tmp_path):
    client, document_id, _scene_id, _dialogue_id = _database_with_story_nodes(tmp_path)
    checks = 0

    def cancel_after_first_item():
        nonlocal checks
        checks += 1
        return checks > 1

    with pytest.raises(DialogueMappingCancelled):
        client.match_game_strings(
            document_id,
            [
                GameString("0", "zel_00", 0, "zel_00_Str_0", "Hello"),
                GameString("0", "zel_00", 1, "zel_00_Str_1", "Hello"),
            ],
            cancel_check=cancel_after_first_item,
        )

    assert client.get_dialogue_mappings(document_id) == ()
