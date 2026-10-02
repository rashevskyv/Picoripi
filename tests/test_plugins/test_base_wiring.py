"""A plugin declares its parts; the base class wires them (WP5 5.2)."""
from types import SimpleNamespace
from unittest.mock import MagicMock

from plugins.base_game_rules import BaseGameRules
from plugins.common.config_factory import generate_base_config, problem_ids
from plugins.common.problem_analyzer import GenericProblemAnalyzer
from plugins.common.tag_logic import compare_tags, process_pasted_segment, tag_kind
from plugins.common.tag_manager import GenericTagManager
from plugins.common.text_fixer import GenericTextFixer
from ui.main_window.main_window_plugin_handler import MainWindowPluginHandler

DEFINITIONS, _DETECTION, _AUTOFIX = generate_base_config("DEMO")


class DemoRules(BaseGameRules):
    problem_prefix = "DEMO"
    problem_definitions = DEFINITIONS


def test_a_plugin_with_problem_definitions_gets_the_standard_parts():
    rules = DemoRules()

    assert type(rules.tag_manager) is GenericTagManager
    assert type(rules.problem_analyzer) is GenericProblemAnalyzer
    assert type(rules.text_fixer) is GenericTextFixer
    assert rules.problem_analyzer.game_rules is rules and rules.text_fixer.game_rules is rules
    assert rules.get_problem_definitions() is DEFINITIONS
    assert rules.problem_ids.PROBLEM_WIDTH_EXCEEDED == "DEMO_WIDTH_EXCEEDED"
    assert len(rules.get_syntax_highlighting_rules()) >= 2


def test_a_plugin_without_problem_definitions_gets_none_of_it():
    rules = BaseGameRules()

    assert not hasattr(rules, "problem_analyzer") and rules.problem_ids is None
    assert rules.get_problem_definitions() == {} and rules.get_syntax_highlighting_rules() == []
    assert rules.analyze_subline("text", None, 0, 0, True, {}, 100, "text") == set()
    assert rules.autofix_data_string("text", {}, 100) == ("text", False)


def test_the_hooks_that_only_pass_a_call_on_work_without_being_written():
    rules = DemoRules()
    wide = "x" * 50

    found = rules.analyze_subline(wide, None, 0, 0, True, {}, 100, wide)
    fixed, changed = rules.autofix_data_string("one  two", {}, 200)

    assert "DEMO_WIDTH_EXCEEDED" in found                # 50 characters of 6 px against a 100 px limit
    assert isinstance(fixed, str) and isinstance(changed, bool)


def test_the_tag_style_is_declared_not_guessed_from_a_module_name():
    class SquareRules(DemoRules):
        tag_style = "square"

    class StarRules(DemoRules):
        tag_style = "curly"
        star_section_mode = True

    assert DemoRules().problem_analyzer.profile.tag_style == "curly"
    assert SquareRules().problem_analyzer.profile.tag_style == "square"
    assert StarRules().problem_analyzer.profile.star_section_mode is True
    assert SquareRules().problem_analyzer.profile.star_section_mode is False


def test_the_whole_string_can_be_analysed_first():
    class WholeFirst(DemoRules):
        analyze_whole_string_first = True

    rules = WholeFirst()
    rules.problem_analyzer = MagicMock()
    rules.problem_analyzer.analyze_subline.return_value = {"LINE"}
    rules.problem_analyzer.analyze_data_string.return_value = [{"A"}, {"B"}]

    assert rules.analyze_subline("b", None, 1, 1, True, {}, 100, "a\nb") == {"B", "LINE"}
    assert rules.analyze_subline("z", None, 5, 5, True, {}, 100, "a\nb") == {"LINE"}      # past the end


def test_short_problem_names_come_from_the_common_table_and_the_plugin_s_own():
    class Named(DemoRules):
        short_problem_names = {"EMPTY_ODD_SUBLINE_DISPLAY": "EmptyPage"}

    rules = Named()

    assert rules.get_short_problem_name("DEMO_WIDTH_EXCEEDED") == "Width"
    assert rules.get_short_problem_name("DEMO_EMPTY_ODD_SUBLINE_DISPLAY") == "EmptyPage"
    assert rules.get_short_problem_name("OTHER_THING") == "OTHER_THING"
    assert BaseGameRules().get_short_problem_name("DEMO_WIDTH_EXCEEDED") == "DEMO_WIDTH_EXCEEDED"


def test_problem_ids_can_leave_out_checks_the_game_does_not_use():
    ids = problem_ids(DEFINITIONS, "DEMO", without=("BROKEN_ICON_HYPHEN",))

    assert ids.PROBLEM_TAG_WARNING == "DEMO_TAG_WARNING" and not hasattr(ids, "PROBLEM_BROKEN_ICON_HYPHEN")


def test_the_preview_shows_spaces_as_dots_when_the_setting_or_the_plugin_default_says_so():
    class Dotted(BaseGameRules):
        show_spaces_as_dots_default = True

    assert BaseGameRules().get_text_representation_for_preview("a  b\nc") == "a  b↵c"
    assert Dotted().get_text_representation_for_preview("a  b") != "a  b"
    host = SimpleNamespace(show_multiple_spaces_as_dots=False, default_tag_mappings={})
    assert Dotted(host).get_text_representation_for_preview("a  b") == "a  b"


class TestGenericTagManager:
    def test_legitimate_tags_can_come_from_the_alias_mappings(self):
        class FromAliases(GenericTagManager):
            legitimate_tags_from_aliases = True
            extra_legitimate_tags = ("{Player}",)

        host = SimpleNamespace(default_tag_mappings={"[P]": "{PLAYER}"})
        manager = FromAliases(host)

        assert manager.get_legitimate_tags() == {"[P]", "{PLAYER}", "{Player}"}
        host.default_tag_mappings["[E]"] = "{END}"
        assert "[E]" not in manager.get_legitimate_tags()          # cached
        manager.forget_legitimate_tags()
        assert {"[E]", "{END}"} <= manager.get_legitimate_tags()

    def test_by_default_only_the_declared_extra_tags_are_legitimate(self):
        assert GenericTagManager().get_legitimate_tags() == set()


class TestNeutralTagLogic:
    def test_tags_are_compared_kind_by_kind(self):
        assert tag_kind("[Color:Red]") == "[color]" and tag_kind("{ Wait : 5 }") == "{wait}"
        assert compare_tags("[Color:Blue]Hi[/C]", "[Color:Red]Hello[/C]") == ("OK", "")

    def test_a_missing_or_different_tag_is_a_warning_that_names_it(self):
        status, message = compare_tags("Hi [Name]", "Hello [Name] {Wait:5}")

        assert status == "WARNING" and "{wait}: 0 pasted, 1 in the original" in message
        assert compare_tags("[Sound:1]", "[Wait:1]")[0] == "WARNING"

    def test_the_pasted_text_itself_is_not_changed(self):
        assert process_pasted_segment("Hi [Name]", "Hello [Name]", "[P]") == ("Hi [Name]", "OK", "")


class TestHostAiActions:
    def test_every_game_gets_the_translate_actions(self):
        host = MagicMock()
        actions = MainWindowPluginHandler(host)._host_ai_actions()

        assert [a["name"] for a in actions] == [
            "ai_translate_current_string", "ai_translate_selected_lines",
            "ai_translate_current_block", "ai_reset_translation_session",
        ]
        assert [a["shortcut"] for a in actions[:3]] == ["Ctrl+Alt+T", "Ctrl+Alt+L", "Ctrl+Alt+B"]
        assert actions[0]["handler"] is host.translation_handler.translate_current_string

    def test_without_a_translation_handler_there_are_none(self):
        assert MainWindowPluginHandler(SimpleNamespace(translation_handler=None))._host_ai_actions() == []
