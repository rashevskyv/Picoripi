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


class TestSpeakerFromGameData:
    """The game binds a dialogue to its NPC in data, not in code."""

    def test_default_is_no_answer(self):
        assert BaseGameRules().get_speaker_for_string(0, 0) is None

    def _rules(self, msg_group=1, flow_ids=(8,), index=None):
        from plugins.zelda_bmg.rules import GameRules

        rules = GameRules.__new__(GameRules)
        rules._get_msg_group_for_block = lambda b: msg_group
        ctx = MagicMock()
        ctx.flows_for_message.return_value = list(flow_ids)
        rules._get_flow_context_for_block = lambda b: ctx
        rules._flow_speaker_index_cache = (
            {(1, 8): "Bou", (1, 12): "Jagar"} if index is None else index
        )
        return rules

    def test_a_line_resolves_to_the_npc_holding_its_flow(self):
        assert self._rules(flow_ids=(8,)).get_speaker_for_string(0, 0) == "Bou"
        assert self._rules(flow_ids=(12,)).get_speaker_for_string(0, 5) == "Jagar"

    def test_flow_numbers_are_scoped_by_message_group(self):
        """Node 8 in another bmgres is a different conversation entirely."""
        assert self._rules(msg_group=2, flow_ids=(8,)).get_speaker_for_string(0, 0) is None

    def test_a_line_in_several_conversations_is_ambiguous(self):
        assert self._rules(flow_ids=(8, 12)).get_speaker_for_string(0, 0) is None

    def test_an_unowned_flow_yields_nothing(self):
        assert self._rules(flow_ids=(999,)).get_speaker_for_string(0, 0) is None

    def test_no_message_group_means_no_answer(self):
        assert self._rules(msg_group=None).get_speaker_for_string(0, 0) is None


class TestFlowSpeakerIndex:
    """Built from the shipped extraction of the retail stage arcs."""

    def test_ambiguous_nodes_are_dropped(self):
        from plugins.zelda_bmg.stage_data import flow_speaker_index

        doc = {"stages": {
            "A": {"msg_group": 1, "flow_owner": {"5": "Bou"}},
            "B": {"msg_group": 1, "flow_owner": {"5": "Kolin", "6": "Taro"}},
        }}
        index = flow_speaker_index(doc)

        assert (1, 5) not in index          # two NPCs claim it
        assert index[(1, 6)] == "Taro"

    def test_the_shipped_data_actually_binds_speakers(self):
        """Guards the extraction: an empty index would silently disable this."""
        from plugins.zelda_bmg.stage_data import flow_speaker_index, load_stage_scene_data

        index = flow_speaker_index(load_stage_scene_data())

        assert len(index) > 200
        # Ordon's mayor, read from F_SP103 R00's ACTR angle.x.
        assert index[(1, 8)] == "Bou"


class TestSpeakerSeeds:
    """NPCs that hold conversations become glossary Characters entries."""

    def _rules(self, msg_groups=(1,), index=None):
        from plugins.zelda_bmg.rules import GameRules

        rules = GameRules.__new__(GameRules)
        rules.mw = MagicMock()
        rules.mw.data_store.data = [["a line"]]
        rules.get_message_attributes = lambda b, s: None      # no window seeds
        rules._get_msg_group_for_block = lambda b: msg_groups[0]
        rules._flow_speaker_index_cache = index if index is not None else {
            (1, 8): "Bou", (1, 12): "Jagar", (2, 3): "Ashei",
        }
        return rules

    def test_npcs_of_the_loaded_group_are_seeded(self):
        seeds = {s["term"]: s for s in self._rules().get_glossary_seed_entries()}

        assert set(seeds) == {"Bou", "Jagar"}          # group 2 is not loaded
        assert seeds["Bou"]["section"] == "Characters"

    def test_speakers_carry_no_description(self):
        """The describe pass reads their own lines and works out who they are."""
        seeds = self._rules().get_glossary_seed_entries()
        assert all(s["description"] == "" for s in seeds)

    def test_provenance_names_the_flow_it_came_from(self):
        seeds = {s["term"]: s for s in self._rules().get_glossary_seed_entries()}
        assert seeds["Bou"]["source_ref"] == "bmgres1 dialogue flow 8"

    def test_one_npc_with_many_flows_is_seeded_once(self):
        rules = self._rules(index={(1, 8): "Bou", (1, 51): "Bou", (1, 52): "Bou"})
        assert [s["term"] for s in rules.get_glossary_seed_entries()] == ["Bou"]
