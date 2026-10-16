"""3DS electronic manual plugin: file load and save, the source and translation roles, the line model and problems.

The tests use a tiny synthetic manual and synthetic widths and geometry, installed on the plugin's own data holder.
The real-data check reads the owner's manual sources only when PICORIPI_ROMHACKING is set.
"""
import importlib.util
import json
import string
from collections import defaultdict
from pathlib import Path

import pytest

import romhacking_root
from core import formats
from plugins.manual_3ds import layout, repo_tools
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
    """Letters 10 units, digits 17, space 9 at the console's 25-unit em (9.6, 16.32 and 8.64 px at font size 24);
    no ink overhangs; `~` has no glyph."""
    advances = {ch: 10.0 for ch in string.ascii_letters + CYRILLIC}
    advances.update({digit: 17.0 for digit in string.digits}, **{" ": 9.0, "": 20.0})
    table = layout.Widths({"advances": advances, "homoglyphs": {}})
    monkeypatch.setattr(m3d._DATA, "widths", table)
    return table


@pytest.fixture
def geometry(monkeypatch):
    """A column paragraph of two lines, one pane each at x 10, box 300, page x 0."""
    column = {"part": "large", "font_size": 24.0, "char_space": 0.0, "icon_widths": [],
              "lines": [[[10.0, 300.0]], [[10.0, 300.0]]]}
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
    assert blocks == [["Привет", "Заметка"]], "the source role gives the original, the Russian"
    assert names == {"0": "synthetic"}
    with formats.translation_parse(rules):
        blocks, _ = rules.load_data_from_json_obj(_text(SAMPLE))
    assert blocks == [["Привіт", ""]], "the translation role gives ua; an empty ua stays empty"


def test_a_file_with_every_language_gives_russian_as_source_and_ukrainian_as_translation(widths, geometry):
    """Regression: a project that reads the owner's files in place parses the same en+ru+ua file for both columns.
    The original is the Russian even where the English is empty: the keys follow the Russian document."""
    rules = check_loads(PLUGIN)
    both = {SAMPLE_KEYS[0]: _entry(2, 50.0, "Hello there", "Привет", "Привіт"),
            SAMPLE_KEYS[1]: _entry(1, 300.0, "", "Заметка", "Нотатка")}
    original, _ = rules.load_data_from_json_obj(_text(both))
    with formats.translation_parse(rules):
        edited, _ = rules.load_data_from_json_obj(_text(both))
    assert original == [["Привет", "Заметка"]]
    assert edited == [["Привіт", "Нотатка"]]
    again, _ = rules.load_data_from_json_obj(_text(both))
    assert again == original, "the role goes back to source after the translation parse"


def test_english_pairs_with_the_russian_only_where_the_kinds_agree():
    """Page 3 of ar_games: the English layout lists a lone marker where the Russian has a sentence with a tag."""
    assert m3d.pairs_agree([("❺", "Нажмите {i0} во время игры")]) is False
    assert m3d.pairs_agree([("Press {i0} during play", "Нажмите {i0} во время игры"), ("❺", "❺")]) is True
    assert m3d.pairs_agree([("Press {s1|x}", "Нажмите {i0}")]) is False, "a different tag kind is a different paragraph"
    assert m3d.pairs_agree([("", "Заметка")]) is False, "a small-text key has no English: the page shows none"


def test_the_english_of_a_page_that_does_not_pair_is_left_out_of_the_reference(tmp_path, widths, geometry):
    """The reference file has the loaded file's key list (the match is by key list); page 001 does not pair."""
    rules = check_loads(PLUGIN)
    shifted = "large/Page_001_large_0"
    reference = {SAMPLE_KEYS[0]: _entry(2, 50.0, "Hello there", "Привет"),
                 SAMPLE_KEYS[1]: _entry(1, 300.0, "Note", "Заметка"),
                 f"{shifted}#0": _entry(1, 300.0, "❺", "Нажмите {i0} во время игры")}
    rules.load_data_from_json_obj(_text(reference))
    (tmp_path / "ref.json").write_text(_text(reference), encoding="utf-8")
    assert rules.get_reference_language_label() == "English (EN)"
    assert rules.load_reference_patch(str(tmp_path / "ref.json")) == {(0, 0): "Hello there", (0, 1): "Note"}


def test_an_unchanged_save_is_the_same_file_and_ua_goes_back_by_key(widths, geometry):
    rules = check_loads(PLUGIN)
    with formats.translation_parse(rules):
        blocks, names = rules.load_data_from_json_obj(_text(SAMPLE))
    assert rules.save_data_to_json_obj(blocks, names) == _text(SAMPLE)
    saved = json.loads(rules.save_data_to_json_obj([["Новий"]], names))
    assert list(saved) == SAMPLE_KEYS, "key order is kept"
    assert saved[SAMPLE_KEYS[0]]["ua"] == "Новий"
    assert saved[SAMPLE_KEYS[0]]["ru"] == "Привет", "ru and en are never changed"


def test_a_column_paragraph_that_needs_three_lines_is_a_line_problem(widths, geometry):
    # Three 288 px words: a line holds 319.5 px (the card edge from page x 0, less rounding room), so no two share one.
    entry = SAMPLE[SAMPLE_KEYS[0]]
    problems = m3d.layout.check_entry(" ".join(["а" * 30] * 3), entry["ru"], entry, _geo(), widths)
    assert [name for name, _ in problems] == ["LINES"]


def test_one_word_past_the_card_edge_is_a_width_problem_with_the_pixels(widths, geometry):
    # 34 letters: 326.4 px, one word on one line, from page x 0: 6.4 px past the 320 px card.
    entry = SAMPLE[SAMPLE_KEYS[0]]
    problems = layout.check_entry("а" * 34, entry["ru"], entry, _geo(), widths)
    assert [(name, message) for name, message in problems if name == "WIDTH"] == [("WIDTH", "line 1 runs 6 px past the card edge")]


def test_a_line_the_build_placed_narrower_than_the_console_draws_it_is_a_wrap_problem(widths):
    """The build widens a pane to the line it measured plus 2.5 px. A line it measured at 90 px keeps its 100 px
    box; the console draws the 16 letters at 153.6 px, more than the box less 2, so it breaks the line inside."""
    geo = layout.Geometry(part="small", font_size=24.0, char_space=0.0, lines=[layout.Line(10.0, 100.0, 10.0, 0.0, 20.0)])
    narrow = [[layout.Piece(style=0, text="а" * 16, x=10.0, width=90.0)]]
    problems = layout.console_problems(narrow, geo, widths, pane=True)
    assert [name for name, _ in problems] == ["WRAP"]
    assert problems[0][1] == "line 1 is 154 px in a 100 px pane; the console breaks it inside"
    # The same line measured as the console does gets a 156.1 px box and is not broken.
    measured = [[layout.Piece(style=0, text="а" * 16, x=10.0, width=153.6)]]
    assert layout.console_problems(measured, geo, widths, pane=True) == []


def test_a_sub_pixel_overrun_is_not_a_width_problem(widths):
    """33 letters are 316.8 px. From page x 3.6 they end 320.4 px: 0.4 px past the card edge, which the console
    rounds away. From 4.1 they end 320.9 px: past."""
    def problems(abs_x):
        geo = layout.Geometry(part="large", font_size=24.0, char_space=0.0, lines=[layout.Line(0.0, 300.0, abs_x)])
        return [name for name, _ in layout.check_entry("а" * 33, "", {"lines": 1}, geo, widths)]
    assert problems(3.6) == []
    assert problems(4.1) == ["WIDTH"]


def test_a_glyph_pane_the_translation_leaves_out_stays_in_its_pane(widths):
    """A button glyph in a pane of its own (manual.mark_panes_out): the translation need not carry it, and the pane
    is no line of the layout. Carrying it is an ICON problem."""
    glyph = ""
    rows = [[layout.Line(10.0, 20.0, 10.0, 0.0, 20.0, mark=glyph), layout.Line(40.0, 260.0, 40.0, 0.0, 20.0)],
            [layout.Line(10.0, 300.0, 10.0, -20.0, 20.0)]]
    geo = layout.Geometry(part="small", font_size=24.0, char_space=0.0, lines=rows)
    ru = f"{glyph} Нажмите"
    kept = geo.marks_out("Натисніть")
    assert kept.kept_marks == glyph and kept.lines[0].x == 40.0 and kept.pane_counts == {0: 2}
    assert layout.check_entry("Натисніть", ru, {"lines": 2}, geo, widths) == []
    # A glyph the translation carries is laid out in the text, on the panes as they are: no mark is kept.
    assert geo.marks_out(f"{glyph} Натисніть") is geo
    assert layout.check_entry(f"{glyph} Натисніть", ru, {"lines": 2}, geo, widths) == []


def test_a_kept_glyph_pane_must_not_be_repeated_in_the_translation():
    glyph = ""
    assert layout.icon_problems(f"Натисніть {glyph}", f"{glyph} Нажмите", kept=glyph) == (
        "button glyph U+E000 is drawn in its own pane and must not be in the translation")
    assert layout.icon_problems("Натисніть", f"{glyph} Нажмите", kept=glyph) == ""


def test_changed_markers_are_reported_alone(widths, geometry):
    entry = SAMPLE[SAMPLE_KEYS[0]]
    problems = layout.check_entry("{s1|Нові} текст", "Нові текст", entry, _geo(), widths)
    assert [name for name, _ in problems] == ["MARKUP"]


def test_a_character_without_a_glyph_is_reported(widths, geometry):
    entry = SAMPLE[SAMPLE_KEYS[1]]
    problems = layout.check_entry("ок~", entry["ru"], entry, _geo(), widths)
    assert ("GLYPH", "no glyph for ['~']") in problems


def test_small_text_ends_by_the_card_edge_and_a_word_that_cannot_is_reported(widths):
    # A pane at page x 250 has 70 px to the card edge: ten letters (96 px) cannot fit, so the paragraph is shown on
    # the column instead (WORD), where the word still ends 26 px past the card (WIDTH).
    small = layout.Geometry(part="small", font_size=24.0, char_space=0.0, lines=[layout.Line(20.0, 100.0, 250.0)])
    problems = layout.check_entry("а" * 10, "", {"lines": 1, "width": 0}, small, widths)
    assert [name for name, _ in problems] == ["WORD", "WIDTH"]
    assert small.edge_width(small.lines[0]) == 70.0
    # A right-aligned pane (text_align 3) whose box ends inside the card has no width limit from the card edge.
    right = layout.Line(20.0, 100.0, 200.0, text_align=3)
    assert small.edge_width(right) == float("inf")


def test_an_empty_translation_has_no_problems(widths, geometry):
    assert layout.check_entry("", "Привет", SAMPLE[SAMPLE_KEYS[0]], _geo(), widths) == []


def test_the_editor_scan_gets_the_problem_ids_of_the_scanned_string(widths, geometry):
    rules = check_loads(PLUGIN)
    rules.load_data_from_json_obj(_text(SAMPLE))
    analyzer = rules.problem_analyzer
    analyzer._current_scan_block_idx = 0
    analyzer._current_scan_string_idx = 0
    found = analyzer.analyze_data_string("а" * 34, {}, 0)
    assert found == [{"M3D_WIDTH"}]


def test_the_problem_detail_is_the_layout_message_of_the_last_analysed_text(widths, geometry):
    rules = check_loads(PLUGIN)
    rules.load_data_from_json_obj(_text(SAMPLE))
    rules.manual_problems(0, 0, "а" * 34)
    assert rules.get_problem_detail(0, 0, "M3D_WIDTH") == "line 1 runs 6 px past the card edge"
    assert rules.get_problem_detail(0, 0, "M3D_LINES") == ""
    rules.manual_problems(0, 0, "а")
    assert rules.get_problem_detail(0, 0, "M3D_WIDTH") == ""


def _panes_geo(rows):
    """rows: the styles of the text panes of each line."""
    return layout.Geometry(part="large", font_size=24.0, char_space=0.0,
                           lines=[[layout.Line(10.0, 300.0, style=style) for style in row] for row in rows])


def test_a_highlight_with_no_pane_of_its_style_is_out_of_panes(widths):
    entry = {"lines": 2, "width": 300.0}
    text = "Привет {s1|там}"
    problems = layout.check_entry(text, text, entry, _panes_geo([[0], [0]]), widths)
    assert ("PANES", "out of panes for style 1 (the original has 0)") in problems


def test_the_paragraph_style_and_a_highlight_each_with_a_pane_is_fine(widths):
    entry = {"lines": 2, "width": 300.0}
    text = "Привет {s1|там}"
    problems = layout.check_entry(text, text, entry, _panes_geo([[0, 1], [0]]), widths)
    assert not [name for name, _ in problems if name == "PANES"]


def test_neighbours_of_one_style_share_a_pane_and_an_icon_ends_the_sharing(widths):
    pieces = [[layout.Piece(style=0, text="a"), layout.Piece(style=0, text="b")],
              [layout.Piece(style=0, text="c"), layout.Piece(style=-1, icon=0), layout.Piece(style=0, text="d")]]
    # line 1: "a b" is one pane; line 2: "c" is one pane, the icon ends it, "d" is a third pane
    assert layout.pane_overflow(pieces, {0: 3}) is None
    assert layout.pane_overflow(pieces, {0: 2}) == (0, 2)


def _geo():
    return layout.Geometry(part="large", font_size=24.0, char_space=0.0,
                           lines=[layout.Line(10.0, 300.0), layout.Line(10.0, 300.0)])


@pytest.mark.skipif(romhacking_root.missing("_shared", "3ds_sysfont_ua", "repo_manual", "src", "manuals") is not None,
                    reason=romhacking_root.missing("_shared", "3ds_sysfont_ua", "repo_manual", "src", "manuals") or "")
def test_every_real_manual_file_has_its_geometry():
    folder = romhacking_root.path("_shared", "3ds_sysfont_ua", "repo_manual", "src", "manuals")
    rules = check_loads(PLUGIN)
    m3d._DATA.load()
    # browser has no dump on the owner's disk, so it has no geometry.
    no_dump = {"browser.json"}
    for path in sorted(folder.glob("*.json")):
        text = path.read_text(encoding="utf-8")
        blocks, _ = rules.load_data_from_json_obj(text)
        assert blocks[0], path.name
        fp = m3d.fingerprint(list(json.loads(text).keys()))
        if path.name not in no_dump:
            assert fp in m3d._DATA.geometry, f"{path.name} has no geometry"


def test_the_column_is_laid_out_to_the_card_edge_not_the_budget(widths, monkeypatch):
    """The budget (Nintendo's widest line) is only shown by the preview; the build lays the lines out to the card."""
    column = {"part": "large", "font_size": 24.0, "char_space": 0.0, "icon_widths": [],
              "lines": [[[10.0, 300.0]], [[10.0, 300.0]]], "budget": 100.0}
    keys = list(SAMPLE.keys())
    monkeypatch.setattr(m3d._DATA, "geometry", {m3d.fingerprint(keys): {"name": "s", "entries": {
        SAMPLE_KEYS[0]: column, SAMPLE_KEYS[1]: column}}})
    rules = check_loads(PLUGIN)
    rules.load_data_from_json_obj(_text(SAMPLE))
    # 20 letters are 192 px: past the 100 px budget, inside the card, on one line.
    assert rules.manual_problems(0, 0, "а" * 20) == set()
    assert rules.preview_budget(0, SAMPLE_KEYS[0]) == 100.0


def _geo_on(occluders, lines, part="large", budget=300.0):
    return layout.Geometry(part=part, font_size=24.0, char_space=0.0, lines=lines, budget=budget,
                           occluders=occluders)


def test_a_picture_to_the_right_of_the_line_ends_it_before_its_left_edge():
    geo = _geo_on([layout.Occluder("pic1", 200.0, 0.0, 80.0, 60.0)], [layout.Line(10.0, 300.0, 10.0, 0.0, 20.0)])
    assert geo.right_limit(0) == 200.0 - layout.OCC_MARGIN


def test_a_picture_in_another_line_band_is_not_in_the_way():
    geo = _geo_on([layout.Occluder("pic1", 200.0, -200.0, 80.0, 60.0)], [layout.Line(10.0, 300.0, 10.0, 0.0, 20.0)])
    assert geo.right_limit(0) == float("inf")


def test_a_box_frame_the_line_starts_in_ends_it_inside_its_right_edge():
    box = layout.Occluder("wnd1", 8.0, 40.0, 304.0, 345.0)
    geo = _geo_on([box], [layout.Line(20.0, 200.0, 40.0, 0.0, 20.0)])
    assert geo.right_limit(0) == 8.0 + 304.0 - layout.FRAME_MARGIN
    # With the painted width of the frame known, the inner edge is the right edge less that width (Nintendo's 4 px
    # box frames paint 2 columns); a frame that paints nothing is no edge at all.
    painted = layout.Occluder("wnd1", 8.0, 40.0, 304.0, 345.0, frame_width=2.0)
    wide = layout.Occluder("wnd1", 8.0, 40.0, 304.0, 345.0, frame_width=18.0)
    clear = layout.Occluder("wnd1", 8.0, 40.0, 304.0, 345.0, frame_width=0.0)
    assert _geo_on([painted], geo.lines).right_limit(0) == 8.0 + 304.0 - 2.0
    assert _geo_on([wide], geo.lines).right_limit(0, 0.0, layout.FRAME_INNER) == 8.0 + 304.0 - 18.0
    assert _geo_on([clear], geo.lines).right_limit(0) == float("inf")


def test_a_small_frame_is_not_a_box():
    frame = layout.Occluder("wnd1", 8.0, 40.0, 60.0, 30.0)
    geo = _geo_on([frame], [layout.Line(20.0, 200.0, 40.0, 0.0, 20.0)])
    assert geo.right_limit(0) == float("inf")


def test_room_is_measured_from_the_start_of_the_line():
    geo = _geo_on([layout.Occluder("pic1", 200.0, 0.0, 80.0, 60.0)], [layout.Line(10.0, 300.0, 10.0, 0.0, 20.0)])
    assert geo.room(0, pane=False) == 200.0 - layout.OCC_MARGIN - 10.0


def test_a_picture_beside_a_pane_line_makes_its_words_wrap_sooner(widths):
    lines = [layout.Line(20.0, 200.0, 20.0, 0.0, 20.0), layout.Line(20.0, 200.0, 20.0, -20.0, 20.0)]
    text = "аааа аааа"  # two 38.4 px words: 85.4 px on one line with 300 to the card edge, 76 px allowed beside the picture
    free = layout.Geometry(part="small", font_size=24.0, char_space=0.0, lines=lines)
    beside = layout.Geometry(part="small", font_size=24.0, char_space=0.0, lines=lines,
                             occluders=[layout.Occluder("pic1", 100.0, 0.0, 80.0, 60.0)])
    one, _, _ = layout.layout_for(text, free, widths)
    two, _, _ = layout.layout_for(text, beside, widths)
    assert len(one) == 1 and len(two) == 2


def test_a_column_line_that_runs_into_a_picture_is_a_beside_problem(widths):
    geo = _geo_on([layout.Occluder("pic1", 100.0, 0.0, 80.0, 60.0)], [layout.Line(10.0, 300.0, 10.0, 0.0, 20.0)])
    problems = layout.check_entry("а" * 12, "а" * 12, {"lines": 1, "width": 300.0}, geo, widths)
    # 12 letters are 115.2 px on the console from x 10; the picture's edge is at 100.
    assert ("BESIDE", "line 1 runs 25 px into the picture or frame") in problems
    # The advance ends 125.2 px, 1.2 px into a picture at 124; the last glyph's ink ends 1.92 px (2 units) before
    # its advance, so with the overhangs known the line stays clear.
    inked = layout.Widths({"advances": widths.advances, "overhangs": {"а": 2.0}})
    geo = _geo_on([layout.Occluder("pic1", 124.0, 0.0, 80.0, 60.0)], [layout.Line(10.0, 300.0, 10.0, 0.0, 20.0)])
    assert layout.check_entry("а" * 12, "а" * 12, {"lines": 1, "width": 300.0}, geo, inked) == []
    assert [name for name, _ in layout.check_entry("а" * 12, "а" * 12, {"lines": 1, "width": 300.0}, geo, widths)] == ["BESIDE"]


def test_a_dropped_button_glyph_is_an_icon_problem():
    assert layout.icon_problems("Натисніть і", "Нажмите  и ") != ""


def test_kept_button_glyphs_are_not_reported():
    assert layout.icon_problems("Натисніть  і ", "Нажмите  и ") == ""


def test_the_english_source_is_the_glyph_source_when_russian_is_empty(widths):
    problems = layout.check_entry("Натисніть", "", {"en": "Press  now"}, None, widths)
    assert [name for name, _ in problems] == ["ICON"]


_REPO_MANUAL = ("_shared", "3ds_sysfont_ua", "repo_manual")
_GATE = romhacking_root.missing(*_REPO_MANUAL, "tools", "manual.py")
# The owner's gate message -> the plugin's problem name (manual.py check output, one line per problem).
_OWNER_KINDS = (
    ("button glyphs", "ICON"), ("markers ", "MARKUP"), ("missing glyphs", "GLYPH"),
    ("WIDTH beside picture", "BESIDE"), ("out of panes", "PANES"), ("needs ", "LINES"),
    ("Russian letters", "STYLE"), ("double space", "STYLE"), ("leading or trailing", "STYLE"),
    ("mixed Latin", "STYLE"), ("лице", "STYLE"), ("page reference", "STYLE"),
)


def _owner_kind(message):
    body = message.split(": ", 1)[1]
    return next((kind for needle, kind in _OWNER_KINDS if needle in body), "OTHER")


def _builder():
    builder_path = Path(m3d.__file__).parents[2] / "scripts" / "build_manual_geometry.py"
    spec = importlib.util.spec_from_file_location("build_manual_geometry", builder_path)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder


def _owner_tools():
    return repo_tools.load_tools(str(romhacking_root.path(*_REPO_MANUAL)))


def _require_geometry_from_owner_head(tools):
    """One clear failure when the owner's tools moved on since geometry.json was built (not an assertion diff)."""
    head = repo_tools.owner_commit(tools.root)
    built = json.loads(Path(m3d._DATA_DIR, "geometry.json").read_text(encoding="utf-8")).get("owner_commit", "")
    if head != built:
        pytest.fail(f"owner tools at {head or 'an unknown commit (not a git checkout)'}, "
                    f"geometry built from {built or 'an unknown commit'}: run scripts/build_manual_geometry.py")


@pytest.mark.parametrize("head", ["1111111", ""])
def test_geometry_from_other_owner_tools_fails_with_one_message(monkeypatch, head):
    from types import SimpleNamespace

    monkeypatch.setattr(repo_tools, "owner_commit", lambda root: head)
    built = json.loads(Path(m3d._DATA_DIR, "geometry.json").read_text(encoding="utf-8"))["owner_commit"]
    shown = head or "an unknown commit (not a git checkout)"
    with pytest.raises(pytest.fail.Exception) as stop:
        _require_geometry_from_owner_head(SimpleNamespace(root="folder"))
    assert str(stop.value) == (f"owner tools at {shown}, geometry built from {built}: "
                               "run scripts/build_manual_geometry.py")


@pytest.mark.skipif(_GATE is not None, reason=_GATE or "")
def test_the_geometry_file_is_the_build_of_the_owners_dumps():
    tools = _owner_tools()
    _require_geometry_from_owner_head(tools)
    committed = json.loads(Path(m3d._DATA_DIR, "geometry.json").read_text(encoding="utf-8"))
    assert _builder().build(tools) == committed["manuals"]


@pytest.mark.skipif(_GATE is not None, reason=_GATE or "")
def test_the_widths_file_is_the_build_of_the_owners_tools():
    tools = _owner_tools()
    _require_geometry_from_owner_head(tools)
    committed = json.loads(Path(m3d._DATA_DIR, "widths.json").read_text(encoding="utf-8"))
    assert _builder().build_widths(tools) == committed


@pytest.mark.skipif(_GATE is not None, reason=_GATE or "")
def test_the_problems_match_the_owners_gate_on_every_dumped_manual():
    tools = _owner_tools()
    _require_geometry_from_owner_head(tools)
    owner = tools.manual
    m3d._DATA.load()
    differences = []
    for name in owner.MANUALS:
        try:
            repo_tools.manual_path(tools, name)
        except repo_tools.ToolsError:
            continue  # no dump on this disk
        problems, _wide, _, _ = owner._problems(name)
        expected = defaultdict(set)
        for message in problems:
            kind = _owner_kind(message)
            # The gate measures lines against pictures with its own model (/24, no charSpace, 4 and 5 px margins);
            # the plugin measures them as the console draws them (BESIDE, WIDTH, WRAP), so only the gate's
            # text and pane failures are compared.
            if kind != "BESIDE":
                expected[message.split(": ", 1)[0]].add(kind)
        doc = owner.load_json(name)
        _, geometry = m3d._geometry_for(doc, layout.fingerprint(list(doc)))
        for key, entry in doc.items():
            if not entry.get("ua"):
                continue
            found = {kind for kind, _ in layout.check_entry(entry["ua"], entry.get("ru", ""), entry,
                                                              geometry.get(key), m3d._DATA.widths)}
            # WORD is the plugin's own rule: a small paragraph the pane model cannot fit is shown on the column
            # and reported here. The gate lays it out on the column and only records it, so it is not compared.
            found -= {"WORD", "WIDTH", "BESIDE", "WRAP"}
            if found != expected.get(key, set()):
                differences.append((name, key, sorted(expected.get(key, set())), sorted(found)))
    assert differences == []


# Console screenshots of the home menu manual (the owner's tests/test_manual_checks.py): the translated line must
# stop short of the picture or frame beside it. The text is the owner's translation, read from the owner's folder.
_HOME_MENU_KEYS = (
    "small/Page_006_small_0#4",    # lines stay left of the picture (page 7)
    "small/Page_009_small_0#19",   # lines stay left of the picture
    "small/Page_020_small_0#13",   # stays inside the blue frame (page 21)
)


@pytest.mark.skipif(_GATE is not None, reason=_GATE or "")
@pytest.mark.parametrize("key", _HOME_MENU_KEYS)
def test_home_menu_line_keeps_off_the_picture_or_frame_beside_it(key):
    tools = _owner_tools()
    _require_geometry_from_owner_head(tools)
    m3d._DATA.load()
    doc = tools.manual.load_json("home_menu_manual")
    entry = doc[key]
    assert entry.get("ua"), f"{key} has no translation in home_menu_manual.json"
    _, geometry = m3d._geometry_for(doc, layout.fingerprint(list(doc)))
    assert geometry[key].occluders, f"{key}: the page's pictures and frames are missing from the geometry"
    problems = layout.check_entry(entry["ua"], entry.get("ru", ""), entry, geometry[key], m3d._DATA.widths)
    assert [message for name, message in problems if name == "BESIDE"] == []


# -- the render's problems in the editor scan -------------------------------------------------------


class _FakeRender:
    """page_build.page_kinds stand-in: records its calls, answers with fixed kinds (detail "d") for a string."""

    def __init__(self, kinds, error=None):
        self.calls = []
        self.kinds = kinds
        self.error = error

    def __call__(self, tools, manual_name, part, page, texts, budgets):
        self.calls.append((manual_name, part, page, dict(texts)))
        if self.error is not None:
            raise self.error
        return {key: {kind: f"{kind} d" for kind in found} for key, found in self.kinds.items()}, {}


def _rules_with_render(monkeypatch, kinds):
    monkeypatch.setattr(m3d.page_build, "load_folder", lambda: "repo")
    monkeypatch.setattr(m3d.repo_tools, "load_tools", lambda root: object())
    render = _FakeRender(kinds)
    monkeypatch.setattr(m3d.page_build, "page_kinds", render)
    rules = check_loads(PLUGIN)
    rules.load_data_from_json_obj(_text(SAMPLE))
    return rules, render


def test_the_render_problems_of_the_page_reach_the_strings_that_own_them(widths, geometry, monkeypatch):
    """A page is built from every current text on it and judged once; its render-only defects (a label leaving its
    cell, two paragraphs' ink meeting, a line painted over) are the editor problems of the strings that own them."""
    rules, render = _rules_with_render(monkeypatch, {SAMPLE_KEYS[0]: {"over_cell", "text_overlap"}, SAMPLE_KEYS[1]: {"covered"}})
    assert rules.manual_problems(0, 0, "Привіт") == {"M3D_CELL", "M3D_OVERLAP"}
    assert rules.get_problem_detail(0, 0, "M3D_CELL") == "over_cell d"
    assert rules.manual_problems(0, 1, "") == {"M3D_COVERED"}
    assert render.calls == [("synthetic", "large", 0, {SAMPLE_KEYS[0]: "Привіт", SAMPLE_KEYS[1]: ""})]
    # The same texts again: the page is not rendered again. A changed text renders it once more.
    rules.manual_problems(0, 0, "Привіт")
    assert len(render.calls) == 1
    rules._manuals[0].doc[SAMPLE_KEYS[1]]["ua"] = "Нотатка"
    rules.manual_problems(0, 1, "Нотатка")
    assert len(render.calls) == 2 and render.calls[1][3][SAMPLE_KEYS[1]] == "Нотатка"


def test_a_page_without_a_translation_is_not_rendered(widths, geometry, monkeypatch):
    rules, render = _rules_with_render(monkeypatch, {SAMPLE_KEYS[0]: {"over_cell"}})
    for entry in rules._manuals[0].doc.values():
        entry["ua"] = ""
    assert rules.manual_problems(0, 0, "") == set()
    assert render.calls == []


def test_a_page_the_tools_cannot_draw_is_cached_as_drawn_and_not_tried_again(widths, geometry, monkeypatch):
    """A failing render leaves no render problems and is not repeated for the same texts (so a background render
    and the host's rescan never chase each other); the folder setting is read from disk once."""
    reads = []
    rules, render = _rules_with_render(monkeypatch, {SAMPLE_KEYS[0]: {"over_cell"}})
    render.error = RuntimeError("no font")
    monkeypatch.setattr(m3d.page_build, "load_folder", lambda: reads.append(1) or "repo")
    first = rules.manual_problems(0, 0, "Привіт")
    second = rules.manual_problems(0, 0, "Привіт")
    assert (first, second, len(render.calls), len(reads)) == (set(), set(), 1, 1)


class _Scanner:
    def __init__(self):
        self.rescanned = []

    def rescan_issues_for_single_block(self, block, show_message_on_completion=True, use_default_mappings=True):
        import threading

        assert threading.current_thread() is threading.main_thread(), 'the rescan must run on the UI thread'
        self.rescanned.append(block)


def _ui_thread_rules(monkeypatch, kinds):
    from types import SimpleNamespace
    from utils import app_mode

    monkeypatch.setattr(app_mode, "headless", False)
    rules, render = _rules_with_render(monkeypatch, kinds)
    rules.mw = SimpleNamespace(issue_scan_handler=_Scanner())
    return rules, render


def test_on_the_ui_thread_the_page_renders_in_the_background_and_the_block_is_rescanned(qtbot, widths, geometry, monkeypatch):
    """The whole-project scan runs on the UI thread: there the render is only scheduled on a WorkerThread (known to
    the exit registry), and when it is done the host rescans the block through the queued signal (then the scan reads
    the page cache)."""
    from utils import thread_utils

    rules, render = _ui_thread_rules(monkeypatch, {SAMPLE_KEYS[0]: {"over_cell"}})
    assert rules.manual_problems(0, 0, "Привіт") == set()   # scheduled, not rendered here
    worker = rules._render_worker
    assert worker is not None and (worker in thread_utils._running or worker.isFinished())
    rules.manual_problems(0, 1, "")   # the same block again: not a second render
    qtbot.waitUntil(lambda: rules.mw.issue_scan_handler.rescanned == [0], timeout=10000)
    assert rules._render_worker is None and len(render.calls) == 1
    assert rules._page_problems[(0, m3d.group_key_of(PAGE))][1] == {SAMPLE_KEYS[0]: {"M3D_CELL": "over_cell d"}}
    assert rules.manual_problems(0, 0, "Привіт") == {"M3D_CELL"}
    worker.wait(5000)


def test_stopping_the_scan_render_drops_its_result_and_rescans_nothing(qtbot, widths, geometry, monkeypatch):
    """A plugin switch or window close (the preview panel's shutdown) interrupts the render: the page it was drawing
    is not cached as judged and the block is not rescanned."""
    import threading

    rules, render = _ui_thread_rules(monkeypatch, {SAMPLE_KEYS[0]: {"over_cell"}})
    started, release = threading.Event(), threading.Event()
    inner = render.__call__

    def slow(*args):
        started.set()
        release.wait(5)
        return inner(*args)

    monkeypatch.setattr(m3d.page_build, "page_kinds", slow)
    rules.manual_problems(0, 0, "Привіт")
    worker = rules._render_worker
    assert started.wait(5)
    threading.Timer(0.1, release.set).start()
    rules.stop_scan_render()
    assert worker.isFinished() and rules._render_worker is None
    qtbot.wait(50)
    assert rules._page_problems == {} and rules.mw.issue_scan_handler.rescanned == []


def test_a_folder_without_the_tools_leaves_the_render_problems_out(widths, geometry, monkeypatch):
    monkeypatch.setattr(m3d.page_build, "load_folder", lambda: "nowhere")
    rules = check_loads(PLUGIN)
    rules.load_data_from_json_obj(_text(SAMPLE))
    assert rules.manual_problems(0, 0, "Привіт") == set()


_CAND = "cand_r19"


@pytest.mark.skipif(_GATE is not None, reason=_GATE or "")
@pytest.mark.parametrize("name", ["home_menu_manual", "system_settings", "camera", "browser_n3ds", "mii_plaza", "eshop",
                                  "friend_list_n3ds", "health_safety_n3ds", "sound", "face_raiders"])
def test_the_editor_scan_flags_what_the_render_of_the_built_manual_flags(name, monkeypatch):
    """The gate: on the sources of tmp/cand_r19 the scan flags the same strings with the same render problems as
    simulator.page_defects on the built archive (the preview build is byte-identical to the owner's build), and the
    untouched original (no translation) flags nothing."""
    from plugins.manual_3ds import page_build, simulator

    tools = _owner_tools()
    _require_geometry_from_owner_head(tools)
    build = tools.root / "tmp" / _CAND
    if not build.is_dir():
        pytest.skip(f"no {build}")
    sim = simulator.Simulator(str(tools.root), build, None)
    if name not in sim.files:
        pytest.skip(f"{name} is not in {build}")
    monkeypatch.setattr(page_build, "load_folder", lambda: str(tools.root))
    doc = tools.manual.load_json(name)
    rules = check_loads(PLUGIN)
    rules.load_data_from_json_obj(_text(doc))
    assert rules._manuals[0].resolved().name == name
    flows = page_build.flows_of(tools, name)
    manual = sim.manual(name)
    expected = {}
    for size in ("small", "large"):
        for page in manual.pages(size):
            owners = {pane.name: f"{size}/Page_{page:03d}_{size}_{index}#{position}"
                      for flow_key, page_flows in flows.items() if flow_key.startswith(f"{size}/Page_{page:03d}_")
                      for position, flow in enumerate(page_flows) for pane in flow.panes
                      for index in [int(flow_key.rsplit("_", 1)[1])]}
            for defect in simulator.find_defects(sim, name, page, size):
                if defect.kind in m3d.RENDER_IDS and defect.pane in owners:
                    expected.setdefault(owners[defect.pane], set()).add(m3d.RENDER_IDS[defect.kind])
    found = {}
    for index, key in enumerate(doc):
        ids = {pid for pid in rules.manual_problems(0, index, str(doc[key].get("ua", ""))) if pid in m3d.RENDER_IDS.values()}
        if ids:
            found[key] = ids
    assert found == expected
    untouched = {key: {k: v for k, v in entry.items() if k != "ua"} for key, entry in doc.items()}
    plain = check_loads(PLUGIN)
    plain.load_data_from_json_obj(_text(untouched))
    assert all(not {pid for pid in plain.manual_problems(0, index, "") if pid in m3d.RENDER_IDS.values()}
               for index in range(len(untouched)))
