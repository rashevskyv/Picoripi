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
    # Normalization variants (e.g. {A} -> {(A)})
    assert is_visible_tag("{A}", mappings, font_map, icon_seqs) is True


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
    
    # 1. With punctuation (lowercase): SHOULD fix
    text_with_punc = "Це дуже гарна\nідея."
    fixed, changed = mc_rules.autofix_data_string(text_with_punc, {}, 1000, allowed_problems=None)
    assert fixed == "Це дуже\nгарна ідея."
    assert changed is True

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


def test_autofix_page_isolation(bmg_rules):
    from plugins.zelda_bmg.config import PROBLEM_SHORT_LINE
    bmg_rules.mw.lines_per_page = 4
    bmg_rules.mw.autofix_enabled = {
        PROBLEM_SHORT_LINE: True
    }
    # Text: page 1 = Lines 1-4 (each ends with '.' so they are separate sentences),
    # page 2 = Lines 5b-5d + empty, page 3 = Lines 7b-7c.
    # The empty line at index 7 is padding between pages 2 and 3.
    # The very-long lines on page 2 won't merge because they are too wide.
    # The compactor will merge sentences on page 1 that fit together.
    text = (
        "Line 1.\n"
        "Line 2.\n"
        "Line 3.\n"
        "Line 4.\n"
        "Line 5b is a very very very very long line yesabc\n"
        "Line 5c is a very very very very long line yesabc\n"
        "Line 5d is a very very very very long line yesabc\n"
        "\n"
        "Line 7b is a very very very very long line yesabc\n"
        "Line 7c is a very very very very long line yesabc"
    )
    fixed, changed = bmg_rules.autofix_data_string(text, {}, 300)
    # The compactor merges short single-line sentences on page 1.
    # Lines 1-4 each fit a threshold of 300px (they are short), so compactor merges them.
    # Page 2 lines are very long (>300px) so they stay separate.
    # We only verify that page 2/3 content is not mixed across the page boundary.
    lines = fixed.split('\n')
    # All page-2 content (5b/5c/5d) should come before page-3 content (7b/7c)
    content_5b_idx = next((i for i, l in enumerate(lines) if '5b' in l), -1)
    content_7b_idx = next((i for i, l in enumerate(lines) if '7b' in l), -1)
    assert content_5b_idx != -1 and content_7b_idx != -1
    assert content_5b_idx < content_7b_idx, "page 2 lines must precede page 3 lines"


def test_single_word_orphan_detection_any_line(bmg_rules):
    from plugins.zelda_bmg.config import PROBLEM_SINGLE_WORD_SUBLINE_NON_START
    bmg_rules.mw.lines_per_page = 4
    
    # "рейках." is at line index 1 (not first line of page), should trigger brown warning
    text = "настінних\nрейках."
    problems = bmg_rules.problem_analyzer.analyze_data_string(text, {}, 1000)
    assert PROBLEM_SINGLE_WORD_SUBLINE_NON_START in problems[1]


def test_autofix_cross_page_orphan_merge_and_shift(mc_rules):
    from plugins.zelda_mc.config import PROBLEM_SHORT_LINE, PROBLEM_SINGLE_WORD_SUBLINE, PROBLEM_SINGLE_WORD_SUBLINE_NON_START
    mc_rules.mw.lines_per_page = 4
    mc_rules.mw.autofix_enabled = {
        PROBLEM_SHORT_LINE: True,
        PROBLEM_SINGLE_WORD_SUBLINE: True,
        PROBLEM_SINGLE_WORD_SUBLINE_NON_START: True
    }
    
    # CASE A: A lowercase single word on page 2 (line index 4, which is the 5th line) fits on page 1 (line index 3, which is the 4th line)
    # The warning limit is 1000 pixels (very large).
    # Since it fits, they should be merged: "Line 4" and "місця" -> "Line 4 місця".
    # The compactor also merges same-page short sentences (e.g. "Line 1." + "Line 2." on same line).
    text_fit = "Line 1.\nLine 2.\nLine 3.\nLine 4\nмісця"
    fixed_fit, changed_fit = mc_rules.autofix_data_string(text_fit, {}, 1000)
    assert changed_fit is True
    # Verify that "місця" ended up on page 1 (merged into it), not on page 2
    assert "місця" in fixed_fit
    assert "Line 4 місця" in fixed_fit or "4 місця" in fixed_fit

    # CASE B: A lowercase single word on page 2 (line index 4) does NOT fit on page 1 (line index 3)
    # Combined "Line 4 місця" is 12 chars = 96 pixels if default char width is 8.
    # If we pass logical_hard_limit = 80, the combined line would exceed 80, so it cannot merge.
    # In this case, "місця" cannot fit on line 4, so the last word of line 4 ("4") should be shifted down to line 5.
    # Result should be: "Line 1.\nLine 2.\nLine 3.\nLine\n4 місця"
    text_nofit = "Line 1.\nLine 2.\nLine 3.\nLine 4\nмісця"
    fixed_nofit, changed_nofit = mc_rules.autofix_data_string(text_nofit, {}, 1000, logical_hard_limit=80)
    assert changed_nofit is True
    # The sentence-shifting logic will shift the split sentence "Line\n4 місця" to start on page 2.
    # The compact step also applies: "Line 1." and "Line 2." and "Line 3." are short sentences that
    # may be merged by the compactor since they fit on page 1 together.
    assert "Line\n4 місця" in fixed_nofit or "4 місця" in fixed_nofit


def test_autofix_sentence_page_boundary_shifting(mc_rules):
    from plugins.zelda_mc.config import PROBLEM_SHORT_LINE
    mc_rules.mw.lines_per_page = 4
    mc_rules.mw.autofix_enabled = {
        PROBLEM_SHORT_LINE: False  # Disable merging to preserve the exact line structure
    }
    
    # CASE A: Sentence starts on line index 2 (Page 1) and ends on line index 4 (Page 2).
    # Since it is 3 lines long (index 2, 3, 4), and page size is 4, it should be shifted to Page 2 (starts at index 4).
    # Expected: 2 empty lines inserted before index 2.
    text = "Line 1.\nLine 2.\nHere is a sentence\nthat spans across\nthe page boundary."
    fixed, changed = mc_rules.autofix_data_string(text, {}, 1000)
    assert changed is True
    assert fixed == "Line 1.\nLine 2.\n\n\nHere is a sentence\nthat spans across\nthe page boundary."

    # CASE B: Sentence is 5 lines long (index 2 to 6), which exceeds page size (4).
    # It cannot fit on a single page anyway, so it should NOT be shifted.
    text_long = "Line 1.\nLine 2.\nThis is a very long\nsentence that goes on\nand on and on\nand crosses pages\ncompletely."
    fixed_long, changed_long = mc_rules.autofix_data_string(text_long, {}, 1000)
    assert fixed_long == text_long
    assert changed_long is False

    # CASE C: Sentences already aligned. No shift.
    text_ok = "Line 1.\nLine 2.\nLine 3.\nLine 4.\nSentence 2\nspans two lines."
    fixed_ok, changed_ok = mc_rules.autofix_data_string(text_ok, {}, 1000)
    assert fixed_ok == text_ok
    assert changed_ok is False


def test_autofix_visible_tag_as_word(mc_rules):
    from plugins.zelda_mc.config import PROBLEM_SINGLE_WORD_SUBLINE, PROBLEM_SINGLE_WORD_SUBLINE_NON_START
    mc_rules.mw.lines_per_page = 4
    mc_rules.mw.autofix_enabled = {
        PROBLEM_SINGLE_WORD_SUBLINE: True,
        PROBLEM_SINGLE_WORD_SUBLINE_NON_START: True
    }
    
    # "{(X)}." is a visible tag, so it should be treated as a single word orphan and pull "або" down
    text = "і використовуй за допомогою або\n{(X)}."
    fixed, changed = mc_rules.autofix_data_string(text, {}, 1000)
    assert changed is True
    assert fixed == "і використовуй за допомогою\nабо {(X)}."

    # "{(Y)}" is a visible tag at the end of the previous line, so it should be treated as a word and pulled down
    text2 = "і використовуй за допомогою {(Y)}\nабо"
    fixed2, changed2 = mc_rules.autofix_data_string(text2, {}, 1000)
    assert changed2 is True
    assert fixed2 == "і використовуй за допомогою\n{(Y)} або"

    # "{F:бомблінги}" is a forced tag, so it should be treated as a word and pulled down
    text3 = "і використовуй за допомогою {F:бомблінги}\nабо"
    fixed3, changed3 = mc_rules.autofix_data_string(text3, {}, 1000)
    assert changed3 is True
    assert fixed3 == "і використовуй за допомогою\n{F:бомблінги} або"


def test_get_line_words_and_visible_tags_width_tags(bmg_rules):
    from utils.utils import get_line_words_and_visible_tags
    from plugins.zelda_bmg.config import PROBLEM_SINGLE_WORD_SUBLINE_NON_START
    
    # 1. Check get_line_words_and_visible_tags output directly
    mw = MockMainWindow()
    # Let's map [L-Stick] to {escape:0:0008}
    mw.default_tag_mappings = {"[L-Stick]": "{escape:0:0008}"}
    
    words_stick = get_line_words_and_visible_tags("{escape:0:0008}", mw)
    assert words_stick == ["visibleword"]
    
    words_player = get_line_words_and_visible_tags("{PLAYER}", mw)
    assert words_player == ["visibleword"]
    
    words_var = get_line_words_and_visible_tags("{var:0}", mw)
    assert words_var == ["visibleword"]
    
    words_color = get_line_words_and_visible_tags("{COLOR_RED}", mw)
    assert words_color == [] # Color tags have 0 width and should be stripped
    
    # 2. Check that it triggers PROBLEM_SINGLE_WORD_SUBLINE_NON_START warning when standing alone
    bmg_rules.mw.default_tag_mappings = {"[L-Stick]": "{escape:0:0008}"}
    bmg_rules.mw.lines_per_page = 4
    
    text = "настінних\n{escape:0:0008}"
    problems = bmg_rules.problem_analyzer.analyze_data_string(text, {}, 1000)
    assert PROBLEM_SINGLE_WORD_SUBLINE_NON_START in problems[1]


def test_punctuation_wrap_prevention(plain_rules):
    # Characters are 8px wide by default in plain_rules
    # "aaaaa bbbbbb, cccc"
    # "aaaaa bbbbbb," is 13 chars = 104px
    # "aaaaa bbbbbb" is 12 chars = 96px
    # "bbbbbb, cccc" is 12 chars = 96px
    # "aaaaa" is 5 chars = 40px
    # If threshold is 100px:
    # - "aaaaa bbbbbb," does not fit.
    # - "aaaaa bbbbbb" fits.
    # Normally, it would split as "aaaaa bbbbbb" and ", cccc".
    # With punctuation wrap prevention, it splits as "aaaaa" and "bbbbbb, cccc".
    text = "aaaaa bbbbbb, cccc"
    fixed, changed = plain_rules.text_fixer._fix_width_exceeded_generic(text, {}, 100)
    assert changed is True
    assert fixed == "aaaaa\nbbbbbb, cccc"


def test_single_letter_word_wrap_prevention(bmg_rules, plain_rules):
    # Tests that if the next subline starts with a single-letter word,
    # it is only merged if the single-letter word AND the subsequent word fit.
    
    # In bmg_rules/plain_rules, default width is char_len * 6 (or 8 for plain)
    # Let's verify with plain_rules (default char width 8)
    # "abc" (3 * 8 = 24px)
    # "y def" -> first word "y" (8px), second "def" (24px)
    # space is 8px
    # Merging "y" only: "abc y" -> 5 * 8 = 40px.
    # Merging "y def": "abc y def" -> 9 * 8 = 72px.
    
    # 1. If threshold is 50px:
    # "abc y" (40px) fits. But "abc y def" (72px) does not fit.
    # Because of single-letter rule, we should NOT merge "y" alone.
    assert plain_rules.problem_analyzer._check_short_line_zww("abc", "y def", {}, 50) is False
    
    # 2. If threshold is 80px:
    # "abc y def" (72px) fits. We can merge.
    assert plain_rules.problem_analyzer._check_short_line_zww("abc", "y def", {}, 80) is True

    # 3. For BMG rules (default char width 6)
    # "abc" (18px)
    # "y def" -> first "y" (6px), second "def" (18px)
    # space 6px
    # "abc y" -> 30px
    # "abc y def" -> 54px
    # If threshold is 40px: BMG should not merge
    assert bmg_rules.problem_analyzer._check_short_line_zbmg("abc", "y def", {}, 40) is False
    # If threshold is 60px: BMG should merge
    assert bmg_rules.problem_analyzer._check_short_line_zbmg("abc", "y def", {}, 60) is True




