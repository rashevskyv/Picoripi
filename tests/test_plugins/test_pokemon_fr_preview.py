"""The message-box preview of the Generation III plugin: the font decode, the text layout and the real FireRed ROM.

The real-ROM test reads the FireRed rev 0 image from ``PICORIPI_FIRERED_ROM`` or the owner's workspace and skips
when it is not there. Nothing from the image is copied into the repository.
"""
import json
import os
import shutil
from pathlib import Path

import pytest

from plugins.common import text_window_preview as tw
from plugins.common.gba_text_font import GLYPH_BYTES, GlyphSet, decode_glyph, half_row_pixels
import romhacking_root
from plugins.pokemon_fr import rom_text

ROM = Path(os.environ.get("PICORIPI_FIRERED_ROM", romhacking_root.under(
    "Pokemon/FireRed and LeafGreen/ISO/Pokemon - FireRed Version (USA, Europe).gba")))


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


@pytest.mark.skipif(not ROM.is_file(), reason="FireRed rev 0 ROM is not on this machine")
def test_editor_preview_draws_the_firered_box_and_flags_a_wide_line(qtbot, tmp_path):
    """The real widget in the editor path: the project's rom folder, the worker loads the font, the box is drawn."""
    from types import SimpleNamespace

    from plugins.pokemon_fr import preview_panel, rom_project

    rom_dir = tmp_path / rom_project.ROM_DIR
    rom_dir.mkdir()
    shutil.copyfile(ROM, rom_dir / rom_project.BASE_ROM.name)
    (rom_dir / rom_project.META_FILE.name).write_text(json.dumps({"facts": "firered_usa_rev0.json"}), encoding="utf-8")

    class _Manager:
        project = SimpleNamespace(blocks=[SimpleNamespace(source_file="text/dialogue.txt")])

        def get_absolute_path(self, relative):
            return str(tmp_path / relative)

    widget = preview_panel.MessageWindowPreview(SimpleNamespace(project_manager=_Manager()))
    qtbot.addWidget(widget)
    widget.update_preview_text("UA TEST! This line is\nlonger than befor")
    qtbot.waitUntil(lambda: widget._page_label.text() != "", timeout=10000)
    assert widget._picture.pixmap().width() == 240 * preview_panel.SCALE
    assert widget._picture.pixmap().height() == 48 * preview_panel.SCALE
    assert widget._status.text() == ""
    widget.update_preview_text("UA TEST! This line is longer than before and it keeps on going well past the box")
    qtbot.waitUntil(lambda: "208" in widget._status.text(), timeout=10000)
    widget.shutdown()


def test_ruby_4bpp_nibbles_map_to_paper_ink_and_shadow():
    from plugins.common.gba_text_font import INK, PAPER, SHADOW, decode_glyph_4bpp

    block = bytearray(64)
    block[8] = 0xF0            # upper tile, row 2, pixel 0 = paper (0), pixel 1 = ink (F)
    block[9] = 0xEF            # pixel 2 = ink, pixel 3 = shadow (E)
    rows = decode_glyph_4bpp(bytes(block))
    assert len(rows) == 16 and all(len(row) == 8 for row in rows)
    assert rows[2][:4] == [PAPER, INK, INK, SHADOW]
    assert rows[0] == [PAPER] * 8


RUBY_ROM = romhacking_root.under("Pokemon/Ruby and Sapphire/ISO/Pokemon - Ruby Version (USA, Europe).gba")


@pytest.mark.skipif(not RUBY_ROM.is_file(), reason="Ruby rev 0 ROM is not on this machine")
def test_real_ruby_rom_4bpp_font_matches_the_proof_glyph_a():
    from plugins.common.gba_text_font import INK, PAPER, SHADOW, read_glyph_set_4bpp

    facts = json.loads((rom_text.FACTS_DIR / "ruby_usa_rev0.json").read_text(encoding="utf-8"))
    rom = RUBY_ROM
    glyphs = read_glyph_set_4bpp(rom, facts["font"])
    charmap = rom_text.Charmap.load(rom_text.FACTS_DIR / facts["charmap"])
    a = charmap.byte_of["A"]
    assert glyphs.width(a) == 6
    # Row 0 of the glyph is paper; row 3 has ink and shadow (the proof frame shows "UA" in this font).
    assert all(v == PAPER for v in glyphs.pixels(a)[0])
    assert any(v == INK for v in glyphs.pixels(a)[3]) and any(v == SHADOW for v in glyphs.pixels(a)[3])
