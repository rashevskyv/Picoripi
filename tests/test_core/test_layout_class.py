"""Layout class of a string (prose / lines), the width tolerance and the letter budget sent to the model."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.translation.layout_class import LINES, PROSE, guess_layout_class, layout_class_for
from utils.width import chars_that_fit, resolve_width_limits

ROOT = Path(__file__).resolve().parents[2]


class TestGuess:
    @pytest.mark.parametrize("text, expected", [
        ("Save game\nLoad game\nOptions", LINES),
        ("Yes\nNo", LINES),
        ("Master Sword", LINES),
        ("Hello there, Link! How are you today?", PROSE),
        ("Hello there\nLink, how are\nyou today?", PROSE),       # five words on one line: sentence-like
        ("Go north.\nThen east.", PROSE),                         # sentence punctuation
        ("{color:red}Rupee{/color}\n[icon] Bomb", LINES),         # tags do not count as words
        ("One\n\nthree\nfour\nfive\n", PROSE),                    # a blank line is a page break: dialogue windows
        ("", PROSE),
    ])
    def test_short_unpunctuated_lines_are_a_list(self, text, expected):
        assert guess_layout_class(text) == expected


class TestPluginAnswer:
    def _mw(self, context):
        rules = SimpleNamespace(get_translation_context_for_string=lambda b, s: context)
        return SimpleNamespace(current_game_rules=rules)

    def test_the_plugin_wins_over_the_guess(self):
        assert layout_class_for(self._mw({"layout_class": "lines"}), 0, 0, "A long sentence here, really.") == LINES
        assert layout_class_for(self._mw({"layout_class": "prose"}), 0, 0, "Yes\nNo") == PROSE

    def test_no_answer_or_a_bad_one_falls_back_to_the_guess(self):
        assert layout_class_for(self._mw({}), 0, 0, "Yes\nNo") == LINES
        assert layout_class_for(self._mw({"layout_class": "sideways"}), 0, 0, "Yes\nNo") == LINES
        assert layout_class_for(SimpleNamespace(current_game_rules=None), 0, 0, "Yes\nNo") == LINES
        assert layout_class_for(self._mw({"layout_class": "lines"}), None, None, "Yes.") == PROSE

    def test_twilight_princess_marks_credits_names_and_boss_cards_as_lines(self):
        from plugins.zelda_bmg.window_kinds import layout_for_kind, load_window_layouts
        layouts = load_window_layouts(str(ROOT / "plugins/zelda_bmg"))
        assert {k for k, v in layouts["kinds"].items() if v.get("layout_class") == "lines"} == {7, 12, 19}
        assert layout_for_kind(layouts, 12)["layout_class"] == "lines"
        assert "layout_class" not in layout_for_kind(layouts, 0)


class TestWidthTolerance:
    def _rules(self, layout):
        return SimpleNamespace(get_string_layout=lambda b, s: layout)

    def test_one_width_from_the_plugin_gives_the_other_through_the_tolerance(self):
        assert resolve_width_limits({}, self._rules({"max_width": 420}), 0, 0, 280, 300, tolerance_percent=5) == (400, 420)
        assert resolve_width_limits({}, self._rules({"warn_width": 400}), 0, 0, 280, 300, tolerance_percent=5) == (400, 420)

    def test_two_widths_or_no_tolerance_change_nothing(self):
        both = self._rules({"warn_width": 410, "max_width": 435})
        assert resolve_width_limits({}, both, 0, 0, 280, 300, tolerance_percent=5) == (410, 435)
        assert resolve_width_limits({}, self._rules({"max_width": 420}), 0, 0, 280, 300) == (280, 420)
        assert resolve_width_limits({"width": 100}, both, 0, 0, 280, 300, tolerance_percent=5) == (100, 100)


class TestLetterBudget:
    def test_the_budget_is_measured_on_the_target_alphabet(self):
        font = {ch: {"width": 10} for ch in "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"}
        font[" "] = {"width": 5}
        budget = chars_that_fit(300, font)
        assert budget == int(300 * 34 / (33 * 10 + 5))   # 30 letters of 10 px, a little more thanks to the space
        assert chars_that_fit(300, {}) is None and chars_that_fit(0, font) is None
