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
