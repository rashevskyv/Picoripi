"""Lunar: the portrait slots ({FA:xx} left, {FB:xx} right) persist across pages; each window has its own room."""
from PIL import Image

import romhacking_root  # noqa: F401  (path setup for the repository's packages)

from plugins.lunar_sssc import dialogue_preview as dp
from plugins.testing import load_rules


def test_a_slot_keeps_its_portrait_across_a_page_until_a_tag_changes_it():
    layout = dp.parse_pages("{FA:06}One{page}Two{page}{FA:00}{FB:10}Three")
    assert [(page[0].left, page[0].right) for page in layout.pages] == [(0x06, 0), (0x06, 0), (0, 0x10)]


def test_a_right_portrait_window_starts_at_the_left_margin_and_ends_before_the_portrait():
    (page,) = dp.parse_pages("{FB:10}Hello").pages
    line = dp.measure_page(page)[0]
    assert line.start == dp.TEXT_X_NO_PORTRAIT
    assert line.limit == dp.RIGHT_PORTRAIT_X - dp.TEXT_X_NO_PORTRAIT


def test_a_left_portrait_window_starts_after_the_portrait_and_a_plain_window_uses_the_full_box():
    (left,) = dp.parse_pages("{FA:06}Hello").pages
    (plain,) = dp.parse_pages("Hello").pages
    assert dp.measure_page(left)[0].start == dp.TEXT_X
    assert dp.measure_page(left)[0].limit == dp.BOX_RIGHT - dp.TEXT_X
    assert dp.measure_page(plain)[0].limit == dp.BOX_RIGHT - dp.TEXT_X_NO_PORTRAIT


def test_a_piece_after_a_page_is_measured_in_its_own_window_not_the_sum():
    # The left window (text at x 80) and the right window (text at x 16) share one editor line.
    text = "{FA:06}" + "A" * 3 + "{page}{FB:10}" + "B" * 3
    left_width = dp.text_width("AAA")
    right_width = dp.text_width("BBB")
    assert dp.line_rights(text) == [max(dp.TEXT_X + left_width, dp.TEXT_X_NO_PORTRAIT + right_width)]


def test_raw_02_is_a_line_break_in_the_window():
    (page,) = dp.parse_pages("KYLE:Zzzz...{raw:02}Guuuhhh").pages
    assert [line.text for line in page] == ["KYLE:Zzzz...", "Guuuhhh"]


def test_raw_02_counts_toward_the_three_lines_of_a_window():
    layout = dp.parse_pages("a{raw:02}b{raw:02}c{raw:02}d")
    assert any("lines" in problem for problem in layout.problems)


def test_right_portrait_is_drawn_at_the_mirrored_place():
    glyphs = {"A": [0x8000] * 16}
    right = Image.new("RGBA", (64, 64), (0, 255, 0, 255))
    picture = dp.render_page([dp.Line("A", right=0x10)], glyphs, None, right)
    assert picture.getpixel((dp.RIGHT_PORTRAIT_X + 1, 1)) == (0, 255, 0, 255)
    assert picture.getpixel((dp.PORTRAIT_X + 1, 1))[3] == 0          # no left portrait drawn


def test_fit_text_counts_raw_02_as_a_line_and_keeps_the_tag():
    # The fourth line of the window goes to the next window: the tag stays as it was typed.
    assert dp.fit_lines("a{raw:02}b{raw:02}c{raw:02}d") == "a{raw:02}b{raw:02}c{page}d"


def test_the_fallback_alias_names_an_unknown_code_by_its_side():
    mapping = load_rules("lunar_sssc").get_default_tag_mappings()
    assert mapping["{Right portrait 20}"] == "{FB:20}"     # 20 has no name on either side
    assert mapping["{Left portrait 20}"] == "{FA:20}"
    assert mapping["{Left portrait off}"] == "{FA:00}"
    assert "{Nash left#06}" in mapping and mapping["{Nash left#06}"] == "{FA:06}"
