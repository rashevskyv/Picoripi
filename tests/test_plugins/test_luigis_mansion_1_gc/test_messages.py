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


def test_record_count_change_is_refused():
    with pytest.raises(ValueError, match="holds 2 records"):
        Table(b"one\r\ntwo\r\n").build(["one"])


def test_crlf_inside_a_record_is_refused():
    with pytest.raises(ValueError, match="record break"):
        Table(b"one\r\ntwo\r\n").build(["one", "a\r\nb"])


def test_character_without_a_shift_jis_code_is_refused_with_its_record():
    with pytest.raises(ValueError, match="record 2"):
        Table(b"one\r\ntwo\r\n").build(["one", "\u0457"])


def test_bytes_that_are_not_shift_jis_are_not_a_table():
    with pytest.raises(ValueError):
        Table(b"\x81\x20\x80\xfd\xff\r\n")
