"""Yakumo ``*.lang`` files: byte-exact round trip and one-value edits (synthetic fixtures only)."""
from plugins.mhp3rd.lang_file import LangDocument, read_lang, write_lang

FIXTURE = (
    "﻿# comment with an equals sign: a = b\n"
    "; semicolon comment\n"
    "language = pt-BR\r\n"
    "name = Português\r\n"
    "\r\n"
    "[16]                     # the shared block\r\n"
    "2:20 = Cancelar\r\n"
    "2:21=Sim\r\n"
    "2:22 =  two leading spaces\r\n"
    "2:23 = tab\\there and a \\\\ backslash\r\n"
    "2:24 = multi\\nline\r\n"
    "2:25 = trailing spaces   \r\n"
    "2:20 = duplicate key keeps both lines\r\n"
    "2:308-382 = range rule\r\n"
    "*:5 = wildcard rule\r\n"
    "41:7 = chat filter\r\n"
    "2:0 = entry zero\r\n"
    "not a key line\r\n"
    "[oops\r\n"
    "[4289]\n"
    "0:4 = dialogue\n"
    "41:0 = dialogue id 41 is editable\r"
)


def test_unchanged_file_round_trips_byte_for_byte():
    assert LangDocument.parse(FIXTURE).serialize() == FIXTURE


def test_file_without_final_newline_round_trips():
    text = "[main]\n2:1 = last line, no newline"
    assert LangDocument.parse(text).serialize() == text


def test_values_are_decoded_like_yakumo():
    entries = {(e.block, e.key): e for e in LangDocument.parse(FIXTURE).entries()}
    assert entries[(16, "2:21")].value == "Sim"
    assert entries[(16, "2:22")].value == " two leading spaces"
    assert entries[(16, "2:23")].value == "tab\there and a \\ backslash"
    assert entries[(16, "2:24")].value == "multi\nline"
    assert entries[(16, "2:25")].value == "trailing spaces   "
    assert entries[(4289, "0:4")].value == "dialogue"


def test_only_the_edited_line_changes():
    doc = LangDocument.parse(FIXTURE)
    entry = next(e for e in doc.entries() if e.key == "2:21")
    doc.set_value(entry, "Так")
    expected = FIXTURE.replace("2:21=Sim\r\n", "2:21=Так\r\n")
    assert doc.serialize() == expected
    reread = next(e for e in LangDocument.parse(doc.serialize()).entries() if e.key == "2:21")
    assert reread.value == "Так"


def test_edited_value_with_special_characters_reads_back_exactly():
    doc = LangDocument.parse(FIXTURE)
    entry = next(e for e in doc.entries() if e.key == "2:20")  # the first of the two duplicates
    value = " line one\nline\ttwo \\ end "
    doc.set_value(entry, value)
    reread = next(e for e in LangDocument.parse(doc.serialize()).entries() if e.key == "2:20")
    assert reread.value == value
    assert doc.serialize().count("\r\n") == FIXTURE.count("\r\n")  # CRLF lines keep their endings


def test_leading_space_in_an_edit_gets_a_separator():
    doc = LangDocument.parse("[16]\n2:1=x\n")
    doc.set_value(doc.entries()[0], " y")
    assert doc.serialize() == "[16]\n2:1=  y\n"
    assert LangDocument.parse(doc.serialize()).entries()[0].value == " y"


def test_protected_entries_are_not_editable():
    entries = {(e.block, e.key): e for e in LangDocument.parse(FIXTURE).entries()}
    assert entries[(16, "2:21")].editable
    assert not entries[(16, "41:7")].editable  # chat filter table
    assert not entries[(16, "2:0")].editable  # entry 0 of a table
    assert entries[(4289, "41:0")].editable  # dialogue ids are not tables
    assert not entries[(16, "2:308-382")].editable  # range rule
    assert not entries[(16, "*:5")].editable  # wildcard rule


def test_edit_refuses_an_entry_of_another_document():
    doc = LangDocument.parse(FIXTURE)
    other = LangDocument.parse(FIXTURE).entries()[0]
    try:
        doc.set_value(other, "x")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_file_io_keeps_crlf_and_replaces_atomically(tmp_path):
    path = tmp_path / "pt.lang"
    path.write_bytes(FIXTURE.encode("utf-8"))
    doc = read_lang(str(path))
    assert doc.serialize() == FIXTURE
    doc.set_value(next(e for e in doc.entries() if e.key == "2:20"), "Скасувати")
    write_lang(str(path), doc)
    assert path.read_bytes().decode("utf-8") == FIXTURE.replace("2:20 = Cancelar", "2:20 = Скасувати", 1)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["pt.lang"]
