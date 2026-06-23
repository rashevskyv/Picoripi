"""Tests for the adapter that reuses Picoripi's existing markup rules."""
from core.script_markup import (
    parse_with_rules,
    transcript_to_psm,
    summarize_transcript,
    highlight_kinds_from_transcript,
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


def test_highlight_kinds_marks_dialogue_and_markers():
    raw_lines = ["[Chapter: Prologue]", "{Action: x}", "Well, look what we have here!", ""]
    transcript = [{"text": "Well, look what we have here!", "speaker": "MIDNA",
                   "timestamp": "Scene_1", "room": "Prologue"}]
    kinds = highlight_kinds_from_transcript(raw_lines, transcript)
    assert kinds[0] == LineKind.CHAPTER
    assert kinds[1] == LineKind.ACTION
    assert kinds[2] == LineKind.SPEAKER


def test_parse_with_rules_handles_none_rules():
    assert parse_with_rules(None, "anything") == []
