import pytest
from unittest.mock import MagicMock, patch
from plugins.zelda_mc.rules import GameRules

@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.data_store = mw
    mw.line_width_warning_threshold_pixels = 200
    mw.font_map = {}
    mw.show_multiple_spaces_as_dots = False
    mw.newline_display_symbol = "↵"
    mw.default_tag_mappings = {"[E]": "{O}"}
    mw.EDITOR_PLAYER_TAG = "[P]"
    mw.ORIGINAL_PLAYER_TAG = "{PLAYER}"
    mw.tag_color_rgba = "#FF8C00"
    mw.tag_bold = True
    mw.tag_italic = False
    mw.tag_underline = False
    mw.newline_color_rgba = "#A020F0"
    mw.newline_bold = True
    mw.newline_italic = False
    mw.newline_underline = False
    mw.edited_text_edit = None
    return mw

@pytest.fixture
def rules(mock_mw):
    return GameRules(mock_mw)

def test_ZeldaMC_display_name(rules):
    assert "Minish Cap" in rules.get_display_name()

def test_ZeldaMC_tag_mappings(rules):
    mappings = rules.get_default_tag_mappings()
    assert mappings["[E]"] == "{O}"
    assert mappings["[P]"] == "{PLAYER}"

def test_ZeldaMC_tag_legitimacy(rules):
    # MC tags are usually {TAG} but plugin might support others
    # Let's check TagManager logic via rules
    assert rules.is_tag_legitimate("{Color:01}") is True
    assert rules.is_tag_legitimate("[Invalid]") is True # ZMC uses {} usually

def test_ZeldaMC_short_problem_names(rules):
    assert rules.get_short_problem_name("ZMC_WIDTH_EXCEEDED") == "Width"
    assert rules.get_short_problem_name("ZMC_SHORT_LINE") == "Short"

@patch('plugins.zelda_mc.problem_analyzer.calculate_string_width', return_value=100)
def test_ZeldaMC_analyze_subline(mock_calc, rules):
    # Testing analyze_subline delegation
    problems = rules.analyze_subline("test", None, 0, 0, True, {}, 200, "test")
    assert isinstance(problems, set)

def test_ZeldaMC_color_marker_definitions(rules):
    defs = rules.get_color_marker_definitions()
    assert isinstance(defs, dict)
    assert len(defs) > 0

@patch('plugins.common.problem_analyzer.calculate_string_width', return_value=250)
def test_ZeldaMC_analyze_subline_with_logical_limit(mock_calc, rules):
    # Width (250) exceeds editor threshold (200), but is less than logical limit (300)
    problems = rules.analyze_subline("test", None, 0, 0, True, {}, 200, "test", logical_hard_limit=300)
    # Since logical_hard_limit is 300 and width is 250, ZMC_WIDTH_EXCEEDED should NOT be triggered
    assert "ZMC_WIDTH_EXCEEDED" not in problems

@patch('plugins.common.problem_analyzer.calculate_string_width', return_value=250)
def test_ZeldaMC_analyze_subline_exceeds_logical_limit(mock_calc, rules):
    # Width (250) exceeds both editor threshold (200) and logical limit (240)
    problems = rules.analyze_subline("test", None, 0, 0, True, {}, 200, "test", logical_hard_limit=240)
    # ZMC_WIDTH_EXCEEDED should be triggered
    assert "ZMC_WIDTH_EXCEEDED" in problems
