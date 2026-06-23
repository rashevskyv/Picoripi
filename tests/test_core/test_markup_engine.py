"""Tests for the Script Markup Studio engine (core/script_markup)."""
from core.script_markup import convert, default_recipe, LineKind
from core.script_markup.markup_recipe import MarkupRecipe


def _kinds(result):
    return [c.kind for c in result.classified]


def test_inline_speaker_and_action_render():
    raw = (
        "[Chapter: Prologue - The Forest Encounter]\n"
        "[Location: Ordon Woods]\n"
        "\n"
        "{Action: Midna drops from a branch}\n"
        "MIDNA: Well, look what we have here!\n"
        "ZELDA: Midna, please, we must be careful.\n"
    )
    result = convert(raw, default_recipe())
    psm = result.psm_text

    assert "## Prologue - The Forest Encounter" in psm
    assert "### Location: Ordon Woods" in psm
    assert "{Action: Midna drops from a branch}" in psm
    assert "MIDNA: Well, look what we have here!" in psm
    assert "ZELDA: Midna, please, we must be careful." in psm
    assert result.speakers == ["MIDNA", "ZELDA"]


def test_dialogue_continuation_is_joined():
    raw = (
        "LINK: This is a long line\n"
        "that wraps onto a second physical line.\n"
    )
    result = convert(raw, default_recipe())
    assert "LINK: This is a long line that wraps onto a second physical line." in result.psm_text
    # The wrapped line is a continuation, not narration.
    assert LineKind.DIALOGUE_CONT in _kinds(result)


def test_gutter_speaker_format_b_default_on():
    raw = (
        "MIDNA\n"
        "Hey! Listen up!\n"
        "We don't have all day!\n"
    )
    # Gutter speakers are enabled by default now (many walkthroughs use Format B).
    result = convert(raw, default_recipe())
    assert "MIDNA: Hey! Listen up! We don't have all day!" in result.psm_text
    assert result.speakers == ["MIDNA"]


def test_gutter_can_be_disabled():
    raw = "MIDNA\nHey! Listen up!\n"
    result = convert(raw, MarkupRecipe(gutter_speakers=False))
    assert "MIDNA:" not in result.psm_text
    assert result.speakers == []


def test_gutter_lookahead_rejects_consecutive_headers():
    # A run of all-caps lines is a header list, not speakers — none should be
    # treated as a gutter speaker.
    raw = "CASTLE TOWN\nDEATH MOUNTAIN\nKAKARIKO VILLAGE\n"
    result = convert(raw, default_recipe())
    assert result.speakers == []


def test_multiline_bracket_action_is_joined():
    raw = (
        "[Link walks slowly\n"
        "into the dark room]\n"
        "ZELDA: Hello.\n"
    )
    result = convert(raw, default_recipe())
    assert "{Action: Link walks slowly into the dark room}" in result.psm_text
    assert "ZELDA: Hello." in result.psm_text


def test_multiline_brace_action_is_joined():
    raw = (
        "{Action: Zelda turns\n"
        "to face the window}\n"
    )
    result = convert(raw, default_recipe())
    assert "{Action: Zelda turns to face the window}" in result.psm_text


def test_timeline_range_excludes_front_matter():
    raw = (
        "Legal stuff line one\n"
        "ACT ONE table of contents\n"
        "ZELDA: This is real dialogue.\n"
    )
    # Only consider from line 3 onward (skip TOC/cast/legal).
    result = convert(raw, default_recipe(), start_line=3)
    assert "ZELDA: This is real dialogue." in result.psm_text
    assert "Legal stuff" not in result.psm_text
    assert "table of contents" not in result.psm_text


def test_noise_and_toc_are_ignored():
    raw = (
        "~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n"
        "Foreword..................................3\n"
        "ZELDA: Real dialogue here.\n"
    )
    result = convert(raw, default_recipe())
    kinds = _kinds(result)
    assert kinds[0] == LineKind.IGNORE   # separator run
    assert kinds[1] == LineKind.IGNORE   # dot-leader TOC
    assert "ZELDA: Real dialogue here." in result.psm_text
    # Noise never leaks into the rendered output.
    assert "Foreword" not in result.psm_text
    assert "~~~" not in result.psm_text


def test_narration_flagged_when_it_contains_quotes():
    raw = 'He turned and said "Hello there, traveler" with a grin.\n'
    result = convert(raw, default_recipe())
    assert any("missed dialogue" in reason for _, reason in result.flags)


def test_recipe_round_trips_through_dict():
    recipe = MarkupRecipe(name="Custom", gutter_speakers=True, continuation=False)
    restored = MarkupRecipe.from_dict(recipe.to_dict())
    assert restored.name == "Custom"
    assert restored.gutter_speakers is True
    assert restored.continuation is False


def test_from_dict_ignores_unknown_keys():
    restored = MarkupRecipe.from_dict({"name": "X", "unknown_future_key": 123})
    assert restored.name == "X"
