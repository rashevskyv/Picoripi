"""Speaker identities entering the glossary from Markup Studio and game data."""
import json
from types import SimpleNamespace

from core.glossary_build.script_seeds import seeds_from_markup


def _project(lines, marks):
    return SimpleNamespace(
        raw_text="\n".join(lines),
        approved_marks=tuple(
            SimpleNamespace(
                start_line=i,
                end_line=i,
                type_id=type_id,
                text="",
                label="",
                start_col=None,
                end_col=None,
                origin="manual",
            )
            for i, type_id in marks
        ),
    )


def test_markup_speakers_become_unique_character_seeds():
    project = _project(
        ["RENADO", "Welcome.", "renado", "Again.", "TELMA"],
        [(0, "speaker"), (1, "text"), (2, "speaker"), (3, "text"), (4, "speaker")],
    )

    seeds = seeds_from_markup(project)

    assert [seed["term"] for seed in seeds] == ["RENADO", "TELMA"]
    assert {seed["section"] for seed in seeds} == {"Characters"}


def test_markup_ignores_structure_and_item_marks():
    project = _project(
        ["Act One", "SYSTEM", "RENADO"],
        [(0, "structure"), (1, "item"), (2, "speaker")],
    )

    assert [seed["term"] for seed in seeds_from_markup(project)] == ["RENADO"]


def test_missing_markup_is_an_empty_seed_source():
    assert seeds_from_markup(None) == []


def test_provisional_seed_survives_save_and_reload():
    from core.glossary_build.pipeline_coordinator import (
        MODE_SEED,
        GlossaryBuildCoordinator,
    )
    from core.glossary_manager import GlossaryManager, _entry_to_dict

    manager = GlossaryManager()
    manager.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
    GlossaryBuildCoordinator(
        manager,
        lambda _messages: "",
        {},
        structural_seeds=[{"term": "CLERK_B", "provisional": True}],
    ).build(dataset=[["line"]], mode=MODE_SEED)
    raw = json.dumps([_entry_to_dict(entry) for entry in manager.get_entries()])

    reloaded = GlossaryManager()
    reloaded.load_from_text(plugin_name=None, glossary_path=None, raw_text=raw)

    assert reloaded.get_entry("CLERK_B").provisional is True


def test_name_suggester_returns_evidence_and_can_refuse():
    from core.glossary_build.ai_adapters import make_name_suggester

    prompts = {
        "name": {
            "system_prompt": "sys {target_lang}",
            "user_prompt_template": "{term} {description}",
        }
    }
    confident = make_name_suggester(
        lambda _messages: json.dumps({
            "name": "BARNES",
            "confidence": "high",
            "evidence": "advertises Barnes's bombs",
        }),
        prompts,
    )("Benz", "Advertises bombs sold at Barnes's shop.")
    refused = make_name_suggester(
        lambda _messages: '{"name":"","confidence":"low","evidence":""}',
        prompts,
    )("X", "A villager.")

    assert confident.name == "BARNES"
    assert confident.is_confident
    assert "Barnes" in confident.evidence
    assert refused.name == ""


def test_coordinator_stores_name_suggestion_without_applying_it():
    from core.glossary_build.pipeline_coordinator import (
        BuildResult,
        GlossaryBuildCoordinator,
    )
    from core.glossary_manager import GlossaryManager

    manager = GlossaryManager()
    manager.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
    manager.seed_entry(
        "Benz",
        section="Characters",
        description="Advertises bombs sold at Barnes's shop.",
        provisional=True,
    )
    prompts = {
        "name": {
            "system_prompt": "sys {target_lang}",
            "user_prompt_template": "{term} {description}",
        }
    }
    coordinator = GlossaryBuildCoordinator(
        manager,
        lambda _messages: json.dumps({
            "name": "BARNES",
            "confidence": "high",
            "evidence": "Barnes's shop",
        }),
        prompts,
    )
    result = BuildResult()

    coordinator._suggest_names(result)

    entry = manager.get_entry("Benz")
    assert entry.original == "Benz"
    assert entry.suggested_name == "BARNES"
    assert "Barnes" in entry.suggested_name_evidence
    assert result.names_suggested == 1
