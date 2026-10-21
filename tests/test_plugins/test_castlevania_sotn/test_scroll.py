"""The prologue caption of Symphony of the Night: the script, the editor lines, the draw and the code patches.

Synthetic bytes and a fake BIOS only; the workspace's ST0.BIN is tested in test_rules.py.
"""
import struct

import pytest

from plugins.castlevania_sotn import menu_text, scroll


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
    raw, _brk = scroll.from_editor("Ай, і Ї", last=True, missing=missing)
    assert raw == "Ай, i ?".encode("cp932")          # Cyrillic pairs, Latin i for і, '?' for Ї
    assert missing == {"Ї"}


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
    glyphs = scroll._cells(b"abc", 50, lambda code: None)
    assert [px for px, _glyph in glyphs] == [200, 212, 256]


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


def test_the_lead_byte_reader_is_installed_at_the_glyph_wrapper():
    cave_at = 109360
    data = bytearray(max(scroll.GLYPH_WRAPPER + 4, cave_at + scroll.CAVE_SIZE))
    struct.pack_into("<I", data, scroll.GLYPH_WRAPPER, scroll.GLYPH_WRAPPER_WORD)
    out = bytearray(data)
    scroll.install_cave(out, bytes(data), cave_at)
    assert bytes(out[cave_at:cave_at + scroll.CAVE_SIZE]) == scroll.CAVE
    assert struct.unpack_from("<I", out, scroll.GLYPH_WRAPPER)[0] == 0x08066ACC   # j 0x8019AB30
    assert scroll.CAVE[:4] == bytes.fromhex("7fffa224")                          # addiu $v0, $a1, -0x81


def test_the_lead_byte_reader_is_refused_when_the_wrapper_differs():
    data = bytearray(max(scroll.GLYPH_WRAPPER + 4, 109360 + scroll.CAVE_SIZE))
    with pytest.raises(scroll.ScrollError):
        scroll.install_cave(bytearray(data), bytes(data), 109360)
