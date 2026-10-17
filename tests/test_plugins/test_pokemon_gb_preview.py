"""The Game Boy message box (Generations I and II): the font decoders, the two-row box rules and the real ROM fonts."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from plugins.common import gb_text_font as gbf
from plugins.common import text_window_preview as tw
from plugins.common.gba_text_font import INK, PAPER, SHADOW
from plugins.common.text_window_panel import SCALE
from plugins.pokemon_gen1 import preview_panel
from plugins.pokemon_gen1 import rom_project

FACTS = {
    "pokered.json": Path(rom_project.FACTS_DIR, "pokered.json"),
    "pokeblue.json": Path(rom_project.FACTS_DIR, "pokeblue.json"),
    "pokeyellow.json": Path(rom_project.FACTS_DIR, "pokeyellow.json"),
    "pokegold.json": Path(rom_project.FACTS_DIR.parent.parent, "pokemon_gsc", "rom_facts", "pokegold.json"),
    "pokesilver.json": Path(rom_project.FACTS_DIR.parent.parent, "pokemon_gsc", "rom_facts", "pokesilver.json"),
    "pokecrystal.json": Path(rom_project.FACTS_DIR.parent.parent, "pokemon_gsc", "rom_facts", "pokecrystal.json"),
    "pokecrystal11.json": Path(rom_project.FACTS_DIR.parent.parent, "pokemon_gsc", "rom_facts", "pokecrystal11.json"),
}
RED_ROM = Path(os.environ.get("PICORIPI_RED_ROM", "E:/Emulators/RomHacking/Pokemon/Red and Blue/ISO/"
                              "Pokemon Red Version (UE) [S][!].gb"))
PROOF_FRAME_INK = 294       # ink pixels of the box text in reports/proof/pkA3_oak/oak_intro_red_v1.png (mGBA)


def _codes(text: str) -> dict:
    """A code per character: each letter, digit and punctuation mark gets its own byte."""
    return {ch: 0x80 + index for index, ch in enumerate(text)}


def _lines(pages):
    return [[line.text for line in page] for page in pages]


def test_1bpp_bit_is_ink_and_2bpp_shade_three_is_ink():
    tile = bytes([0x80] + [0] * 7)
    rows = gbf.decode_1bpp(tile)
    assert rows[0][0] == INK and rows[0][1] == PAPER and rows[1][0] == PAPER
    two = bytes([0x80, 0x80] + [0] * 14)        # low and high planes both set on the first pixel: shade 3
    assert gbf.decode_2bpp(two)[0][0] == INK
    one = bytes([0x80, 0x00] + [0] * 14)        # low plane only: shade 1
    assert gbf.decode_2bpp(one)[0][0] == SHADOW


def test_default_breaks_show_two_rows_then_scroll_one_row_at_a_time():
    code_of = _codes("abcd").get
    pages = tw.parse_gb_pages("a\nb\nc\nd", code_of, 0)
    assert _lines(pages) == [["a", "b"], ["b", "c"], ["c", "d"]]
    assert [] == tw.check_pages(pages, _set(), _window())


def test_a_next_tag_past_two_rows_is_an_overflow_and_a_scroll_is_not():
    code_of = _codes("abc").get
    stacked = tw.parse_gb_pages("a\n{next}b\n{next}c", code_of, 0)
    assert _lines(stacked) == [["a", "b", "c"]]
    assert [(o.line, o.kind) for o in tw.check_pages(stacked, _set(), _window())] == [(2, "lines")]
    scrolled = tw.parse_gb_pages("a\nb\n{cont}c", code_of, 0)
    assert _lines(scrolled) == [["a", "b"], ["b", "c"]]
    assert tw.check_pages(scrolled, _set(), _window()) == []


def test_a_scroll_after_a_single_line_leaves_the_top_row_empty():
    pages = tw.parse_gb_pages("a\n{cont}b", _codes("ab").get, 0)
    assert _lines(pages) == [["a"], ["", "b"]]


def test_two_newlines_clear_the_box_and_start_a_new_screen():
    pages = tw.parse_gb_pages("a\n\nb", _codes("ab").get, 0)
    assert _lines(pages) == [["a"], ["b"]]


def test_placeholder_draws_the_name_cells_and_flow_tags_draw_nothing():
    placeholders = dict(preview_panel.PLACEHOLDERS)
    pages = tw.parse_gb_pages("{Player}", _codes("PLAYER").get, 0, placeholders)
    assert len(pages[0][0].codes) == 7
    assert _lines(tw.parse_gb_pages("x\n{line}y", _codes("xy").get, 0)) == [["x", "y"]]


def test_every_game_facts_file_has_the_font_and_the_two_row_box():
    for name, path in FACTS.items():
        facts = json.loads(path.read_text(encoding="utf-8"))
        font = facts.get("font")
        assert font, name
        assert font["tiles_1bpp"]["code"] == 0x80, name
        assert font["tiles_2bpp"]["code"] == 0x60, name
        window = font["window"]
        assert (window["text_width"], window["lines"], window["text_top"]) == (144, 2, 16), name


@pytest.mark.skipif(not RED_ROM.is_file(), reason="Red ROM is not on this machine")
def test_real_red_rom_box_matches_the_mgba_frame_of_the_same_line():
    facts = json.loads((rom_project.FACTS_DIR / "pokered.json").read_text(encoding="utf-8"))
    byte_of = {}
    for char, code in facts["charmap"]:
        byte_of.setdefault(str(char), int(code))
    window = dict(facts["font"]["window"])
    window["frame"] = {key: byte_of[char] for key, char in gbf.FRAME_CHARS.items()}
    glyphs = gbf.read_gb_glyph_set(RED_ROM, facts["font"])
    pages = tw.parse_gb_pages("is longer than\nbefore, so it", byte_of.get, byte_of["?"], preview_panel.PLACEHOLDERS)
    image = tw.render_page(pages[0], glyphs, tw.Window.from_facts(window))
    ink = sum(1 for x in range(8, image.width() - 8) for y in range(8, image.height() - 8)
              if image.pixelColor(x, y).red() < 128)
    assert ink == PROOF_FRAME_INK


def _set():
    class _Glyphs:
        def width(self, code):
            return 8

        def drawn_width(self, code):
            return 8

        def pixels(self, code):
            return [[PAPER] * 8 for _ in range(8)]
    return _Glyphs()


def _window():
    return tw.Window(text_x=8, text_width=144, lines=2, line_height=16, box_width=160, box_height=48, text_top=16)


@pytest.mark.skipif(not RED_ROM.is_file(), reason="Red ROM is not on this machine")
def test_editor_preview_draws_the_red_box_and_flags_a_wide_line(qtbot, tmp_path):
    """The real widget in the editor path: the project's rom folder, the worker loads the font, the box is drawn."""
    import shutil
    from types import SimpleNamespace

    rom_dir = tmp_path / rom_project.ROM_DIR
    rom_dir.mkdir()
    shutil.copyfile(RED_ROM, rom_dir / rom_project.BASE_ROM.name)
    (rom_dir / rom_project.META_FILE.name).write_text(json.dumps({"facts": "pokered.json"}), encoding="utf-8")

    class _Manager:
        project = SimpleNamespace(blocks=[SimpleNamespace(source_file="text/dialogue.asm")])

        def get_absolute_path(self, relative):
            return str(tmp_path / relative)

    widget = preview_panel.MessageWindowPreview(SimpleNamespace(project_manager=_Manager()))
    qtbot.addWidget(widget)
    widget.update_preview_text("is longer than\nbefore, so it")
    qtbot.waitUntil(lambda: widget._page_label.text() != "", timeout=10000)
    assert widget._picture.pixmap().width() == 160 * SCALE
    assert widget._picture.pixmap().height() == 48 * SCALE
    assert widget._status.text() == ""
    widget.update_preview_text("is longer than before, so it keeps on going well past the box")
    qtbot.waitUntil(lambda: "144 px" in widget._status.text(), timeout=10000)
    widget.shutdown()


def test_a_label_on_the_db_line_starts_its_own_body():
    from plugins.pokemon_gen1 import rom_text

    groups = rom_text.read_labels('Foo:   db "CANCEL@"\n\nBar::\n\ttext "x"\n')
    assert [label for label, _lines in groups] == ["Foo", "Bar"]
    assert groups[0][1] == [("db", '"CANCEL@"')]
