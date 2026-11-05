"""Lunar SSS JP codec: raw glyph bytes to characters (synthetic bytes, no game data)."""
from plugins.lunar_sssc import jp_codec


def test_katakana_and_space_from_the_raw_table():
    assert jp_codec.decode_message(bytes([0x62, 0x74, 0x10, 0xFF]), 0, 4) == "アス　{end}"


def test_kanji_from_the_shift_jis_code():
    kanji = bytes([0x88, 0xEA]).decode("cp932")
    assert jp_codec.decode_message(bytes([0x98, 0x62, 0xFF]), 0, 3) == kanji + "ア{end}"


def test_unknown_control_keeps_raw_tag_and_end_marker_is_kept():
    assert jp_codec.decode_message(bytes([0x01, 0x62, 0xFF]), 0, 3) == "{raw:01}ア{end}"
