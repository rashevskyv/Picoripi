from core.script_markup import (
    BREAKER_LINE,
    HierarchyMark,
    HierarchyType,
    build_hierarchy_tree,
    default_type_definitions,
    line_styles_for_marks,
    render_hierarchy_markdown,
)


def test_hierarchy_depth_builds_parent_child_and_siblings():
    root = build_hierarchy_tree([
        HierarchyMark(0, 0, 0, HierarchyType.STRUCTURE, text="Act I"),
        HierarchyMark(1, 1, 1, HierarchyType.STRUCTURE, text="Chapter One"),
        HierarchyMark(2, 2, 1, HierarchyType.ACTION, text="Door opens"),
        HierarchyMark(3, 3, 2, HierarchyType.SPEAKER, text="MIDNA"),
    ])

    act = root.children[0]
    assert act.mark.text == "Act I"
    assert [child.mark.type_id for child in act.children] == [
        HierarchyType.STRUCTURE,
        HierarchyType.ACTION,
    ]
    action = act.children[1]
    assert action.children[0].mark.text == "MIDNA"


def test_hierarchy_parent_can_share_start_line_with_child():
    root = build_hierarchy_tree([
        HierarchyMark(0, 4, 0, HierarchyType.STRUCTURE, text="Act 1"),
        HierarchyMark(0, 2, 1, HierarchyType.STRUCTURE, text="Chapter 1"),
    ])

    act = root.children[0]
    assert act.mark.text == "Act 1"
    assert act.children[0].mark.text == "Chapter 1"


def test_render_hierarchy_markdown_uses_canonical_syntax():
    raw = "\n".join([
        "Act I",
        "Chapter One",
        "MIDNA",
        "Well, look what we have here.",
        "Midna drops from a branch",
        "sarcastic",
        "Scene change",
        "Nobody speaks this line.",
    ])
    marks = [
        HierarchyMark(0, 0, 0, HierarchyType.STRUCTURE),
        HierarchyMark(1, 1, 1, HierarchyType.STRUCTURE),
        HierarchyMark(2, 2, 2, HierarchyType.SPEAKER),
        HierarchyMark(3, 3, 3, HierarchyType.TEXT),
        HierarchyMark(4, 4, 2, HierarchyType.ACTION),
        HierarchyMark(5, 5, 2, HierarchyType.NOTE),
        HierarchyMark(6, 6, 2, HierarchyType.BREAKER),
        HierarchyMark(7, 7, 2, HierarchyType.NARRATOR),
    ]

    rendered = render_hierarchy_markdown(marks, raw)

    assert "# Act I" in rendered
    assert "## Chapter One" in rendered
    assert "**MIDNA**: Well, look what we have here." in rendered
    assert "[*Midna drops from a branch*]" in rendered
    assert "[*Midna drops from a branch*] (sarcastic)" in rendered
    assert BREAKER_LINE in rendered
    assert "**Nobody speaks this line.**" in rendered


def test_speaker_and_text_are_separate_marks_but_one_line():
    rendered = render_hierarchy_markdown([
        HierarchyMark(0, 0, 0, HierarchyType.SPEAKER, text="RUSL"),
        HierarchyMark(1, 1, 1, HierarchyType.TEXT, text="Take this shield."),
    ])

    assert rendered == "**RUSL**: Take this shield.\n"


def test_speaker_children_render_text_action_text_in_source_order():
    raw = "\n".join([
        "ILIA",
        "Oh, hi, Link.",
        "I washed Epona for you!",
        "Link plucks a reed from the ground",
        "It's such a nice melody...",
        "Epona looks happy.",
        "Link returns to Ordon Village",
    ])
    rendered = render_hierarchy_markdown([
        HierarchyMark(0, 6, 4, HierarchyType.SPEAKER, text="ILIA"),
        HierarchyMark(1, 2, 5, HierarchyType.TEXT),
        HierarchyMark(3, 3, 5, HierarchyType.ACTION),
        HierarchyMark(4, 5, 5, HierarchyType.TEXT),
        HierarchyMark(6, 6, 5, HierarchyType.ACTION),
    ], raw)

    assert rendered == (
        "**ILIA**: Oh, hi, Link. I washed Epona for you!\n"
        "\n"
        "[*Link plucks a reed from the ground*]\n"
        "\n"
        "**ILIA**: It's such a nice melody... Epona looks happy.\n"
        "\n"
        "[*Link returns to Ordon Village*]\n"
    )


def test_container_marks_use_first_source_line_instead_of_flattened_range():
    raw = "\n".join([
        "Act One",
        "RUSL",
        "Tell me something.",
        "More dialogue.",
    ])

    rendered = render_hierarchy_markdown([
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE),
        HierarchyMark(1, 3, 1, HierarchyType.SPEAKER),
        HierarchyMark(2, 3, 2, HierarchyType.TEXT),
    ], raw)

    first_line = rendered.splitlines()[0]
    assert first_line == "# Act One"
    assert "RUSL" not in first_line
    assert "Tell me something." not in first_line
    assert "**RUSL**: Tell me something. More dialogue." in rendered


def test_structure_raw_fallback_skips_full_rendered_subtree():
    raw = "\n".join([
        "Scene 1",
        "RUSL",
        "Tell me something.",
        "More dialogue.",
        "[Rusl leaves]",
        "FADO",
        "Hey, Link!",
    ])

    rendered = render_hierarchy_markdown([
        HierarchyMark(0, 6, 2, HierarchyType.STRUCTURE, text="Scene 1"),
        HierarchyMark(1, 1, 3, HierarchyType.SPEAKER, text="RUSL"),
        HierarchyMark(2, 3, 4, HierarchyType.TEXT),
        HierarchyMark(4, 4, 3, HierarchyType.ACTION),
        HierarchyMark(5, 5, 3, HierarchyType.SPEAKER, text="FADO"),
        HierarchyMark(6, 6, 4, HierarchyType.TEXT),
    ], raw)

    assert rendered == (
        "### Scene 1\n"
        "\n"
        "**RUSL**: Tell me something. More dialogue.\n"
        "\n"
        "[*Rusl leaves*]\n"
        "\n"
        "**FADO**: Hey, Link!\n"
    )


def test_only_structure_explicit_text_overrides_source_text():
    raw = "\n".join([
        "ASCII title line",
        "FADO",
        "Hey, Link!",
        "[The diminishing light cascades into Link's house]",
    ])

    rendered = render_hierarchy_markdown([
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One"),
        HierarchyMark(1, 1, 1, HierarchyType.SPEAKER, text="Scene 4"),
        HierarchyMark(2, 2, 2, HierarchyType.TEXT, text="Scene 4"),
        HierarchyMark(3, 3, 1, HierarchyType.ACTION, text="Scene 4"),
    ], raw)

    assert "# Act One" in rendered
    assert "ASCII title line" not in rendered.splitlines()[0]
    assert "**FADO**: Hey, Link!" in rendered
    assert "[*The diminishing light cascades into Link's house*]" in rendered
    assert "Scene 4" not in rendered


def test_structure_renders_unmarked_inner_lines_as_raw_fallback():
    raw = "\n".join([
        "Scene 2",
        "TALO",
        "Hey, Link!",
    ])
    rendered = render_hierarchy_markdown([
        HierarchyMark(0, 2, 2, HierarchyType.STRUCTURE, text="Scene 2"),
    ], raw)

    assert rendered == "### Scene 2\n\n> [RAW] TALO\n> Hey, Link!\n"


def test_line_styles_use_type_default_color_then_mark_override():
    defs = default_type_definitions()
    styles = line_styles_for_marks([
        HierarchyMark(0, 1, 0, HierarchyType.ACTION),
        HierarchyMark(2, 2, 0, HierarchyType.SPEAKER, color="#123456"),
    ], defs)

    assert styles[0] == (HierarchyType.ACTION, defs[HierarchyType.ACTION].color)
    assert styles[1] == (HierarchyType.ACTION, defs[HierarchyType.ACTION].color)
    assert styles[2] == (HierarchyType.SPEAKER, "#123456")


def test_ignored_and_unmarked_types_do_not_render_to_markdown():
    rendered = render_hierarchy_markdown([
        HierarchyMark(0, 0, 0, HierarchyType.IGNORE, text="Legal notice"),
        HierarchyMark(1, 1, 0, HierarchyType.UNMARKED, text="Needs work"),
        HierarchyMark(2, 2, 0, HierarchyType.STRUCTURE, text="Act I"),
    ])

    assert "Legal notice" not in rendered
    assert "Needs work" not in rendered
    assert "# Act I" in rendered

