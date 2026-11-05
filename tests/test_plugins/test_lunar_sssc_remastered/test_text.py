"""Lunar SSS Remastered text: pairing, the English slots, the translation file (synthetic scripts, no game data)."""
import struct

import pytest

from plugins.lunar_sssc import script
from plugins.lunar_sssc_remastered import text


def _script(*code: bytes) -> bytes:
    labels = struct.pack("<1024H", *([script.HEADER // 2] + [0] * 1023))
    return labels + b"".join(code)


def _message(*raw: int) -> bytes:
    body = struct.pack("<H", script.MESSAGE) + bytes(raw) + b"\xff"
    return body + (b"\x00" if len(body) % 2 else b"")


def _other() -> bytes:
    return struct.pack("<HH", 4, 0)


_END = struct.pack("<H", 5) + b"\x00\x00"


def test_translation_file_round_trips_utf8_text():
    lines = ["Привіт, Луно!", "", "plain"]
    assert text.read_translation(text.translation_bytes(lines)) == lines


def test_a_text_file_is_not_a_translation_file():
    assert text.read_translation(_script(_message(0x01), _END)) is None


def test_pairs_skip_a_message_the_other_file_does_not_have():
    english = _script(_message(0x01), _other(), _message(0x02), _END)
    japanese = _script(_message(0x01), _message(0x09), _other(), _message(0x02), _END)
    assert text.string_pairs(english, japanese) == [(0, 0), (1, 2)]


def test_reference_has_an_empty_line_where_no_english_pairs():
    english = _script(_message(0x01), _other(), _message(0x02), _END)
    japanese = _script(_message(0x01), _message(0x09), _other(), _message(0x02), _END)
    reference = text.reference_for_japanese(english, japanese)
    assert len(reference) == 3
    assert reference[1] == ""
    assert reference[0] and reference[2]


def test_translated_line_goes_to_its_english_slot_and_the_rest_stay():
    english = _script(_message(0x01), _other(), _message(0x02), _END)
    japanese = _script(_message(0x01), _message(0x09), _other(), _message(0x02), _END)
    before = text.strings_of(english, japanese=False)
    out, missing = text.english_with_translation(english, japanese, ["Hi there", "", "Second"])
    after = text.strings_of(out, japanese=False)
    assert after[0] == "Hi there"
    assert after[1] == "Second"      # the Japanese string 2 pairs with English string 1
    assert before[1] != "Second"
    assert missing == set()


def test_a_line_equal_to_the_japanese_source_is_not_written():
    english = _script(_message(0x01), _other(), _message(0x02), _END)
    japanese = _script(_message(0x01), _message(0x09), _other(), _message(0x02), _END)
    source = text.strings_of(japanese, japanese=True)
    out, _missing = text.english_with_translation(english, japanese, list(source))
    assert out == english


@pytest.mark.parametrize("line", ["Hi"])
def test_the_file_reads_back_with_the_new_text(line):
    english = _script(_message(0x01), _END)
    japanese = _script(_message(0x01), _END)
    out, _ = text.english_with_translation(english, japanese, [line])
    assert text.strings_of(out, japanese=False)[0] == line
