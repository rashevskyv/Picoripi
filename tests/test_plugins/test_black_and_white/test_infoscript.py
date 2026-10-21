"""Black & White text table: the ADD_TEXT reader and the splice-back writer, on synthetic lines only."""
import pytest

from plugins.black_and_white import infoscript


def _table(lines, bom=True):
    text = "\r\n".join(lines) + "\r\n"
    return (("﻿" if bom else "") + text).encode("utf-16-le")


def _call(flag, narrator, key, text):
    return f'ADD_TEXT( {flag}, {narrator}, "{key}", "{text}")'


def test_reads_fields_and_texts_in_file_order():
    raw = _table([_call(1, "NARRATOR_A", "SYN_01", "First line"), _call(0, "NARRATOR_B", "SYN_02", "Second")])
    records = infoscript.records(raw)
    assert [r.key for r in records] == ["SYN_01", "SYN_02"]
    assert [r.flag for r in records] == ["1", "0"]
    assert [r.narrator for r in records] == ["NARRATOR_A", "NARRATOR_B"]
    assert infoscript.texts(raw) == ["First line", "Second"]


def test_bare_line_feed_inside_a_text_and_escaped_breaks_are_kept_as_they_are():
    raw = _table([_call(1, "NARRATOR_A", "SYN_03", "one\nTwo\\\\nThree")])
    assert infoscript.texts(raw) == ["one\nTwo\\\\nThree"]


def test_reads_a_file_without_byte_order_mark():
    raw = _table([_call(1, "NARRATOR_A", "SYN_04", "No mark")], bom=False)
    assert infoscript.texts(raw) == ["No mark"]


def test_replace_with_the_same_texts_gives_the_same_bytes():
    raw = _table([_call(1, "NARRATOR_A", "SYN_05", "Same"), _call(0, "NARRATOR_B", "SYN_06", "Also same")])
    assert infoscript.replace_texts(raw, infoscript.texts(raw)) == raw


def test_replace_changes_only_the_text_literals():
    raw = _table([_call(1, "NARRATOR_A", "SYN_07", "Old"), _call(0, "NARRATOR_B", "SYN_08", "Keep")])
    out = infoscript.replace_texts(raw, ["New", "Keep"])
    assert infoscript.records(out) == [
        infoscript.TextRecord("1", "NARRATOR_A", "SYN_07", "New"),
        infoscript.TextRecord("0", "NARRATOR_B", "SYN_08", "Keep"),
    ]
    assert out.replace("New".encode("utf-16-le"), "Old".encode("utf-16-le")) == raw
    assert out[:2] == b"\xff\xfe"


def test_ukrainian_letters_round_trip_through_utf16():
    raw = _table([_call(1, "NARRATOR_A", "SYN_09", "Hello")])
    out = infoscript.replace_texts(raw, ["Привіт, світ — їжак…"])
    assert infoscript.texts(out) == ["Привіт, світ — їжак…"]


def test_replace_refuses_a_count_change():
    raw = _table([_call(1, "NARRATOR_A", "SYN_10", "Only")])
    with pytest.raises(infoscript.InfoScriptError):
        infoscript.replace_texts(raw, ["One", "Two"])


def test_replace_refuses_a_double_quote_in_a_text():
    raw = _table([_call(1, "NARRATOR_A", "SYN_11", "Only")])
    with pytest.raises(infoscript.InfoScriptError):
        infoscript.replace_texts(raw, ['say "hi"'])


def test_looks_like_table_checks_the_start_of_the_bytes():
    assert infoscript.looks_like_table(_table([_call(1, "NARRATOR_A", "SYN_12", "x")]))
    assert not infoscript.looks_like_table(_table(["plain text, no calls"]))
    assert not infoscript.looks_like_table(b"\x00\x01\x02")
