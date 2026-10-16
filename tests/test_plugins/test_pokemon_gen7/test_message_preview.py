"""Pokémon Sun / Moon message window (``plugins.pokemon_gen7.message_preview``): page splitting and colours, the width
of a FFNT-style font, the box render, and the widget and worker lifecycle. A small synthetic font stands in for the
game font, so the test needs no game files."""
from PIL import Image

from plugins.pokemon_gen7 import message_preview as mp


def _font():
    """Two glyphs in one 12 x 4 sheet: 'a' is 3 px wide (advance 3), 'b' is 5 px wide (advance 5)."""
    sheet = Image.new("RGBA", (12, 4), (0, 0, 0, 0))
    sheet.paste((255, 255, 255, 255), (0, 0, 3, 4))
    sheet.paste((255, 255, 255, 255), (6, 0, 11, 4))
    return mp.BoxFont(sheets=[sheet], cell=(6, 4), grid=(2, 1), cmap={ord("a"): 0, ord("b"): 1}, advances=[3, 5])


def _facts(text_width=20):
    return mp.BoxFacts(font_member="", text_x=2, first_line_top=2, line_pitch=6, text_width=text_width, box_lines=3)


def test_page_break_starts_a_new_page_without_an_empty_line():
    assert mp.split_pages("one{PAGE}\ntwo") == [[("one", "white")], [("two", "white")]]


def test_colour_tag_before_the_first_letter_colours_the_line():
    pages = mp.split_pages("{COLOR 0001}red\nstill red{COLOR 0000}\nwhite")
    assert pages == [[("red", "red"), ("still red", "red"), ("white", "white")]]


def test_width_is_the_sum_of_advances_and_wide_lines_are_flagged():
    font = _font()
    assert font.width("abab") == 16
    assert font.width("ab?") == 8           # a character the font does not have adds nothing
    assert mp.overflow_lines([("ab", "white"), ("bbbb", "white")], font, _facts(text_width=12)) == [1]


def test_too_many_lines_for_the_box_are_flagged():
    page = [("a", "white")] * 4
    assert mp.overflow_lines(page, _font(), _facts()) == [3]


def test_curly_apostrophe_uses_the_font_apostrophe():
    font = _font()
    font.cmap[ord("'")] = 0
    assert font.glyph_of("’") == 0


def test_red_line_is_drawn_red_inside_the_box():
    img = mp.render_page([("a", "red")], _font(), _facts())
    r, g, b, a = img.getpixel((3, 4))       # inside the 'a' cell, first line
    assert a == 255 and r > 200 and g < 120


def test_default_facts_come_from_config():
    facts = mp.BoxFacts.load()
    assert facts.font_member == "romfs/a/0/2/5/000.bffnt"
    assert (facts.text_x, facts.first_line_top, facts.line_pitch) == (10, 10, 20)


def test_widget_draws_once_the_font_is_received(qtbot, tmp_path):
    widget = mp.MessageWindowPreview(str(tmp_path))
    qtbot.addWidget(widget)
    widget.update_preview_text("ab\n{COLOR 0001}ab")     # no font yet: the box is empty, no error
    widget.receive((str(tmp_path), mp.Resolved(_font())))
    widget.refresh()
    widget.shutdown()


def test_widget_ignores_another_folder(qtbot, tmp_path):
    widget = mp.MessageWindowPreview(str(tmp_path / "project"))
    qtbot.addWidget(widget)
    widget.receive((str(tmp_path / "other"), mp.Resolved(_font())))
    assert widget._font is None


def test_resolver_without_the_font_emits_none(qtbot, tmp_path):
    worker = mp.WindowResolver(str(tmp_path))
    with qtbot.waitSignal(worker.resolved, timeout=5000) as blocker:
        worker.start()
    assert blocker.args == [(str(tmp_path), None)]
    worker.wait()


def test_dialogue_facts_are_the_top_screen_text_with_no_box_and_no_measured_width():
    facts = mp.BoxFacts.load("dialogue_window")
    assert (facts.screen_width, facts.text_x, facts.first_line_top, facts.line_pitch) == (400, 57, 205, 21)
    assert facts.draw_box is False
    assert facts.text_width == 0
    assert mp.overflow_lines([("a" * 50, "white")], _font(), facts) == []
