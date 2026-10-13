r"""Silent Hill 3 (PC) plugin: the English message codec, the message table, the plugin contract.

The real-data test reads ``data\msg.arc`` of the installed game and skips when it is missing.
"""
import romhacking_root
import struct

import pytest

from core.containers import sh3_arc
from plugins.silent_hill_3_pc import codec, doc
from plugins.testing import check_loads, check_round_trip, check_validator

PLUGIN = "silent_hill_3_pc"
MSG_ARC = romhacking_root.under('Silent Hill\\Silent Hill 3\\PC\\ISO\\data\\msg.arc')
needs_game = pytest.mark.skipif(not MSG_ARC.is_file(), reason="Silent Hill 3 data not installed here")


def table(strings):
    """A message file with the given raw strings (each padded to whole units)."""
    padded = [s + b"\0" * (len(s) % 2) for s in strings]
    count = len(padded)
    offsets = [count]
    for part in padded:
        offsets.append(offsets[-1] + len(part) // 2)
    return struct.pack("<%dH" % count, *offsets[:count]) + b"".join(padded)


def test_codec_reads_glyphs_as_ascii_minus_0x20():
    # "It's locked." with the game's glyph bytes, then "?"
    raw = bytes([0x29, 0x54, 0x07, 0x53, 0x00, 0x4C, 0x4F, 0x43, 0x4B, 0x45, 0x44, 0x0E, 0x1F])
    assert codec.decode(raw) == "It's locked.?"


def test_codec_shows_control_and_tag_bytes_as_tags():
    assert codec.decode(bytes([0x80, 0xFF, 0x90, 0x3C, 0x5B, 0x5D, 0x5F])) == "{80}{FF}{90}{3C}{5B}{5D}{5F}"


def test_codec_encodes_capitals_and_small_letters_back():
    assert codec.encode("UA TEST.{FF}") == bytes([0x35, 0x21, 0x00, 0x34, 0x25, 0x33, 0x34, 0x0E, 0xFF])
    assert codec.encode("ua") == bytes([0x55, 0x41])


@pytest.mark.parametrize("text", ["Ї", "{", "}", "\\"])
def test_codec_rejects_a_character_without_a_glyph(text):
    with pytest.raises(ValueError):
        codec.encode(text)


def test_codec_puts_a_marker_on_an_even_offset():
    # "A", a space, then the message-end marker 0x90: the space would sit at offset 1 (odd), so one pad
    assert codec.encode("A {90}") == bytes([0x21, 0x00, 0x00, 0x90])
    # "AB", a space, then 0x90: the space sits at offset 2 (even), so no pad
    assert codec.encode("AB {90}") == bytes([0x21, 0x22, 0x00, 0x90])



def test_doc_reads_strings_and_rebuilds_unchanged_bytes():
    source = table([b"\x80LOCKED\x0e\xff\xff", b"\x80IT\x1f\xff\xff"])
    assert doc.texts(source) == ["{80}locked.{FF}{FF}", "{80}it?{FF}{FF}"]
    out, problems = doc.build(source, doc.texts(source))
    assert problems == []
    assert out == source


def test_doc_edit_changes_one_string_only():
    source = table([b"\x80LOCKED\x0e\xff\xff", b"\x80IT\x1f\xff\xff"])
    texts = doc.texts(source)
    texts[1] = "{80}UA TEST.{FF}{FF}"
    out, problems = doc.build(source, texts)
    assert problems == []
    # an odd-length string is padded with one zero byte, which reads back as a space
    assert doc.texts(out) == ["{80}locked.{FF}{FF}", "{80}UA TEST.{FF}{FF} "]


def test_doc_keeps_a_string_that_cannot_be_encoded():
    source = table([b"\x80IT\x1f\xff\xff"])
    out, problems = doc.build(source, ["Ї"])
    assert out == source
    assert len(problems) == 1


def test_plugin_contract():
    check_loads(PLUGIN)
    check_round_trip(PLUGIN, table([b"\x80IT\x1f\xff\xff", b"\x80LOCKED\x0e\xff\xff"]))


def test_plugin_validator_reports_no_error():
    check_validator(PLUGIN)


@needs_game
def test_every_english_message_file_round_trips_byte_for_byte():
    catalog = sh3_arc.parse_catalog((MSG_ARC.parent / "arc.arc").read_bytes())
    names = dict(catalog["msg"])
    data = MSG_ARC.read_bytes()
    _, entries = sh3_arc.parse(data)
    messages = [i for i, name in names.items() if name.endswith("_msg.mes")]
    assert len(messages) == 368
    for index in messages:
        raw = sh3_arc.entry_bytes(data, entries[index])
        out, problems = doc.build(raw, doc.texts(raw))
        assert problems == [], names[index]
        assert out == raw, names[index]


def test_codec_shows_a_page_break_as_a_tag_and_a_digit_zero_as_a_digit():
    assert codec.decode(bytes([0x00, 0x10, 0x00, 0x80])) == " {10} {80}"
    # the 0x10 here follows a space at an odd offset, so it is the digit zero
    assert codec.decode(bytes([0x01, 0x00, 0x10, 0x00, 0x80])) == "! 0 {80}"


def test_codec_writes_a_typed_zero_as_the_digit_byte_without_a_pad():
    assert codec.encode("A0") == bytes([0x21, 0x10])
    assert codec.encode("A 0") == bytes([0x21, 0x00, 0x10])


def test_codec_page_break_tag_round_trips_as_a_marker():
    text = " {10} {80}"
    assert codec.decode(codec.encode(text)) == text
