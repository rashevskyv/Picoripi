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
    assert rules.calculate_string_width_override(line, FONT, 6) == dp.TEXT_X + max(dp.text_width("The White Dragon Cave, Alex?"), dp.text_width("I knew something was wrong"))
    assert rules.calculate_string_width_override("abc", FONT, 6) == dp.TEXT_X_NO_PORTRAIT + dp.text_width("abc")


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


OWNER_MESSAGE = ("{FB:38}What's the matter, Luna? You look awful! Do you have to hurl on deck?{page}{FB:00}{FA:1D}"
                 "I do feel seasick, Nall, now that you mention it...{page}I think I'm going to lie down before I get any worse."
                 "{page}{FA:1A}Besides, I want to be ready when we arrive in Meribia...{page}{FA:00}{FB:39}"
                 "I can't wait! And I still can't believe we're really doing this!")


def test_right_speaker_tag_names_the_window_and_each_page_keeps_its_portrait():
    layout = dp.parse_pages(OWNER_MESSAGE)
    # FB:38 names the first window. A window with no tag at its start has no portrait (no state carried over).
    assert [page[0].face for page in layout.pages] == [0x38, 0x1D, 0, 0x1A, 0x39]
    rules = load_rules("lunar_sssc")
    rules.mw = SimpleNamespace(data_store=SimpleNamespace(data=[[OWNER_MESSAGE]]))
    assert rules.get_speaker_for_string(0, 0) == "Nall"


def test_the_left_speaker_wins_when_both_tags_are_set():
    layout = dp.parse_pages("{FA:1D}{FB:38}Hi{page}{FB:00}Bye")
    assert [page[0].face for page in layout.pages] == [0x1D, 0]


@needs_data
def test_every_portrait_of_the_owner_message_is_in_the_face_files():
    files = {path.name: path.read_bytes() for path in sorted((SOURCE / "LUNADATA").glob("FACE_*.TIZ"))}
    if not files:
        pytest.skip("the workspace source has no FACE_*.TIZ portrait files (not unpacked); no portrait can be drawn")
    index = dp.index_faces(files)
    for face in (0x38, 0x1D, 0x1A, 0x39):
        assert face in index, hex(face)


def test_the_fit_check_is_the_preview_measure_without_the_widget():
    # The measure is pure: it must not need Qt or the preview widget (the editor and check_fit run headless).
    source = Path(dp.__file__).read_text(encoding="utf-8")
    assert "PyQt6" not in source and "dialogue_panel" not in source
    assert dp.measure("{FA:6E}" + "W" * 40)[0].limit == dp.WINDOW_X + dp.WINDOW_W - dp.TEXT_X
    assert dp.measure("plain")[0].limit == dp.WINDOW_X + dp.WINDOW_W - dp.TEXT_X_NO_PORTRAIT
    rules = load_rules("lunar_sssc")
    assert rules.calculate_string_width_override("{FA:6E}" + "W" * 40, FONT, 6) > 320   # a line past the box edge


def _ink_right(glyphs, text, start):
    """The rightmost lit pixel of a line as the preview blits it (glyph bits, not advances)."""
    x = start
    best = start
    for ch in text:
        if ch in glyphs:
            for ry, word in enumerate(glyphs[ch]):
                for rx in range(16):
                    if word >> (15 - rx) & 1:
                        best = max(best, x + rx + 1)
        x += dp.advance(ch)
    return best


@needs_data
def test_the_warning_is_red_exactly_when_the_preview_draws_outside_the_box():
    glyphs = dp.decode_glyphs((SOURCE / "SLUS_006.28").read_bytes())
    rules = load_rules("lunar_sssc")
    flagged = []
    checked = 0
    for path in sorted((SOURCE / "LUNADATA").glob("TEXT*.DAT")):
        blocks, _ = rules.load_data_from_json_obj(path.read_bytes())
        for bi, block in enumerate(blocks):
            for si, text in enumerate(block):
                for page in dp.parse_pages(text).pages:
                    for line, m in zip(page[:dp.LINES_PER_PAGE], dp.measure_page(page)):
                        checked += 1
                        if m.right < dp.WINDOW_X + dp.WINDOW_W - 16:
                            assert not m.over    # far inside the box: no glyph can reach the edge
                            continue
                        ink_over = _ink_right(glyphs, line.text, m.start) > dp.WINDOW_X + dp.WINDOW_W
                        assert m.over == ink_over, (path.name, bi, si, line.text[:40])
                        if m.over:
                            flagged.append(f"{path.name}:{bi}:{si}")
    assert checked > 40000
    # The real English lines that leave the box in the preview too (see the report); no other line.
    assert len(flagged) == 10, flagged
