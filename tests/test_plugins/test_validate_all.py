"""The plugin contract (plugins/spec.py) and its validator (WP5 5.1)."""
import ast
import re
from pathlib import Path

import pytest

from plugins.base_game_rules import BaseGameRules
from plugins.spec import HOOK_NAMES, HOOKS, KNOWN_CONFIG_KEYS, SESSION_KEYS
from plugins.validate import (
    Report,
    check_config,
    check_font_map,
    check_prompts,
    check_rules,
    check_sources,
    main,
    plugin_names,
    validate_plugin,
)

HOST_CODE = ["core", "handlers", "ui", "components", "utils", "dialogs", "main.py"]
_RULES_VARIABLE = re.compile(r"(^|_)(game_rules|rules|plugin)$")


@pytest.mark.parametrize("name", plugin_names())
def test_every_shipped_plugin_passes_the_validator(name):
    report = validate_plugin(name)

    assert report.errors == [], report.render()


def test_the_shipped_plugins_are_found():
    assert {"default_plugin", "plain_text", "pokemon_fr", "zelda_bmg", "zelda_mc", "zelda_ww"} <= set(plugin_names())
    assert "import_plugins" not in plugin_names() and "common" not in plugin_names()


def test_the_command_line_reports_and_returns_zero_for_a_good_plugin(capsys):
    assert main(["plain_text"]) == 0
    assert "plain_text: OK" in capsys.readouterr().out


def test_the_command_line_fails_for_a_plugin_that_is_not_there(capsys):
    assert main(["no_such_plugin"]) == 1
    assert "no config.json" in capsys.readouterr().out


class TestTheSpecIsComplete:
    def test_every_public_method_of_the_base_class_is_a_hook(self):
        public = {name for name, value in vars(BaseGameRules).items() if callable(value) and not name.startswith("_")}

        assert public - HOOK_NAMES == set()

    def test_hooks_marked_as_on_the_base_class_are_there_and_the_others_are_not(self):
        on_base = {hook.name for hook in HOOKS if hook.on_base}
        probed = {hook.name for hook in HOOKS if not hook.on_base}

        assert {name for name in on_base if not hasattr(BaseGameRules, name)} == set()
        assert {name for name in probed if hasattr(BaseGameRules, name)} == set()

    def test_hook_names_are_unique_and_described(self):
        assert len(HOOK_NAMES) == len(HOOKS)
        assert [hook.name for hook in HOOKS if not hook.summary.strip()] == []

    def test_everything_host_code_reads_on_a_rules_object_is_a_hook(self):
        """A host call the spec does not list is a hook nobody documented."""
        def owner(node):
            return node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else ""

        touched = {}
        for root in HOST_CODE:
            paths = [Path(root)] if root.endswith(".py") else sorted(Path(root).rglob("*.py"))
            for path in paths:
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Attribute) and _RULES_VARIABLE.search(owner(node.value)):
                        touched.setdefault(node.attr, path.as_posix())
                    elif (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id in ("getattr", "hasattr")
                        and len(node.args) >= 2
                        and isinstance(node.args[1], ast.Constant)
                        and isinstance(node.args[1].value, str)
                        and _RULES_VARIABLE.search(owner(node.args[0]))
                    ):
                        touched.setdefault(node.args[1].value, path.as_posix())

        # objects that are not GameRules but share a variable name ("rules" of the rule engine, …)
        not_game_rules = {name for name in touched if name.startswith("__")}
        base_internals = {name for name in vars(BaseGameRules) if name.startswith("_")}
        unknown = {
            name: where for name, where in touched.items()
            if name not in HOOK_NAMES and name not in not_game_rules and name not in base_internals
        }
        assert unknown == {}

    def test_session_keys_are_not_config_keys(self):
        assert SESSION_KEYS & KNOWN_CONFIG_KEYS == set()


class TestCheckConfig:
    def test_a_minimal_config_is_fine(self):
        report = Report("demo")
        check_config({"display_name": "Demo"}, report)
        assert (report.errors, report.warnings) == ([], [])

    def test_a_missing_name_and_session_leftovers_are_errors(self):
        report = Report("demo")
        check_config({"display_name": " ", "search_history": [], "last_selected_block_index": 3}, report)
        assert len(report.errors) == 2 and "last_selected_block_index, search_history" in report.errors[1]

    def test_an_unknown_key_is_a_warning(self):
        report = Report("demo")
        check_config({"display_name": "Demo", "line_widht": 200}, report)
        assert report.errors == [] and "line_widht" in report.warnings[0]


def test_font_map_entries_need_an_integer_width():
    good, bad = Report("demo"), Report("demo")
    check_font_map({"A": {"width": 7}, "[PLAYER]": {"width": 32, "file": "x.bmp"}}, good)
    check_font_map({"widths": {"32": 4}, "A": {"width": "7"}}, bad)

    assert good.errors == [] and "2 entries" in bad.errors[0]


def test_prompt_sections_are_checked_by_name():
    report = Report("demo")
    check_prompts({"translation": {}, "glosary": {}}, report)

    assert report.errors == [] and "glosary" in report.warnings[0]


class TestCheckRules:
    def _errors(self, rules_class):
        report = Report("demo")
        check_rules(rules_class, report)
        return report.errors

    def test_the_base_class_itself_passes(self):
        assert self._errors(BaseGameRules) == []

    def test_a_class_that_is_not_game_rules_is_refused(self):
        assert "subclass" in self._errors(dict)[0]

    def test_a_hook_that_raises_is_an_error(self):
        class Rules(BaseGameRules):
            def get_display_name(self):
                raise RuntimeError("no window")

        assert self._errors(Rules) == ["get_display_name() raised RuntimeError: no window"]

    def test_a_wrong_return_type_is_an_error(self):
        class Rules(BaseGameRules):
            def get_capabilities(self):
                return ["glossary_seed"]

            def get_enter_char(self):
                return None

        assert self._errors(Rules) == [
            "get_enter_char: returned None, expected str",
            "get_capabilities: returned list, expected set",
        ]

    def test_none_is_accepted_where_the_hook_may_have_no_answer(self):
        class Rules(BaseGameRules):
            def get_speaker_for_string(self, block_idx, string_idx):
                return None

        assert self._errors(Rules) == []

    def test_a_signature_the_host_cannot_call_is_an_error(self):
        class Rules(BaseGameRules):
            def autofix_data_string(self, data_string, font_map, threshold):      # the host passes more
                return data_string, False

            def analyze_subline(self, *args, **kwargs):                           # this one is fine
                return set()

        errors = self._errors(Rules)
        assert len(errors) == 1 and errors[0].startswith("autofix_data_string: does not accept the keyword argument(s)")

    def test_positional_arguments_may_be_renamed(self):
        class Rules(BaseGameRules):
            def load_data_from_json_obj(self, file_content):
                return [[str(file_content)]], {}

        assert self._errors(Rules) == []

    def test_a_plugin_that_needs_a_main_window_to_exist_is_an_error(self):
        class Rules(BaseGameRules):
            def __init__(self, main_window_ref=None):
                super().__init__(main_window_ref)
                self.limit = main_window_ref.lines_per_page

        assert "cannot be built without a main window" in self._errors(Rules)[0]

    def test_a_bad_spellcheck_pattern_and_a_nameless_problem_are_errors(self):
        class Rules(BaseGameRules):
            def get_spellcheck_ignore_pattern(self):
                return "("

            def get_problem_definitions(self):
                return {"X_WIDTH": {"color": None}}

        errors = self._errors(Rules)
        assert any("not a valid regex" in e for e in errors) and any("without a 'name'" in e for e in errors)


def test_a_main_window_attribute_outside_the_allowed_list_is_a_warning(tmp_path):
    source = tmp_path / "rules.py"
    source.write_text(
        "class GameRules:\n"
        "    def f(self):\n"
        "        a = self.mw.default_tag_mappings\n"
        "        b = self.mw.secret_internal_cache\n"
        "        return getattr(self.mw, 'another_internal', None), a, b\n",
        encoding="utf-8",
    )
    report = Report("demo")

    check_sources([source], report, root=tmp_path)

    assert report.errors == []
    assert [w.split("'")[1] for w in report.warnings] == ["another_internal", "secret_internal_cache"]
    assert "rules.py:4" in report.warnings[1]


class TestTheContractPage:
    def test_the_committed_page_is_what_the_spec_generates(self):
        from plugins.spec import render_markdown

        committed = Path("docs/PLUGIN_CONTRACT.md").read_text(encoding="utf-8")

        assert committed == render_markdown(), "run: python -m plugins.spec --write"

    def test_every_hook_is_on_the_page_once(self):
        page = Path("docs/PLUGIN_CONTRACT.md").read_text(encoding="utf-8")

        assert [hook.name for hook in HOOKS if page.count(f"| `{hook.name}` |") != 1] == []

    def test_one_plugin_guide_remains(self):
        assert not Path("docs/PLUGIN_AUTHORING_GUIDE.md").exists()
        assert not Path("plugins/DEVELOPER_GUIDE.md").exists()
        for guide in ("docs/wiki/3_Plugin_Developer_Guide.md", "docs/wiki/uk/3_Plugin_Developer_Guide.md"):
            text = Path(guide).read_text(encoding="utf-8")
            assert "PLUGIN_CONTRACT.md" in text and "tools/new_plugin.py" in text
            assert "ui/settings/logging_mixin.py" in text and "project_action_handler" not in text


def test_no_two_plugins_show_the_same_name_in_the_plugin_list():
    import json

    names = {}
    for name in plugin_names():
        config = json.loads((Path("plugins") / name / "config.json").read_text(encoding="utf-8"))
        names.setdefault(config["display_name"], []).append(name)

    assert {label: ids for label, ids in names.items() if len(ids) > 1} == {}
