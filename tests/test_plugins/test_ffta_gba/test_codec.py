"""Final Fantasy Tactics Advance (GBA) text codes: every control reads and writes back, Ukrainian letters have codes,
a character without one is refused by name, single-byte names and the LZSS decoder."""
import pytest

from plugins.ffta_gba import codec


def db(*parts) -> bytes:
    return b"".join(bytes.fromhex(p) for p in parts)


def test_two_byte_text_with_controls_round_trips():
    raw = db("80b0 80ca 4073 80e4", "406e", "4072 03", "403e 02", "4025 21", "4066 0102", "4067 00", "4077", "4070 4063")
    text = codec.decode_db(raw)
    assert text == "Aa .\n[crn:03][sp:02][var:21][c66:0102][c67:00][c77][next][clear]"
    assert codec.encode_db(text) == raw


def test_a_cleared_box_inside_a_text_starts_a_new_editor_line():
    raw = db("80b0 4070 4063", "80b1 4063 406e", "80b2 4063")
    text = codec.decode_db(raw)
    assert text == "A[next][clear]\nB[clear]\n\nC[clear]"
    assert codec.encode_db(text) == raw


def test_choice_answers_end_with_sep():
    raw = db("80b0 4053 11", "80b1 00", "80b2 00", "4063")
    text = codec.decode_db(raw)
    assert text == "A[choice:11]B[sep]C[sep][clear]"
    assert codec.encode_db(text) == raw


def test_bytes_that_are_not_text_are_rejected():
    with pytest.raises(ValueError):
        codec.decode_db(db("80b0 00 80b1"))            # a 00 outside a choice
    with pytest.raises(ValueError):
        codec.decode_db(db("4022"))                    # a control the game does not know


def test_ukrainian_letters_use_kana_codes_and_unknown_characters_are_named():
    assert len(codec.UA_CODES) == 66 and max(codec.UA_CODES.values()) < 0x80A0
    assert codec.decode_db(codec.encode_db("Їжак ґ")) == "Їжак ґ"
    with pytest.raises(codec.EncodeError, match="'Ы'"):
        codec.encode_db("Ы")
    assert codec.unknown_chars("Привіт, Ы!") == ["Ы"]


def test_codes_without_a_letter_keep_their_number():
    assert codec.decode_db(db("8922")) == "[x8922]"
    assert codec.encode_db("[x8922]") == db("8922")


def test_single_byte_names():
    raw = b"\x01" + bytes([0xBD, 0xD3]) + b"\0"          # "Mi": low byte of 80BC / 80D2, plus one
    assert codec.decode_plain(raw) == "Mi"
    assert codec.encode_plain("Mi", single_byte=True) == raw
    assert codec.encode_plain("Mi\n", single_byte=True) == codec.encode_db("Mi\n") + b"\0"   # a control: two-byte
    assert codec.plain_length(raw + b"zz", 0) == len(raw)


def test_lzss_decoder_reads_every_form():
    stream = bytes.fromhex("00000010" "42414243" "8002" "22" "0200" "0103")
    # literals "ABC", copy 3 from 3 back, 4 zeros, 3 zeros, 6 x FF: 3 + 3 + 4 + 3 + 6 = 19 > 16, cut to 16
    data, used = codec.lzss_decode(stream, 0)
    assert data == b"ABCABC" + bytes(7) + b"\xff" * 3
    assert used == len(stream)
    # literals "ABCD", copy 4 from 4 back (14-bit form), copy 5 from 4 back (long form)
    assert codec.lzss_decode(bytes.fromhex("0000000d" "4341424344" "100003" "00000003"), 0)[0] == b"ABCDABCDABCDA"


def test_line_width_counts_pixel_spaces():
    font_map = {"A": {"width": 7}, " ": {"width": 4}}
    assert codec.line_width("AA[sp:03]\nA", font_map, 8) == 17
