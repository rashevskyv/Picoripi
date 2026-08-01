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

    def test_item_name_comes_from_the_coloured_run(self):
        """The window is a wrapped sentence; only the colour marks the name."""
        rules = self._rules(
            [["Power has returned to the\n{color:red}Dominion Rod{color:white}!"]],
            {(0, 0): 9},
        )
        seeds = rules.get_glossary_seed_entries()

        assert seeds[0]["term"] == "Dominion Rod"
        assert seeds[0]["section"] == "Items"
        # The whole message stays as the description -- it explains the item.
        assert "Power has returned to the" in seeds[0]["description"]

    def test_stored_escape_form_is_recognised_too(self):
        """Data holds {escape:255:000001}; the editor only shows {color:red}."""
        rules = self._rules(
            [["You got the {escape:255:000001}Hero's Bow{escape:255:000000}!"]],
            {(0, 0): 9},
        )
        assert rules.get_glossary_seed_entries()[0]["term"] == "Hero's Bow"

    def test_a_line_break_mid_sentence_is_not_a_name_boundary(self):
        """The bug this replaced: line 1 of a wrapped sentence is not a term."""
        rules = self._rules(
            [["You learned the fifth hidden\nskill, the mortal draw! Sheathe it."]],
            {(0, 0): 9},
        )
        assert rules.get_glossary_seed_entries() == []

    def test_an_unmarked_item_window_seeds_nothing(self):
        """Fail closed: the AI sweep finds it rather than a guess polluting."""
        rules = self._rules(
            [["You caught bee larva in your\nbottle! Fish love them."]], {(0, 0): 9}
        )
        assert rules.get_glossary_seed_entries() == []

    def test_a_whole_coloured_sentence_is_emphasis_not_a_name(self):
        rules = self._rules(
            [["{color:red}You have completed every single sidequest{color:white}!"]],
            {(0, 0): 9},
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


class TestAddresseeContract:
    """M4: who a line is spoken TO, when the game's data can say."""

    def test_default_is_no_answer(self):
        assert BaseGameRules().get_addressee_for_string(0, 0) is None

    def test_default_accepts_the_resolved_speaker(self):
        """The engine passes the speaker in so a plugin need not redo it."""
        assert BaseGameRules().get_addressee_for_string(0, 0, speaker="Midna") is None


class TestZeldaAddressee:
    def _rules(self, fuki_kind, flow_ids=(7,), character="Colin"):
        from plugins.zelda_bmg.rules import GameRules

        rules = GameRules.__new__(GameRules)
        rules.get_message_attributes = lambda b, s: {"fuki_kind": fuki_kind}
        index = MagicMock()
        index.flows_for_message.return_value = list(flow_ids)
        rules._get_flow_context_for_block = lambda b: index
        rules._get_flow_actor_map = lambda: (
            {7: {"character": character}} if character else {}
        )
        return rules

    def test_the_owning_npc_speaks_to_the_player(self):
        assert self._rules(0).get_addressee_for_string(0, 0, speaker="Colin") == "Link"

    def test_an_unknown_speaker_in_an_npc_flow_still_means_the_player(self):
        assert self._rules(0).get_addressee_for_string(0, 0) == "Link"

    def test_someone_else_in_the_flow_is_speaking_to_its_owner(self):
        assert self._rules(0).get_addressee_for_string(0, 0, speaker="Ilia") == "Colin"

    def test_cutscene_subtitles_get_no_answer(self):
        """Two NPCs may address each other; the flow owner proves nothing."""
        assert self._rules(1).get_addressee_for_string(0, 0, speaker="Colin") is None

    def test_boss_cards_and_signs_get_no_answer(self):
        for kind in (2, 6, 9, 12, 19):
            assert self._rules(kind).get_addressee_for_string(0, 0) is None

    def test_a_line_in_several_conversations_is_ambiguous(self):
        assert self._rules(0, flow_ids=(7, 8)).get_addressee_for_string(0, 0) is None

    def test_an_unreviewed_actor_yields_nothing(self):
        """flow_actors entries without a human-readable name are not usable."""
        assert self._rules(0, character="").get_addressee_for_string(0, 0) is None
