import sqlite3

from core.mempalace.schema import migrate_mempalace_schema
from core.mempalace.dialogue_alignment import (
    GameMessage,
    MarkedDialogue,
    infer_tag_equivalents,
    load_dialogues,
    lock_relation_choice,
    save_relations,
    simulate,
)


def test_loader_uses_only_approved_dialogue_under_approved_speaker(tmp_path):
    database = tmp_path / "mempalace.db"
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys = ON")
    migrate_mempalace_schema(connection)
    document_id = connection.execute(
        "INSERT INTO story_documents "
        "(source_path, source_hash, markup_format, markup_version) "
        "VALUES ('project.json', 'hash', 'hierarchy', 1)"
    ).lastrowid
    act_id = connection.execute(
        "INSERT INTO story_nodes "
        "(stable_id, document_id, node_type, order_index, text, approved) "
        "VALUES ('act', ?, 'act', 0, 'Act Two', 1)",
        (document_id,),
    ).lastrowid
    speaker_id = connection.execute(
        "INSERT INTO story_nodes "
        "(stable_id, document_id, parent_id, node_type, order_index, text, approved) "
        "VALUES ('speaker', ?, ?, 'speaker', 0, 'MIDNA', 1)",
        (document_id, act_id),
    ).lastrowid
    connection.execute(
        "INSERT INTO story_nodes "
        "(stable_id, document_id, parent_id, node_type, order_index, text, approved) "
        "VALUES ('real', ?, ?, 'dialogue', 0, 'Real spoken line.', 1)",
        (document_id, speaker_id),
    )
    context_id = connection.execute(
        "INSERT INTO story_nodes "
        "(stable_id, document_id, parent_id, node_type, order_index, text, approved) "
        "VALUES ('context', ?, ?, 'context', 1, '(Yes)', 1)",
        (document_id, speaker_id),
    ).lastrowid
    connection.execute(
        "INSERT INTO story_nodes "
        "(stable_id, document_id, parent_id, node_type, order_index, text, approved) "
        "VALUES ('conditioned', ?, ?, 'dialogue', 0, 'Conditioned reply.', 1)",
        (document_id, context_id),
    )
    connection.execute(
        "INSERT INTO story_nodes "
        "(stable_id, document_id, parent_id, node_type, order_index, text, approved) "
        "VALUES ('decorative', ?, ?, 'dialogue', 1, 'Act Two decoration', 1)",
        (document_id, act_id),
    )
    connection.commit()
    connection.close()

    dialogues = load_dialogues(database, document_id)

    assert [dialogue.text for dialogue in dialogues] == [
        "Real spoken line.",
        "Conditioned reply.",
    ]
    assert {dialogue.speaker for dialogue in dialogues} == {"MIDNA"}


def test_simulator_aligns_multiple_game_messages_to_one_marked_dialogue():
    dialogues = [MarkedDialogue(
        1,
        0,
        "Tell me, Master Link, have you heard the ancient story? "
        "Young Master Link, the princess is waiting in the tower.",
        "AURU",
        100,
    )]
    messages = [
        GameMessage(
            0, "0", "zel_00", 10, "zel_00_Str_10",
            "Tell me, Master {escape:0:0000}... Have you heard the ancient story?",
        ),
        GameMessage(
            1, "0", "zel_00", 11, "zel_00_Str_11",
            "Young Master {escape:0:0000}, the princess is waiting in the tower.",
        ),
    ]

    report = simulate(dialogues, messages)

    assert report["inferred_tag_equivalents"] == {"{escape:0:0000}": "link"}
    assert report["spoken_only"]["supported_relation_coverage"] == 100.0
    assert len(report["relations"]) == 2
    assert {relation["dialogue_node_id"] for relation in report["relations"]} == {1}


def test_simulator_reports_stage_directions_separately():
    dialogues = [
        MarkedDialogue(1, 0, "Welcome back to Hyrule.", "MIDNA", 10),
        MarkedDialogue(2, 1, "[Link opens the ancient gate]", "MIDNA", 11),
    ]
    messages = [
        GameMessage(0, "0", "zel_00", 0, "zel_00_Str_0", "Welcome back to Hyrule!"),
    ]

    report = simulate(dialogues, messages)

    assert report["stage_direction_nodes"] == 1
    assert report["spoken_only"]["supported_relation_coverage"] == 100.0
    assert report["all_marked"]["supported_relation_coverage"] < 100.0


def test_tag_inference_requires_repeated_consistent_evidence():
    dialogues = [MarkedDialogue(
        1,
        0,
        "Master Link, please listen. Tell me, Master Link, are you ready?",
        "AURU",
        20,
    )]
    messages = [
        GameMessage(0, "0", "zel_00", 0, "a", "Master {tag:name}, please listen."),
        GameMessage(1, "0", "zel_00", 1, "b", "Tell me, Master {tag:name}, are you ready?"),
    ]

    assert infer_tag_equivalents(dialogues, messages) == {"{tag:name}": "link"}


def test_inferred_control_tag_does_not_hide_exact_walkthrough_dialogue():
    dialogues = [
        MarkedDialogue(1, 0, "Move the analog stick now.", "SYSTEM", 1),
        MarkedDialogue(2, 1, "Push the analog stick gently.", "SYSTEM", 2),
        MarkedDialogue(
            3, 2, "Frog Lure. The must-have lure for bass.", "HENA", 3
        ),
    ]
    messages = [
        GameMessage(0, "0", "zel_07", 0, "a", "Move the {control} now."),
        GameMessage(1, "0", "zel_07", 1, "b", "Push the {control} gently."),
        GameMessage(
            2, "0", "zel_07", 2, "lure",
            "Frog Lure. The must-have lure for bass. {control}",
        ),
    ]

    report = simulate(dialogues, messages)

    assert report["inferred_tag_equivalents"] == {"{control}": "analog stick"}
    assert any(
        relation["game_string_id"] == "lure"
        and relation["dialogue_node_id"] == 3
        for relation in report["relations"]
    )


def test_context_cannot_promote_a_different_financial_phrase_to_a_match():
    dialogues = [
        MarkedDialogue(1, 0, "Welcome to Kakariko Village.", "GORON", 10),
        MarkedDialogue(
            2,
            1,
            "We are 200 Rupees short of funding for bridge repairs. "
            "That bridge is vital to a steady flow of goods to Castle Town.",
            "GORON",
            11,
        ),
        MarkedDialogue(3, 2, "Thank you for your cooperation, Brudda!", "GORON", 12),
    ]
    messages = [
        GameMessage(0, "0", "zel_00", 0, "a", "Welcome to Kakariko Village."),
        GameMessage(
            1,
            "0",
            "zel_00",
            1,
            "b",
            "We are 200 Rupees short of our financial objective for the "
            "opening of a shop in Castle Town.",
        ),
        GameMessage(
            2, "0", "zel_00", 2, "c", "Thank you for your cooperation, Brudda!"
        ),
    ]

    report = simulate(dialogues, messages)

    assert not any(relation["game_string_id"] == "b" for relation in report["relations"])


def test_literal_contradictions_are_not_accepted_as_fuzzy_matches():
    dialogues = [MarkedDialogue(
        1,
        0,
        "There are still four hidden skills for you to learn. "
        "The doctor on West Street gave up.",
        "HERO'S SHADE",
        20,
    )]
    messages = [
        GameMessage(
            0, "0", "zel_00", 0, "count",
            "There are still six hidden skills for you to learn.",
        ),
        GameMessage(
            1, "0", "zel_00", 1, "direction",
            "The doctor on East Street gave up.",
        ),
    ]

    report = simulate(dialogues, messages)

    assert report["relations"] == []


def test_direction_adjectives_and_named_phrases_cannot_false_match():
    dialogues = [
        MarkedDialogue(
            1, 0,
            "Do you know what's in the tent on the eastern thoroughfare?",
            "WOMAN", 20,
        ),
        MarkedDialogue(
            2, 1,
            "You mastered the last skill I taught you, the helm splitter.",
            "HERO'S SHADE", 21,
        ),
    ]
    messages = [
        GameMessage(
            0, "0", "zel_00", 0, "direction",
            "Do you know what's in the tent on the western thoroughfare?",
        ),
        GameMessage(
            1, "0", "zel_00", 1, "skill",
            "You mastered the last skill I taught you, the ending blow.",
        ),
    ]

    report = simulate(dialogues, messages)

    assert report["relations"] == []


def test_alignment_relations_allow_one_game_resource_in_multiple_story_contexts():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    migrate_mempalace_schema(connection)
    document_id = connection.execute(
        "INSERT INTO story_documents "
        "(source_path, source_hash, markup_format, markup_version) "
        "VALUES ('project.json', 'hash', 'hierarchy', 1)"
    ).lastrowid
    node_ids = [
        connection.execute(
            "INSERT INTO story_nodes "
            "(stable_id, document_id, node_type, order_index, text) "
            "VALUES (?, ?, 'dialogue', ?, 'The gate is closed.')",
            (f"dialogue:{index}", document_id, index),
        ).lastrowid
        for index in range(2)
    ]
    messages = [GameMessage(
        0, "0", "zel_00", 7, "zel_00_Str_7", "The gate is closed."
    )]
    report = {
        "relations": [
            {
                "game_block_id": "0",
                "string_index": 7,
                "dialogue_node_id": node_id,
                "method": "exact_or_contained",
                "score": 1.0,
                "game_coverage": 1.0,
                "primary": index == 0,
            }
            for index, node_id in enumerate(node_ids)
        ]
    }

    assert save_relations(connection, document_id, report, messages) == 2
    rows = connection.execute(
        "SELECT game_string_id, dialogue_node_id FROM story_dialogue_relations "
        "ORDER BY dialogue_node_id"
    ).fetchall()
    assert rows == [("zel_00_Str_7", node_ids[0]), ("zel_00_Str_7", node_ids[1])]
    compatibility = connection.execute(
        "SELECT dialogue_node_id, review_status FROM story_dialogue_mappings"
    ).fetchall()
    assert compatibility == [(node_ids[0], "matched")]

    for relation in report["relations"]:
        relation["primary"] = False
    save_relations(connection, document_id, report, messages)
    assert connection.execute(
        "SELECT COUNT(*) FROM story_dialogue_mappings"
    ).fetchone()[0] == 0

    assert lock_relation_choice(
        connection, document_id, "0", 7, node_ids[1]
    ) == 2
    locked = connection.execute(
        "SELECT dialogue_node_id, primary_link, relation_status, locked "
        "FROM story_dialogue_relations ORDER BY dialogue_node_id"
    ).fetchall()
    assert locked == [
        (node_ids[0], 0, "rejected", 1),
        (node_ids[1], 1, "approved", 1),
    ]
