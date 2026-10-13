"""3DS electronic manual plugin: file load and save, the source and translation roles, the line model and problems.

The tests use a tiny synthetic manual and synthetic widths and geometry, installed on the plugin's own data holder.
The real-data check reads the owner's manual sources only when PICORIPI_ROMHACKING is set.
"""
import json
import string

import pytest

import romhacking_root
from plugins.manual_3ds import layout
from plugins.manual_3ds import rules as m3d
from plugins.testing import check_loads, check_round_trip, check_validator

PLUGIN = "manual_3ds"
CYRILLIC = "абвгґдеєжзиіїйклмнопрстуфхцчшщьюяАБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"
PAGE = "large/Page_000_large_0"
SAMPLE_KEYS = [f"{PAGE}#0", f"{PAGE}#1"]


def _entry(lines, width, en, ru, ua=None):
    entry = {"lines": lines, "width": width, "en": en, "ru": ru}
    if ua is not None:
        entry["ua"] = ua
    return entry


SAMPLE = {
    SAMPLE_KEYS[0]: _entry(2, 50.0, "Hello there", "Привет", "Привіт"),
    SAMPLE_KEYS[1]: _entry(1, 300.0, "Note", "Заметка", ""),
}


def _text(doc) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


@pytest.fixture
def widths(monkeypatch):
    """Letters 10 px, digits 16.3, space 8.7 at a 24 px em; `~` has no glyph."""
    advances = {ch: 10.0 for ch in string.ascii_letters + CYRILLIC}
    table = layout.Widths({"advances": advances, "homoglyphs": {}})
    monkeypatch.setattr(m3d._DATA, "widths", table)
    return table


@pytest.fixture
def geometry(monkeypatch):
    """A column paragraph of two lines at x 10, box 300 (the budget is the JSON width)."""
    column = {"part": "large", "font_size": 24.0, "char_space": 0.0, "icon_widths": [],
              "lines": [[10.0, 300.0], [10.0, 300.0]]}
    entries = {SAMPLE_KEYS[0]: column, SAMPLE_KEYS[1]: column}
    keys = list(SAMPLE.keys())
    table = {m3d.fingerprint(keys): {"name": "synthetic", "entries": entries}}
    monkeypatch.setattr(m3d._DATA, "geometry", table)
    return table


def test_the_plugin_loads_round_trips_and_validates(widths, geometry):
    check_loads(PLUGIN)
    check_round_trip(PLUGIN, _text(SAMPLE))
    check_validator(PLUGIN)


def test_source_and_translation_load_differently(widths, geometry):
    rules = check_loads(PLUGIN)
    source = {k: {x: y for x, y in v.items() if x != "ua"} for k, v in SAMPLE.items()}
    blocks, names = rules.load_data_from_json_obj(_text(source))
    assert blocks == [["Hello there", "Note"]], "the source role gives the original, the English"
    assert names == {"0": "synthetic"}
    blocks, _ = rules.load_data_from_json_obj(_text(SAMPLE))
    assert blocks == [["Привіт", ""]], "the translation role gives ua; an empty ua stays empty"


def test_an_unchanged_save_is_the_same_file_and_ua_goes_back_by_key(widths, geometry):
    rules = check_loads(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(_text(SAMPLE))
    assert rules.save_data_to_json_obj(blocks, names) == _text(SAMPLE)
    saved = json.loads(rules.save_data_to_json_obj([["Новий"]], names))
    assert list(saved) == SAMPLE_KEYS, "key order is kept"
    assert saved[SAMPLE_KEYS[0]]["ua"] == "Новий"
    assert saved[SAMPLE_KEYS[0]]["ru"] == "Привет", "ru and en are never changed"


def test_a_column_paragraph_that_needs_three_lines_is_a_line_problem(widths, geometry):
    # 54 px is the budget with slack: "аааа" is 40 px, "бббб вв" is 68.7 px, so the text takes three lines.
    entry = SAMPLE[SAMPLE_KEYS[0]]
    problems = m3d.layout.check_entry("аааа бббб вв", entry["ru"], entry, _geo(), widths)
    assert [name for name, _ in problems] == ["LINES"]


def test_one_word_wider_than_the_column_is_a_width_problem_with_the_pixels(widths, geometry):
    entry = SAMPLE[SAMPLE_KEYS[0]]
    problems = layout.check_entry("а" * 13, entry["ru"], entry, _geo(), widths)
    width = [message for name, message in problems if name == "WIDTH"]
    assert width and "line 1 is 76 px past the 50 px column" in width[0]


def test_changed_markers_are_reported_alone(widths, geometry):
    entry = SAMPLE[SAMPLE_KEYS[0]]
    problems = layout.check_entry("{s1|Нові} текст", "Нові текст", entry, _geo(), widths)
    assert [name for name, _ in problems] == ["MARKUP"]


def test_a_character_without_a_glyph_is_reported(widths, geometry):
    entry = SAMPLE[SAMPLE_KEYS[1]]
    problems = layout.check_entry("ок~", entry["ru"], entry, _geo(), widths)
    assert ("GLYPH", "no glyph for ['~']") in problems


def test_small_text_uses_the_pane_box_and_a_word_that_cannot_fit_is_reported(widths):
    small = layout.Geometry(part="small", font_size=24.0, char_space=0.0, lines=[layout.Line(20.0, 100.0)])
    problems = layout.check_entry("а" * 10, "", {"lines": 1, "width": 0}, small, widths)
    assert [name for name, _ in problems] == ["WORD"], "100 px cannot fit a 92 px pane (box less 8, edge 310)"


def test_an_empty_translation_has_no_problems(widths, geometry):
    assert layout.check_entry("", "Привет", SAMPLE[SAMPLE_KEYS[0]], _geo(), widths) == []


def test_the_editor_scan_gets_the_problem_ids_of_the_scanned_string(widths, geometry):
    rules = check_loads(PLUGIN)
    rules.load_data_from_json_obj(_text(SAMPLE))
    analyzer = rules.problem_analyzer
    analyzer._current_scan_block_idx = 0
    analyzer._current_scan_string_idx = 0
    found = analyzer.analyze_data_string("а" * 13, {}, 0)
    assert found == [{"M3D_WIDTH"}]


def _geo():
    return layout.Geometry(part="large", font_size=24.0, char_space=0.0,
                           lines=[layout.Line(10.0, 300.0), layout.Line(10.0, 300.0)])


@pytest.mark.skipif(romhacking_root.missing("_shared", "3ds_sysfont_ua", "repo_manual", "src", "manuals") is not None,
                    reason=romhacking_root.missing("_shared", "3ds_sysfont_ua", "repo_manual", "src", "manuals") or "")
def test_every_real_manual_file_has_its_geometry():
    folder = romhacking_root.path("_shared", "3ds_sysfont_ua", "repo_manual", "src", "manuals")
    rules = check_loads(PLUGIN)
    m3d._DATA.load()
    # browser and face_raiders have no dump on the owner's disk, so they have no geometry.
    no_dump = {"browser.json", "face_raiders.json"}
    for path in sorted(folder.glob("*.json")):
        text = path.read_text(encoding="utf-8")
        blocks, _ = rules.load_data_from_json_obj(text)
        assert blocks[0], path.name
        fp = m3d.fingerprint(list(json.loads(text).keys()))
        if path.name not in no_dump:
            assert fp in m3d._DATA.geometry, f"{path.name} has no geometry"


def test_the_build_budget_beats_the_stale_json_width(widths, monkeypatch):
    """The JSON width is a copy from extraction time; the geometry budget is the build's current number."""
    column = {"part": "large", "font_size": 24.0, "char_space": 0.0, "icon_widths": [],
              "lines": [[10.0, 300.0], [10.0, 300.0]], "budget": 200.0}
    keys = list(SAMPLE.keys())
    monkeypatch.setattr(m3d._DATA, "geometry", {m3d.fingerprint(keys): {"name": "s", "entries": {
        SAMPLE_KEYS[0]: column, SAMPLE_KEYS[1]: column}}})
    rules = check_loads(PLUGIN)
    rules.load_data_from_json_obj(_text(SAMPLE))
    # 13 letters = 130 px fit a 204 px column (budget 200 + slack), so no width problem.
    assert rules.manual_problems(0, 0, "а" * 13) == set()
