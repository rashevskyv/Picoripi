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
