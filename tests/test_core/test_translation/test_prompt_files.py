"""Prompts are merged key by key: application, common defaults, plugin, override (WP5 5.3)."""
import json
from pathlib import Path
from unittest.mock import MagicMock

from core.translation.prompt_files import deep_merge, load_merged_prompts, prompt_layers
from handlers.translation.batch_translator import AIBatchTranslator
from handlers.translation.glossary_prompt_manager import _DEFAULT_GLOSSARY_PROMPT, GlossaryPromptManager

COMMON = json.loads(Path("plugins/common/defaults/prompts.json").read_text(encoding="utf-8"))
ZELDA_MC = json.loads(Path("plugins/zelda_mc/translation_prompts/prompts.json").read_text(encoding="utf-8"))


def test_deep_merge_replaces_values_and_merges_sections():
    base = {"translation": {"system_prompt": "base", "extra": 1}, "glossary": {"prompt_template": "g"}}
    top = {"translation": {"system_prompt": "top"}, "new": {"x": 1}}

    assert deep_merge(base, top) == {
        "translation": {"system_prompt": "top", "extra": 1},
        "glossary": {"prompt_template": "g"},
        "new": {"x": 1},
    }
    assert base["translation"]["system_prompt"] == "base"          # inputs are not changed


def test_a_plugin_with_a_translation_only_file_still_gets_the_other_sections():
    assert list(ZELDA_MC) == ["translation"]                        # the premise

    merged = load_merged_prompts("zelda_mc")

    assert merged["translation"]["system_prompt"] == ZELDA_MC["translation"]["system_prompt"]
    assert merged["editor_review"] == COMMON["editor_review"]
    assert merged["glossary"] == COMMON["glossary"]
    assert merged["mempalace"] == COMMON["mempalace"]


def test_the_layers_are_application_then_common_then_plugin_then_overrides(tmp_path):
    (tmp_path / "prompts.json").write_text(json.dumps({"translation": {"system_prompt": "mine"}}), encoding="utf-8")

    layers = [path.as_posix() for path in prompt_layers("zelda_mc", [tmp_path, None])]
    merged = load_merged_prompts("zelda_mc", [tmp_path])

    assert layers[0] == "translation_prompts/prompts.json"
    assert layers[1].endswith("plugins/common/defaults/prompts.json")
    assert layers[2].endswith("plugins/zelda_mc/translation_prompts/prompts.json")
    assert layers[3].endswith("/prompts.json") and len(layers) == 4
    assert merged["translation"]["system_prompt"] == "mine" and merged["editor_review"] == COMMON["editor_review"]


def test_an_unreadable_file_is_skipped_and_an_unknown_plugin_gets_the_defaults(tmp_path):
    (tmp_path / "prompts.json").write_text("{ not json", encoding="utf-8")

    assert load_merged_prompts("zelda_mc", [tmp_path]) == load_merged_prompts("zelda_mc")
    assert load_merged_prompts("no_such_plugin")["glossary"] == COMMON["glossary"]
    assert load_merged_prompts(None)["translation"]


def _manager(tmp_path, plugin="zelda_mc"):
    mw = MagicMock()
    mw.active_game_plugin = plugin
    mw.target_language = "Ukrainian"
    mw.project_manager.project_dir = str(tmp_path)
    main_handler = MagicMock()
    main_handler.prompt_composer._get_target_lang.return_value = "Ukrainian"
    return GlossaryPromptManager(mw, main_handler, MagicMock())


def test_the_editor_review_prompt_is_found_for_a_translation_only_plugin(tmp_path):
    prompt = _manager(tmp_path).load_editor_review_prompt()

    assert prompt and "{target_lang}" not in prompt


def test_the_glossary_template_comes_from_the_common_file_not_from_the_built_in_text(tmp_path):
    template, _path = _manager(tmp_path).get_glossary_prompt_template()

    assert template and template != _DEFAULT_GLOSSARY_PROMPT
    assert COMMON["glossary"]["prompt_template"][:40].split("{")[0] in template


def test_a_project_override_wins_for_its_own_keys_only(tmp_path):
    override = tmp_path / "plugin_overrides" / "zelda_mc"
    override.mkdir(parents=True)
    (override / "prompts.json").write_text(
        json.dumps({"editor_review": {"system_prompt": "PROJECT EDITOR"}}), encoding="utf-8")
    manager = _manager(tmp_path)

    assert manager.load_editor_review_prompt() == "PROJECT EDITOR"
    assert manager.merged_prompts("zelda_mc")["translation"] == ZELDA_MC["translation"]


class TestEditorReviewSwitch:
    def _translator(self, config):
        translator = AIBatchTranslator.__new__(AIBatchTranslator)
        translator.mw = MagicMock()
        translator.mw.translation_config = config
        translator.main_handler = MagicMock()
        translator.main_handler.glossary_handler.load_editor_review_prompt.return_value = "EDITOR PROMPT"
        return translator

    def test_the_pass_is_off_unless_switched_on(self):
        context = {"enable_editor_review": True}
        self._translator({})._attach_editor_review(context)

        assert context == {"enable_editor_review": False}

    def test_switched_on_it_gets_its_prompt(self):
        context = {"enable_editor_review": True}
        self._translator({"editor_review_enabled": True})._attach_editor_review(context)

        assert context == {"enable_editor_review": True, "editor_system_prompt": "EDITOR PROMPT"}

    def test_a_run_that_declined_the_pass_keeps_it_off(self):
        context = {"enable_editor_review": False}
        self._translator({"editor_review_enabled": True})._attach_editor_review(context)

        assert context == {"enable_editor_review": False}

    def test_no_prompt_means_no_pass(self):
        translator = self._translator({"editor_review_enabled": True})
        translator.main_handler.glossary_handler.load_editor_review_prompt.side_effect = RuntimeError("boom")
        context = {}
        translator._attach_editor_review(context)

        assert context == {"enable_editor_review": False}
