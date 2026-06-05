import pytest
from unittest.mock import MagicMock
from utils.utils import clean_spaces
from plugins.zelda_mc.rules import GameRules as ZeldaMCRules
from plugins.zelda_mc.config import PROBLEM_BAD_SPACING as ZMC_BAD_SPACING
from plugins.zelda_ww.rules import GameRules as ZeldaWWRules
from plugins.zelda_ww.config import PROBLEM_BAD_SPACING as ZWW_BAD_SPACING
from plugins.plain_text.rules import GameRules as PlainTextRules
from plugins.plain_text.config import PROBLEM_BAD_SPACING as PLAIN_BAD_SPACING
from plugins.zelda_bmg.rules import GameRules as ZeldaBMGRules
from plugins.zelda_bmg.config import PROBLEM_BAD_SPACING as ZBMG_BAD_SPACING
from plugins.pokemon_fr.rules import GameRules as PokemonFRRules
from plugins.pokemon_fr.config import PROBLEM_BAD_SPACING as PKFR_BAD_SPACING


class MockMainWindow:
    def __init__(self):
        self.data_store = self
        self.show_multiple_spaces_as_dots = False
        self.default_tag_mappings = {}
        self.newline_display_symbol = "↵"
        self.plugin_handler = MagicMock()
        self.data_processor = MagicMock()
        self.original_text_edit = MagicMock()
        self.preview_text_edit = MagicMock()
        self.game_dialog_max_width_pixels = 300
        self.line_width_warning_threshold_pixels = 280

@pytest.fixture
def mc_rules(qapp):
    return ZeldaMCRules(MockMainWindow())

@pytest.fixture
def ww_rules(qapp):
    return ZeldaWWRules(MockMainWindow())

@pytest.fixture
def plain_rules(qapp):
    return PlainTextRules(MockMainWindow())

@pytest.fixture
def bmg_rules(qapp):
    return ZeldaBMGRules(MockMainWindow())

@pytest.fixture
def pokemon_rules(qapp):
    return PokemonFRRules(MockMainWindow())


def test_clean_spaces():
    # 1. Simple spaces collapse
    assert clean_spaces("Hello  World") == "Hello World"
    # 2. Leading space stripping
    assert clean_spaces("  Hello") == "Hello"
    # 3. Trailing space stripping
    assert clean_spaces("Hello  ") == "Hello"
    # 4. Spaces around tags
    assert clean_spaces("У {color:red} королівстві") == "У {color:red}королівстві"
    assert clean_spaces(" {color:red} замок") == "{color:red}замок"
    assert clean_spaces("{color:red} замок") == "{color:red}замок"
    assert clean_spaces(" {color:red}  замок  ") == "{color:red}замок"
    assert clean_spaces("У {color:red}  {color:blue}   королівстві") == "У {color:red}{color:blue}королівстві"
    assert clean_spaces("слово1 {tag1}   {tag2} слово2") == "слово1 {tag1}{tag2}слово2"
    # 5. Multiple lines
    assert clean_spaces(" Hello\n  World ") == "Hello\nWorld"
    # 6. Forced aliases treated as text
    assert clean_spaces("слово1 {F:Link}   слово2") == "слово1 {F:Link} слово2"
    assert clean_spaces(" {F:Link} слово2 ") == "{F:Link} слово2"


def test_zelda_mc_spacing_detection(mc_rules):
    # OK case
    problems = mc_rules.analyze_subline(
        text="Hello {color:red}World",
        next_text=None,
        subline_number_in_data_string=0,
        qtextblock_number_in_editor=0,
        is_last_subline_in_data_string=True,
        editor_font_map={},
        editor_line_width_threshold=1000,
        full_data_string_text_for_logical_check="Hello {color:red}World"
    )
    assert ZMC_BAD_SPACING not in problems

    # Leading space case
    problems = mc_rules.analyze_subline(
        text="{color:red} Hello",
        next_text=None,
        subline_number_in_data_string=0,
        qtextblock_number_in_editor=0,
        is_last_subline_in_data_string=True,
        editor_font_map={},
        editor_line_width_threshold=1000,
        full_data_string_text_for_logical_check="{color:red} Hello"
    )
    assert ZMC_BAD_SPACING in problems

    # Consecutive spaces case
    problems = mc_rules.analyze_subline(
        text="Hello {color:red} World",
        next_text=None,
        subline_number_in_data_string=0,
        qtextblock_number_in_editor=0,
        is_last_subline_in_data_string=True,
        editor_font_map={},
        editor_line_width_threshold=1000,
        full_data_string_text_for_logical_check="Hello {color:red} World"
    )
    assert ZMC_BAD_SPACING in problems


def test_zelda_ww_spacing_detection(ww_rules):
    # Call analyze_data_string which is WW's main entry point
    problems = ww_rules.problem_analyzer.analyze_data_string(
        data_string="Hello [Color:Red] World",
        font_map={},
        threshold=1000
    )
    assert ZWW_BAD_SPACING in problems[0]


def test_plain_text_spacing_detection(plain_rules):
    problems = plain_rules.problem_analyzer.analyze_data_string(
        data_string="Hello [Color:Red] World",
        font_map={},
        threshold=1000
    )
    assert PLAIN_BAD_SPACING in problems[0]


def test_zelda_bmg_spacing_detection(bmg_rules):
    problems = bmg_rules.problem_analyzer.analyze_data_string(
        data_string="Hello {COLOR_RED} World",
        font_map={},
        threshold=1000
    )
    assert ZBMG_BAD_SPACING in problems[0]


def test_pokemon_fr_spacing_detection(pokemon_rules):
    problems = pokemon_rules.problem_analyzer.analyze_data_string(
        data_string="Hello {PLAYER} World",
        font_map={},
        threshold=1000
    )
    assert PKFR_BAD_SPACING in problems[0]


def test_zelda_mc_pasted_segment_clean(mc_rules):
    # pasted segment should have its spacing automatically cleaned
    res, status, msg = mc_rules.process_pasted_segment(
        "У {color:red} королівстві",
        "У {color:red} королівстві",
        "[PLAYER]"
    )
    assert res == "У {color:red}королівстві"


def test_zelda_mc_autofix(mc_rules):
    fixed, changed = mc_rules.autofix_data_string(
        "У {color:red} королівстві",
        {},
        1000
    )
    assert fixed == "У {color:red}королівстві"
    assert changed is True


def test_clean_spaces_with_length_tags(monkeypatch):
    mock_font_map = {
        "{(Y)}": {"width": 50},
        "{(X)}": 50,
        "[(A)]": {"width": 45}
    }
    mock_mappings = {
        "{(Y)}": "{escape:0:0010}",
        "{(X)}": "{escape:0:000f}",
        "[(A)]": "{escape:0:000a}"
    }
    
    monkeypatch.setattr("utils.utils.get_active_font_map", lambda: mock_font_map)
    monkeypatch.setattr("utils.utils.get_active_tag_mappings", lambda: mock_mappings)
    
    assert clean_spaces("У {(Y)} королівстві") == "У {(Y)} королівстві"
    assert clean_spaces("У   {(Y)}   королівстві") == "У {(Y)} королівстві"
    assert clean_spaces("У {color:red} королівстві") == "У {color:red}королівстві"


def test_zelda_bmg_spacing_detection_with_length_tags(bmg_rules):
    bmg_rules.mw.font_map = {
        "{(Y)}": {"width": 50}
    }
    bmg_rules.mw.default_tag_mappings = {
        "{(Y)}": "{escape:0:0010}"
    }
    
    problems = bmg_rules.problem_analyzer.analyze_data_string(
        data_string="Hello {(Y)} World",
        font_map=bmg_rules.mw.font_map,
        threshold=1000
    )
    assert ZBMG_BAD_SPACING not in problems[0]


def test_is_visible_tag():
    from utils.utils import is_visible_tag
    font_map = {"{(A)}": {"width": 10}, "{some_tag}": {"width": 0}, "{icon}": 15}
    mappings = {"{(A)}": "{escape:1}", "{btn_b}": "{escape:2}"}
    icon_seqs = ["{icon}"]
    
    # Tags containing parentheses
    assert is_visible_tag("{(A)}", mappings, font_map, icon_seqs) is True
    assert is_visible_tag("{btn_b}", mappings, font_map, icon_seqs) is False
    # Target value mapped to a parentheses key
    assert is_visible_tag("{escape:1}", mappings, font_map, icon_seqs) is True
    # Non-zero width tags
    assert is_visible_tag("{icon}", mappings, font_map, icon_seqs) is True
    # Regular tag with zero width
    assert is_visible_tag("{some_tag}", mappings, font_map, icon_seqs) is False


def test_find_missing_icon_spacing_spans():
    from utils.utils import find_missing_icon_spacing_spans
    visible_tags = {"{(A)}", "{icon}"}
    check_visible = lambda t: t in visible_tags
    
    # Both sides spaced - OK
    assert len(find_missing_icon_spacing_spans("Hello {(A)} World", check_visible)) == 0
    
    # Missing left
    spans = find_missing_icon_spacing_spans("Hello{(A)} World", check_visible)
    assert len(spans) == 1
    assert spans[0] == (5, 10)
    
    # Missing right
    spans = find_missing_icon_spacing_spans("Hello {(A)}World", check_visible)
    assert len(spans) == 1
    
    # Missing both
    spans = find_missing_icon_spacing_spans("Hello{(A)}World", check_visible)
    assert len(spans) == 1

    # Punctuation adjacent is OK
    assert len(find_missing_icon_spacing_spans("Hello,{(A)} World", check_visible)) == 0
    assert len(find_missing_icon_spacing_spans("Hello {(A)}. World", check_visible)) == 0
    assert len(find_missing_icon_spacing_spans("Hello-{(A)} World", check_visible)) == 0
    assert len(find_missing_icon_spacing_spans("Hello {(A)}! World", check_visible)) == 0


def test_fix_missing_icon_spacing():
    from utils.utils import fix_missing_icon_spacing
    visible_tags = {"{(A)}", "{icon}"}
    check_visible = lambda t: t in visible_tags
    
    assert fix_missing_icon_spacing("Hello{(A)} World", check_visible) == "Hello {(A)} World"
    assert fix_missing_icon_spacing("Hello {(A)}World", check_visible) == "Hello {(A)} World"
    assert fix_missing_icon_spacing("Hello{(A)}World", check_visible) == "Hello {(A)} World"
    assert fix_missing_icon_spacing("{(A)}World", check_visible) == "{(A)} World"
    assert fix_missing_icon_spacing("Hello{(A)}", check_visible) == "Hello {(A)}"
    assert fix_missing_icon_spacing("Hello{color:red}{(A)}World", check_visible) == "Hello{color:red} {(A)} World"
    
    # Punctuation adjacent should NOT be spaced
    assert fix_missing_icon_spacing("Hello,{(A)} World", check_visible) == "Hello,{(A)} World"
    assert fix_missing_icon_spacing("Hello {(A)}. World", check_visible) == "Hello {(A)}. World"
    assert fix_missing_icon_spacing("Hello-{(A)} World", check_visible) == "Hello-{(A)} World"
    assert fix_missing_icon_spacing("Hello {(A)}! World", check_visible) == "Hello {(A)}! World"


def test_plugin_missing_icon_spacing_detection_and_fix(mc_rules, ww_rules, plain_rules, bmg_rules, pokemon_rules):
    from plugins.zelda_mc.config import PROBLEM_MISSING_ICON_SPACING as ZMC_MIS
    from plugins.zelda_ww.config import PROBLEM_MISSING_ICON_SPACING as ZWW_MIS
    from plugins.plain_text.config import PROBLEM_MISSING_ICON_SPACING as PLAIN_MIS
    from plugins.zelda_bmg.config import PROBLEM_MISSING_ICON_SPACING as ZBMG_MIS
    from plugins.pokemon_fr.config import PROBLEM_MISSING_ICON_SPACING as PKFR_MIS
    
    for rules in [mc_rules, ww_rules, plain_rules, bmg_rules, pokemon_rules]:
        rules.mw.font_map = {"{(A)}": {"width": 10}, "[(A)]": {"width": 10}, "{btn}": 12}
        rules.mw.default_tag_mappings = {"{(A)}": "{escape:1}", "[(A)]": "[escape:2]"}
        rules.mw.detection_enabled = {
            ZMC_MIS: True, ZWW_MIS: True, PLAIN_MIS: True, ZBMG_MIS: True, PKFR_MIS: True
        }
        rules.mw.autofix_enabled = {
            ZMC_MIS: True, ZWW_MIS: True, PLAIN_MIS: True, ZBMG_MIS: True, PKFR_MIS: True
        }

    # Zelda MC
    problems = mc_rules.analyze_subline(
        text="Hello{(A)}World",
        next_text=None,
        subline_number_in_data_string=0,
        qtextblock_number_in_editor=0,
        is_last_subline_in_data_string=True,
        editor_font_map=mc_rules.mw.font_map,
        editor_line_width_threshold=1000,
        full_data_string_text_for_logical_check="Hello{(A)}World"
    )
    assert ZMC_MIS in problems
    fixed, changed = mc_rules.autofix_data_string("Hello{(A)}World", mc_rules.mw.font_map, 1000)
    assert fixed == "Hello {(A)} World"
    assert changed is True

    # Zelda WW
    problems = ww_rules.problem_analyzer.analyze_data_string(
        data_string="Hello[(A)]World",
        font_map=ww_rules.mw.font_map,
        threshold=1000
    )
    assert ZWW_MIS in problems[0]
    fixed, changed = ww_rules.autofix_data_string("Hello[(A)]World", ww_rules.mw.font_map, 1000)
    assert fixed == "Hello [(A)] World"
    assert changed is True

    # Plain Text
    problems = plain_rules.problem_analyzer.analyze_data_string(
        data_string="Hello[(A)]World",
        font_map=plain_rules.mw.font_map,
        threshold=1000
    )
    assert PLAIN_MIS in problems[0]
    fixed, changed = plain_rules.autofix_data_string("Hello[(A)]World", plain_rules.mw.font_map, 1000)
    assert fixed == "Hello [escape:2] World"
    assert changed is True

    # Zelda BMG
    problems = bmg_rules.problem_analyzer.analyze_data_string(
        data_string="Hello{(A)}World",
        font_map=bmg_rules.mw.font_map,
        threshold=1000
    )
    assert ZBMG_MIS in problems[0]
    fixed, changed = bmg_rules.autofix_data_string("Hello{(A)}World", bmg_rules.mw.font_map, 1000)
    assert fixed == "Hello {(A)} World"
    assert changed is True

    # Pokemon FR
    problems = pokemon_rules.problem_analyzer.analyze_data_string(
        data_string="Hello{(A)}World",
        font_map=pokemon_rules.mw.font_map,
        threshold=1000
    )
    assert PKFR_MIS in problems[0]
    fixed, changed = pokemon_rules.autofix_data_string("Hello{(A)}World", pokemon_rules.mw.font_map, 1000)
    assert fixed == "Hello {(A)} World"
    assert changed is True


def test_autofix_disabled_settings(mc_rules):
    from plugins.zelda_mc.config import PROBLEM_SHORT_LINE
    # Disable short line autofix in settings
    mc_rules.mw.autofix_enabled = {
        PROBLEM_SHORT_LINE: False
    }
    
    text = "Hello\nworld"
    fixed, changed = mc_rules.autofix_data_string(text, {}, 1000, allowed_problems=None)
    assert fixed == text
    assert changed is False
    
    # Enable it
    mc_rules.mw.autofix_enabled[PROBLEM_SHORT_LINE] = True
    fixed, changed = mc_rules.autofix_data_string(text, {}, 1000, allowed_problems=None)
    assert changed is True


def test_autofix_single_word_orphan_with_punctuation(mc_rules):
    from plugins.zelda_mc.config import PROBLEM_SINGLE_WORD_SUBLINE, PROBLEM_SINGLE_WORD_SUBLINE_NON_START
    mc_rules.mw.autofix_enabled = {
        PROBLEM_SINGLE_WORD_SUBLINE: True,
        PROBLEM_SINGLE_WORD_SUBLINE_NON_START: True
    }
    
    # 1. With punctuation: should NOT fix
    text_with_punc = "Це дуже гарна\nідея."
    fixed, changed = mc_rules.autofix_data_string(text_with_punc, {}, 1000, allowed_problems=None)
    assert fixed == text_with_punc
    assert changed is False

    # 2. Without punctuation: should fix
    text_no_punc = "Це дуже гарна\nідея"
    fixed, changed = mc_rules.autofix_data_string(text_no_punc, {}, 1000, allowed_problems=None)
    assert fixed == "Це дуже\nгарна ідея"
    assert changed is True

    # 3. Previous line ends with sentence punctuation: should NOT fix
    text_prev_ends_punc = "Це дуже гарна.\nідея"
    fixed, changed = mc_rules.autofix_data_string(text_prev_ends_punc, {}, 1000, allowed_problems=None)
    assert fixed == text_prev_ends_punc
    assert changed is False

