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


def test_the_problem_detail_is_the_layout_message_of_the_last_analysed_text(widths, geometry):
    rules = check_loads(PLUGIN)
    rules.load_data_from_json_obj(_text(SAMPLE))
    rules.manual_problems(0, 0, "а" * 13)
    assert rules.get_problem_detail(0, 0, "M3D_WIDTH") == "line 1 is 76 px past the 50 px column"
    assert rules.get_problem_detail(0, 0, "M3D_LINES") == ""
    rules.manual_problems(0, 0, "а")
    assert rules.get_problem_detail(0, 0, "M3D_WIDTH") == ""


def _panes_geo(panes):
    return layout.Geometry(part="large", font_size=24.0, char_space=0.0,
                           lines=[layout.Line(10.0, 300.0), layout.Line(10.0, 300.0)], panes=panes)


def test_a_highlight_with_no_pane_of_its_style_is_out_of_panes(widths):
    entry = {"lines": 2, "width": 300.0}
    text = "Привет {s1|там}"
    problems = layout.check_entry(text, text, entry, _panes_geo({0: 1}), widths)
    assert ("PANES", "out of panes for style 1 (the original has 0)") in problems


def test_the_paragraph_style_and_a_highlight_each_with_a_pane_is_fine(widths):
    entry = {"lines": 2, "width": 300.0}
    text = "Привет {s1|там}"
    problems = layout.check_entry(text, text, entry, _panes_geo({0: 1, 1: 1}), widths)
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


def test_a_small_frame_is_not_a_box():
    frame = layout.Occluder("wnd1", 8.0, 40.0, 60.0, 30.0)
    geo = _geo_on([frame], [layout.Line(20.0, 200.0, 40.0, 0.0, 20.0)])
    assert geo.right_limit(0) == float("inf")


def test_room_is_measured_from_the_start_of_the_line():
    geo = _geo_on([layout.Occluder("pic1", 200.0, 0.0, 80.0, 60.0)], [layout.Line(10.0, 300.0, 10.0, 0.0, 20.0)])
    assert geo.room(0, pane=False) == 200.0 - layout.OCC_MARGIN - 10.0


def test_a_picture_beside_a_pane_line_makes_its_words_wrap_sooner(widths):
    lines = [layout.Line(20.0, 200.0, 20.0, 0.0, 20.0), layout.Line(20.0, 200.0, 20.0, -20.0, 20.0)]
    text = "аааа аааа"  # two 40 px words: 108.7 px on one line with the box, 76 px allowed beside the picture
    free = layout.Geometry(part="small", font_size=24.0, char_space=0.0, lines=lines)
    beside = layout.Geometry(part="small", font_size=24.0, char_space=0.0, lines=lines,
                             occluders=[layout.Occluder("pic1", 100.0, 0.0, 80.0, 60.0)])
    one, _, _ = layout.layout_for(text, free, 300.0, widths, 2)
    two, _, _ = layout.layout_for(text, beside, 300.0, widths, 2)
    assert len(one) == 1 and len(two) == 2


def test_a_column_line_that_runs_into_a_picture_is_a_beside_problem(widths):
    geo = _geo_on([layout.Occluder("pic1", 100.0, 0.0, 80.0, 60.0)], [layout.Line(10.0, 300.0, 10.0, 0.0, 20.0)])
    problems = layout.check_entry("а" * 12, "а" * 12, {"lines": 1, "width": 300.0}, geo, widths)
    assert ("BESIDE", "line 1 runs 34 px into the picture or frame") in problems


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
        problems, wide, _, _ = owner._problems(name)
        expected = defaultdict(set)
        for message in problems:
            expected[message.split(": ", 1)[0]].add(_owner_kind(message))
        for message in wide:
            expected[message.split(": ", 1)[0]].add("WIDTH")
        doc = owner.load_json(name)
        _, geometry = m3d._geometry_for(doc, layout.fingerprint(list(doc)))
        for key, entry in doc.items():
            if not entry.get("ua"):
                continue
            found = {kind for kind, _ in layout.check_entry(entry["ua"], entry.get("ru", ""), entry,
                                                              geometry.get(key), m3d._DATA.widths)}
            # WORD is the plugin's own rule: a small paragraph the pane model cannot fit is shown on the column
            # and reported here. The gate lays it out on the column and only records it, so it is not compared.
            found.discard("WORD")
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
