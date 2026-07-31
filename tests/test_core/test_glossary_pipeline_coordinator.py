"""Tests for the build coordinator (core/glossary_build/pipeline_coordinator.py).

The AI call is faked and routed by the pass-specific prompt wording, so the
whole thorough/draft/augment/translate flow runs against an in-memory manager
without a model.
"""
import json
from pathlib import Path

from core.glossary_build.pipeline_coordinator import (
    MODE_AUGMENT,
    MODE_DRAFT,
    MODE_SEED,
    MODE_THOROUGH,
    MODE_TRANSLATE,
    GlossaryBuildCoordinator,
)
from core.glossary_manager import (
    STATUS_FRAGMENTS,
    STATUS_SYNTHESIZED,
    STATUS_TRANSLATED,
    GlossaryManager,
)

PROMPTS = json.loads(
    Path("translation_prompts/glossary_pipeline_prompts.json").read_text(encoding="utf-8")
)


class FakeAI:
    """Routes a call to a canned reply based on the pass-specific user prompt."""

    def __init__(self, extract=None, description="a description", variants=None):
        self.extract = extract if extract is not None else [
            {"term": "Ordon", "section": "Places", "fragment": "a village"},
            {"term": "Link", "section": "Characters", "fragment": "the hero"},
        ]
        self.description = description
        self.variants = variants if variants is not None else [
            {"translation": "Ордон", "rationale": "translit"}
        ]
        self.calls = []

    def __call__(self, messages):
        user = messages[1]["content"]
        self.calls.append(user)
        if "Game text chunk" in user:
            return json.dumps(self.extract)
        if "Excerpts where it appears" in user:
            return json.dumps({"description": self.description})
        if "Partial descriptions" in user:
            return json.dumps({"description": "folded"})
        if "Description:" in user:
            return json.dumps(self.variants)
        return "[]"


def _manager():
    m = GlossaryManager()
    m.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
    return m


DATASET = [["Ordon village is calm today", "Link visits Ordon often"]]


class TestThorough:
    def test_seeds_then_describes(self):
        m = _manager()
        ai = FakeAI()
        coord = GlossaryBuildCoordinator(m, ai, PROMPTS)
        result = coord.build(DATASET, MODE_THOROUGH)

        assert result.seeded == 2
        assert result.described == 2
        ordon = m.get_entry("Ordon")
        assert ordon.status == STATUS_SYNTHESIZED
        assert ordon.notes == "a description"
        assert ordon.section == "Places"
        assert ordon.translation == ""  # translation waits for pass 3
        assert ordon.is_valid()

    def test_does_not_overwrite_real_entry(self):
        m = _manager()
        m.add_entry("Link", "Лінк", "existing hero note")
        coord = GlossaryBuildCoordinator(m, FakeAI(), PROMPTS)
        coord.build(DATASET, MODE_THOROUGH)

        link = m.get_entry("Link")
        assert link.translation == "Лінк"  # untouched
        assert link.status == ""  # not seeded/described over


class TestDraft:
    def test_seeds_with_fragment_no_describe(self):
        m = _manager()
        ai = FakeAI()
        coord = GlossaryBuildCoordinator(m, ai, PROMPTS)
        result = coord.build(DATASET, MODE_DRAFT)

        assert result.seeded == 2
        assert result.described == 0
        ordon = m.get_entry("Ordon")
        assert ordon.status == STATUS_FRAGMENTS
        assert ordon.notes == "a village"  # the sweep fragment
        # no describe call was made
        assert not any("Excerpts where it appears" in c for c in ai.calls)


class TestAugment:
    def test_describes_existing_seeded_entries(self):
        m = _manager()
        m.seed_entry("Ordon", section="Places")  # status seeded, no description
        ai = FakeAI()
        coord = GlossaryBuildCoordinator(m, ai, PROMPTS)
        result = coord.build(DATASET, MODE_AUGMENT)

        assert result.seeded == 0  # augment never seeds
        assert result.described == 1
        assert m.get_entry("Ordon").status == STATUS_SYNTHESIZED
        # augment did not sweep
        assert not any("Game text chunk" in c for c in ai.calls)


class TestTranslate:
    def test_proposes_and_sets_active(self):
        m = _manager()
        coord = GlossaryBuildCoordinator(m, FakeAI(), PROMPTS)
        coord.build(DATASET, MODE_THOROUGH)
        result = coord.run_translate()

        assert result.translated == 2
        ordon = m.get_entry("Ordon")
        assert ordon.translation == "Ордон"
        assert ordon.status == STATUS_TRANSLATED
        assert len(ordon.translation_variants) == 1

    def test_multiple_variants_stored(self):
        m = _manager()
        ai = FakeAI(
            variants=[
                {"translation": "Ґорон Джерела", "rationale": "spring=bath"},
                {"translation": "Весняний Ґорон", "rationale": "spring=season"},
            ]
        )
        coord = GlossaryBuildCoordinator(m, ai, PROMPTS)
        coord.build(DATASET, MODE_THOROUGH)
        coord.run_translate()

        ordon = m.get_entry("Ordon")
        assert len(ordon.translation_variants) == 2
        assert ordon.is_unconfirmed  # translated but not confirmed -> yellow


class TestTranslateOnly:
    """Running the translation pass on its own, after skipping it earlier."""

    def test_translate_only_does_not_sweep_or_describe(self):
        m = _manager()
        m.seed_entry("Ordon", section="Places", description="a village")
        ai = FakeAI()
        coord = GlossaryBuildCoordinator(m, ai, PROMPTS)

        result = coord.build(DATASET, MODE_TRANSLATE)
        coord.run_translate(result)

        assert result.seeded == 0
        assert result.described == 0
        assert result.translated == 1
        assert not any("Game text chunk" in c for c in ai.calls)
        assert not any("Excerpts where it appears" in c for c in ai.calls)
        assert m.get_entry("Ordon").translation == "Ордон"

    def test_entry_without_status_is_translated(self):
        """Entries from older tools or added by hand carry no status."""
        m = _manager()
        m.add_entry("Ordon", "", "a village")  # description, no translation
        coord = GlossaryBuildCoordinator(m, FakeAI(), PROMPTS)
        result = coord.run_translate()
        assert result.translated == 1

    def test_already_translated_entry_is_left_alone(self):
        m = _manager()
        m.add_entry("Ordon", "Мій Ордон", "a village")
        coord = GlossaryBuildCoordinator(m, FakeAI(), PROMPTS)
        result = coord.run_translate()
        assert result.translated == 0
        assert m.get_entry("Ordon").translation == "Мій Ордон"

    def test_entry_without_description_is_skipped(self):
        """Nothing to translate from — the term alone is not enough."""
        m = _manager()
        m.seed_entry("Ordon", section="Places")  # no description
        coord = GlossaryBuildCoordinator(m, FakeAI(), PROMPTS)
        result = coord.run_translate()
        assert result.translated == 0


class TestCancellation:
    def test_cancel_stops_before_work(self):
        m = _manager()
        coord = GlossaryBuildCoordinator(m, FakeAI(), PROMPTS, is_cancelled=lambda: True)
        result = coord.build(DATASET, MODE_THOROUGH)
        assert result.cancelled is True
        assert result.seeded == 0
        assert m.get_entries() == []


class TestProgress:
    def test_progress_stages_reported(self):
        m = _manager()
        stages = []
        coord = GlossaryBuildCoordinator(
            m, FakeAI(), PROMPTS, on_progress=lambda stage, d, t: stages.append(stage)
        )
        coord.build(DATASET, MODE_THOROUGH)
        assert "sweep" in stages
        assert "seed" in stages
        assert "describe" in stages


def _no_ai(messages):
    raise AssertionError("structural seeding must not call the model")


class TestStructuralSeeding:
    """Terms the game names itself: seeded without a single AI call."""

    SEEDS = [
        {"term": "Ordon Village", "section": "Places"},
        {"term": "Diababa", "section": "Boss Names"},
        {"term": "Hero's Bow", "section": "Items", "description": "Fires arrows."},
    ]

    def _coordinator(self, manager, call=None, **kw):
        return GlossaryBuildCoordinator(
            manager,
            call or _no_ai,
            PROMPTS,
            structural_seeds=self.SEEDS,
            **kw,
        )

    def test_seed_mode_makes_no_ai_call(self):
        manager = _manager()
        result = self._coordinator(manager).build([["anything"]], MODE_SEED)

        assert result.seeded == 3
        assert manager.get_entry("Ordon Village").section == "Places"
        assert manager.get_entry("Diababa").section == "Boss Names"

    def test_a_supplied_description_lands_as_notes(self):
        manager = _manager()
        self._coordinator(manager).build([["anything"]], MODE_SEED)

        entry = manager.get_entry("Hero's Bow")
        assert entry.notes == "Fires arrows."
        assert entry.status == STATUS_FRAGMENTS

    def test_seeding_never_overwrites_a_decided_entry(self):
        manager = _manager()
        manager.add_entry("Diababa", "Діабаба", "my own note")

        self._coordinator(manager).build([["anything"]], MODE_SEED)

        entry = manager.get_entry("Diababa")
        assert entry.translation == "Діабаба"
        assert entry.notes == "my own note"

    def test_blank_terms_are_ignored(self):
        manager = _manager()
        coordinator = GlossaryBuildCoordinator(
            manager, _no_ai, PROMPTS,
            structural_seeds=[{"term": "  "}, {"section": "Items"}],
        )
        assert coordinator.build([["x"]], MODE_SEED).seeded == 0
        assert manager.get_entries() == []
