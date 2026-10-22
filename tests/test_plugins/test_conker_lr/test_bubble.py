"""Conker: Live & Reloaded bubble wrap and the length problems: 20 characters a line, 4 lines a bubble, tags count as one."""
from plugins.conker_lr import bubble


def test_a_line_wraps_at_20_characters_at_a_space():
    assert bubble.bubble_lines("a" * 20) == 1
    assert bubble.bubble_lines("aaaa bbbb cccc dddd eeee ffff") == 2  # breaks at the space before "eeee"


def test_a_word_longer_than_the_width_stays_whole():
    assert bubble.bubble_lines("a" * 45) == 1


def test_a_pmarker_is_a_break_point_and_a_tag_counts_as_one_unit():
    assert bubble.bubble_lines("a" * 10 + "{PMARKER}" + "b" * 22) == 2
    assert bubble.units("{PMARKER}") == 1
    assert bubble.units("ab{X}") == 3


def test_paragraphs_are_split_on_the_paragraph_tag():
    assert bubble.paragraphs("one{PARAGRAPH}two") == ["one", "two"]


def test_more_than_four_lines_is_flagged_and_four_is_not():
    assert bubble.bubble_lines("word " * 16) == 4
    assert bubble.bubble_lines("word " * 20) == 5
    assert "BUBBLE_LINES" in bubble.problems("word " * 20)
    assert "BUBBLE_LINES" not in bubble.problems("word " * 16)


def test_a_long_line_is_flagged_by_its_length():
    assert bubble.problems("x" * 100) == []
    assert "LINE_LIMIT" in bubble.problems("x" * 512)
    assert "STRING_LIMIT" not in bubble.problems("x" * 512)
    assert bubble.problems("x" * 2048) == ["STRING_LIMIT", "LINE_LIMIT"]
