"""The budget box of a 3DS system string on a fake font: tags, width and line checks, missing glyphs, the status line.

The rules part reads the shipped budgets.json; the panel part needs pytest-qt. The real font is tested in test_box_real.py.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from plugins.system_3ds import box, preview_panel
from plugins.system_3ds.rules import GameRules

BUDGETS = Path(box.__file__).resolve().parent / "budgets.json"


class _FakeGlyphs:
    """The attributes of console_render.Glyphs that box.draw_box reads: every glyph is 5 x 7 with an advance of 6."""

    width = 6
    height = 8
    ascent = 6
    line_feed = 10

    def __init__(self, chars):
        self.font = SimpleNamespace(sheets=SimpleNamespace(cell_width=6, cell_height=8))
        self._codes = {ord(char) for char in chars}

    def has(self, code):
        return code in self._codes

    def metrics(self, code):
        return 0, 5, 6

    def cell(self, code):
        return Image.new("L", (5, 7), 255) if code in self._codes else None


def _glyphs():
    return _FakeGlyphs(chr(code) for code in range(32, 127))


def test_runs_keep_scale_tags_out_of_the_text_and_split_lines():
    lines = box.runs("a{t:1.0:c800}b{/t:1.0}\nc")
    assert lines == [[["a", 1.0], ["b", 2.0]], [["c", 1.0]]]


def test_a_line_is_wide_when_its_rounded_width_passes_the_budget():
    result = box.draw_box("abc\nde", [40.4, 40.6], 40, None, _glyphs())
    assert result.wide_lines == [2]
    assert result.widest == pytest.approx(40.6)


def test_a_string_without_a_width_budget_is_drawn_to_its_widest_line():
    result = box.draw_box("abc", [30.0], None, None, _glyphs())
    assert result.wide_lines == []
    assert result.image.width >= 30 + 2 * box.MARGIN


def test_lines_past_the_line_budget_are_counted_and_banded_red():
    glyphs = _glyphs()
    result = box.draw_box("a\nb\nc", [5.0, 5.0, 5.0], None, 1, glyphs)
    assert result.extra_lines == 2
    band_row = box.MARGIN + glyphs.line_feed * 2 + 1
    assert result.image.getpixel((2, band_row)) == box.RED_FILL
    assert result.image.getpixel((2, box.MARGIN + 2)) != box.RED_FILL


def test_a_character_the_font_has_no_glyph_for_is_listed_as_missing():
    result = box.draw_box("ab\u00e9", [12.0], None, None, _FakeGlyphs("ab"))
    assert result.missing == ["\u00e9"]


def test_status_names_the_wide_line_the_widest_and_the_budget():
    result = box.draw_box("abc\nde", [12.0, 41.0], 40, 1, _glyphs())
    text = preview_panel.status_text(result)
    assert "Line 2 is wider than the budget: 41 px, budget 40 px." in text
    assert "2 lines, budget 1: 1 past the budget." in text


def test_status_of_a_fitting_string_says_it_fits_its_budget():
    result = box.draw_box("abc", [30.0], 40, 1, _glyphs())
    assert preview_panel.status_text(result).startswith("Widest line 30 px, budget 40 px.")


def _rules_with_one_string(monkeypatch, part, key):
    rules = GameRules()
    block = SimpleNamespace(source_file=f"strings/{part}/message.json")
    monkeypatch.setattr(rules, "_project_blocks", lambda: [block])
    rules._blocks = [{"keys": [key]}]
    return rules


def test_the_budget_and_the_line_budget_of_a_label_come_from_budgets_json(monkeypatch):
    table = json.loads(BUDGETS.read_text(encoding="utf-8"))
    rules = _rules_with_one_string(monkeypatch, "home_menu", "lau_title_menu")
    assert rules.budget(0, 0) == table["labels"]["home_menu"]["lau_title_menu"]
    assert rules.line_budget(0, 0) == table["lines"]["home_menu"]["lau_title_menu"]
    assert rules.part_of(0) == "home_menu"


def test_a_label_without_a_budget_has_no_line_budget(monkeypatch):
    rules = _rules_with_one_string(monkeypatch, "home_menu", "no_such_label")
    assert rules.budget(0, 0) is None
    assert rules.line_budget(0, 0) is None


def test_a_stopped_draw_returns_nothing(monkeypatch):
    monkeypatch.setattr(preview_panel, "load_folder", lambda: "")
    monkeypatch.setattr(preview_panel.repo_tools, "load_tools", lambda root: SimpleNamespace(bcfnt=None))
    monkeypatch.setattr(preview_panel.repo_tools, "load_font", lambda tools: SimpleNamespace())
    monkeypatch.setattr(preview_panel.cr, "Glyphs", lambda font, bcfnt: _glyphs())
    request = preview_panel._Request("C:/x", "abc", 40, 1, "", _no_widths)
    assert preview_panel.draw_request(request, lambda: True) is None


def test_a_folder_that_is_not_set_is_reported_as_such(monkeypatch):
    monkeypatch.setattr(preview_panel, "load_folder", lambda: "")
    request = preview_panel._Request("", "abc", 40, 1, "", _no_widths)
    with pytest.raises(preview_panel.repo_tools.ToolsError):
        preview_panel.draw_request(request, lambda: False)


def _no_widths(text):
    return [0.0]


def test_the_panel_paints_a_result_and_states_its_numbers(qtbot):
    panel = preview_panel.SystemPreviewPanel(None, GameRules())
    qtbot.addWidget(panel)
    panel._generation = 1
    result = box.draw_box("abc\nde", [12.0, 41.0], 40, 1, _glyphs())
    shown = preview_panel.Shown(result.image, preview_panel.status_text(result))
    panel._on_rendered(1, ("", "abc\nde", 40, 1), shown)
    assert panel._image is not None
    assert panel._image.width() == result.image.width
    assert "wider than the budget" in panel._status.text()


def test_the_panel_shows_the_folder_message_it_is_given(qtbot):
    panel = preview_panel.SystemPreviewPanel(None, GameRules())
    qtbot.addWidget(panel)
    panel._generation = 1
    panel._on_rendered(1, ("", "abc", 40, 1), preview_panel.repo_tools.NO_FOLDER)
    assert panel._status.text() == "Set the repo_manual folder to draw the page."
    assert panel._image is None
