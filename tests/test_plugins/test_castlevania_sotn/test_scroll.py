"""The prologue caption of Symphony of the Night: the script, the editor lines, the draw, the code patches, the
private letters and the width rule.

Synthetic bytes and a fake BIOS only; the workspace's ST0.BIN is tested in test_rules.py.
"""
import struct

import pytest

from core import texture_formats
from plugins.castlevania_sotn import codec, menu_text, scroll


def _script(*pieces) -> bytes:
    return b"".join(pieces)


def test_a_script_reads_its_lines_breaks_and_offsets():
    data = _script(b"\x00" * 4, b"AB", bytes([1, 5]), b"CD", bytes([2, 9]), b"E", bytes([0]), b"\xff")
    lines, length = scroll.read_script(data, 4, len(data))
    assert [(c.raw, c.brk, c.x) for c in lines] == [
        (b"AB", scroll.LINE_BREAK, scroll.FIRST_X),
        (b"CD", scroll.PAGE_BREAK, 5),
        (b"E", scroll.END, 9),
    ]
    assert length == len(data) - 4 - 1                    # the bytes up to and with the end byte


def test_a_script_builds_back_to_the_same_bytes():
    data = _script(b"AB", bytes([1, 5]), b"CD", bytes([2, 9]), b"E", bytes([0]))
    lines, _length = scroll.read_script(data, 0, len(data))
    rebuilt = scroll.build_script([c.raw for c in lines], [c.brk for c in lines], [c.x for c in lines])
    assert rebuilt == data


def test_a_missing_end_byte_is_an_error():
    with pytest.raises(scroll.ScrollError):
        scroll.read_script(b"AB\x01", 0, 3)


def test_the_editor_shows_a_page_break_as_a_tag_at_the_end():
    lines, _length = scroll.read_script(_script(b"Hi there", bytes([2, 9]), b"Bye", bytes([0])), 0, 99)
    assert scroll.to_editor(lines[0]) == "Hi there{PAGE}"
    assert scroll.to_editor(lines[1]) == "Bye"


def test_the_editor_text_writes_back_with_its_break_kind():
    raw, brk = scroll.from_editor("Hi there{PAGE}", last=False)
    assert (raw, brk) == (b"Hi there", scroll.PAGE_BREAK)
    raw, brk = scroll.from_editor("Bye", last=False)
    assert (raw, brk) == (b"Bye", scroll.LINE_BREAK)
    raw, brk = scroll.from_editor("end.", last=True)
    assert (raw, brk) == (b"end.", scroll.END)


def test_a_page_tag_must_end_its_line_and_the_last_line_cannot_end_a_page():
    with pytest.raises(scroll.ScrollError):
        scroll.from_editor("a{PAGE}b", last=False)
    with pytest.raises(scroll.ScrollError):
        scroll.from_editor("end.{PAGE}", last=True)


def test_braces_and_control_bytes_read_as_tags():
    lines, _length = scroll.read_script(_script(b"{x}\x7f", bytes([0])), 0, 99)
    assert scroll.to_editor(lines[0]) == "{7B}x{7D}{7F}"
    raw, _brk = scroll.from_editor("{7B}x{7D}{7F}", last=True)
    assert raw == b"{x}\x7f"


def test_cyrillic_goes_to_its_shift_jis_code_and_capital_i_stands_for_ukrainian_i():
    missing = set()
    raw, _brk = scroll.from_editor("Ай, і Ж", last=True, missing=missing)
    assert raw == "Ай, i Ж".encode("cp932")          # Cyrillic pairs, Latin i for і
    assert missing == set()


def test_the_private_letters_are_their_codes_and_read_back_as_letters():
    raw, _brk = scroll.from_editor("Їжак Єнот Ґанок ї є ґ", last=True)
    assert raw.startswith(b"\xf0\x40") and b"\xf0\x41" in raw and b"\xf0\x42" in raw
    assert b"\xf0\x43" in raw and b"\xf0\x44" in raw and b"\xf0\x45" in raw
    lines, _length = scroll.read_script(raw + b"\x00", 0, len(raw) + 1)
    assert scroll.to_editor(lines[0]) == "Їжак Єнот Ґанок ї є ґ"
    assert codec.SJ_PRIVATE["Ї"] == 0xF040 and codec.SJ_PRIVATE_CHAR[0xF045] == "ґ"


def test_a_letter_the_bios_font_lacks_is_a_question_mark_and_a_missing_entry():
    missing = set()
    raw, _brk = scroll.from_editor("ж€", last=True, missing=missing)
    assert raw == "ж".encode("cp932") + b"?"
    assert missing == {"€"}


def test_the_game_maps_a_byte_to_its_shift_jis_code():
    assert scroll.glyph_code(ord("A")) == 0x8260
    assert scroll.glyph_code(ord("a")) == 0x8281
    assert scroll.glyph_code(ord("0")) == 0x824F
    assert scroll.glyph_code(ord(",")) == 0x8143
    assert scroll.glyph_code(ord(".")) == 0x8144
    assert scroll.glyph_code(0x20) is None
    assert scroll.glyph_code(0x82, trail=0x40) == 0x8240


def test_a_glyph_that_would_start_in_the_column_gap_moves_past_it():
    # starts at panel 200 px: 200, 212 next; 224 is in the gap [224, 256) so the third glyph starts at 256
    assert [px for px, _code in scroll._cells(b"abc", 50)] == [200, 212, 256]


def test_the_width_is_12_px_a_letter_and_8_px_a_space():
    assert scroll.advance_px(b"abc") == 36
    assert scroll.advance_px(b"a b") == 32
    assert scroll.advance_px(b"\xf0\x40\xf0\x41") == 24          # two private letters, a pair each


def test_a_line_is_too_wide_past_the_panel_right_of_its_offset():
    assert not scroll.line_too_wide(b"x" * 42, 0)         # 504 px
    assert scroll.line_too_wide(b"x" * 43, 0)             # 516 px
    assert scroll.line_too_wide(b"x" * 40, 10)            # 480 px against 512 - 40 = 472
    assert not scroll.line_too_wide(b"x" * 39, 10)        # 468 px


def test_a_page_draws_its_ink_at_the_line_places_on_the_panel():
    code = 0x8268                                      # full-width capital I
    glyph = bytes([0x11] * 30)                         # every nibble set: a solid 12 x 16 block
    size = menu_text.BIOS_KROM_OFFSET + 0x200 * menu_text.GLYPH_BYTES
    bios = bytearray(size)
    start = menu_text.BIOS_KROM_OFFSET + menu_text.glyph_index(code) * menu_text.GLYPH_BYTES
    bios[start:start + menu_text.GLYPH_BYTES] = glyph
    panel = scroll.render_page(bytes(bios), [(10, bytes([ord("I")])), (10, bytes([ord("I")]))])
    assert panel.size == (scroll.PANEL_W, scroll.LINE_PITCH + scroll.GLYPH_ROWS)
    alpha = panel.getchannel("A")
    left = 10 * 4 + scroll.SPRITE_X                                       # the glyph's left edge
    assert alpha.crop((left, 0, left + 12, scroll.GLYPH_ROWS)).getextrema()[1] == 255          # line 1 has ink
    assert alpha.crop((left, scroll.LINE_PITCH, left + 12, scroll.LINE_PITCH + scroll.GLYPH_ROWS)).getextrema()[1] == 255
    assert alpha.crop((0, 0, left, scroll.GLYPH_ROWS)).getextrema()[1] == 0    # nothing left of the line


def test_the_placeholder_letters_are_16_rows_of_12_pixels_and_the_table_holds_them():
    for char in scroll.PLACEHOLDER_LETTERS:
        rows = scroll.placeholder_rows(char)
        assert len(rows) == 16 and all(len(row) == 12 for row in rows)
        assert any("#" in row for row in rows)
    table = scroll.glyph_table()
    assert len(table) == scroll.GLYPH_BYTES == 192
    for index, char in enumerate(scroll.PLACEHOLDER_LETTERS):
        ink = scroll.table_rows(table, index)
        assert ["".join("#" if v else "." for v in row) for row in ink] == scroll.placeholder_rows(char)


def test_the_letter_table_reads_and_writes_through_the_texture_format():
    params = {"offset": scroll.GLYPH_AT, "count": 6, "width": 12, "height": 16}
    data = bytearray(scroll.GLYPH_AT + scroll.GLYPH_BYTES + 16)
    data[scroll.GLYPH_AT:scroll.GLYPH_AT + scroll.GLYPH_BYTES] = scroll.glyph_table()
    sheet = texture_formats.read("glyph_bits", bytes(data), params)[0].image
    assert sheet.size == (72, 16)
    again = texture_formats.write("glyph_bits", bytes(data), {0: sheet}, params)
    assert again == bytes(data)                                  # an unedited table writes back the same bytes


def test_the_draw_code_script_pointer_is_read_and_written_back():
    data = bytearray(scroll.SCRIPT_LOAD + 8)
    struct.pack_into("<II", data, scroll.SCRIPT_LOAD, scroll.LUI_A0 | 0x8018, scroll.ADDIU_A0 | 0x2C58)
    assert scroll.script_start(bytes(data)) == 0x2C58
    out = bytearray(data)
    scroll.point_at(out, bytes(data), scroll.BASE + 0x10C30)
    assert scroll.script_start(bytes(out)) == 0x10C30
    assert struct.unpack_from("<II", out, scroll.SCRIPT_LOAD) == (scroll.LUI_A0 | 0x8019, scroll.ADDIU_A0 | 0x0C30)


def test_a_pointer_with_the_sign_bit_in_its_low_half_carries_into_the_high_half():
    data = bytearray(scroll.SCRIPT_LOAD + 8)
    struct.pack_into("<II", data, scroll.SCRIPT_LOAD, scroll.LUI_A0 | 0x8018, scroll.ADDIU_A0 | 0x0000)
    out = bytearray(data)
    scroll.point_at(out, bytes(data), scroll.BASE + 0x18000)     # low half 0x8000 is negative: hi gets +1
    assert scroll.script_start(bytes(out)) == 0x18000


def test_the_reader_fits_its_window_and_its_jump_is_the_one_that_reaches_it():
    assert scroll.CAVE_SIZE <= 256
    assert scroll.CAVE[:4] == bytes.fromhex("7fffa224")                       # addiu $v0, $a1, -0x81
    assert scroll.CAVE_JUMP_WORD == 0x08066ACC                                # j 0x8019AB30
    assert scroll.CAVE_AT + scroll.CAVE_SIZE <= 109616                        # inside the file's spare range


def test_the_lead_byte_reader_is_installed_at_the_glyph_wrapper():
    data = bytearray(max(scroll.GLYPH_WRAPPER + 4, scroll.CAVE_AT + scroll.CAVE_SIZE))
    struct.pack_into("<I", data, scroll.GLYPH_WRAPPER, scroll.GLYPH_WRAPPER_WORD)
    out = bytearray(data)
    scroll.install_cave(out, bytes(data))
    assert bytes(out[scroll.CAVE_AT:scroll.CAVE_AT + scroll.CAVE_SIZE]) == scroll.CAVE
    assert struct.unpack_from("<I", out, scroll.GLYPH_WRAPPER)[0] == scroll.CAVE_JUMP_WORD


def test_the_lead_byte_reader_is_refused_when_the_wrapper_differs():
    data = bytearray(max(scroll.GLYPH_WRAPPER + 4, scroll.CAVE_AT + scroll.CAVE_SIZE))
    with pytest.raises(scroll.ScrollError):
        scroll.install_cave(bytearray(data), bytes(data))


def test_a_caption_line_gets_only_the_width_problem_and_other_lines_keep_the_generic_checks():
    from types import SimpleNamespace

    from plugins.castlevania_sotn.problem_analyzer import ProblemAnalyzer

    class Rules:
        def caption_too_wide(self, block, string, text):
            return None if block != 3 else text == "too wide"

    analyzer = ProblemAnalyzer.__new__(ProblemAnalyzer)
    analyzer.game_rules = Rules()
    analyzer.problem_ids = SimpleNamespace(PROBLEM_CAPTION_WIDTH="SOTN_CAPTION_WIDTH")
    analyzer._current_scan_block_idx, analyzer._current_scan_string_idx = 3, 0
    assert analyzer.analyze_data_string("too wide", {}, 0) == [{"SOTN_CAPTION_WIDTH"}]
    assert analyzer.analyze_data_string("fits", {}, 0) == [set()]
