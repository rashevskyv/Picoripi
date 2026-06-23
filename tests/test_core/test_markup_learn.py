"""Tests for teach-by-example pattern inference (core/script_markup/learn.py)."""
import re

from core.script_markup.learn import (
    learn_speaker_pattern,
    learn_speaker_pattern_from_parts,
    learn_ignore_pattern,
    learn_header_pattern,
)


def test_learn_speaker_uppercase():
    pat = learn_speaker_pattern("MIDNA: Hey there!")
    assert pat is not None
    m = re.match(pat, "ZELDA: Be careful.")
    assert m and m.group("speaker") == "ZELDA" and m.group("text") == "Be careful."


def test_learn_speaker_mixed_case():
    pat = learn_speaker_pattern("Midna: Hey!")
    assert pat is not None
    # Mixed-case sample yields a pattern that also accepts mixed-case names.
    m = re.match(pat, "Rusl: Take this.")
    assert m and m.group("speaker") == "Rusl"


def test_learn_speaker_requires_colon():
    assert learn_speaker_pattern("just some narration") is None


def test_learn_speaker_from_parts_custom_separator():
    # Format the colon rule cannot handle: 'Name - text'
    pat = learn_speaker_pattern_from_parts("Rusl - Take this shield.", "Rusl", "Take this shield.")
    assert pat is not None
    m = re.match(pat, "Midna - Hello there.")
    assert m and m.group("speaker") == "Midna" and m.group("text") == "Hello there."


def test_learn_speaker_from_parts_bracketed_with_suffix():
    pat = learn_speaker_pattern_from_parts('[RUSL] "Take this."', "RUSL", "Take this.")
    assert pat is not None
    m = re.match(pat, '[LINK] "Hyah!"')
    assert m and m.group("speaker") == "LINK" and m.group("text") == "Hyah!"


def test_learn_speaker_from_parts_needs_an_anchor():
    # name immediately followed by text, no separator → refuse (ambiguous).
    assert learn_speaker_pattern_from_parts("RuslTake", "Rusl", "Take") is None


def test_learn_speaker_from_parts_parts_must_exist_in_sample():
    assert learn_speaker_pattern_from_parts("RUSL: hi", "ZELDA", "hi") is None


def test_learn_ignore_matches_exact_line_only():
    pat = learn_ignore_pattern("(c) 1998 GameFAQs")
    assert pat is not None
    assert re.match(pat, "(c) 1998 GameFAQs")
    assert not re.match(pat, "(c) 1999 GameFAQs")


def test_learn_header_with_delimiters():
    pat = learn_header_pattern("=== Ordon Village ===")
    assert pat is not None
    m = re.match(pat, "=== Death Mountain ===")
    assert m and m.group("name") == "Death Mountain"


def test_learn_header_refuses_without_delimiter():
    # A bare line has no anchor — inference must refuse rather than match all.
    assert learn_header_pattern("Ordon Village") is None
