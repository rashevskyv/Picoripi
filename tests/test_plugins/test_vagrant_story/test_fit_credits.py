"""Vagrant Story fit checks (balloon lines, bytes of a place) and the staff-roll letter route."""
import romhacking_root
import pytest

from plugins.vagrant_story import codec
from plugins.vagrant_story import doc as docs
from plugins.vagrant_story.config import PROBLEM_BYTES, PROBLEM_LINES
from plugins.vagrant_story.rules import page_overflow

ENDING = romhacking_root.under('Vagrant Story') / "source" / "ENDING" / "ENDING.PRG"


def test_page_overflow_counts_lines_from_each_page_start():
    assert page_overflow("a\nb\nc", 3) == []
    assert page_overflow("a\nb\nc\nd", 3) == [3]
    assert page_overflow("a\nb\nc\n{page}d\ne", 3) == []              # {page} starts a new page
    assert page_overflow("a\nb\n{wait}c\nd", 3) == [3]                # {wait} stays in the box


def test_dialogue_lines_beyond_the_balloon_are_a_problem(project):
    # string 0 has a 13 x 3 balloon, string 1 a 14 x 4 balloon (see the fixture)
    assert project.get_text_fit_problems_for_string(0, 0, "one\ntwo\nthree") == []
    assert project.get_text_fit_problems_for_string(0, 0, "one\ntwo\nthree\nfour") == [PROBLEM_LINES]
    assert project.get_text_fit_problems_for_string(0, 1, "a\nb\nc\nd") == []
    assert project.overflow_lines(0, 1, "a\nb\nc\nd\ne") == [4]
    assert project.get_text_fit_problems_for_string(0, 1, "a\nb\nc\nd\n{page}e\nf") == []


def test_the_editor_analyzer_reports_both_fit_problems(project):
    from handlers.analyzer_context import analyzer_string_context

    analyzer = project.problem_analyzer
    with analyzer_string_context(analyzer, 0, 0):             # the balloon of string 0: 3 lines
        lines = analyzer.analyze_data_string("a\nb\nc\nd", {}, 10000, None)
    assert [PROBLEM_LINES in found for found in lines] == [False, False, False, True]
    with analyzer_string_context(analyzer, 2, 0):             # an item name: 23 bytes
        found = analyzer.analyze_data_string("A" * 24, {}, 10000, None)
    assert any(PROBLEM_BYTES in line for line in found)


def test_in_place_names_have_a_byte_budget(project):
    # item names: a 24-byte place, 23 bytes of text plus the end byte (fixture item 0 is "Battle Knife")
    assert project.bytes_over(2, 0, "Battle Knife") is False
    assert project.get_text_fit_problems_for_string(2, 0, "Battle Knife") == []
    assert project.get_text_fit_problems_for_string(2, 0, "A" * 24) == [PROBLEM_BYTES]
    assert project.get_text_fit_problems_for_string(2, 0, "A" * 23) == []


def test_tables_have_no_byte_budget_here(project):
    # dialogue lines live in a table: their size is not one place
    assert project.bytes_over(0, 0, "x" * 500) is False


def test_staff_roll_letters_take_bytes_the_credits_never_draw():
    values = list(codec.CREDITS_LETTERS.values())
    assert len(values) == len(set(values)) == 46
    assert all(0x20 <= code <= 0x8F for code in values)
    assert codec.credits_encode("Б") == b"\x80"
    assert codec.credits_encode("Ї") == bytes([codec.CREDITS_LETTERS["Ї"]])
    assert codec.credits_decode(b"\x80A") == "БA"
    assert codec.credits_decode(b"\x01") == "{x01}"                  # a control code is shown as its byte
    # the byte of a letter cannot be typed as its ASCII character
    with pytest.raises(ValueError):
        codec.credits_encode("!")
    assert codec.credits_encode("A") == b"A"
    assert codec.credits_encode("А", {"А": "A"}) == b"A"             # Cyrillic look-alike keeps the Latin cell


def test_staff_roll_letter_map_is_exactly_the_staff_roll_cells_not_drawn_by_english():
    if not ENDING.is_file():
        pytest.skip("the Vagrant Story workspace is not unpacked here")
    lines = docs.parse(ENDING.read_bytes(), "ENDING/ENDING.PRG").groups[0].lines
    used = {byte for line in lines for byte in line.raw}
    assert not used & set(codec.CREDITS_LETTERS.values())
    assert len(lines) == 300
