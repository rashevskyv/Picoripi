from core.script_markup import (
    HierarchyMark,
    HierarchyType,
    infer_hierarchy_marks_from_examples,
)


def test_local_autofill_continues_speaker_text_blocks_from_examples():
    raw = "\n".join([
        "Act One",
        "RUSL",
        "Hello.",
        "FADO",
        "Hey!",
    ])
    marks = [
        HierarchyMark(0, 4, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.SPEAKER, text="RUSL", order=2),
        HierarchyMark(2, 2, 2, HierarchyType.TEXT, order=3),
    ]

    result = infer_hierarchy_marks_from_examples(raw, marks)

    assert [(mark.start_line, mark.end_line, mark.depth, mark.type_id, mark.text) for mark in result.marks] == [
        (3, 3, 1, HierarchyType.SPEAKER, "FADO"),
        (4, 4, 2, HierarchyType.TEXT, ""),
    ]
    assert result.speakers == 1
    assert result.texts == 1


def test_local_autofill_recognizes_unicode_speaker_with_number_suffix():
    raw = "\n".join([
        "MIDNA",
        "Known line.",
        "CAFÉ MAN #1",
        "Welcome to my shop.",
        "MAÎTRE D’ #2",
        "The second reply.",
        "CAFE\u0301 MAN #3",
        "The decomposed accent reply.",
    ])
    marks = [
        HierarchyMark(0, 0, 1, HierarchyType.SPEAKER, text="MIDNA", order=1),
        HierarchyMark(1, 1, 2, HierarchyType.TEXT, order=2),
    ]

    result = infer_hierarchy_marks_from_examples(raw, marks)

    assert [
        (mark.start_line, mark.text)
        for mark in result.marks
        if mark.type_id == HierarchyType.SPEAKER
    ] == [
        (2, "CAFÉ MAN #1"),
        (4, "MAÎTRE D’ #2"),
        (6, "CAFE\u0301 MAN #3"),
    ]
    assert [
        (mark.start_line, mark.end_line)
        for mark in result.marks
        if mark.type_id == HierarchyType.TEXT
    ] == [(3, 3), (5, 5), (7, 7)]


def test_local_autofill_reuses_seen_structure_keyword_depths():
    raw = "\n".join([
        "Act One",
        "Scene A",
        "Act Two",
        "Scene B",
    ])
    marks = [
        HierarchyMark(0, 1, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.STRUCTURE, text="Scene A", order=2),
    ]

    result = infer_hierarchy_marks_from_examples(raw, marks)

    assert [(mark.start_line, mark.depth, mark.type_id, mark.text) for mark in result.marks] == [
        (2, 0, HierarchyType.STRUCTURE, "Act Two"),
        (3, 1, HierarchyType.STRUCTURE, "Scene B"),
    ]
    assert result.structures == 2


def test_local_autofill_learns_scene_children_and_nests_exact_breakers():
    raw = "\n".join([
        "Act One", "Chapter I", "RUSL", "Hello.", "~~~~~~~~~~~~~~~~",
        "FADO", "Goodbye.", "Chapter II", "TALO", "Wake up!",
        "~~~~~~~~~~~~~~~~", "MALO", "Let's go.",
    ])
    marks = [
        HierarchyMark(0, 12, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 6, 1, HierarchyType.STRUCTURE, text="Chapter I", order=2),
        HierarchyMark(2, 4, 2, HierarchyType.STRUCTURE, text="Scene 1", order=3),
        HierarchyMark(2, 2, 3, HierarchyType.SPEAKER, text="RUSL", order=4),
        HierarchyMark(3, 3, 4, HierarchyType.TEXT, order=5),
        HierarchyMark(4, 4, 3, HierarchyType.BREAKER, order=6),
        HierarchyMark(5, 6, 2, HierarchyType.STRUCTURE, text="Scene 2", order=7),
        HierarchyMark(7, 12, 1, HierarchyType.STRUCTURE, text="Chapter II", order=8),
    ]

    result = infer_hierarchy_marks_from_examples(raw, marks)
    structures = [mark for mark in result.marks if mark.type_id == HierarchyType.STRUCTURE]
    breakers = [mark for mark in result.marks if mark.type_id == HierarchyType.BREAKER]

    assert [(mark.start_line, mark.end_line, mark.depth, mark.text) for mark in structures] == [
        (8, 10, 2, "Scene 1"),
        (11, 12, 2, "Scene 2"),
    ]
    assert [(mark.start_line, mark.end_line, mark.depth) for mark in breakers] == [
        (10, 10, 3),
    ]

    repeated = infer_hierarchy_marks_from_examples(raw, [*marks, *result.marks])
    assert not any(
        mark.type_id == HierarchyType.STRUCTURE and mark.depth == 2
        for mark in repeated.marks
    )


def test_local_autofill_requires_the_exact_learned_breaker_text():
    raw = "\n".join([
        "Act One", "Chapter I", "RUSL", "Hello.", "~~~~~~~~",
        "FADO", "Goodbye.", "Chapter II", "TALO", "Wake up!",
        "--------", "MALO", "Let's go.",
    ])
    marks = [
        HierarchyMark(0, 12, 0, HierarchyType.STRUCTURE, text="Act One"),
        HierarchyMark(1, 6, 1, HierarchyType.STRUCTURE, text="Chapter I"),
        HierarchyMark(2, 4, 2, HierarchyType.STRUCTURE, text="Scene 1"),
        HierarchyMark(2, 2, 3, HierarchyType.SPEAKER, text="RUSL"),
        HierarchyMark(3, 3, 4, HierarchyType.TEXT),
        HierarchyMark(4, 4, 3, HierarchyType.BREAKER),
        HierarchyMark(5, 6, 2, HierarchyType.STRUCTURE, text="Scene 2"),
        HierarchyMark(7, 12, 1, HierarchyType.STRUCTURE, text="Chapter II"),
    ]

    result = infer_hierarchy_marks_from_examples(raw, marks)

    assert not any(mark.type_id == HierarchyType.BREAKER for mark in result.marks)
    assert not any(
        mark.type_id == HierarchyType.STRUCTURE and mark.depth == 2
        for mark in result.marks
    )


def test_local_autofill_keeps_text_until_next_speaker_across_actions_and_blanks():
    raw = "\n".join([
        "MIDNA",
        "First line.",
        "",
        "[Midna looks away]",
        "I... did not know.",
        "Another line.",
        "ZELDA",
        "Final reply.",
    ])
    marks = [
        HierarchyMark(0, 0, 1, HierarchyType.SPEAKER, text="MIDNA", order=1),
        HierarchyMark(1, 1, 2, HierarchyType.TEXT, order=2),
        HierarchyMark(3, 3, 1, HierarchyType.ACTION, order=3),
    ]

    result = infer_hierarchy_marks_from_examples(raw, marks)

    assert not any(mark.type_id == HierarchyType.SPEAKER and mark.start_line == 4 for mark in result.marks)
    assert [
        (mark.start_line, mark.end_line, mark.depth)
        for mark in result.marks
        if mark.type_id == HierarchyType.TEXT
    ] == [(4, 5, 2), (7, 7, 2)]
    assert [
        (mark.start_line, mark.text)
        for mark in result.marks
        if mark.type_id == HierarchyType.SPEAKER
    ] == [(6, "ZELDA")]


def test_local_autofill_splits_inline_and_choice_contexts_under_speaker():
    raw = "\n".join([
        "MIDNA",
        "Ordinary line.",
        "MIDNA (Sample condition)",
        "Sample conditional line.",
        "(Sample choice)",
        "Sample choice line.",
        "MIDNA (If other people are around)",
        "Do not transform here.",
        "(Yes)",
        "I understand.",
        "(No)",
        "Then go from me.",
        "ZELDA",
        "Next dialogue.",
    ])
    marks = [
        HierarchyMark(0, 0, 3, HierarchyType.SPEAKER, text="MIDNA", order=1),
        HierarchyMark(1, 1, 4, HierarchyType.TEXT, order=2),
        HierarchyMark(2, 2, 3, HierarchyType.SPEAKER, start_col=0, end_col=5, order=3),
        HierarchyMark(2, 2, 4, HierarchyType.CONTEXT, start_col=7, end_col=23, order=4),
        HierarchyMark(3, 3, 5, HierarchyType.TEXT, order=5),
        HierarchyMark(4, 4, 4, HierarchyType.CONTEXT, start_col=1, end_col=14, order=6),
        HierarchyMark(5, 5, 5, HierarchyType.TEXT, order=7),
    ]

    result = infer_hierarchy_marks_from_examples(raw, marks)
    speakers = [mark for mark in result.marks if mark.type_id == HierarchyType.SPEAKER]
    contexts = [mark for mark in result.marks if mark.type_id == HierarchyType.CONTEXT]
    texts = [mark for mark in result.marks if mark.type_id == HierarchyType.TEXT]

    assert [(mark.start_line, mark.text, mark.start_col, mark.end_col) for mark in speakers] == [
        (6, "MIDNA", 0, 5),
        (12, "ZELDA", None, None),
    ]
    assert [(mark.start_line, mark.text, mark.depth) for mark in contexts] == [
        (6, "If other people are around", 4),
        (8, "Yes", 4),
        (10, "No", 4),
    ]
    assert [(mark.start_line, mark.end_line, mark.depth) for mark in texts] == [
        (7, 7, 5),
        (9, 9, 5),
        (11, 11, 5),
        (13, 13, 4),
    ]
    assert result.contexts == 3


def test_local_autofill_learns_context_with_mismatched_closing_brace():
    raw = "\n".join([
        "MIDNA",
        "Known line.",
        "(Example condition}",
        "Example reply.",
        "(Another condition}",
        "Another reply.",
    ])
    marks = [
        HierarchyMark(0, 0, 3, HierarchyType.SPEAKER, text="MIDNA", order=1),
        HierarchyMark(1, 1, 4, HierarchyType.TEXT, order=2),
        HierarchyMark(2, 2, 4, HierarchyType.CONTEXT, start_col=1, end_col=18, order=3),
        HierarchyMark(3, 3, 5, HierarchyType.TEXT, order=4),
    ]

    result = infer_hierarchy_marks_from_examples(raw, marks)

    context = next(
        mark
        for mark in result.marks
        if mark.type_id == HierarchyType.CONTEXT and mark.start_line == 4
    )
    assert (context.text, context.start_col, context.end_col, context.depth) == (
        "Another condition",
        1,
        18,
        4,
    )


def test_local_autofill_does_not_infer_context_without_approved_example():
    raw = "MIDNA\nKnown line.\nMIDNA (Condition)\nConditional line."
    marks = [
        HierarchyMark(0, 0, 3, HierarchyType.SPEAKER, order=1),
        HierarchyMark(1, 1, 4, HierarchyType.TEXT, order=2),
    ]

    result = infer_hierarchy_marks_from_examples(raw, marks)

    assert not any(mark.type_id == HierarchyType.CONTEXT for mark in result.marks)
    assert not any(mark.type_id == HierarchyType.SPEAKER and mark.start_line == 2 for mark in result.marks)


def test_local_autofill_marks_are_unapproved_and_cannot_become_examples():
    raw = "MIDNA\nKnown line.\nZELDA\nNew line."
    examples = [
        HierarchyMark(0, 0, 3, HierarchyType.SPEAKER, order=1),
        HierarchyMark(1, 1, 4, HierarchyType.TEXT, order=2),
    ]

    result = infer_hierarchy_marks_from_examples(raw, examples)

    assert result.marks
    assert all(mark.origin == "local_autofill" and not mark.approved for mark in result.marks)
    only_automatic = infer_hierarchy_marks_from_examples(raw, result.marks)
    assert only_automatic.marks == []


def test_local_autofill_learns_wrapper_for_custom_type_from_manual_example():
    raw = "MIDNA\nKnown line.\n<Camera: close-up>\nReply.\n<Camera: wide shot>\nNext reply."
    custom_type = "custom:camera"
    marks = [
        HierarchyMark(0, 0, 3, HierarchyType.SPEAKER, order=1),
        HierarchyMark(1, 5, 4, HierarchyType.TEXT, order=2),
        HierarchyMark(
            2,
            2,
            4,
            custom_type,
            text="Camera: close-up",
            start_col=1,
            end_col=17,
            order=3,
        ),
    ]

    result = infer_hierarchy_marks_from_examples(raw, marks)

    custom = next(
        mark
        for mark in result.marks
        if mark.type_id == custom_type and mark.start_line == 4
    )
    assert (custom.text, custom.start_col, custom.end_col, custom.depth) == (
        "Camera: wide shot",
        1,
        18,
        4,
    )
    assert result.other_types == 1


def test_local_autofill_learns_wrapper_for_builtin_note_type():
    raw = "(Known note)\nDialogue.\n(New note)"
    marks = [
        HierarchyMark(
            0,
            0,
            4,
            HierarchyType.NOTE,
            text="Known note",
            start_col=1,
            end_col=11,
        ),
    ]

    result = infer_hierarchy_marks_from_examples(raw, marks)

    note = next(
        mark
        for mark in result.marks
        if mark.type_id == HierarchyType.NOTE and mark.start_line == 2
    )
    assert (note.text, note.start_col, note.end_col, note.depth) == (
        "New note",
        1,
        9,
        4,
    )


def test_local_autofill_supplements_builtin_action_with_learned_wrapper():
    raw = "{Door opens}\nDialogue.\n{Door closes}"
    marks = [
        HierarchyMark(
            0,
            0,
            4,
            HierarchyType.ACTION,
            text="Door opens",
            start_col=1,
            end_col=11,
        ),
    ]

    result = infer_hierarchy_marks_from_examples(raw, marks)

    action = next(
        mark
        for mark in result.marks
        if mark.type_id == HierarchyType.ACTION and mark.start_line == 2
    )
    assert (action.text, action.start_col, action.end_col, action.depth) == (
        "Door closes",
        1,
        12,
        4,
    )


def test_local_autofill_never_learns_custom_pattern_from_automatic_mark():
    raw = "<Camera: close-up>\n<Camera: wide shot>"
    marks = [
        HierarchyMark(
            0,
            0,
            2,
            "custom:camera",
            start_col=1,
            end_col=17,
            origin="local_autofill",
            approved=True,
        ),
    ]

    result = infer_hierarchy_marks_from_examples(raw, marks)

    assert result.marks == []


def test_local_autofill_skips_wrapper_learned_as_two_different_types():
    raw = "<Camera: close-up>\n<Weather: rain>\n<Camera: wide shot>"
    marks = [
        HierarchyMark(0, 0, 2, "custom:camera", start_col=1, end_col=17, order=1),
        HierarchyMark(1, 1, 2, "custom:weather", start_col=1, end_col=14, order=2),
    ]

    result = infer_hierarchy_marks_from_examples(raw, marks)

    assert result.marks == []


def test_local_autofill_never_searches_or_marks_inside_ignored_ranges():
    raw = "\n".join([
        "MIDNA",
        "Known line.",
        "ZELDA",
        "This whole block is ignored.",
        "TALO",
        "Outside the ignored block.",
    ])
    marks = [
        HierarchyMark(0, 0, 1, HierarchyType.SPEAKER, text="MIDNA", order=1),
        HierarchyMark(1, 1, 2, HierarchyType.TEXT, order=2),
        HierarchyMark(2, 3, 0, HierarchyType.IGNORE, order=3),
    ]

    result = infer_hierarchy_marks_from_examples(raw, marks)

    assert [(mark.start_line, mark.end_line, mark.type_id) for mark in result.marks] == [
        (4, 4, HierarchyType.SPEAKER),
        (5, 5, HierarchyType.TEXT),
    ]
    assert not any(
        mark.start_line <= 3 and mark.end_line >= 2 for mark in result.marks
    )


def test_ignored_range_terminates_autofilled_speaker_text_block():
    raw = "\n".join([
        "MIDNA",
        "Known line.",
        "Do not inspect this.",
        "Narrative after ignored block.",
    ])
    marks = [
        HierarchyMark(0, 0, 1, HierarchyType.SPEAKER, text="MIDNA", order=1),
        HierarchyMark(1, 1, 2, HierarchyType.TEXT, order=2),
        HierarchyMark(2, 2, 0, HierarchyType.IGNORE, order=3),
    ]

    result = infer_hierarchy_marks_from_examples(raw, marks)

    assert result.marks == []


def test_synthetic_scene_start_does_not_hide_first_speaker_line():
    raw = "\n".join([
        "TALO",
        "Time to practice!",
        "~~~~~~~~~~~~~~~~",
        "MALO",
        "Known dialogue example.",
    ])
    marks = [
        HierarchyMark(
            0, 2, 2, HierarchyType.STRUCTURE, text="Scene 4", order=1
        ),
        HierarchyMark(3, 3, 3, HierarchyType.SPEAKER, text="MALO", order=2),
        HierarchyMark(4, 4, 4, HierarchyType.TEXT, order=3),
    ]

    result = infer_hierarchy_marks_from_examples(raw, marks)

    assert [
        (mark.start_line, mark.end_line, mark.depth, mark.type_id, mark.text)
        for mark in result.marks
    ] == [
        (0, 0, 3, HierarchyType.SPEAKER, "TALO"),
        (1, 1, 4, HierarchyType.TEXT, ""),
    ]


def test_local_autofill_learns_item_description_pairs_only_inside_parent_structure():
    raw = "\n".join([
        "Collection Screen",
        "",
        "Wallet",
        "A wallet from your childhood.",
        "",
        "Big Wallet",
        "A wallet with greater capacity.",
        "",
        "Outside section",
        "This paragraph must stay unmarked.",
    ])
    marks = [
        HierarchyMark(0, 6, 1, HierarchyType.STRUCTURE, text="Collection Screen", order=1),
        HierarchyMark(2, 2, 4, HierarchyType.ITEM, order=2),
        HierarchyMark(3, 3, 5, HierarchyType.ITEM_DESCRIPTION, order=3),
    ]

    result = infer_hierarchy_marks_from_examples(raw, marks)

    assert [
        (mark.start_line, mark.end_line, mark.depth, mark.type_id)
        for mark in result.marks
    ] == [
        (5, 5, 4, HierarchyType.ITEM),
        (6, 6, 5, HierarchyType.ITEM_DESCRIPTION),
    ]
    assert (result.items, result.item_descriptions, result.speakers, result.texts) == (1, 1, 0, 0)
