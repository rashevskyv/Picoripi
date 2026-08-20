"""Seeding the glossary from a marked-up script's own speaker marks."""
from types import SimpleNamespace

from core.glossary_build.script_seeds import seeds_from_markup


def _project(lines, marks):
    """``marks`` are ``(line_index, type_id)`` over ``lines``."""
    return SimpleNamespace(
        raw_text="\n".join(lines),
        approved_marks=tuple(
            SimpleNamespace(start_line=i, end_line=i, type_id=t, text="", label="",
                            start_col=None, end_col=None, origin="manual")
            for i, t in marks
        ),
    )


class TestSeedsFromMarkup:
    def test_every_speaker_becomes_a_character_term(self):
        project = _project(
            ["RENADO", "Welcome.", "TELMA", "Come in, honey."],
            [(0, "speaker"), (1, "text"), (2, "speaker"), (3, "text")],
        )

        seeds = seeds_from_markup(project)

        assert [s["term"] for s in seeds] == ["RENADO", "TELMA"]
        assert {s["section"] for s in seeds} == {"Characters"}

    def test_a_speaker_is_seeded_once_however_often_they_talk(self):
        project = _project(
            ["MIDNA", "a", "MIDNA", "b", "MIDNA", "c"],
            [(0, "speaker"), (1, "text"), (2, "speaker"), (3, "text"), (4, "speaker"), (5, "text")],
        )

        assert [s["term"] for s in seeds_from_markup(project)] == ["MIDNA"]

    def test_the_same_name_in_another_case_is_not_a_second_term(self):
        """The glossary matches terms case-insensitively; seeding must too."""
        project = _project(["MIDNA", "a", "Midna", "b"], [(0, "speaker"), (2, "speaker")])

        assert [s["term"] for s in seeds_from_markup(project)] == ["MIDNA"]

    def test_only_speakers_are_taken(self):
        """Acts and scenes are headings, and an Item mark names the window."""
        project = _project(
            ["Act One", "Scene 1", "SYSTEM", "You got the lantern!", "RENADO"],
            [(0, "structure"), (1, "structure"), (2, "item"),
             (3, "item_description"), (4, "speaker")],
        )

        assert [s["term"] for s in seeds_from_markup(project)] == ["RENADO"]

    def test_a_seed_carries_no_description(self):
        """The script says who spoke, never who they are."""
        seeds = seeds_from_markup(_project(["RENADO"], [(0, "speaker")]))

        assert not seeds[0].get("description")
        assert seeds[0]["source_ref"] == "script markup"

    def test_no_markup_project_is_not_an_error(self):
        assert seeds_from_markup(None) == []
        assert seeds_from_markup(SimpleNamespace(raw_text="", approved_marks=())) == []


class TestSectionBreakdown:
    """"Items are missing" and "Items were already there" must look different."""

    def _coordinator(self, seeds):
        from core.glossary_build.pipeline_coordinator import GlossaryBuildCoordinator
        from core.glossary_manager import GlossaryManager

        manager = GlossaryManager()
        manager.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
        return GlossaryBuildCoordinator(
            manager, lambda _m: "", {}, structural_seeds=seeds
        ), manager

    def test_each_section_reports_what_the_sources_offered(self):
        from core.glossary_build.pipeline_coordinator import MODE_SEED

        coordinator, _ = self._coordinator([
            {"term": "Lantern", "section": "Items"},
            {"term": "Ordon", "section": "Places"},
            {"term": "RENADO", "section": "Characters"},
            {"term": "TALO", "section": "Characters"},
        ])

        result = coordinator.build(dataset=[["a line"]], mode=MODE_SEED)

        assert result.offered_by_section == {"Items": 1, "Places": 1, "Characters": 2}

    def test_a_section_offering_nothing_is_absent_from_the_breakdown(self):
        from core.glossary_build.pipeline_coordinator import MODE_SEED

        coordinator, _ = self._coordinator([{"term": "RENADO", "section": "Characters"}])

        result = coordinator.build(dataset=[["a line"]], mode=MODE_SEED)

        assert "Items" not in result.offered_by_section


class TestProvisionalTerms:
    """A term that is an actor id is a stand-in, and must be shown as one."""

    def _seed(self, seeds):
        from core.glossary_build.pipeline_coordinator import (
            MODE_SEED,
            GlossaryBuildCoordinator,
        )
        from core.glossary_manager import GlossaryManager

        manager = GlossaryManager()
        manager.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
        GlossaryBuildCoordinator(
            manager, lambda _m: "", {}, structural_seeds=seeds
        ).build(dataset=[["a line"]], mode=MODE_SEED)
        return manager

    def test_a_flagged_seed_becomes_a_provisional_entry(self):
        manager = self._seed([
            {"term": "CLERK_B", "section": "Characters", "provisional": True},
            {"term": "RENADO", "section": "Characters"},
        ])

        assert manager.get_entry("CLERK_B").provisional is True
        assert manager.get_entry("RENADO").provisional is False

    def test_the_flag_survives_a_save_and_reload(self):
        """It has to outlive the session that seeded it, like any other field."""
        from core.glossary_manager import GlossaryManager, _entry_to_dict
        import json

        manager = self._seed([{"term": "CLERK_B", "provisional": True}])
        raw = json.dumps([_entry_to_dict(e) for e in manager.get_entries()])

        reloaded = GlossaryManager()
        reloaded.load_from_text(plugin_name=None, glossary_path=None, raw_text=raw)

        assert reloaded.get_entry("CLERK_B").provisional is True


class TestNameSuggestions:
    """A description written from a character's lines usually names them."""

    def _suggest(self, reply):
        import json as _json

        from core.glossary_build.ai_adapters import make_name_suggester

        prompts = {"name": {
            "system_prompt": "sys {target_lang}",
            "user_prompt_template": "{term} {description}",
        }}
        return make_name_suggester(lambda _m: _json.dumps(reply), prompts)

    def test_the_name_comes_back_as_a_field_not_prose(self):
        guess = self._suggest(
            {"name": "BARNES", "confidence": "high", "evidence": "advertises Barnes's bombs"}
        )("Bans", "Advertises the bombs sold at Barnes's shop.")

        assert guess.name == "BARNES"
        assert guess.is_confident
        assert "Barnes" in guess.evidence

    def test_a_low_confidence_guess_says_so(self):
        guess = self._suggest({"name": "VILLAGER", "confidence": "low"})("X", "A villager.")

        assert guess.name == "VILLAGER"
        assert not guess.is_confident

    def test_an_empty_answer_is_a_valid_answer(self):
        """Better no name than a wrong one stamped onto every line."""
        guess = self._suggest({"name": "", "confidence": "low"})("X", "Says hello.")

        assert guess.name == ""
        assert not guess.is_confident

    def test_a_term_with_no_description_is_never_asked_about(self):
        calls = []
        from core.glossary_build.ai_adapters import make_name_suggester

        prompts = {"name": {"system_prompt": "s", "user_prompt_template": "u"}}
        suggest = make_name_suggester(lambda m: calls.append(m) or '{"name":"X"}', prompts)

        assert suggest("Bans", "").name == ""
        assert calls == []

    def test_a_suggestion_is_stored_but_never_applied(self):
        """Renaming a character rewrites every line they speak."""
        from core.glossary_manager import GlossaryManager

        manager = GlossaryManager()
        manager.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
        manager.seed_entry("Bans", section="Characters", provisional=True)

        manager.suggest_name("Bans", "BARNES", "advertises Barnes's bombs")

        entry = manager.get_entry("Bans")
        assert entry.original == "Bans"          # the term is untouched
        assert entry.suggested_name == "BARNES"
        assert "Barnes" in entry.suggested_name_evidence

    def test_editing_an_entry_keeps_its_suggestion_and_its_flag(self):
        from core.glossary_manager import GlossaryManager

        manager = GlossaryManager()
        manager.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
        manager.seed_entry("Bans", section="Characters", provisional=True)
        manager.suggest_name("Bans", "BARNES")

        manager.update_entry("Bans", translation="Барнс", notes="a shopkeeper")

        entry = manager.get_entry("Bans")
        assert entry.provisional is True
        assert entry.suggested_name == "BARNES"

    def test_coordinator_stores_a_suggestion_without_applying_it(self):
        import json

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
        prompts = {"name": {
            "system_prompt": "sys {target_lang}",
            "user_prompt_template": "{term} {description}",
        }}
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
        assert result.names_suggested == 1
