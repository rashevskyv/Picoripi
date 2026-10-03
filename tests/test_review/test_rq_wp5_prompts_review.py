"""WP5 review queue, prompts (5.3), the deterministic parts:

- "Run python -m plugins.validate": no warning for any shipped plugin (the prompt-section warning is gone).
- "Glossary and MemPalace prompts now come from plugins/common/defaults/prompts.json": every shipped plugin
  gets every section; a plugin that does not define a section gets the common text.
- "An override copy of prompts.json no longer freezes the other sections".
- "The editor-review pass never ran": off by default; switched on, every chunk sends a second request with
  the plugin's editor-review prompt (fake OpenAI-compatible server, real provider and worker).
Whether the new wording is better is for a live run.
"""
import json
from pathlib import Path

import pytest

from core.translation.prompt_files import load_merged_prompts
from plugins.validate import main as validate_main, validate_plugin

from . import _rq_wp5_helpers as h

COMMON = json.loads((h.REPO_PLUGINS / "common" / "defaults" / "prompts.json").read_text(encoding="utf-8"))
SECTIONS = {"translation": "system_prompt", "glossary": "prompt_template",
            "glossary_occurrence_update": "system_prompt",
            "editor_review": "system_prompt"}


@pytest.mark.parametrize("plugin", h.PLUGINS)
def test_the_validator_has_no_warning(plugin, capsys):
    report = validate_plugin(plugin)
    assert report.errors == [] and report.warnings == [], report.render()


def test_the_validator_command_prints_only_ok(capsys):
    assert validate_main([]) == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert sorted(lines) == sorted(f"{plugin}: OK" for plugin in h.PLUGINS)


@pytest.mark.parametrize("plugin", h.PLUGINS)
def test_every_plugin_gets_every_prompt_section(plugin):
    own = json.loads((h.REPO_PLUGINS / plugin / "translation_prompts" / "prompts.json").read_text(encoding="utf-8"))
    merged = load_merged_prompts(plugin)

    for section, key in SECTIONS.items():
        assert isinstance(merged.get(section, {}).get(key), str) and merged[section][key].strip(), (plugin, section)
        if section not in own:          # glossary, editor review: the common wording
            assert merged[section] == COMMON[section], (plugin, section)
    assert merged["translation"] == {**COMMON["translation"], **own["translation"]}
    assert merged["mempalace"] == COMMON["mempalace"]   # its prompts are null there: built-in text is used


class _Window:
    def __init__(self, plugin, project_dir):
        self.active_game_plugin = plugin
        self.target_language = "Ukrainian"
        self.project_manager = type("PM", (), {"project_dir": str(project_dir)})()
        self.translation_config = {}


class _MainHandler:
    class prompt_composer:   # noqa: N801 - the attribute the manager reads
        @staticmethod
        def _get_target_lang():
            return "Ukrainian"


def _manager(plugin, project_dir):
    from handlers.translation.glossary_prompt_manager import GlossaryPromptManager

    return GlossaryPromptManager(_Window(plugin, project_dir), _MainHandler(), None)


@pytest.mark.parametrize("plugin", ["zelda_bmg", "pokemon_fr"])
def test_an_override_copy_does_not_freeze_the_other_sections(tmp_path, plugin):
    manager = _manager(plugin, tmp_path)
    copy = manager.materialize_prompts_override(plugin)        # "Edit Prompts JSON"
    assert copy == tmp_path / "plugin_overrides" / plugin / "prompts.json" and copy.exists()
    data = json.loads(copy.read_text(encoding="utf-8"))
    assert set(data) == {"translation"}                         # the plugin's file, as before
    data["translation"]["system_prompt"] = "MY OWN TRANSLATION PROMPT"
    copy.write_text(json.dumps(data), encoding="utf-8")

    merged = manager.merged_prompts(plugin)

    assert merged["translation"]["system_prompt"] == "MY OWN TRANSLATION PROMPT"
    for section in ("glossary", "glossary_occurrence_update", "mempalace", "editor_review"):
        assert merged[section] == COMMON[section]
    assert manager.load_editor_review_prompt()


# --- editor review over a fake server -------------------------------------------------------------------

class _Composer:
    """What the chunked worker asks the prompt composer for."""
    mw = None

    def compose_batch_request(self, **kwargs):
        items = [{"id": item["id"], "text": item["text"]} for item in kwargs["source_items"]]
        return "TRANSLATE SYSTEM", json.dumps({"strings": items}), {}

    def _get_mempalace_client(self):
        return None

    def _get_wing_name(self):
        return None

    def _get_block_label(self, *args, **kwargs):
        return ""


class _Translator:
    """The parts of AIBatchTranslator that _attach_editor_review reads."""

    def __init__(self, translation_config, manager):
        self.mw = type("W", (), {"translation_config": translation_config})()
        self.main_handler = type("H", (), {"glossary_handler": manager})()


def _reply(body):
    """Echo every string back as its translation; the editor marks its copy."""
    system = body["messages"][0]["content"]
    payload = json.loads(body["messages"][1]["content"].split("JSON DATA TO PROCESS:")[-1].strip())
    mark = " (edited)" if system != "TRANSLATE SYSTEM" else ""
    return json.dumps({"translated_strings": [{"id": s["id"], "translation": s.get("translation", s["text"]) + mark}
                                              for s in payload["strings"]]})


def _run_block(qapp, config, tmp_path, plugin="zelda_bmg"):
    from core.translation.config import build_default_translation_config
    from core.translation.providers import OpenAIProvider
    from handlers.translation.batch_translator import AIBatchTranslator
    from handlers.translation.worker import AIWorker

    server = h.FakeChatServer(_reply)
    try:
        translation_config = {**build_default_translation_config(), **config}
        context = {"enable_editor_review": True}
        AIBatchTranslator._attach_editor_review(_Translator(translation_config, _manager(plugin, tmp_path)), context)
        items = [{"id": i, "text": f"Line {i}"} for i in range(3)]
        worker = AIWorker(OpenAIProvider({"base_url": server.url, "api_key": "k", "model": "m"}), _Composer(), {
            "type": "translate_block_chunked", "block_idx": 0, "source_items": items, "workers": 1,
            "composer_args": {"system_prompt": "TRANSLATE SYSTEM", "block_idx": 0, "mode_description": "block"},
            **context,
        })
        chunks = []
        worker.chunk_translated.connect(lambda idx, text, ctx: chunks.append(json.loads(text)))
        worker.run()
        return server.requests, chunks, context
    finally:
        server.close()


def test_the_editor_review_pass_is_off_by_default(qapp, tmp_path):
    from core.translation.config import build_default_translation_config

    assert build_default_translation_config()["editor_review_enabled"] is False
    requests, chunks, context = _run_block(qapp, {}, tmp_path)

    assert context["enable_editor_review"] is False
    assert len(requests) == 1 and requests[0]["messages"][0]["content"] == "TRANSLATE SYSTEM"
    assert [s["translation"] for s in chunks[0]["translated_strings"]] == ["Line 0", "Line 1", "Line 2"]


@pytest.mark.parametrize("plugin", h.PLUGINS)
def test_switched_on_each_chunk_gets_a_second_request_with_the_editor_prompt(qapp, tmp_path, plugin):
    requests, chunks, context = _run_block(qapp, {"editor_review_enabled": True}, tmp_path, plugin)
    expected_prompt = _manager(plugin, tmp_path).load_editor_review_prompt()

    assert context["enable_editor_review"] is True and context["editor_system_prompt"] == expected_prompt
    assert len(requests) == 2
    review = requests[1]["messages"]
    assert review[0] == {"role": "system", "content": expected_prompt}
    assert [s["translation"] for s in json.loads(review[1]["content"])["strings"]] == ["Line 0", "Line 1", "Line 2"]
    # The polished reply is what the block gets.
    assert [s["translation"] for s in chunks[0]["translated_strings"]] == [f"Line {i} (edited)" for i in range(3)]
    assert Path(tmp_path / "plugin_overrides").exists() is False      # nothing was written for the user
