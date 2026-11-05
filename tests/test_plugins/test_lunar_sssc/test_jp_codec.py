"""Lunar SSS JP codec: raw glyph bytes to characters (synthetic bytes, no game data)."""
from plugins.lunar_sssc import jp_codec


def test_katakana_and_space_from_the_raw_table():
    assert jp_codec.decode_message(bytes([0x62, 0x74, 0x10, 0xFF]), 0, 4) == "アス　{end}"


def test_kanji_from_the_shift_jis_code():
    kanji = bytes([0x88, 0xEA]).decode("cp932")
    assert jp_codec.decode_message(bytes([0x98, 0x62, 0xFF]), 0, 3) == kanji + "ア{end}"


def test_unknown_control_keeps_raw_tag_and_end_marker_is_kept():
    assert jp_codec.decode_message(bytes([0x01, 0x62, 0xFF]), 0, 3) == "{raw:01}ア{end}"


def test_two_byte_glyph_is_the_shift_jis_code_lead_minus_0x55():
    assert jp_codec.decode_message(bytes([0xE9, 0x92, 0xDD, 0xAB, 0xFF]), 0, 5) == "白悪{end}"


def test_two_byte_glyph_in_the_symbol_range_uses_the_symbol_table():
    assert jp_codec.decode_message(bytes([0xEE, 0x94, 0xFF]), 0, 3) == "ア{end}"


def test_portrait_control_stays_a_tag():
    assert jp_codec.decode_message(bytes([0xFA, 0x00, 0x62, 0xFF]), 0, 4) == "{FA:00}ア{end}"
