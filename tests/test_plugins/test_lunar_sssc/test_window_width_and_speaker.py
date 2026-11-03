"""Lunar: the editor measures each window alone, and a speaker comes from the portrait tag of its message."""
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import romhacking_root  # noqa: F401  (path setup for the repository's packages)

from plugins.lunar_sssc import dialogue_preview as dp
from plugins.lunar_sssc import doc as doc_module
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


def _words_up_to(words, limit):
    line = ""
    for word in words:
        if dp.text_width((line + " " + word).strip()) > limit:
            break
        line = (line + " " + word).strip()
    return line


def test_a_continuation_line_of_a_portrait_window_is_measured_with_the_portrait_start():
    # The second line has no tag of its own; its window has a portrait, so it starts at x 80 and is too wide.
    second = _words_up_to("I think I'm going to lie down before I get any worse and then some".split(), 262)
    assert 240 < dp.text_width(second) <= 304
    text = "{FA:6E}Short line.\n" + second
    rights = dp.line_rights(text)
    assert rights[1] == dp.TEXT_X + dp.text_width(second) and rights[1] > dp.BOX_RIGHT
    assert dp.measure(text)[1].over is True
    rules = load_rules("lunar_sssc")
    assert rules.line_widths(text, FONT) == rights


def test_fit_text_wraps_a_message_inside_each_window_and_keeps_its_tags():
    paragraph = ("What's the matter, Luna? You look awful! Do you have to hurl on deck? I do feel seasick, Nall, "
                 "now that you mention it, and I think I'm going to lie down before I get any worse. Besides, I want "
                 "to be ready when we arrive in Meribia, I can't wait!")
    text = "{FB:38}" + paragraph + "{page}{FA:1D}" + paragraph
    fitted = dp.fit_lines(text)
    assert [m.over for p in dp.parse_pages(fitted).pages for m in dp.measure_page(p)].count(True) == 0
    strip = lambda s: re.sub(r"\{[^{}]*\}|\s", "", s)
    assert strip(fitted) == strip(text)                  # the same words and tags, only spaces moved
    assert dp.parse_pages(fitted).pages[0][0].face == 0x38
    assert dp.parse_pages(fitted).pages[-1][0].face == 0x1D      # the second paragraph keeps its portrait
    assert dp.fit_lines("{FA:6E}Hi.") == "{FA:6E}Hi."


def test_fit_text_leaves_table_strings_to_the_generic_path():
    rules = load_rules("lunar_sssc")
    rules.mw = SimpleNamespace(data_store=SimpleNamespace(data=[["Attack"]]), current_game_rules=None)
    assert rules.fit_text_to_window("Attack", 0, 0) is None
    rules.mw = SimpleNamespace(data_store=SimpleNamespace(data=[[OWNER_MESSAGE]]), current_game_rules=None)
    fitted = rules.fit_text_to_window(OWNER_MESSAGE, 0, 0)
    assert isinstance(fitted, str) and fitted != ""


def _rules_with_aliases():
    rules = load_rules("lunar_sssc")
    config = json.loads((Path(dp.__file__).parent / "config.json").read_text(encoding="utf-8"))
    rules.mw = SimpleNamespace(default_tag_mappings=config["default_tag_mappings"])
    return rules


def test_speaker_codes_show_as_names_and_go_back_to_the_same_bytes():
    rules = _rules_with_aliases()
    data = "{FA:39}Hi{page}{FB:39}Bye{FA:03}x{FA:6E}y"
    shown = rules.get_text_representation_for_editor(data)
    assert "{Nall#39}Hi" in shown and "{Nall#FB39}Bye" in shown
    assert "{FA:03}x" in shown                         # no name for 03: the code stays visible
    assert rules.convert_editor_text_to_data(shown) == data
    assert rules.convert_editor_text_to_data("{Nall#FA39}") == "{Nall#FA39}"   # not an alias: kept as typed


def test_the_alias_table_matches_the_speaker_names():
    config = json.loads((Path(dp.__file__).parent / "config.json").read_text(encoding="utf-8"))["default_tag_mappings"]
    assert len(config) == 2 * len(NAMES)
    for code, name in NAMES.items():
        assert config.get("{%s#%s}" % (name, code)) == "{FA:%s}" % code or config.get("{%s}" % name) == "{FA:%s}" % code
        assert config["{%s#FB%s}" % (name, code)] == "{FB:%s}" % code


def _families_of_real_data():
    """Tag families of the real scripts: 'FA', 'raw', '{page}' … (the key the catalogue uses)."""
    families = set()
    for path in sorted((SOURCE / "LUNADATA").glob("TEXT*.DAT")):
        blocks, _ = doc_module.read(path.read_bytes())
        for block in blocks:
            for text in block:
                for tag in re.findall(r"\{[^{}]*\}", text):
                    if re.fullmatch(r"\{[0-9A-F]{2}:[0-9A-F]{2}\}", tag):
                        families.add(tag[1:3])
                    elif tag.startswith("{raw:"):
                        families.add("raw")
                    else:
                        families.add(tag)
    return families


@needs_data
def test_every_speaker_number_the_script_uses_has_a_portrait_file():
    files = {path.name: path.read_bytes() for path in sorted((SOURCE / "LUNADATA").glob("FACE_*.TIZ"))}
    index = dp.index_faces(files)
    used = set()
    for path in sorted((SOURCE / "LUNADATA").glob("TEXT*.DAT")):
        blocks, _ = doc_module.read(path.read_bytes())
        for block in blocks:
            for text in block:
                used.update(int(v, 16) for _k, v in re.findall(r"\{(FA|FB):([0-9A-F]{2})\}", text) if v != "00")
    assert used and used <= set(index), sorted(hex(v) for v in used - set(index))


@needs_data
def test_the_tag_catalogue_names_every_tag_family_of_the_real_data():
    catalogue = json.loads((Path(dp.__file__).parent / "tags.json").read_text(encoding="utf-8"))["tags"]
    names = set()
    for row in catalogue:
        pattern = row["pattern"]
        if pattern.startswith("{raw:"):
            names.add("raw")
        elif re.fullmatch(r"\{[0-9A-F]{2}:xx\}", pattern):
            names.add(pattern[1:3])
        else:
            names.add(pattern)
    assert _families_of_real_data() <= names, sorted(_families_of_real_data() - names)
    assert all(row["count"] > 0 and row["name"] and row["translator"] for row in catalogue)
