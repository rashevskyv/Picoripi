import json
from pathlib import Path

from plugins.default_plugin.config import PROBLEM_WIDTH_EXCEEDED
from plugins.default_plugin.rules import GameRules


class FakeMainWindow:
    def __init__(self):
        self.default_tag_mappings = {}
        self.icon_sequences = ["[PLAYER]", "[A]", "[B]"]
        self.newline_display_symbol = "↵"
        self.show_multiple_spaces_as_dots = False
        self.line_width_warning_threshold_pixels = 80
        self.game_dialog_max_width_pixels = 100
        self.lines_per_page = 4
        self.data_store = type("FakeStore", (), {"data": []})()
        self.detection_enabled = {}
        self.autofix_enabled = {}


def test_default_plugin_loads_and_exposes_core_contract(qapp):
    rules = GameRules(FakeMainWindow())

    assert rules.get_display_name() == "Default Plugin Template"
    assert rules.get_default_script_name() == "default_plugin_script.md"
    assert rules.get_problem_definitions()
    assert rules.get_editor_page_size() == 4
    assert rules.is_tag_legitimate("[PLAYER]")
    assert rules.is_tag_legitimate("{PAGE}")
    assert not rules.is_tag_legitimate("[PLAYER")


def test_default_plugin_has_discovery_config_and_ai_prompt():
    plugin_dir = Path("plugins/default_plugin")
    config = json.loads((plugin_dir / "config.json").read_text(encoding="utf-8"))

    assert config["display_name"] == "Default Plugin Template"
    assert config["default_font_file"] == "default_font.json"
    assert (plugin_dir / "AI_PLUGIN_ASSISTANT_PROMPT.md").is_file()
    assert (plugin_dir / "translation_prompts/prompts.json").is_file()


def test_default_plugin_parses_and_serializes_plain_text(qapp):
    rules = GameRules(FakeMainWindow())
    data, names = rules.load_data_from_json_obj("Hello\nWorld\n\nSecond block")

    assert data == [["Hello", "World"], ["Second block"]]
    assert names == {"0": "Block 1", "1": "Block 2"}
    assert rules.save_data_to_json_obj(data, names) == "Hello\nWorld\n\nSecond block"


def test_default_plugin_width_warning_uses_shared_rule_engine(qapp):
    rules = GameRules(FakeMainWindow())
    problems = rules.analyze_subline(
        text="A" * 20,
        next_text=None,
        subline_number_in_data_string=0,
        qtextblock_number_in_editor=0,
        is_last_subline_in_data_string=True,
        editor_font_map={"A": {"width": 8}},
        editor_line_width_threshold=80,
        full_data_string_text_for_logical_check="A" * 20,
        logical_hard_limit=80,
    )

    assert PROBLEM_WIDTH_EXCEEDED in problems


def test_default_plugin_autofix_and_width_override_are_safe(qapp):
    rules = GameRules(FakeMainWindow())

    fixed, changed = rules.autofix_data_string(
        "Hello world",
        {"H": {"width": 8}, "e": {"width": 7}, "l": {"width": 3}, "o": {"width": 7}, " ": {"width": 4}},
        500,
    )
    width = rules.calculate_string_width_override("Hi [PLAYER]", {"H": {"width": 8}, "i": {"width": 3}, " ": {"width": 4}, "[PLAYER]": {"width": 32}})

    assert isinstance(fixed, str)
    assert isinstance(changed, bool)
    assert width == 47
