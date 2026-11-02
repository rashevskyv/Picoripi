"""Lunar: the editor measures each window alone, and a speaker comes from the portrait tag of its message."""
import json
from pathlib import Path
from types import SimpleNamespace

import romhacking_root  # noqa: F401  (path setup for the repository's packages)

from plugins.lunar_sssc import dialogue_preview as dp
from plugins.testing import load_rules

FONT = json.loads((Path(dp.__file__).parent / "fonts" / "lunar_font.json").read_text(encoding="utf-8"))


def test_width_counter_measures_the_widest_window_not_the_sum_across_a_page_tag():
    rules = load_rules("lunar_sssc")
    line = "{FB:1A}The White Dragon Cave, Alex?{page}{FB:1E}I knew something was wrong"
    # The two windows measure 219 and 209 px; the line as one run measured 428 px (the bug).
    assert rules.calculate_string_width_override(line, FONT, 6) == 219
    assert rules.calculate_string_width_override("abc", FONT, 6) == dp.text_width("abc")


def test_speaker_comes_from_the_portrait_of_the_first_line():
    rules = load_rules("lunar_sssc")
    rules.mw = SimpleNamespace(data_store=SimpleNamespace(data=[["{FA:6E}Yikes!", "{FA:39}Hi", "plain"]]))
    assert rules.get_speaker_for_string(0, 0) == "Nall"
    assert rules.get_speaker_for_string(0, 1) is None      # a face with no checked name stays unnamed
    assert rules.get_speaker_for_string(0, 2) is None      # no portrait
    assert rules.get_speaker_for_string(5, 0) is None      # no such string
    assert rules.is_placeholder_speaker("Nall") is False
