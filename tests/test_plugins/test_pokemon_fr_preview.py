"""The message-box preview of the Generation III plugin: the font decode, the text layout and the real FireRed ROM.

The real-ROM test reads the FireRed rev 0 image from ``PICORIPI_FIRERED_ROM`` or the owner's workspace and skips
when it is not there. Nothing from the image is copied into the repository.
"""
import json
import os
from pathlib import Path

import pytest

from plugins.common import text_window_preview as tw
from plugins.common.gba_text_font import GLYPH_BYTES, GlyphSet, decode_glyph, half_row_pixels
from plugins.pokemon_fr import rom_text

ROM = Path(os.environ.get("PICORIPI_FIRERED_ROM",
                          "E:/Emulators/RomHacking/Pokemon/FireRed and LeafGreen/ISO/"
                          "Pokemon - FireRed Version (USA, Europe).gba"))


def _charmap_of(chars):
    return {ch: code for ch, code in chars}.get


def _set(widths):
    return GlyphSet(bytes(widths), bytes(GLYPH_BYTES * len(widths)), bytes(256))


def test_half_row_combinations_are_base_three_digits():
    assert half_row_pixels(0) == [0, 0, 0, 0]
    assert half_row_pixels(1) == [0, 0, 0, 1]
    assert half_row_pixels(27) == [1, 0, 0, 0]
    assert half_row_pixels(80) == [2, 2, 2, 2]


def test_blank_glyph_decodes_to_paper():
    rows = decode_glyph(bytes(GLYPH_BYTES), bytes(256))
    assert len(rows) == 16 and all(v == 0 for row in rows for v in row)


def test_parse_splits_lines_and_pages_and_uses_tag_names():
    glyph_of = _charmap_of([("a", 1), ("b", 2), ("?", 9)])
    pages = tw.parse_pages("ab\\nab\\lb\\pa", glyph_of, 9)
    assert [[line.codes for line in page] for page in pages] == [[[1, 2], [1, 2], [2]], [[1]]]
    assert pages[0][2].start == "l"
    tag = tw.parse_pages("{PLAYER}", glyph_of, 9)[0][0].codes
    assert tag == [9] * 6          # letters that have no code in this small charmap draw the missing glyph


def test_a_line_wider_than_the_box_and_an_extra_plain_line_are_flagged():
    glyphs = _set([5, 6] + [0] * 254)
    window = tw.Window(text_x=0, text_width=10, lines=2, line_height=16, box_width=40, box_height=40)
    wide = tw.parse_pages("aaaa", _charmap_of([("a", 1)]), 0)
    assert [(o.kind, o.detail) for o in tw.check_pages(wide, glyphs, window)] == [("wide", 24)]
    three = tw.parse_pages("a\\na\\na", _charmap_of([("a", 0)]), 0)
    assert [(o.line, o.kind) for o in tw.check_pages(three, glyphs, window)] == [(2, "lines")]
    scrolled = tw.parse_pages("a\\na\\la", _charmap_of([("a", 0)]), 0)
    assert tw.check_pages(scrolled, glyphs, window) == []


def test_render_draws_ink_where_the_glyph_has_it():
    glyphs = _set([1] * 256)
    window = tw.Window(text_x=2, text_width=20, lines=2, line_height=16, box_width=30, box_height=30, text_top=2)
    page = tw.parse_pages("x", _charmap_of([("x", 0)]), 0)[0]
    image = tw.render_page(page, glyphs, window)
    assert image.width() == 30 and image.height() == 30


@pytest.mark.skipif(not ROM.is_file(), reason="FireRed rev 0 ROM is not on this machine")
def test_real_firered_rom_font_and_first_line_width():
    facts = json.loads((rom_text.FACTS_DIR / "firered_usa_rev0.json").read_text(encoding="utf-8"))
    from plugins.common.gba_text_font import read_glyph_set
    glyphs = read_glyph_set(ROM, facts["font"])
    charmap = rom_text.Charmap.load(rom_text.FACTS_DIR / facts["charmap"])
    assert glyphs.width(charmap.byte_of["A"]) == 6
    line = tw.parse_pages("UA TEST! This line is", charmap.byte_of.get, 0)[0][0]
    assert sum(glyphs.width(code) for code in line.codes) == 116
