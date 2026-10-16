"""Pokémon generation IV message window (``plugins.pokemon_gen4.message_preview``): the page layout, the glyph
pixels of a Gen 4 font bin, and (real data, skipped without the workspace) the Platinum box drawn with the game's font."""
import struct
from pathlib import Path

import pytest

import romhacking_root
from core.font_formats import gen4_glyphs
from plugins.common import gen4msg
from plugins.pokemon_gen4 import message_preview as mp

CHARMAP = Path(__file__).resolve().parents[3] / "plugins" / "pokemon_gen4" / "charmaps" / "charmap_platinum.txt"


def test_a_page_has_two_lines_and_a_page_break_says_more_follows():
    lines, more = mp.page_lines("Hello\\nWorld\\rNext page")
    assert ["".join(line) for line in lines] == ["Hello", "World"]
    assert more is True


def test_a_third_line_on_the_page_says_more_follows_and_is_not_shown():
    lines, more = mp.page_lines("one\\ntwo\\nthree")
    assert ["".join(line) for line in lines] == ["one", "two"]
    assert more is True


def test_a_short_message_has_nothing_more():
    lines, more = mp.page_lines("Just this")
    assert ["".join(line) for line in lines] == ["Just this"]
    assert more is False


def test_tags_take_no_width_and_a_player_tag_shows_the_player_name():
    lines, _more = mp.page_lines("{COLOR 1}Hi {STRVAR_01 3,0}!{COLOR 0}")
    assert "".join(lines[0]) == "Hi PLAYER!"


def _font_bin(glyphs, widths):
    """A Gen 4 font bin of ``glyphs`` (lists of 2-bit levels, 16 x 16 each) with the given advance widths."""
    count = len(glyphs)
    glyph_size = 16 * 2 * 2
    widths_at = 16 + count * glyph_size
    head = struct.pack("<IIIBBBB", 16, widths_at, count, 0, 0, 2, 2)
    body = bytearray()
    for levels in glyphs:
        cells = bytearray(glyph_size)
        for tile in range(4):
            tx, ty = tile % 2, tile // 2
            for row in range(8):
                for x in range(8):
                    level = levels[ty * 8 + row][tx * 8 + x]
                    at = tile * 16 + row * 2 + (1 if x < 4 else 0)
                    shift = 6 - 2 * (x % 4)
                    cells[at] |= level << shift
        body += cells
    return bytes(head) + bytes(body) + bytes(widths)


def test_glyph_levels_read_back_the_pixels_of_a_glyph():
    blank = [[0] * 16 for _ in range(16)]
    marked = [[0] * 16 for _ in range(16)]
    marked[0][0] = 3
    marked[15][15] = 2
    data = _font_bin([blank, marked], [4, 9])
    assert gen4_glyphs.glyph_widths(data) == [4, 9]
    levels = gen4_glyphs.glyph_levels(data, 1)
    assert levels[0][0] == 3 and levels[15][15] == 2
    assert levels[0][1] == 0
    with pytest.raises(ValueError):
        gen4_glyphs.glyph_levels(data, 2)


def test_facts_name_the_platinum_font_and_only_it():
    assert mp.facts_for("CPUE") == ("graphic/pl_font.narc", 1)
    assert mp.facts_for("ADAE") is None
    assert mp.LINES_PER_PAGE == 2 and mp.BOX_PX == 216


def test_real_platinum_box_is_drawn_with_the_game_font(qtbot, tmp_path):
    source = romhacking_root.path("Pokemon", "Platinum", "source")
    reason = romhacking_root.missing("Pokemon", "Platinum", "source", "graphic", "pl_font.narc")
    if reason:
        pytest.skip(reason)
    font = mp.load_font(str(source), "graphic/pl_font.narc", 1)
    assert font is not None and gen4_glyphs.is_font_bin(font)
    widget = mp.MessageWindowPreview(font, gen4msg.Codec(str(CHARMAP)))
    qtbot.addWidget(widget)
    widget.update_preview_text("Hello there!\\nWelcome.\\r")
    assert widget._overflow is False
    widget.update_preview_text("A line that is far too long for the box, so it runs past the right edge of it")
    assert widget._overflow is True
    widget.shutdown()
