import pytest
from unittest.mock import MagicMock
from plugins.common.problem_rules import (
    RuleContext,
    GameProblemProfile,
    WidthRule,
    BadSpacingRule,
    MissingIconSpacingRule,
    ShortLineRule,
    SingleWordSublineRule,
    EmptyFirstLineOfPageRule,
    EmptyOddSublineDisplayRule,
    StarTagRule
)

class MockMainWindow:
    def __init__(self):
        self.game_dialog_max_width_pixels = 300
        self.line_width_warning_threshold_pixels = 280
        self.lines_per_page = 4
        self.default_tag_mappings = {}
        self.icon_sequences = []
        self.detection_enabled = {}
        self.autofix_enabled = {}

def build_context(text: str, profile: GameProblemProfile, original_text: str = None) -> RuleContext:
    mw = profile.main_window if profile else None
    default_tag_mappings = getattr(mw, 'default_tag_mappings', {}) if mw else {}
    icon_sequences = getattr(mw, 'icon_sequences', []) if mw else []
    return RuleContext(
        text=text,
        font_map={},
        width_threshold=100,  # Narrow width threshold to trigger short line / width warnings easily
        logical_hard_limit=120,
        lines_per_page=getattr(mw, 'lines_per_page', 4) if mw else 4,
        default_tag_mappings=default_tag_mappings,
        icon_sequences=icon_sequences,
        original_text=original_text,
        game_profile=profile
    )

@pytest.fixture
def base_profile():
    mw = MockMainWindow()
    return GameProblemProfile(
        problem_ids={
            "WIDTH_EXCEEDED": "TEST_WIDTH",
            "BAD_SPACING": "TEST_SPACING",
            "MISSING_ICON_SPACING": "TEST_MISSING",
            "SHORT_LINE": "TEST_SHORT",
            "SINGLE_WORD_SUBLINE": "TEST_SINGLE",
            "SINGLE_WORD_SUBLINE_NON_START": "TEST_SINGLE_NON_START",
            "EMPTY_FIRST_LINE_OF_PAGE": "TEST_EMPTY_FIRST",
            "EMPTY_ODD_SUBLINE_DISPLAY": "TEST_EMPTY_ODD",
            "STAR_TAG_RULES": "TEST_STAR",
        },
        tag_style="curly",
        main_window=mw
    )

def test_width_rule_contract(base_profile):
    rule = WidthRule()
    # A single very long line of letters (1 char = 6px by default, 30 chars = 180px, threshold = 120px)
    dirty_text = "abcdefghij klmnopqrst abcdefgh"
    context = build_context(dirty_text, base_profile)
    
    # 1. detect finds warning
    matches = rule.detect(context)
    assert len(matches) > 0
    assert matches[0].problem_id == "WIDTH_EXCEEDED"
    
    # 2. fix changes text
    res = rule.fix(context, matches)
    assert res.changed is True
    assert res.text != dirty_text
    
    # 3. subsequent detect finds no warning on fixed text
    fixed_context = build_context(res.text, base_profile)
    assert len(rule.detect(fixed_context)) == 0

def test_bad_spacing_rule_contract(base_profile):
    rule = BadSpacingRule()
    dirty_text = "Hello  World"
    context = build_context(dirty_text, base_profile)
    
    matches = rule.detect(context)
    assert len(matches) > 0
    
    res = rule.fix(context, matches)
    assert res.changed is True
    assert res.text == "Hello World"
    
    fixed_context = build_context(res.text, base_profile)
    assert len(rule.detect(fixed_context)) == 0

def test_missing_icon_spacing_rule_contract(base_profile):
    rule = MissingIconSpacingRule()
    base_profile.default_tag_mappings = {"{(A)}": "{escape:1}"}
    base_profile.icon_sequences = ["{(A)}"]
    
    dirty_text = "Hello{(A)}World"
    context = build_context(dirty_text, base_profile)
    # Mock font map to give tag a width
    context.font_map = {"{(A)}": {"width": 10}}
    
    matches = rule.detect(context)
    assert len(matches) > 0
    
    res = rule.fix(context, matches)
    assert res.changed is True
    assert res.text == "Hello {(A)} World"
    
    fixed_context = build_context(res.text, base_profile)
    fixed_context.font_map = {"{(A)}": {"width": 10}}
    assert len(rule.detect(fixed_context)) == 0

def test_short_line_rule_contract(base_profile):
    rule = ShortLineRule()
    # "abc" is short, next line starts with lowercase "def"
    dirty_text = "abc\ndef"
    context = build_context(dirty_text, base_profile)
    
    matches = rule.detect(context)
    assert len(matches) > 0
    
    res = rule.fix(context, matches)
    assert res.changed is True
    assert "abc def" in res.text
    
    fixed_context = build_context(res.text, base_profile)
    assert len(rule.detect(fixed_context)) == 0

def test_short_line_rule_header_protection(base_profile):
    rule = ShortLineRule()
    # "Abc" is short (width < 50% of threshold=100), but next line starts with uppercase "Def"
    dirty_text = "Abc\nDef"
    context = build_context(dirty_text, base_profile)

    matches = rule.detect(context)
    # Header should not be flagged as a short line (no merge expected)
    assert len(matches) == 0

def test_short_line_rule_punctuation_protection(base_profile):
    rule = ShortLineRule()
    # "abc:" ends with colon, which is a list indicator, so it should not be merged
    dirty_text = "abc:\ndef"
    context = build_context(dirty_text, base_profile)

    matches = rule.detect(context)
    assert len(matches) == 0

    # "abc;" ends with semicolon, should not be merged
    dirty_text = "abc;\ndef"
    context = build_context(dirty_text, base_profile)

    matches = rule.detect(context)
    assert len(matches) == 0

def test_single_word_subline_rule_contract(base_profile):
    rule = SingleWordSublineRule()
    # A single word on the second line (index 1) which is lowercase, not starting sentence
    dirty_text = "Це дуже довге та красиве речення\nідея"
    context = build_context(dirty_text, base_profile)
    
    matches = rule.detect(context)
    assert len(matches) > 0
    
    res = rule.fix(context, matches)
    assert res.changed is True
    assert res.text == "Це дуже довге та красиве\nречення ідея"
    
    fixed_context = build_context(res.text, base_profile)
    assert len(rule.detect(fixed_context)) == 0

def test_empty_first_line_of_page_rule_contract(base_profile):
    rule = EmptyFirstLineOfPageRule()
    dirty_text = "\nContent on line 2\nLine 3\nLine 4"
    context = build_context(dirty_text, base_profile)
    
    matches = rule.detect(context)
    assert len(matches) > 0
    
    res = rule.fix(context, matches)
    assert res.changed is True
    assert res.text == "Content on line 2\nLine 3\nLine 4"
    
    fixed_context = build_context(res.text, base_profile)
    assert len(rule.detect(fixed_context)) == 0

def test_empty_odd_subline_display_rule_contract(base_profile):
    rule = EmptyOddSublineDisplayRule()
    dirty_text = "\nLine 2\nLine 3"
    context = build_context(dirty_text, base_profile)
    
    matches = rule.detect(context)
    assert len(matches) > 0
    
    res = rule.fix(context, matches)
    assert res.changed is True
    assert res.text == "Line 2\nLine 3"
    
    fixed_context = build_context(res.text, base_profile)
    assert len(rule.detect(fixed_context)) == 0

def test_star_tag_rule_contract(base_profile):
    base_profile.star_section_mode = True
    rule = StarTagRule()
    
    # {*} starts a tab section, subsequent line should start with {tab}
    dirty_text = "{escape:6:000a}\nLine 2"
    context = build_context(dirty_text, base_profile)
    
    matches = rule.detect(context)
    assert len(matches) > 0
    
    res = rule.fix(context, matches)
    assert res.changed is True
    assert res.text == "{escape:6:000a}\n{escape:6:000b}Line 2"
    
    fixed_context = build_context(res.text, base_profile)
    assert len(rule.detect(fixed_context)) == 0

def test_all_rule_engine_problem_ids_are_defined_for_each_plugin():
    """
    Parametrized test for each plugin: GameRules returns only problem IDs 
    that exist in its get_problem_definitions() mapping.
    """
    from plugins.zelda_ww.rules import GameRules as ZeldaWWRules
    from plugins.zelda_mc.rules import GameRules as ZeldaMCRules
    from plugins.zelda_bmg.rules import GameRules as ZeldaBMGRules
    from plugins.plain_text.rules import GameRules as PlainTextRules
    from plugins.pokemon_fr.rules import GameRules as PokemonFRRules

    plugins = [
        ZeldaWWRules(),
        ZeldaMCRules(),
        ZeldaBMGRules(),
        PlainTextRules(),
        PokemonFRRules()
    ]

    dirty_strings = [
        "Very long line that exceeds the default limit of characters for a width warning test",
        "Hello  World",  # Bad spacing (double spaces)
        "Hello{(A)}World",  # Missing icon spacing
        "abc\ndef",  # Short line
        "Це дуже довге та красиве речення\nідея",  # Single word subline / orphan
        "\nContent on line 2\nLine 3\nLine 4",  # Empty first line of page
        "\nLine 2\nLine 3",  # Empty odd subline display
        "{escape:6:000a}\nLine 2",  # Star rules BMG
        "Unclosed {Tag tag warning",  # Tag warnings
    ]

    for rules in plugins:
        defs = rules.get_problem_definitions()
        assert defs, f"Problem definitions are empty for {rules.get_display_name()}"
        
        for dirty in dirty_strings:
            if hasattr(rules.problem_analyzer, 'analyze_data_string'):
                problems_all = rules.problem_analyzer.analyze_data_string(dirty, {}, 100)
                for line_probs in problems_all:
                    for pid in line_probs:
                        assert pid in defs, f"Unknown problem ID '{pid}' emitted by rules '{rules.get_display_name()}' for string '{dirty}'"

def test_registry_fix_all_respects_empty_allowed_problems(base_profile):
    from plugins.common.problem_rules import create_default_registry
    registry = create_default_registry(base_profile)
    dirty_text = "Hello  World"
    context = build_context(dirty_text, base_profile)
    
    fixed_text, changed = registry.fix_all(context, allowed_problems=set())
    assert changed is False
    assert fixed_text == dirty_text

def test_registry_fix_all_respects_disabled_autofix_setting(base_profile):
    from plugins.common.problem_rules import create_default_registry
    
    prefixed_spacing_id = base_profile.problem_ids["BAD_SPACING"]
    base_profile.main_window.autofix_enabled = {prefixed_spacing_id: False}
    
    registry = create_default_registry(base_profile)
    dirty_text = "Hello  World"
    context = build_context(dirty_text, base_profile)
    
    fixed_text, changed = registry.fix_all(context, allowed_problems=None)
    assert changed is False
    assert fixed_text == dirty_text

def test_registry_detect_all_respects_detection_enabled_false(base_profile):
    from plugins.common.problem_rules import create_default_registry
    
    prefixed_spacing_id = base_profile.problem_ids["BAD_SPACING"]
    base_profile.main_window.detection_enabled = {prefixed_spacing_id: False}
    
    registry = create_default_registry(base_profile)
    dirty_text = "Hello  World"
    context = build_context(dirty_text, base_profile)
    
    problems = registry.detect_all(context)
    for p_set in problems:
        assert prefixed_spacing_id not in p_set

def test_rule_context_globals_are_restored_after_exception_or_second_scan(base_profile):
    import utils.utils as uu
    
    uu._ACTIVE_FONT_MAP = {"initial": "val"}
    uu._ACTIVE_TAG_MAPPINGS = {"initial_t": "val_t"}
    uu._ACTIVE_ICON_SEQUENCES = ["initial_i"]
    
    from plugins.common.problem_analyzer import GenericProblemAnalyzer
    definitions = {pref_id: {} for pref_id in base_profile.problem_ids.values()}
    gen_analyzer = GenericProblemAnalyzer(
        main_window_ref=base_profile.main_window,
        tag_manager_ref=MagicMock(),
        problem_definitions_ref=definitions,
        problem_ids_ref=base_profile.problem_ids
    )
    
    bad_rule = gen_analyzer.registry.get_rule("BAD_SPACING")
    orig_detect = bad_rule.detect
    try:
        def mock_detect(*args, **kwargs):
            raise ValueError("Simulated detect error")
        bad_rule.detect = mock_detect
        
        with pytest.raises(ValueError, match="Simulated detect error"):
            gen_analyzer.analyze_data_string("Hello  World", {"temp": "val"}, 100)
            
        assert uu._ACTIVE_FONT_MAP == {"initial": "val"}
        assert uu._ACTIVE_TAG_MAPPINGS == {"initial_t": "val_t"}
        assert uu._ACTIVE_ICON_SEQUENCES == ["initial_i"]
        
    finally:
        bad_rule.detect = orig_detect
        uu._ACTIVE_FONT_MAP = None
        uu._ACTIVE_TAG_MAPPINGS = None
        uu._ACTIVE_ICON_SEQUENCES = None
