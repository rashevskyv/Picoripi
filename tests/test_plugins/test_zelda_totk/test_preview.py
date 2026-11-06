"""The TotK-engine talk window preview (Tears of the Kingdom, Ocarina of Time on Switch 2): pages, colours, widths."""
import json
from types import SimpleNamespace

import pytest

import romhacking_root

from core.containers import sarc
from plugins.common import flyt_message as fm
from plugins.zelda_totk import preview as pv
from plugins.zelda_oot_switch2.rules import GameRules as OotRules
from plugins.zelda_totk.rules import GameRules as TotkRules

OOT_PROJECT = romhacking_root.under("Zelda\\Ocarina of Time\\Switch 2\\picoripi")


class SquareFace:
    """A fake font: every character is half the glyph size wide and is drawn as a filled square."""

    def has(self, ch):
        return ch != "\u2603"

    def advance(self, ch, px):
        return px / 2

    def ascent(self, px):
        return px * 0.8

    def draw(self, image, ch, pen, baseline, px, colour):
        image.paste(colour, (int(pen), int(baseline - px * 0.6), int(pen + px / 2 - 2), int(baseline)))


CHAIN = fm.FontChain([SquareFace()])
FACTS = pv.BoxFacts(fonts=(), em=20.0, width=100.0, lines=3)


def test_page_breaks_colours_and_hidden_tags():
    text = "{tag:4:0:0600}{color:0}Red{color:-1} white{delay8}\nline 2{pageBreak}{voice:x}next"
    pages = pv.parse_pages(text)
    assert [[[part for part, _c in line] for line in page] for page in pages] == [[["Red", " white"], ["line 2"]], [["next"]]]
    assert pages[0][0][0][1] == pv.COLOURS[0]
    assert pages[0][0][1][1] == pv.WHITE


def test_a_line_break_before_a_page_break_adds_no_empty_line():
    assert len(pv.parse_pages("one\n{pageBreak}two")[0]) == 1


def test_long_lines_and_extra_lines_are_reported():
    pages = pv.parse_pages("x" * 11 + "\nb\nc\nd")       # 11 x 10 px = 110 px > 100; four lines
    notes = pv.problems(pages, CHAIN, FACTS)
    assert notes == ["Page 1: a line is 110 px, the box holds 100 px.", "Page 1: 4 lines, the box holds 3."]


def test_render_page_draws_the_coloured_run_in_its_colour():
    image = pv.render_page(pv.parse_pages("{color:0}AA")[0], CHAIN, FACTS)
    assert image.size == (int(100 + 2 * pv.PADDING), int(3 * 20 * pv.PITCH + 2 * pv.PADDING))
    colours = {colour for _count, colour in image.getcolors(1 << 16)}
    assert pv.COLOURS[0] in colours


def test_both_plugins_give_a_preview_with_their_own_facts():
    assert TotkRules.preview_box is pv.TOTK_BOX
    assert OotRules.preview_box is pv.OOT_SWITCH2_BOX


def _project(tmp_path, source):
    (tmp_path / "p.uiproj").write_text(json.dumps({"metadata": {"source_path": str(source)}}), encoding="utf-8")
    return SimpleNamespace(project_manager=SimpleNamespace(project_dir=str(tmp_path)))


def test_widget_without_the_font_says_so_and_shuts_down(qtbot, tmp_path):
    widget = pv.TalkWindowPreview(_project(tmp_path, tmp_path / "romfs" / "Mals"), pv.OOT_SWITCH2_BOX)
    qtbot.addWidget(widget)
    qtbot.waitUntil(lambda: widget._note == "The game font is not in this project's unpacked game.", timeout=5000)
    widget.update_preview_text("text")
    assert widget._images == []
    widget.shutdown()


@pytest.mark.skipif(not (OOT_PROJECT / "unpacked/romfs/Font2").is_dir(), reason="the OoT Switch 2 project is not on disk")
def test_real_oot_widget_draws_cyrillic_pages(qtbot, monkeypatch):
    romfs = OOT_PROJECT / "unpacked" / "romfs"
    monkeypatch.setattr(sarc, "dictionary_dirs", lambda: [romfs / "Pack"])
    widget = pv.TalkWindowPreview(SimpleNamespace(project_manager=SimpleNamespace(project_dir=str(OOT_PROJECT))),
                                  pv.OOT_SWITCH2_BOX)
    qtbot.addWidget(widget)
    qtbot.waitUntil(lambda: widget._chain is not None, timeout=10000)
    widget.update_preview_text("Привіт, Лінку! Їжак ґанок.{pageBreak}{color:0}Духовний камінь{color:-1}.")
    assert len(widget._images) == 2
    assert widget._note == ""
    assert all(face.has("ї") and face.has("ґ") for face in widget._chain.faces[:1])
    widget.shutdown()
