"""Tests for the adapter that reuses Picoripi's existing markup rules."""
from core.script_markup import (
    parse_with_rules,
    transcript_to_psm,
    summarize_transcript,
    annotate_source_lines,
    LineKind,
)
from plugins.base_game_rules import BaseGameRules


def test_parse_with_rules_uses_base_parser():
    text = (
        "[Chapter: Prologue]\n"
        "[Location: Ordon]\n"
        "{Action: Midna appears}\n"
        "MIDNA: Well, look what we have here!\n"
    )
    transcript = parse_with_rules(BaseGameRules(), text)
    assert any(e.get("speaker") == "MIDNA" and "look what we have" in e.get("text", "")
               for e in transcript)


def test_transcript_to_psm_round_trips_structure():
    transcript = [
        {"text": "Well, look what we have here!", "speaker": "MIDNA",
         "timestamp": "Action: Midna appears", "room": "Prologue"},
        {"text": "Be careful.", "speaker": "ZELDA",
         "timestamp": "Scene_5", "room": "Prologue"},
    ]
    psm = transcript_to_psm(transcript)
    assert "## Prologue" in psm
    assert "{Action: Midna appears}" in psm
    assert "MIDNA: Well, look what we have here!" in psm
    assert "ZELDA: Be careful." in psm


def test_transcript_to_psm_sanitizes_speaker_charset():
    # Default narrator label contains '/', which is not valid in the SPEAKER charset.
    transcript = [{"text": "Some narration.", "speaker": "Dialogue/Narrator",
                   "timestamp": "Scene_1", "room": "Intro"}]
    psm = transcript_to_psm(transcript)
    assert "DIALOGUE NARRATOR: Some narration." in psm
    assert "/" not in psm.split("DIALOGUE NARRATOR")[0].splitlines()[-1]


def test_summarize_transcript_counts_and_speakers():
    transcript = [
        {"text": "Hi", "speaker": "MIDNA", "timestamp": "Scene_1", "room": "A"},
        {"text": "Yo", "speaker": "LINK", "timestamp": "Action: waves", "room": "A"},
        {"text": "narr", "speaker": "Dialogue/Narrator", "timestamp": "Scene_2", "room": "B"},
    ]
    speakers, stats = summarize_transcript(transcript)
    assert "MIDNA" in speakers and "LINK" in speakers
    assert "DIALOGUE NARRATOR" not in speakers  # default narrator excluded
    assert stats[LineKind.SPEAKER] == 3
    assert stats[LineKind.CHAPTER] == 2  # rooms A, B


def test_annotate_marks_markers_and_groups_speaker():
    raw_lines = [
        "[Chapter: Prologue]",
        "{Action: x}",
        "MIDNA",                              # gutter speaker header
        "Well, look what we have here!",      # her dialogue body
        "Take a look at this!",               # more of her dialogue
        "ZELDA: Be careful.",                 # inline header (different speaker)
    ]
    transcript = [
        {"text": "Well, look what we have here!", "speaker": "MIDNA", "timestamp": "Scene_1", "room": "P"},
        {"text": "Take a look at this!", "speaker": "MIDNA", "timestamp": "Scene_2", "room": "P"},
        {"text": "Be careful.", "speaker": "ZELDA", "timestamp": "Scene_3", "room": "P"},
    ]
    ann = annotate_source_lines(raw_lines, transcript)
    assert ann[0] == (LineKind.CHAPTER, None)
    assert ann[1] == (LineKind.ACTION, None)
    assert ann[2] == (LineKind.SPEAKER, "MIDNA")        # gutter header
    assert ann[3] == (LineKind.DIALOGUE_CONT, "MIDNA")  # body, same speaker
    assert ann[4] == (LineKind.DIALOGUE_CONT, "MIDNA")
    assert ann[5] == (LineKind.SPEAKER, "ZELDA")        # inline header, new speaker


def test_annotate_marks_multiline_square_brackets_as_action():
    raw_lines = [
        "[Link rushes through the forest,",
        "where the twilight parts around him]",
        "ILIA",
        "Oh, hi, Link.",
    ]
    transcript = [{"text": "Oh, hi, Link.", "speaker": "ILIA", "timestamp": "Scene_3", "room": "P"}]
    ann = annotate_source_lines(raw_lines, transcript)
    assert ann[0] == (LineKind.ACTION, None)
    assert ann[1] == (LineKind.ACTION, None)
    assert ann[2] == (LineKind.SPEAKER, "ILIA")
    assert ann[3] == (LineKind.DIALOGUE_CONT, "ILIA")


def test_parse_with_rules_uses_multiline_square_brackets_as_action_context():
    text = (
        "[Link rushes through the forest,\n"
        "where the twilight parts around him]\n"
        "ILIA\n"
        "Oh, hi, Link.\n"
    )
    transcript = parse_with_rules(BaseGameRules(), text)
    assert len(transcript) == 1
    assert transcript[0]["speaker"] == "ILIA"
    assert transcript[0]["timestamp"].startswith("Action: Link rushes through the forest")
    assert "twilight parts around him" in transcript[0]["timestamp"]


def test_parse_with_rules_handles_none_rules():
    assert parse_with_rules(None, "anything") == []
