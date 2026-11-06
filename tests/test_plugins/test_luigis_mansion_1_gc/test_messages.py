"""Message table: records end with CRLF, an LF inside a record is a line break, Shift-JIS on disc."""
import pytest

from plugins.luigis_mansion_1_gc.messages import Table


def test_unchanged_table_builds_the_original_bytes():
    raw = b"alpha\r\nbeta\r\ngamma line\nwrapped here.\r\n\r\n"
    table = Table(raw)
    assert table.texts() == ["alpha", "beta", "gamma line\nwrapped here.", ""]
    assert table.build(table.texts()) == raw


def test_a_file_without_the_final_record_end_keeps_that_shape():
    raw = b"one\r\ntwo"
    table = Table(raw)
    assert table.texts() == ["one", "two"]
    assert table.build(["one", "2"]) == b"one\r\n2"


def test_edited_record_keeps_the_record_count_and_the_tail():
    raw = b"one\r\ntwo\r\n"
    assert Table(raw).build(["one", "TWO"]) == b"one\r\nTWO\r\n"


def test_an_editor_form_tag_is_written_in_the_game_form():
    assert Table(b"one\r\ntwo\r\n").build(["one", "{COLOR(3)}Luigi{COLOR(0)}"]) == b"one\r\n<COLOR>(3)Luigi<COLOR>(0)\r\n"


def test_record_count_change_is_refused():
    with pytest.raises(ValueError, match="holds 2 records"):
        Table(b"one\r\ntwo\r\n").build(["one"])


def test_crlf_inside_a_record_is_refused():
    with pytest.raises(ValueError, match="record break"):
        Table(b"one\r\ntwo\r\n").build(["one", "a\r\nb"])


def test_latin_accent_without_a_glyph_is_written_as_its_base_letter_with_a_warning():
    # The GC dialogue font has no glyph for a Latin accent: the letter is written without it, and the line stays.
    with pytest.warns(UserWarning, match="record 2: the character '\u00e8' has no Shift-JIS code; written as 'e'"):
        raw = Table(b"one\r\ntwo\r\n").build(["one", "Zen tr\u00e8s bien"])
    assert Table(raw).texts() == ["one", "Zen tres bien"]


def test_character_without_a_base_letter_is_written_as_question_mark_with_a_warning():
    with pytest.warns(UserWarning, match="record 2"):
        raw = Table(b"one\r\ntwo\r\n").build(["one", "\u0452"])   # Serbian dje: no cp932 code, no base letter
    assert Table(raw).texts() == ["one", "?"]


def test_every_accent_of_french_and_german_words_encodes_without_error():
    with pytest.warns(UserWarning):
        raw = Table(b"one\r\n").build(["\u00e0\u00e8\u00e9\u00ea\u00e7\u00f9\u00fc\u00f6\u00e4\u00df\u00f1"])
    assert Table(raw).texts() == ["aeeecuuoa?n"]   # the sharp s has no base letter: "?"


def test_bytes_that_are_not_shift_jis_are_not_a_table():
    with pytest.raises(ValueError):
        Table(b"\x81\x20\x80\xfd\xff\r\n")


def test_event_script_is_not_a_message_table():
    # text/eventNN.txt: Shift-JIS-decodable, but its command tags are not message tags
    with pytest.raises(ValueError, match="event script"):
        Table(b"<CANCEL>\r\n<CASE>\"case1\"\r\n<END>\r\n")


def test_color_tags_keep_a_message_a_message():
    assert Table(b"<COLOR>(3)Ghost<COLOR>(0)\r\n").texts() == ["<COLOR>(3)Ghost<COLOR>(0)"]


def test_event_script_loads_as_no_strings():
    from plugins.luigis_mansion_1_gc.rules import GameRules
    assert GameRules().load_data_from_json_obj(b"<END>\r\n<WAIT>\r\n") == ([[]], {})
