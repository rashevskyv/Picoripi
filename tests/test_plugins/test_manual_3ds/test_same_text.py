"""3DS manuals: one translation for the same text in two paragraphs (D46).

The duplicate key ignores the page, the line count and the width (get_duplicate_context_for_string), and every
place that takes a translation is checked for its own layout (get_text_fit_problems_for_string, text_fits_place).
Synthetic keys, texts and geometry only.
"""
import json
import string
from types import SimpleNamespace

import pytest

from core.translation.layout_contract import text_fits_place
from plugins.manual_3ds import layout
from plugins.manual_3ds import rules as m3d

WIDE = "large/Page_000_large_0#0"
NARROW = "small/Page_001_small_0#1"
LETTERS = "а" * 12   # 115 px at the test font: fits a 300 px pane, not a 70 px edge


@pytest.fixture
def widths(monkeypatch):
    advances = {ch: 10.0 for ch in string.ascii_letters + "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"}
    advances.update({" ": 9.0})
    table = layout.Widths({"advances": advances, "homoglyphs": {}})
    monkeypatch.setattr(m3d._DATA, "widths", table)
    return table


@pytest.fixture
def two_places(monkeypatch, widths):
    """A manual of two paragraphs with the same source text: a wide one, and a small one at page x 250 (70 px to
    the card edge)."""
    doc = {WIDE: {"lines": 1, "width": 300.0, "en": "", "ru": "Текст"},
           NARROW: {"lines": 1, "width": 100.0, "en": "", "ru": "Текст"}}
    wide = {"part": "large", "font_size": 24.0, "char_space": 0.0, "icon_widths": [],
            "lines": [[[10.0, 300.0]]]}
    narrow = {"part": "small", "font_size": 24.0, "char_space": 0.0, "icon_widths": [],
              "lines": [[[20.0, 100.0, 250.0]]]}
    table = {m3d.fingerprint(list(doc)): {"name": "synthetic", "entries": {WIDE: wide, NARROW: narrow}}}
    monkeypatch.setattr(m3d._DATA, "geometry", table)
    rules = m3d.GameRules()
    rules.load_data_from_json_obj(json.dumps(doc, ensure_ascii=False))
    return rules


def test_the_duplicate_context_is_one_constant_for_every_paragraph(two_places):
    assert two_places.get_duplicate_context_for_string(0, 0) == {"content_role": "Manual text"}
    assert two_places.get_duplicate_context_for_string(0, 1) == two_places.get_duplicate_context_for_string(0, 0)


def test_an_unknown_paragraph_has_no_duplicate_context(two_places):
    assert two_places.get_duplicate_context_for_string(0, 9) is None
    assert two_places.get_duplicate_context_for_string(5, 0) is None


def test_a_text_that_fits_the_wide_pane_is_a_word_problem_in_the_small_one(two_places):
    assert two_places.get_text_fit_problems_for_string(0, 0, LETTERS) == []
    problems = two_places.get_text_fit_problems_for_string(0, 1, LETTERS)
    assert "WORD" in problems and "WIDTH" in problems
    assert set(problems) <= m3d.FIT_PROBLEMS


def test_an_empty_translation_has_no_fit_problems(two_places):
    assert two_places.get_text_fit_problems_for_string(0, 1, "") == []


def test_a_place_refuses_the_text_when_the_plugin_reports_a_problem(two_places):
    mw = SimpleNamespace(current_game_rules=two_places, lines_per_page=99)
    assert text_fits_place(mw, "Текст", LETTERS, 0, 0) is True
    assert text_fits_place(mw, "Текст", LETTERS, 0, 1) is False


def test_a_failing_layout_check_refuses_the_text(two_places):
    class Broken:
        def get_string_layout(self, block_idx, string_idx):
            return {"lines_per_page": 99}

        def get_text_fit_problems_for_string(self, block_idx, string_idx, text):
            raise RuntimeError("no geometry")

    mw = SimpleNamespace(current_game_rules=Broken(), lines_per_page=99)
    assert text_fits_place(mw, "Текст", "Текст", 0, 0) is False
