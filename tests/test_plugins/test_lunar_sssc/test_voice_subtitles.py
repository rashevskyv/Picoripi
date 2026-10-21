"""Opening-monologue subtitles of Lunar: SSSC. Synthetic scripts only (no game bytes).

The subtitle messages go after the clip-start op at ``voice_subtitles.ANCHOR``, so the synthetic script
places that op and the op that follows it at the same offset as the real TEXT001.DAT.
"""
import struct

import romhacking_root  # noqa: F401  (path setup for the repository's packages)

from plugins.lunar_sssc import codec, doc, script, voice_subtitles as vs

BLANK = [""] * len(vs.SEGMENTS)


def _synthetic_script() -> bytes:
    """Label 1: one message, then the end op (code at 0x800). Label 2: the clip-start op at ANCHOR,
    the op 0x0052 that follows it, then the end op."""
    message = b"\x02\x00" + codec.Encoder().message("Hello, Alex!")
    code = message + bytes(len(message) & 1) + b"\x05\x00"
    labels = [0] * script.LABELS
    labels[1] = 0x800 // 2
    labels[2] = vs.ANCHOR // 2
    gap = bytes(vs.ANCHOR - 0x800 - len(code))
    tail = b"\x53\x00" + vs.FOLLOW + b"\x05\x00"
    return struct.pack(f"<{script.LABELS}H", *labels) + code + gap + tail


def _region(lines) -> bytes:
    return vs.build(lines)


def test_an_unedited_script_reads_its_empty_subtitle_block_and_writes_back_identical():
    source = _synthetic_script()
    blocks, names = doc.read(source)
    assert names == {"1": "Voice subtitles"}
    assert blocks == [["Hello, Alex!"], BLANK]
    assert doc.write(source, blocks, set()) == source


def test_subtitle_lines_come_back_in_their_segments_and_resetting_restores_the_original():
    source = _synthetic_script()
    lines = ["First line", "", "Third line", "", "", "Sixth line", "", ""]
    edited = doc.write(source, [["Hello, Alex!"], lines], set())
    assert (len(edited) - len(source)) % 4 == 0
    blocks, names = doc.read(edited)
    assert names == {"1": "Voice subtitles"}
    assert blocks[0] == ["Hello, Alex!"]
    assert blocks[1] == lines
    assert doc.write(edited, [["Hello, Alex!"], BLANK], set()) == source


def test_every_set_of_lines_keeps_the_code_after_it_on_the_four_byte_grid():
    cases = [["Short"] + [""] * 7, ["A" * 40, "B" * 3, "", "C", "", "", "D", ""],
             ["x" * n for n in range(1, 9)]]
    for lines in cases:
        region = _region(lines)
        assert len(region) % 4 == 0
        assert vs.lines_of(_with_region(region)) == lines


def test_each_line_is_held_for_its_segment_in_frames():
    region = _region(["ONE", "", "THREE"] + [""] * 5)
    first = codec.decode_message(region, 2, len(region))     # the first message: segment 0 starts at 0 s
    start, end = vs.SEGMENTS[0]
    assert first.startswith("ONE")
    assert ("{F8:%02X}{close}" % round((end - start) * vs.FPS)) in first


def test_splice_moves_the_labels_after_the_insert_and_keeps_the_others():
    data = _synthetic_script()
    before = struct.unpack_from(f"<{script.LABELS}H", data, 0)
    moved = script.splice(data, vs.ANCHOR + 2, vs.ANCHOR + 2, b"\x05\x00" * 2)
    after = struct.unpack_from(f"<{script.LABELS}H", moved, 0)
    assert after[1] == before[1]
    assert after[2] == before[2]
    assert len(moved) == len(data) + 4


def _with_region(region: bytes) -> bytes:
    """The synthetic script with exactly this subtitle region after its clip-start op."""
    return script.splice(_synthetic_script(), vs.ANCHOR + 2, vs.ANCHOR + 2, region)
