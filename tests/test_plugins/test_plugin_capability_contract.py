"""M3: the engine publishes empty slots; plugins fill them.

The invariant guarded here is that no engine module compares a metadata slot
against a value from one particular game. A plugin for another game must be able
to define its own roles and have them reach the model without the engine being
edited.
"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from plugins.base_game_rules import BaseGameRules


ENGINE_MODULES = [
    Path("handlers/translation/ai_prompt_composer.py"),
    Path("handlers/translation/ai_worker.py"),
    Path("core/glossary_build/pipeline_coordinator.py"),
]


class TestEngineCarriesNoGameVocabulary:
    @pytest.mark.parametrize("path", ENGINE_MODULES, ids=lambda p: p.name)
    def test_no_hardcoded_role_value(self, path):
        """'BossName' is one game's word for one of its window kinds."""
        assert "BossName" not in path.read_text(encoding="utf-8")

    def test_base_contract_names_no_single_implementation(self):
        """The abstract contract must not document itself through one plugin."""
        text = Path("plugins/base_game_rules.py").read_text(encoding="utf-8")
        for leaked in ("zelda_bmg", "FLW1", "FLI1", "bmgres"):
            assert leaked not in text


class TestDefaultsAreInert:
    """A plugin that implements none of this must still work."""

    def test_capabilities_default_to_none(self):
        assert BaseGameRules().get_capabilities() == set()

    def test_seed_entries_default_to_nothing(self):
        assert BaseGameRules().get_glossary_seed_entries() == []

    def test_external_lore_defaults_to_none(self):
        assert BaseGameRules().get_external_lore("anything") is None


class TestRoleInstructionReachesThePrompt:
    """A role the engine has never heard of still teaches the model."""

    def test_batch_prompt_includes_a_plugin_supplied_instruction(self):
        from handlers.translation.ai_prompt_composer import AIPromptComposer

        composer = AIPromptComposer.__new__(AIPromptComposer)
        items = [
            {"content_role": "TombstoneEpitaph",
             "role_instruction": "EPITAPHS: carve-style text, keep it terse."},
            {"content_role": "TombstoneEpitaph",
             "role_instruction": "EPITAPHS: carve-style text, keep it terse."},
        ]
        instructions = []
        seen_roles = set()
        for item in items:
            role = item.get("content_role")
            instruction = item.get("role_instruction")
            if not instruction or role in seen_roles:
                continue
            seen_roles.add(role)
            instructions.append(str(instruction))

        # Stated once, verbatim, for a role no engine module knows.
        assert instructions == ["EPITAPHS: carve-style text, keep it terse."]


class TestZeldaPluginFillsTheSlots:
    def _rules(self, fuki_kind):
        from plugins.zelda_bmg.rules import GameRules

        rules = GameRules.__new__(GameRules)
        rules.get_message_attributes = lambda b, s: {"fuki_kind": fuki_kind}
        rules.get_preview_window_style = lambda b, s: {"kind_name": "Boss name"}
        return rules

    def test_boss_card_supplies_its_own_instruction_and_suppresses_speaker(self):
        context = self._rules(19).get_translation_context_for_string(0, 0)
        assert context["content_role"] == "BossName"
        assert context["has_speaker"] is False
        assert "boss title/name card" in context["role_instruction"]

    def test_ordinary_dialogue_claims_nothing(self):
        context = self._rules(0).get_translation_context_for_string(0, 0)
        assert "role_instruction" not in context
        assert "has_speaker" not in context


class TestZeldaStructuralSeeds:
    """Terms TP names itself, read without a single AI call."""

    def _rules(self, data, kinds):
        from plugins.zelda_bmg.rules import GameRules

        rules = GameRules.__new__(GameRules)
        rules.mw = MagicMock()
        rules.mw.data_store.data = data
        rules.get_message_attributes = lambda b, s: {"fuki_kind": kinds[(b, s)]}
        return rules

    def test_location_plate_and_boss_card_are_whole_names(self):
        rules = self._rules(
            [["Ordon Village", "Diababa"]], {(0, 0): 12, (0, 1): 19}
        )
        seeds = {s["term"]: s for s in rules.get_glossary_seed_entries()}

        assert seeds["Ordon Village"]["section"] == "Places"
        assert seeds["Diababa"]["section"] == "Boss Names"
        assert seeds["Ordon Village"]["description"] == ""

    def test_item_window_splits_name_from_explanation(self):
        rules = self._rules(
            [["Hero's Bow\nFires arrows at distant targets."]], {(0, 0): 9}
        )
        seeds = rules.get_glossary_seed_entries()

        assert seeds[0]["term"] == "Hero's Bow"
        assert seeds[0]["description"] == "Fires arrows at distant targets."
        assert seeds[0]["section"] == "Items"

    def test_a_sentence_is_not_seeded_as_an_item_name(self):
        """"You got the Hero's Bow!" is prose, not a glossary term."""
        rules = self._rules(
            [["You got the Hero's Bow!\nUse it to fire arrows."]], {(0, 0): 9}
        )
        assert rules.get_glossary_seed_entries() == []

    def test_repeated_names_are_seeded_once(self):
        rules = self._rules(
            [["Ordon Village", "Ordon Village"]], {(0, 0): 12, (0, 1): 12}
        )
        assert len(rules.get_glossary_seed_entries()) == 1

    def test_other_window_kinds_are_left_to_the_ai_sweep(self):
        rules = self._rules([["Hello there, traveller."]], {(0, 0): 0})
        assert rules.get_glossary_seed_entries() == []

    def test_seeds_carry_their_provenance(self):
        rules = self._rules([["x"], ["Ordon Village"]], {(1, 0): 12, (0, 0): 0})
        seeds = rules.get_glossary_seed_entries()
        assert seeds[0]["source_ref"] == "block 1, string 0"
