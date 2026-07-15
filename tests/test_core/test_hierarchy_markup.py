from core.script_markup import (
    BREAKER_LINE,
    HierarchyMark,
    HierarchyType,
    HierarchyAIPromptTooLarge,
    build_hierarchy_tree,
    build_hierarchy_auto_markup_messages,
    default_type_definitions,
    line_styles_for_marks,
    parse_hierarchy_auto_markup_response,
    render_hierarchy_markdown,
    resolve_structure_name_iterator,
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


def test_structure_name_iterator_counts_siblings_and_resets_per_parent():
    marks = [
        HierarchyMark(0, 5, 0, HierarchyType.STRUCTURE, text="Chapter 1"),
        HierarchyMark(1, 2, 1, HierarchyType.STRUCTURE, text="Scene 1"),
        HierarchyMark(3, 4, 1, HierarchyType.STRUCTURE, text="Scene 2"),
        HierarchyMark(6, 9, 0, HierarchyType.STRUCTURE, text="Chapter 2"),
    ]

    assert resolve_structure_name_iterator(
        "Scene $", marks, start_line=5, end_line=5, depth=1
    ) == "Scene 3"
    assert resolve_structure_name_iterator(
        "Scene $", marks, start_line=7, end_line=8, depth=1
    ) == "Scene 1"
    assert resolve_structure_name_iterator(
        "Scene $4", marks, start_line=7, end_line=8, depth=1
    ) == "Scene 4"
    assert resolve_structure_name_iterator(
        "Scene", marks, start_line=7, end_line=8, depth=1
    ) == "Scene"


def test_inline_context_uses_character_ranges_and_renders_under_speaker():
    raw = "MIDNA (If other people are around)\nDo not transform here."
    marks = [
        HierarchyMark(
            0, 0, 3, HierarchyType.SPEAKER,
            start_col=0, end_col=5, order=1,
        ),
        HierarchyMark(
            0, 0, 4, HierarchyType.CONTEXT,
            start_col=7, end_col=33, order=2,
        ),
        HierarchyMark(1, 1, 5, HierarchyType.TEXT, order=3),
    ]

    assert render_hierarchy_markdown(marks, raw) == (
        "{Context: If other people are around}\n\n"
        "**MIDNA**: Do not transform here.\n"
    )


def test_choice_context_groups_following_text_under_same_speaker():
    raw = "GREAT FAIRY\nWould you like to return?\n(Yes)\nI will take you."
    rendered = render_hierarchy_markdown([
        HierarchyMark(0, 0, 3, HierarchyType.SPEAKER, order=1),
        HierarchyMark(1, 1, 4, HierarchyType.TEXT, order=2),
        HierarchyMark(2, 2, 4, HierarchyType.CONTEXT, start_col=1, end_col=4, order=3),
        HierarchyMark(3, 3, 5, HierarchyType.TEXT, order=4),
    ], raw)

    assert "**GREAT FAIRY**: Would you like to return?" in rendered
    assert "{Context: Yes}" in rendered
    assert "**GREAT FAIRY**: I will take you." in rendered


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


def test_render_hierarchy_markdown_emits_glossary_categories_for_mempalace():
    raw = "\n".join([
        "Glossary",
        "Characters",
        "RUSL",
        "Link's mentor from Ordon Village.",
        "Items",
        "Ordon Shield",
        "A wooden shield crafted for Link.",
    ])

    rendered = render_hierarchy_markdown([
        HierarchyMark(0, 6, 0, HierarchyType.GLOSSARY),
        HierarchyMark(1, 3, 1, HierarchyType.STRUCTURE, text="Characters"),
        HierarchyMark(2, 2, 2, HierarchyType.SPEAKER),
        HierarchyMark(3, 3, 3, HierarchyType.TEXT),
        HierarchyMark(4, 6, 1, HierarchyType.STRUCTURE, text="Items"),
        HierarchyMark(5, 5, 2, HierarchyType.STRUCTURE),
        HierarchyMark(6, 6, 3, HierarchyType.TEXT),
    ], raw)

    assert "# Glossary" in rendered
    assert "## Characters" in rendered
    assert "- **RUSL**" in rendered
    assert "  - **Description**: Link's mentor from Ordon Village." in rendered
    assert "## Items" in rendered
    assert "- **Ordon Shield**" in rendered
    assert "  - **Description**: A wooden shield crafted for Link." in rendered


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


def test_line_styles_let_ignored_override_other_marks():
    defs = default_type_definitions()
    styles = line_styles_for_marks([
        HierarchyMark(0, 2, 0, HierarchyType.ACTION),
        HierarchyMark(1, 1, 0, HierarchyType.IGNORE),
    ], defs)

    assert styles[0] == (HierarchyType.ACTION, defs[HierarchyType.ACTION].color)
    assert styles[1] == (HierarchyType.IGNORE, defs[HierarchyType.IGNORE].color)
    assert styles[2] == (HierarchyType.ACTION, defs[HierarchyType.ACTION].color)


def test_ignored_and_unmarked_types_do_not_render_to_markdown():
    rendered = render_hierarchy_markdown([
        HierarchyMark(0, 0, 0, HierarchyType.IGNORE, text="Legal notice"),
        HierarchyMark(1, 1, 0, HierarchyType.UNMARKED, text="Needs work"),
        HierarchyMark(2, 2, 0, HierarchyType.STRUCTURE, text="Act I"),
    ])

    assert "Legal notice" not in rendered
    assert "Needs work" not in rendered
    assert "# Act I" in rendered


def test_ignored_lines_do_not_render_as_structure_raw_gaps():
    rendered = render_hierarchy_markdown([
        HierarchyMark(0, 2, 0, HierarchyType.STRUCTURE, text="Act I"),
        HierarchyMark(1, 1, 0, HierarchyType.IGNORE),
    ], "Act I\nLegal notice\nStory line\n")

    assert "Legal notice" not in rendered
    assert "> [RAW] Story line" in rendered


def test_build_hierarchy_auto_markup_messages_uses_unmarked_source_blocks():
    payload = {
        "raw_text": "Act One\nScene One\nRUSL\nHello.\n",
        "type_definitions": [
            {"type_id": "structure", "label": "Structure"},
            {"type_id": "speaker", "label": "Speaker"},
            {"type_id": "text", "label": "Text"},
        ],
        "hierarchy_marks": [
            {"start_line": 0, "end_line": 1, "depth": 0, "type_id": "structure"},
        ],
        "unmarked_ranges": [
            {"start_line": 2, "end_line": 3},
        ],
        "ai_instructions": ["Depth 1 is inside depth 0."],
    }

    prepared = build_hierarchy_auto_markup_messages(payload)
    user_text = prepared.messages[1]["content"]

    assert prepared.unmarked_range_count == 1
    assert prepared.scope_label == "full script"
    assert '"line_number": 3' in user_text
    assert '"text": "RUSL"' in user_text
    assert "approved_hierarchy_marks" in user_text
    assert "infer the recurring markup pattern" in user_text
    assert "Return only valid JSON" in prepared.messages[0]["content"]


def test_build_hierarchy_auto_markup_messages_compacts_huge_approved_examples():
    huge = "A" * 5000
    payload = {
        "raw_text": "Act One\nRUSL\nHello.\n",
        "type_definitions": [{"type_id": "structure", "label": "Structure"}],
        "hierarchy_marks": [
            {
                "start_line_number": 1,
                "end_line_number": 300,
                "depth": 0,
                "type_id": "structure",
                "type_label": "Structure",
                "text": "Act One",
                "source_excerpt": huge,
            },
        ],
        "unmarked_ranges": [{"start_line": 1, "end_line": 2}],
        "scope": {"label": "Act One", "start_line_number": 1, "end_line_number": 300},
    }

    prepared = build_hierarchy_auto_markup_messages(payload, max_prompt_chars=4000)

    assert prepared.scope_label == "Act One"
    assert huge not in prepared.messages[1]["content"]
    assert "AAA..." in prepared.messages[1]["content"]


def test_build_hierarchy_auto_markup_messages_rejects_huge_prompt():
    payload = {
        "raw_text": "A very long line\n",
        "type_definitions": [],
        "hierarchy_marks": [],
        "unmarked_ranges": [{"start_line": 0, "end_line": 0}],
    }

    try:
        build_hierarchy_auto_markup_messages(payload, max_prompt_chars=10)
    except HierarchyAIPromptTooLarge:
        pass
    else:
        raise AssertionError("Expected prompt size guard to fire.")


def test_parse_hierarchy_auto_markup_response_accepts_fenced_json_and_labels():
    defs = default_type_definitions()
    response = """```json
{
  "marks": [
    {
      "start_line_number": 3,
      "end_line_number": 3,
      "depth": 2,
      "type_label": "Speaker",
      "text": "RUSL"
    },
    {
      "start_line_number": 4,
      "end_line_number": 4,
      "depth": 3,
      "type_id": "text"
    },
    {
      "start_line_number": 10,
      "end_line_number": 10,
      "depth": 3,
      "type_id": "text"
    }
  ]
}
```"""

    marks, warnings = parse_hierarchy_auto_markup_response(
        response,
        raw_line_count=4,
        type_definitions=defs,
    )

    assert [(mark.start_line, mark.end_line, mark.depth, mark.type_id, mark.text) for mark in marks] == [
        (2, 2, 2, HierarchyType.SPEAKER, "RUSL"),
        (3, 3, 3, HierarchyType.TEXT, ""),
    ]
    assert warnings == ["Skipped mark 3: start line is outside the file."]


def test_item_types_render_as_reference_entry_not_speaker_dialogue():
    raw = "Collection Screen\nWallet\nA wallet from your childhood.\n"
    marks = [
        HierarchyMark(0, 2, 0, HierarchyType.STRUCTURE, text="Collection Screen", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.ITEM, order=2),
        HierarchyMark(2, 2, 2, HierarchyType.ITEM_DESCRIPTION, order=3),
    ]

    rendered = render_hierarchy_markdown(marks, raw)

    definitions = default_type_definitions()
    assert definitions[HierarchyType.ITEM].label == "Item"
    assert definitions[HierarchyType.ITEM_DESCRIPTION].label == "Item Description"
    assert "- **Wallet**: A wallet from your childhood." in rendered
    assert "**Wallet**:" not in rendered.replace("- **Wallet**:", "")
