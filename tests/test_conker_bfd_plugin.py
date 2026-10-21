"""Conker's Bad Fur Day (N64) plugin: ROM reader, RZIP, font RLE, text tags, width, problems, voice (synthetic data only)."""
import struct
import zlib

import pytest

from plugins.conker_bfd import font, n64_archive as na, preview, text_blocks, voice
from plugins.conker_bfd.config import PROBLEM_CHARACTER, PROBLEM_LENGTH
from plugins.conker_bfd.rules import LEGACY_FORMAT_ID, GameRules


def rzip(payload: bytes) -> bytes:
    deflater = zlib.compressobj(9, zlib.DEFLATED, -15)
    return struct.pack(">I", len(payload)) + deflater.compress(payload) + deflater.flush()


def build_rom(entries_by_bank, table_start=0x100):
    """A minimal ROM: outer table at table_start, one inner table per bank, entries after it."""
    rom = bytearray(0x4000)
    bank_count = len(entries_by_bank)
    pos = table_start + 8 * bank_count
    outer = []
    for entries in entries_by_bank:
        slots = max((i for i, _ in entries), default=-1) + 1
        inner_size = 8 * slots
        bank_start = pos
        inner = bytearray(inner_size)
        cursor = bank_start + inner_size
        for index, (blob, rzip_flag) in entries:
            struct.pack_into(">II", inner, index * 8, cursor - bank_start,
                             len(blob) | (0x10 << 24 if rzip_flag else 0))
            rom[cursor:cursor + len(blob)] = blob
            cursor += len(blob)
        rom[bank_start:bank_start + inner_size] = inner
        outer.append((bank_start - table_start, cursor - bank_start))
        pos = cursor
    struct.pack_into(">I", rom, table_start, 8 * bank_count)
    for i, (rel, size) in enumerate(outer):
        struct.pack_into(">II", rom, table_start + 8 * i, rel, size)
    return bytes(rom[:pos + 0x10]), table_start


def test_normalize_accepts_z64_v64_n64_and_rejects_others():
    z64 = b"\x80\x37\x12\x40" + b"\x01\x02\x03\x04"
    assert na.normalize_rom(z64) == z64
    swapped = bytearray(len(z64))
    swapped[0::2] = z64[1::2]
    swapped[1::2] = z64[0::2]
    assert na.normalize_rom(bytes(swapped)) == z64
    n64 = bytearray(len(z64))
    for pos in range(0, len(z64), 4):
        n64[pos:pos + 4] = z64[pos:pos + 4][::-1]
    assert na.normalize_rom(bytes(n64)) == z64
    with pytest.raises(na.RomError):
        na.normalize_rom(b"\x00\x00\x00\x00")


def test_rzip_round_trip_and_error_cases():
    payload = bytes(range(256)) * 3
    blob = rzip(payload)
    decoded, consumed = na.decode_rzip(blob + b"\xAA\xBB")
    assert decoded == payload and consumed == len(blob)
    with pytest.raises(na.RomError):
        na.decode_rzip(blob[:-3])
    with pytest.raises(na.RomError):
        na.decode_rzip(struct.pack(">I", len(payload) + 1) + blob[4:])


def test_bank_index_reads_entries_raw_and_compressed_and_skips_empty_slots():
    raw = b"raw entry bytes"
    packed = b"packed entry payload " * 4
    rom, table = build_rom([[(0, (raw, False)), (2, (rzip(packed), True))]])
    banks = na.parse_banks(rom, table)
    assert len(banks) == 1 and banks[0].flags == 0
    entries = na.parse_entries(rom, banks[0])
    assert [e.index for e in entries] == [0, 2]
    assert na.read_entry(rom, entries[0]) == raw
    assert na.read_entry(rom, entries[1]) == packed


def test_bank_index_rejects_out_of_range_entry():
    rom, table = build_rom([[(0, (b"abcdefgh", False))]])
    bank = na.parse_banks(rom, table)[0]
    broken = bytearray(rom)
    struct.pack_into(">II", broken, bank.start, 0x7FFF0, 8)
    with pytest.raises(na.RomError):
        na.parse_entries(bytes(broken), bank)


def test_glyph_rle_round_trip_and_row_boundaries():
    pixels = bytes([0x00] * 5 + [0xF0] * 5 + [0x30] * 5)
    rle = font.encode_rle(5, 3, pixels)
    assert font.decode_rle(5, 3, rle) == pixels
    assert all(((value & 0x0F) + 1) <= 16 for value in rle)


def test_font_table_parses_records_and_rejects_nonzero_padding():
    glyph = font.Glyph(index=0, width=2, height=2, meta=b"\x01\x02",
                       pixels=bytes([0x10, 0x10, 0x20, 0x20]), rle=b"")
    record = font.encode_record(glyph)
    rom = record + b"\x00\x00"
    parsed = font.parse_table(rom, 0, len(rom), count=1)
    assert parsed[0].pixels == glyph.pixels and parsed[0].meta == b"\x01\x02"
    with pytest.raises(na.RomError):
        font.parse_table(record + b"\x00\x07", 0, len(record) + 2, count=1)
    assert font.pgm_bytes(parsed[0]).startswith(b"P5\n2 2\n255\n")


def test_glyph_lookup_folds_lowercase_and_skips_the_space():
    glyph_map = bytes([0x41, 0x42, 0x43]) + bytes(92)
    assert font.glyph_index(0x61, glyph_map) == 0      # 'a' draws the 'A' glyph
    assert font.glyph_index(0x43, glyph_map) == 2
    assert font.glyph_index(0x20, glyph_map) is None   # space has no glyph
    assert font.glyph_index(0x7F, glyph_map) is None   # not in the map


def test_glyph_map_must_have_95_codes_with_93_distinct_values():
    codes = bytes(range(0x30, 0x30 + 93)) + bytes([0x30, 0x31])
    assert font.read_glyph_map(codes, 0) == codes
    with pytest.raises(na.RomError):
        font.read_glyph_map(bytes(range(0x30, 0x30 + 95)), 0)


def test_text_runs_keep_inline_codes_as_tags_and_bounded_words_as_text():
    data = b"\x00\x01Lorem ipsum dolor.\n\xaf\xbd\x00Alpha\x00ab\x00\x7f"
    segments = text_blocks.split_segments(data)
    assert text_blocks.join_segments(segments) == data
    texts = [text_blocks.bytes_to_string(raw) for kind, raw in segments if kind == "text"]
    assert texts == ["Lorem ipsum dolor.\n[@AF][@BD]", "Alpha"]   # "ab" has two letters: binary
    assert [kind for kind, _ in segments] == ["bin", "text", "bin", "text", "bin"]


def test_text_form_round_trips_and_refuses_characters_it_cannot_carry():
    raw = b"Mix \xa9 of [brackets] and\nnewline \x80\x81."
    text = text_blocks.bytes_to_string(raw)
    assert text == "Mix [@A9] of [@5B]brackets] and\nnewline [@80][@81]."
    assert text_blocks.string_to_bytes(text) == raw
    with pytest.raises(ValueError):
        text_blocks.string_to_bytes("café")


def test_json_segments_join_back_to_the_same_bytes():
    data = b"junk\x00Lorem ipsum dolor sit.\n\xba\xbd\x00\xff"
    segments = text_blocks.split_segments(data)
    back = text_blocks.from_json_segments(text_blocks.to_json_segments(segments))
    assert text_blocks.join_segments(back) == data


def synthetic_metrics():
    """Glyph 0 'A': 2x2, offsets (1, 0); glyph 1 'B': 3x3, offsets (0, 2)."""
    return [preview.Metric(2, 2, bytes([1, 0])), preview.Metric(3, 3, bytes([0, 2]))], bytes([0x41, 0x42]) + bytes(93)


def synthetic_glyphs():
    a = font.Glyph(index=0, width=2, height=2, meta=bytes([1, 0]), pixels=bytes([0xF0] * 4), rle=b"")
    b = font.Glyph(index=1, width=3, height=3, meta=bytes([0, 2]), pixels=bytes([0xF0] * 9), rle=b"")
    return [a, b], synthetic_metrics()[1]


def test_layout_uses_measured_advance_and_line_height():
    glyphs, glyph_map = synthetic_glyphs()
    items = preview.layout_line_items(b"AB\nA", glyphs, glyph_map)
    assert [(x, y, g.index) for x, y, g in items] == [(1, 0, 0), (3, 2, 1), (1, 12, 0)]


def test_measure_sums_advances_spaces_icons_and_skips_control_codes():
    metrics, glyph_map = synthetic_metrics()
    assert preview.measure_px(b"AB", metrics, glyph_map) == 3 + 3          # (2+1) + (3+0)
    assert preview.measure_px(b"A B", metrics, glyph_map) == 3 + 4 + 3
    assert preview.measure_px(b"A\xaf", metrics, glyph_map) == 3 + 46      # icon 0xAF is 46 px wide
    assert preview.measure_px(b"\xbc\x01\x02A", metrics, glyph_map) == 3   # the control code takes no room
    assert preview.measure_px(b"AB\nA", metrics, glyph_map) == 6           # widest line


def test_render_draws_white_glyph_with_black_shadow_and_whole_zoom():
    glyphs, glyph_map = synthetic_glyphs()
    canvas = preview.render_text(b"A", glyphs, glyph_map, origin=(0, 0), canvas_size=(16, 16))
    assert canvas.getpixel((1, 0)) == (255, 255, 255, 240)   # glyph body
    assert canvas.getpixel((3, 1)) == (0, 0, 0, 240)         # shadow only, offset (1, 1)
    assert canvas.getpixel((0, 0))[3] == 0                    # outside the glyph
    zoomed = preview.render_text(b"A", glyphs, glyph_map, origin=(0, 0), zoom=3, canvas_size=(16, 16))
    assert zoomed.size == (48, 48)


def synthetic_text_table(texts):
    """A text table as the unpack writes it: segments, glyph metrics and the map, with synthetic text."""
    font_block = {"map": (bytes([0x41, 0x42]) + bytes(93)).hex(),
                  "glyphs": [[2, 2, 1, 0]] + [[3, 3, 0, 2]] + [[2, 2, 1, 0]] * 93}
    segments = []
    for text in texts:
        segments.append({"kind": "bin", "hex": "0001"})
        segments.append({"kind": "text", "text": text})
    return {"format": LEGACY_FORMAT_ID, "source": "bank_1A/entry_0000", "bytes": 0,
            "segments": segments, "font": font_block}


def test_text_block_load_and_save_round_trip_is_exact():
    table = synthetic_text_table(["Alpha beta gamma.\n[@AF] delta."])
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(table)
    assert names == {"0": "bank_1A/entry_0000"}
    assert blocks == [["Alpha beta gamma.\n[@AF] delta."]]
    assert rules.save_data_to_json_obj(blocks, names) == table


def test_edited_text_is_saved_and_a_bad_character_keeps_the_original():
    table = synthetic_text_table(["Alpha beta."])
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(table)
    blocks[0][0] = "Gamma."
    assert rules.save_data_to_json_obj(blocks, names)["segments"][1]["text"] == "Gamma."
    blocks[0][0] = "café"
    assert rules.save_data_to_json_obj(blocks, names)["segments"][1]["text"] == "Alpha beta."


def test_translation_longer_than_the_original_is_flagged():
    rules = GameRules()
    rules.load_data_from_json_obj(synthetic_text_table(["Alpha."]))
    assert rules.get_text_fit_problems_for_string(0, 0, "Alpha.") == []
    assert rules.get_text_fit_problems_for_string(0, 0, "Alphas.") == [PROBLEM_LENGTH]
    assert rules.get_text_fit_problems_for_string(0, 0, "café") == [PROBLEM_CHARACTER]


def test_width_override_uses_the_text_tables_metrics():
    rules = GameRules()
    assert rules.calculate_string_width_override("AB", {}) is None   # nothing loaded yet
    rules.load_data_from_json_obj(synthetic_text_table(["Alpha."]))
    assert rules.calculate_string_width_override("AB", {}) == 6       # (2+1) for A, (3+0) for B
    assert rules.calculate_string_width_override("A B", {}) == 3 + 4 + 3


def test_input_that_is_not_a_text_table_gives_no_strings():
    rules = GameRules()
    blocks, _names = rules.load_data_from_json_obj(["not", "a", "table"])
    assert blocks == [[]]
    assert rules.save_data_to_json_obj(blocks, {}) == {}


def test_plugin_identifies_nothing_for_a_non_rom(tmp_path):
    path = tmp_path / "not_a_rom.z64"
    path.write_bytes(b"hello")
    assert GameRules().identify_source(str(path)) is None


def mpeg2_l3_frame(payload_fill=b"\x00"):
    """A mono 24 kbps, 22050 Hz MPEG-2 Layer III frame: 78 bytes."""
    head = bytes([0xFF, 0xF3, 0x30, 0xC0])
    return head + payload_fill * (78 - 4)


def test_voice_walk_counts_frames_and_skips_cues():
    cue = b"L:" + b"\x01\x02\x03\x04\x05\x06" + b"\x00"
    data = mpeg2_l3_frame() * 3 + cue + mpeg2_l3_frame() * 2 + b"TAG" + b"\x00" * 10
    info = voice.describe(data)
    assert info.frames == 5
    assert info.sample_rate == 22050 and info.bitrate_kbps == 24 and info.channels == 1
    assert info.cues == [b"L:" + b"\x01\x02\x03\x04\x05\x06"]
    assert info.seconds == pytest.approx(5 * 576 / 22050)
    assert info.trailer_bytes == len(b"TAG" + b"\x00" * 10)


def test_splice_cues_places_them_marks_the_frame_before_and_keeps_the_trailer():
    cue = b"L:" + bytes(range(1, 7)) + b"\x00"
    original = mpeg2_l3_frame() * 3 + cue + mpeg2_l3_frame() * 2 + b"TAG" + b"\x00" * 4
    encoded = mpeg2_l3_frame(b"\x07") * 4
    spliced = voice.splice_cues(original, encoded)
    info = voice.describe(spliced)
    assert info.frames == 4
    assert info.cues == [cue[:-1]]
    assert [flag for _, _, flag in voice.walk(spliced).frames] == [False, False, True, False]
    assert spliced.endswith(b"TAG" + b"\x00" * 4)


def test_splice_cues_refuses_an_encoding_that_already_has_copyright_bits():
    marked = bytearray(mpeg2_l3_frame())
    marked[3] |= 0x08
    with pytest.raises(ValueError):
        voice.splice_cues(mpeg2_l3_frame(), bytes(marked))
