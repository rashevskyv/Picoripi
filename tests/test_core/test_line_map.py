"""Tests for the source<->output line correspondence used by pane sync."""
from core.script_markup import build_line_map, nearest_output, convert, default_recipe


def test_build_line_map_matches_dialogue_lines():
    raw = [
        "[Chapter: Prologue]",
        "MIDNA: Well, look what we have here!",
        "ZELDA: Be careful.",
    ]
    output = [
        "# Timeline",
        "",
        "## Prologue",
        "",
        "MIDNA: Well, look what we have here!",
        "ZELDA: Be careful.",
    ]
    m = build_line_map(raw, output)
    # source line 1 (MIDNA) -> output line index 4; source 2 (ZELDA) -> 5
    assert m[1] == 4
    assert m[2] == 5


def test_build_line_map_handles_action_and_location_markers():
    raw = ["{Action: Midna appears}", "Some dialogue here"]
    output = ["{Action: Midna appears}", "NARRATOR: Some dialogue here"]
    m = build_line_map(raw, output)
    assert m[0] == 0   # action line matches
    assert m[1] == 1   # 'Some dialogue here' after the 'NARRATOR: ' prefix


def test_nearest_output_falls_back_to_previous_mapped_line():
    src_to_out = {2: 10, 5: 20}
    mapped = sorted(src_to_out)
    assert nearest_output(src_to_out, mapped, 2) == 10   # exact
    assert nearest_output(src_to_out, mapped, 4) == 10   # between → previous
    assert nearest_output(src_to_out, mapped, 9) == 20   # after last → last
    assert nearest_output(src_to_out, mapped, 0) == 10   # before first → first


def test_nearest_output_empty_map():
    assert nearest_output({}, [], 3) is None


def test_line_map_round_trips_with_real_convert():
    raw_text = (
        "[Chapter: Prologue]\n"
        "MIDNA: Hello there friend.\n"
        "ZELDA: And to you.\n"
    )
    result = convert(raw_text, default_recipe())
    m = build_line_map(raw_text.splitlines(), result.psm_text.splitlines())
    # Both dialogue source lines should map somewhere into the output.
    assert 1 in m and 2 in m
