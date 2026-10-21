"""Subtitle timing of the Lunar opening monologue: model, file, problems, editing, build and read back.

Synthetic scripts and timings only (no game bytes, no audio).
"""
import json
import struct
from pathlib import Path

import pytest

import romhacking_root  # noqa: F401  (path setup for the repository's packages)

from plugins.lunar_sssc import codec, doc, script, subtitle_timing as st, voice, voice_subtitles as vs
from plugins.lunar_sssc.rules import GameRules
from plugins.lunar_sssc.subtitle_timing import Cue, Timing


def _script() -> bytes:
    message = b"\x02\x00" + codec.Encoder().message("Hello, Alex!")
    code = message + bytes(len(message) & 1) + b"\x05\x00"
    labels = [0] * script.LABELS
    labels[1] = 0x800 // 2
    labels[2] = vs.ANCHOR // 2
    gap = bytes(vs.ANCHOR - 0x800 - len(code))
    return struct.pack(f"<{script.LABELS}H", *labels) + code + gap + b"\x53\x00" + vs.FOLLOW + b"\x05\x00"


def _timing(*pairs, offset=0):
    return Timing(offset, tuple(Cue(a, b) for a, b in pairs))


# ---------------------------------------------------------------- model and file

def test_defaults_are_the_speech_spans_in_whole_frames():
    assert len(st.SEGMENTS) == 8
    assert st.defaults().cues[0] == Cue(0, 132)                 # 2.20 s
    assert st.defaults().cues[1] == Cue(168, 375)               # 2.80 s .. 6.25 s
    assert all(isinstance(v, int) for cue in st.defaults().cues for v in (cue.start, cue.end))


def test_json_round_trip_and_rejection_of_bad_shapes():
    timing = _timing((0, 60), (90, 200), offset=12)
    assert st.from_json(json.loads(json.dumps(st.to_json(timing)))) == timing
    for bad in ({}, {"cues": 3}, {"cues": [5]}, {"cues": [{"start_frame": -1, "end_frame": 4}]},
                {"cues": [{"start_frame": 9, "end_frame": 4}]}, {"cues": [{"start_frame": 1.5, "end_frame": 4}]}):
        with pytest.raises(ValueError):
            st.from_json(bad)


def test_file_is_written_atomically_and_missing_or_broken_files_are_told_apart(tmp_path):
    path = tmp_path / "voice" / st.TIMING_FILE
    assert st.read_file(path) is None
    timing = _timing((0, 60), offset=3)
    st.write_file(path, timing)
    assert st.read_file(path) == timing
    assert [p.name for p in path.parent.iterdir()] == [st.TIMING_FILE]    # no temporary file left behind
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        st.read_file(path)


def test_rules_save_and_load_the_timing_next_to_the_voice_wav(tmp_path):
    rules = GameRules(None)
    project = tmp_path / "picoripi"
    assert rules.timing_for(str(project)) == st.defaults()
    timing = _timing((10, 70), (80, 140))
    saved = rules.save_subtitle_timing(str(project), timing)
    assert Path(saved) == tmp_path / "translation" / "voice" / st.TIMING_FILE
    assert rules.timing_for(str(project)) == timing


def test_seconds_and_frames_convert_both_ways():
    assert st.frames_of(2.2) == 132
    assert st.seconds(132) == 2.2
    assert st.from_spans([(0.0, 1.0), (2.0, 2.5)], offset=4) == _timing((0, 60), (120, 150), offset=4)


# ---------------------------------------------------------------- problems

def test_problems_name_overlaps_short_cues_and_cues_past_the_clip():
    timing = _timing((0, 60), (50, 120), (200, 202))         # cue 2 overlaps cue 1; cue 3 is 2 frames
    found = st.problems(timing, ["x" * 20, "y" * 20, "z" * 20], duration=3.0)
    assert ("overlap", 1) in found
    assert any(p[0] == "short" and p[1] == 2 for p in found)  # 20 characters need 1 s at 20 per second
    assert st.problems(_timing((0, 60)), ["a"]) == []
    assert st.problems(_timing((0, 60)), ["a", "b"]) == [("count", 2, 1), ("short", 1, 0.05)]
    assert ("past_end", 0) in st.problems(_timing((0, 200)), ["ok"], duration=2.0)


def test_a_cue_that_fits_its_text_has_no_problem():
    assert st.problems(_timing((0, 60), (60, 120)), ["twenty characters ok", "fine"], duration=5.0) == []


# ---------------------------------------------------------------- editing

def test_move_keeps_length_and_stops_at_the_neighbours():
    timing = _timing((0, 60), (100, 160), (200, 260))
    assert st.move(timing, 1, 10).cues[1] == Cue(110, 170)
    assert st.move(timing, 1, 500).cues[1] == Cue(140, 200)   # stops where the next cue starts
    assert st.move(timing, 1, -500).cues[1] == Cue(60, 120)   # stops where the previous cue ends


def test_set_edge_keeps_order_and_at_least_one_frame():
    timing = _timing((0, 60), (100, 160))
    assert st.set_edge(timing, 1, "start", 0).cues[1] == Cue(60, 160)
    assert st.set_edge(timing, 0, "end", 500).cues[0] == Cue(0, 100)
    assert st.set_edge(timing, 0, "end", -3).cues[0] == Cue(0, 1)


def test_split_and_merge_are_inverse_on_times():
    timing = _timing((0, 60), (100, 160))
    split = st.split(timing, 1)
    assert split.cues == (Cue(0, 60), Cue(100, 130), Cue(130, 160))
    assert st.merge(split, 1).cues == timing.cues


# ---------------------------------------------------------------- build and read back

def test_build_then_read_gives_the_same_lines_and_keeps_the_grid():
    timing = _timing((0, 90), (120, 200), (260, 300), (300, 340), offset=30)
    lines = ["First", "", "Third line", "Fourth"]
    region = vs.build(lines, timing)
    assert len(region) % 4 == 0
    assert vs.lines_of(_with(region), timing) == lines


def test_the_first_message_waits_for_the_offset_and_the_gap_is_after_its_close():
    timing = _timing((0, 60), (100, 160), offset=30)
    region = vs.build(["ONE", "TWO"], timing)
    # lead-in 30 frames before the text; shown 60 frames; the box closes; the gap to TWO (130 - 90 = 40) follows
    assert codec.decode_message(region, 2, len(region)).startswith("{F8:1E}ONE{F8:3C}{close}{F8:28}")


def test_a_file_read_with_a_timing_it_was_not_built_with_uses_the_defaults_for_the_mapping():
    built = _timing(*[(a, b) for a, b in st.SEGMENTS], offset=0)
    lines = ["one", "", "three"] + [""] * 5
    region = vs.build(lines, built)
    shifted = _timing((10, 20), (500, 520), (900, 950), (1000, 1010), (1100, 1120),
                      (1200, 1260), (1300, 1400), (1500, 1600))
    read = vs.lines_of(_with(region), shifted)
    assert read[0] == "one" and read[2] == "three"


def test_doc_writes_and_reads_the_subtitle_block_with_a_timing():
    timing = _timing((0, 90), (120, 200), offset=10)
    source = _script()
    edited = doc.write(source, [["Hello, Alex!"], ["Alpha", "Beta"]], set(), timing=timing)
    blocks, names = doc.read(edited, timing=timing)
    assert names == {"1": "Voice subtitles"}
    assert blocks == [["Hello, Alex!"], ["Alpha", "Beta"]]


# ---------------------------------------------------------------- waveform helper

def test_peaks_are_the_loudest_level_per_part_and_scale_to_one():
    assert voice.peaks([0, 16384, -32768, 0], buckets=2) == [0.5, 1.0]
    assert voice.peaks([], buckets=3) == [0.0, 0.0, 0.0]


def _with(region: bytes) -> bytes:
    return script.splice(_script(), vs.ANCHOR + 2, vs.ANCHOR + 2, region)
