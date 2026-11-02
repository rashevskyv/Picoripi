"""Lunar: the editor measures each window alone, and a speaker comes from the portrait tag of its message."""
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import romhacking_root  # noqa: F401  (path setup for the repository's packages)

from plugins.lunar_sssc import dialogue_preview as dp
from plugins.testing import load_rules

FONT = json.loads((Path(dp.__file__).parent / "fonts" / "lunar_font.json").read_text(encoding="utf-8"))
NAMES = json.loads((Path(dp.__file__).parent / "speaker_names.json").read_text(encoding="utf-8"))
SOURCE = romhacking_root.under('Lunar\\Silver Star Story\\source')
needs_data = pytest.mark.skipif(not (SOURCE / "SLUS_006.28").is_file(), reason="Lunar SSSC not unpacked here")


def test_width_counter_measures_the_widest_window_not_the_sum_across_a_page_tag():
    rules = load_rules("lunar_sssc")
    line = "{FB:1A}The White Dragon Cave, Alex?{page}{FB:1E}I knew something was wrong"
    # The two windows measure 219 and 209 px; the line as one run measured 428 px (the bug).
    assert rules.calculate_string_width_override(line, FONT, 6) == 219
    assert rules.calculate_string_width_override("abc", FONT, 6) == dp.text_width("abc")


def test_speaker_comes_from_the_portrait_of_the_first_line():
    rules = load_rules("lunar_sssc")
    rules.mw = SimpleNamespace(data_store=SimpleNamespace(data=[["{FA:6E}Yikes!", "{FA:04}Hi", "plain", "{FA:1A}Hey"]]))
    assert rules.get_speaker_for_string(0, 0) == "Nall"
    assert rules.get_speaker_for_string(0, 1) is None      # a face with no name in speaker_names.json stays unnamed
    assert rules.get_speaker_for_string(0, 2) is None      # no portrait
    assert rules.get_speaker_for_string(0, 3) == "Luna"    # a sample message of a second character
    assert rules.get_speaker_for_string(5, 0) is None      # no such string
    assert rules.is_placeholder_speaker("Nall") is False


def test_every_named_number_is_a_two_digit_hex_face_with_a_plain_english_name():
    assert NAMES, "speaker_names.json names no portrait"
    for face, name in NAMES.items():
        assert re.fullmatch(r"[0-9A-F]{2}", face) and face != "00", face
        assert re.fullmatch(r"[A-Z][a-z]+", name), (face, name)


@needs_data
def test_every_named_number_is_a_portrait_the_game_script_uses():
    rules = load_rules("lunar_sssc")
    used = set()
    for path in sorted((SOURCE / "LUNADATA").glob("TEXT*.DAT")):
        blocks, _ = rules.load_data_from_json_obj(path.read_bytes())
        for block in blocks:
            for text in block:
                used.update(face.upper() for face in re.findall(r"\{FA:([0-9A-Fa-f]{2})\}", str(text)))
    assert set(NAMES) <= used, sorted(set(NAMES) - used)
