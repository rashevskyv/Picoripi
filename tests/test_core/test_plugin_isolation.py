"""A plugin that fails, or was loaded before, does not take the host with it (WP5 5.6)."""
import importlib
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.plugin_call import safe_call
from handlers.app_action_handler import AppActionHandler
from handlers.text_autofix_logic import TextAutofixLogic
from plugins.base_game_rules import BaseGameRules
from plugins.common.generic_rules import GenericRules
from ui.main_window.main_window_plugin_handler import forget_plugin_modules
from utils.constants import plugins_root

HOST = ("core", "handlers", "ui", "components", "utils")


class TestSafeCall:
    def test_a_working_hook_returns_its_value(self):
        assert safe_call(BaseGameRules(), "get_enter_char", default="?") == "\n"
        assert safe_call(BaseGameRules(), "get_tag_tooltip", "{x}", default="?") == ""

    def test_a_missing_hook_or_no_plugin_gives_the_default(self):
        assert safe_call(BaseGameRules(), "no_such_hook", 1, 2, default="fallback") == "fallback"
        assert safe_call(None, "get_enter_char", default="\n") == "\n"

    def test_a_hook_that_raises_is_logged_and_gives_the_default(self):
        class Broken(BaseGameRules):
            def get_text_representation_for_editor(self, text):
                raise KeyError("alias table")

        with patch("core.plugin_call.log_error") as log_error:
            assert safe_call(Broken(), "get_text_representation_for_editor", "raw", default="raw") == "raw"

        assert "get_text_representation_for_editor() failed: KeyError" in log_error.call_args[0][0]

    def test_keyword_arguments_reach_the_hook(self):
        class Rules(BaseGameRules):
            def get_addressee_for_string(self, block_idx, string_idx, speaker=None):
                return f"{block_idx}:{string_idx}:{speaker}"

        assert safe_call(Rules(), "get_addressee_for_string", 1, 2, speaker="Midna") == "1:2:Midna"


def test_a_plugin_that_cannot_parse_a_file_is_reported_not_raised():
    mw = MagicMock()
    mw.data_store = mw
    mw.state.enter.return_value.__enter__.return_value = MagicMock()
    mw.data_store.block_names = {}
    mw.current_game_rules.load_data_from_json_obj.side_effect = ValueError("unexpected header")
    ui = MagicMock()
    handler = AppActionHandler(mw, MagicMock(), ui, mw.current_game_rules)

    with patch("core.formats.load_json_file", return_value=({"key": "value"}, None)), \
         patch("handlers.app_action_handler.QMessageBox") as message_box:
        handler.load_all_data_for_path("dummy.json")           # must not raise

    message_box.critical.assert_called_once()
    assert "could not parse the file" in message_box.critical.call_args[0][2]
    assert mw.json_path is None and mw.data == []


class TestPluginReload:
    @pytest.fixture(autouse=True)
    def _keep_the_loaded_plugins_for_other_tests(self):
        """Other tests hold classes from the plugin modules loaded now; put those modules back."""
        before = {name: module for name, module in sys.modules.items() if name.startswith("plugins.")}
        yield
        for name in [name for name in sys.modules if name.startswith("plugins.")]:
            del sys.modules[name]
        sys.modules.update(before)

    def test_every_module_of_the_plugin_is_dropped_and_no_other(self):
        importlib.import_module("plugins.zelda_bmg.rules")
        importlib.import_module("plugins.zelda_mc.rules")
        before = {name for name in sys.modules if name.startswith("plugins.zelda_bmg")}
        assert {"plugins.zelda_bmg.rules", "plugins.zelda_bmg.config", "plugins.zelda_bmg.tag_catalog"} <= before

        dropped = forget_plugin_modules("zelda_bmg")

        assert set(dropped) == before
        assert not [name for name in sys.modules if name.startswith("plugins.zelda_bmg")]
        assert "plugins.zelda_mc.rules" in sys.modules and "plugins.base_game_rules" in sys.modules

    def test_switching_back_and_forth_gives_fresh_modules_each_time(self):
        first = importlib.import_module("plugins.zelda_ww.rules")
        first.marker = "state of the previous load"

        forget_plugin_modules("zelda_ww")
        importlib.import_module("plugins.zelda_mc.rules")
        forget_plugin_modules("zelda_mc")
        second = importlib.import_module("plugins.zelda_ww.rules")

        assert second is not first and not hasattr(second, "marker")

    def test_a_plugin_whose_name_starts_like_another_is_left_alone(self):
        sys.modules["plugins.zelda_mc_extra"] = MagicMock()
        try:
            importlib.import_module("plugins.zelda_mc.rules")
            forget_plugin_modules("zelda_mc")
            assert "plugins.zelda_mc_extra" in sys.modules
        finally:
            del sys.modules["plugins.zelda_mc_extra"]


class TestPluginsRoot:
    def test_it_does_not_depend_on_the_current_directory(self, tmp_path, monkeypatch):
        expected = plugins_root()
        monkeypatch.chdir(tmp_path)

        assert plugins_root() == expected and plugins_root().is_absolute()
        assert (plugins_root() / "base_game_rules.py").is_file()

    def test_host_code_builds_no_plugin_path_from_the_current_directory(self):
        pattern = re.compile(r"""Path\(\s*["']plugins["']""")
        offenders = [
            path.as_posix()
            for root in HOST
            for path in Path(root).rglob("*.py")
            if pattern.search(path.read_text(encoding="utf-8"))
        ]
        assert offenders == []


class TestNoBorrowedGame:
    def test_code_without_a_main_window_gets_generic_rules_not_a_game(self):
        logic = TextAutofixLogic(MagicMock(), MagicMock(), MagicMock())

        rules = logic._get_rules()

        assert type(rules) is GenericRules
        assert "GEN_WIDTH_EXCEEDED" in rules.get_problem_definitions()
        assert rules.problem_analyzer.profile.tag_style == "curly"

    def test_no_host_module_imports_the_minish_cap_plugin(self):
        offenders = [
            path.as_posix()
            for root in HOST
            for path in Path(root).rglob("*.py")
            if "plugins.zelda_mc" in path.read_text(encoding="utf-8")
        ]
        assert offenders == []
