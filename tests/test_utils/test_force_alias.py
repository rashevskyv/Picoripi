"""Tests for Force-alias utilities (utils/force_alias.py).

Covers:
- apply_aliases_to_text: replacing original tags with aliases
- extract_force_aliases: detecting {F:Word} patterns and replacing with plain words
- prepare_text_for_ai: full pipeline (apply + extract)
- restore_force_aliases_in_translation: restoring original tags in translated text
- Edge cases: empty inputs, missing glossary, multiple Force aliases, mixed tags
"""
from utils.force_alias import (
    ForceAliasMapping,
    apply_aliases_to_text,
    extract_force_aliases,
    prepare_text_for_ai,
    restore_force_aliases_in_translation,
)


# ── apply_aliases_to_text ───────────────────────────────────────────

class TestApplyAliasesToText:
    def test_basic_replacement(self):
        text = "Hello {escape:0:0000}!"
        mappings = {"{F:Link}": "{escape:0:0000}"}
        assert apply_aliases_to_text(text, mappings) == "Hello {F:Link}!"

    def test_multiple_replacements(self):
        text = "{escape:0:0000} and {escape:0:0022}"
        mappings = {
            "{F:Link}": "{escape:0:0000}",
            "{F:Epona}": "{escape:0:0022}",
        }
        result = apply_aliases_to_text(text, mappings)
        assert "{F:Link}" in result
        assert "{F:Epona}" in result

    def test_non_force_aliases_also_applied(self):
        text = "Press {escape:0:FFFF}"
        mappings = {"{Jump}": "{escape:0:FFFF}"}
        assert apply_aliases_to_text(text, mappings) == "Press {Jump}"

    def test_empty_text(self):
        assert apply_aliases_to_text("", {"{F:Link}": "{escape:0:0000}"}) == ""

    def test_none_text(self):
        assert apply_aliases_to_text(None, {"{F:Link}": "{escape:0:0000}"}) == ""

    def test_empty_mappings(self):
        text = "Hello {escape:0:0000}!"
        assert apply_aliases_to_text(text, {}) == text

    def test_longest_tag_first(self):
        """Longer original tags should be replaced first to avoid partial matches."""
        text = "{escape:0:00001}"
        mappings = {
            "{F:Short}": "{escape:0:0000}",
            "{F:Long}": "{escape:0:00001}",
        }
        result = apply_aliases_to_text(text, mappings)
        assert result == "{F:Long}"

    def test_same_tag_appears_twice(self):
        text = "{escape:0:0000} said hello to {escape:0:0000}"
        mappings = {"{F:Link}": "{escape:0:0000}"}
        result = apply_aliases_to_text(text, mappings)
        assert result == "{F:Link} said hello to {F:Link}"


# ── extract_force_aliases ───────────────────────────────────────────

class TestExtractForceAliases:
    def test_basic_extraction(self):
        text = "Hello {F:Link}!"
        mappings = {"{F:Link}": "{escape:0:0000}"}
        cleaned, aliases = extract_force_aliases(text, mappings)
        assert cleaned == "Hello Link!"
        assert len(aliases) == 1
        assert aliases[0].word == "Link"
        assert aliases[0].original_tag == "{escape:0:0000}"
        assert aliases[0].alias == "{F:Link}"

    def test_lowercase_f_prefix(self):
        text = "Hello {f:Link}!"
        mappings = {"{f:Link}": "{escape:0:0000}"}
        cleaned, aliases = extract_force_aliases(text, mappings)
        assert cleaned == "Hello Link!"
        assert len(aliases) == 1
        assert aliases[0].word == "Link"

    def test_multiple_force_aliases(self):
        text = "{F:Link} is riding {F:Epona}"
        mappings = {
            "{F:Link}": "{escape:0:0000}",
            "{F:Epona}": "{escape:0:0022}",
        }
        cleaned, aliases = extract_force_aliases(text, mappings)
        assert cleaned == "Link is riding Epona"
        assert len(aliases) == 2
        words = {a.word for a in aliases}
        assert words == {"Link", "Epona"}

    def test_non_force_aliases_untouched(self):
        text = "Hello {Jump} and {F:Link}!"
        mappings = {"{F:Link}": "{escape:0:0000}", "{Jump}": "{escape:0:FFFF}"}
        cleaned, aliases = extract_force_aliases(text, mappings)
        assert cleaned == "Hello {Jump} and Link!"
        assert len(aliases) == 1
        assert aliases[0].word == "Link"

    def test_no_force_aliases(self):
        text = "Hello {Jump} world"
        mappings = {"{Jump}": "{escape:0:FFFF}"}
        cleaned, aliases = extract_force_aliases(text, mappings)
        assert cleaned == text
        assert len(aliases) == 0

    def test_empty_text(self):
        cleaned, aliases = extract_force_aliases("", {})
        assert cleaned == ""
        assert aliases == []

    def test_force_alias_not_in_mappings(self):
        """If a Force alias doesn't have a mapping, original_tag should be empty."""
        text = "Hello {F:Unknown}!"
        mappings = {}
        cleaned, aliases = extract_force_aliases(text, mappings)
        assert cleaned == "Hello Unknown!"
        assert len(aliases) == 1
        assert aliases[0].original_tag == ""

    def test_same_force_alias_twice(self):
        text = "{F:Link} told {F:Link} to go"
        mappings = {"{F:Link}": "{escape:0:0000}"}
        cleaned, aliases = extract_force_aliases(text, mappings)
        assert cleaned == "Link told Link to go"
        assert len(aliases) == 2
        assert all(a.word == "Link" for a in aliases)


# ── prepare_text_for_ai ────────────────────────────────────────────

class TestPrepareTextForAI:
    def test_full_pipeline(self):
        """Original text with game tags -> Force words replaced, non-Force tags remain."""
        original = "I have a favor to ask of you, {escape:0:0000}."
        mappings = {"{F:Link}": "{escape:0:0000}"}
        result, force_maps = prepare_text_for_ai(original, mappings)
        assert result == "I have a favor to ask of you, Link."
        assert len(force_maps) == 1
        assert force_maps[0].word == "Link"
        assert force_maps[0].original_tag == "{escape:0:0000}"

    def test_mixed_force_and_regular_tags(self):
        original = "{Color:Red}{escape:0:0000} is here{Color:White}"
        mappings = {
            "{F:Link}": "{escape:0:0000}",
            "{Red}": "{Color:Red}",
            "{White}": "{Color:White}",
        }
        result, force_maps = prepare_text_for_ai(original, mappings)
        assert "Link" in result
        assert "{Red}" in result
        assert "{White}" in result
        assert "{F:Link}" not in result
        assert len(force_maps) == 1

    def test_no_force_aliases_returns_aliased_text(self):
        original = "{Color:Red}Hello world"
        mappings = {"{Red}": "{Color:Red}"}
        result, force_maps = prepare_text_for_ai(original, mappings)
        assert result == "{Red}Hello world"
        assert force_maps == []

    def test_empty_inputs(self):
        result, force_maps = prepare_text_for_ai("", {})
        assert result == ""
        assert force_maps == []

    def test_text_with_two_different_force_aliases(self):
        original = "{escape:0:0000} called {escape:0:0022} by name."
        mappings = {
            "{F:Link}": "{escape:0:0000}",
            "{F:Epona}": "{escape:0:0022}",
        }
        result, force_maps = prepare_text_for_ai(original, mappings)
        assert result == "Link called Epona by name."
        assert len(force_maps) == 2


# ── restore_force_aliases_in_translation ────────────────────────────

class TestRestoreForceAliasesInTranslation:
    def test_basic_restoration_with_glossary(self):
        """Force aliases are not restored to tags; they remain as plain translated text."""
        translated = "У мене є до тебе прохання, Лінку."
        force_maps = [ForceAliasMapping(word="Link", original_tag="{escape:0:0000}", alias="{F:Link}")]
        glossary = {"link": "Лінк; Лінку; Лінкові; Лінком"}
        result = restore_force_aliases_in_translation(translated, force_maps, glossary)
        assert result == "У мене є до тебе прохання, Лінку."

    def test_restoration_original_english_word(self):
        translated = "Hello Link, welcome back."
        force_maps = [ForceAliasMapping(word="Link", original_tag="{escape:0:0000}", alias="{F:Link}")]
        glossary = {}
        result = restore_force_aliases_in_translation(translated, force_maps, glossary)
        assert result == "Hello Link, welcome back."

    def test_restoration_multiple_aliases(self):
        translated = "Лінк скачет на Епоні."
        force_maps = [
            ForceAliasMapping(word="Link", original_tag="{escape:0:0000}", alias="{F:Link}"),
            ForceAliasMapping(word="Epona", original_tag="{escape:0:0022}", alias="{F:Epona}"),
        ]
        glossary = {
            "link": "Лінк; Лінку",
            "epona": "Епона; Епоні; Епоною",
        }
        result = restore_force_aliases_in_translation(translated, force_maps, glossary)
        assert result == "Лінк скачет на Епоні."

    def test_restoration_longest_form_preferred(self):
        translated = "Дай це Лінкові."
        force_maps = [ForceAliasMapping(word="Link", original_tag="{escape:0:0000}", alias="{F:Link}")]
        glossary = {"link": "Лінк; Лінкові"}
        result = restore_force_aliases_in_translation(translated, force_maps, glossary)
        assert result == "Дай це Лінкові."

    def test_restoration_case_insensitive(self):
        translated = "Привіт, лінк!"
        force_maps = [ForceAliasMapping(word="Link", original_tag="{escape:0:0000}", alias="{F:Link}")]
        glossary = {"link": "Лінк"}
        result = restore_force_aliases_in_translation(translated, force_maps, glossary)
        assert result == "Привіт, лінк!"

    def test_no_force_mappings(self):
        translated = "Hello world"
        result = restore_force_aliases_in_translation(translated, [], {})
        assert result == "Hello world"

    def test_empty_translation(self):
        force_maps = [ForceAliasMapping(word="Link", original_tag="{escape:0:0000}", alias="{F:Link}")]
        result = restore_force_aliases_in_translation("", force_maps, {})
        assert result == ""

    def test_word_boundary_respected(self):
        translated = "Лінкольн — не Лінк."
        force_maps = [ForceAliasMapping(word="Link", original_tag="{escape:0:0000}", alias="{F:Link}")]
        glossary = {"link": "Лінк"}
        result = restore_force_aliases_in_translation(translated, force_maps, glossary)
        assert result == "Лінкольн — не Лінк."

    def test_restoration_with_semicolon_separated_translations(self):
        translated = "Я бачив Лінком у селі."
        force_maps = [ForceAliasMapping(word="Link", original_tag="{escape:0:0000}", alias="{F:Link}")]
        glossary = {"link": "Лінк; Лінку; Лінкові; Лінком"}
        result = restore_force_aliases_in_translation(translated, force_maps, glossary)
        assert result == "Я бачив Лінком у селі."

    def test_restoration_same_word_appears_twice(self):
        translated = "Лінк розмовляє з Лінком."
        force_maps = [
            ForceAliasMapping(word="Link", original_tag="{escape:0:0000}", alias="{F:Link}"),
            ForceAliasMapping(word="Link", original_tag="{escape:0:0000}", alias="{F:Link}"),
        ]
        glossary = {"link": "Лінк; Лінком"}
        result = restore_force_aliases_in_translation(translated, force_maps, glossary)
        assert result == "Лінк розмовляє з Лінком."

    def test_fallback_when_no_glossary_match(self):
        translated = "Привіт, Link!"
        force_maps = [ForceAliasMapping(word="Link", original_tag="{escape:0:0000}", alias="{F:Link}")]
        glossary = {}
        result = restore_force_aliases_in_translation(translated, force_maps, glossary)
        assert result == "Привіт, Link!"

    def test_real_world_scenario_full_cycle(self):
        original = "I have a favor to ask of you, {escape:0:0000}."
        tag_mappings = {"{F:Link}": "{escape:0:0000}"}

        prepared, force_maps = prepare_text_for_ai(original, tag_mappings)
        assert prepared == "I have a favor to ask of you, Link."

        ai_translation = "У мене є до тебе прохання, Лінку."

        glossary = {"link": "Лінк; Лінку; Лінкові; Лінком"}
        restored = restore_force_aliases_in_translation(ai_translation, force_maps, glossary)
        assert restored == "У мене є до тебе прохання, Лінку."

    def test_real_world_scenario_horse_name(self):
        original = "Your horse, {escape:0:0022}, is waiting for you."
        tag_mappings = {"{F:Epona}": "{escape:0:0022}"}

        prepared, force_maps = prepare_text_for_ai(original, tag_mappings)
        assert prepared == "Your horse, Epona, is waiting for you."

        ai_translation = "Ваш кінь, Епона, чекає на вас."

        glossary = {"epona": "Епона; Епони; Епоні; Епоною"}
        restored = restore_force_aliases_in_translation(ai_translation, force_maps, glossary)
        assert restored == "Ваш кінь, Епона, чекає на вас."

    def test_real_world_scenario_both_player_and_horse(self):
        original = "{escape:0:0000} mounted {escape:0:0022} and rode away."
        tag_mappings = {
            "{F:Link}": "{escape:0:0000}",
            "{F:Epona}": "{escape:0:0022}",
        }

        prepared, force_maps = prepare_text_for_ai(original, tag_mappings)
        assert prepared == "Link mounted Epona and rode away."

        ai_translation = "Лінк сів на Епону і поїхав."

        glossary = {
            "link": "Лінк; Лінку; Лінкові; Лінком",
            "epona": "Епона; Епони; Епоні; Епоною; Епону",
        }
        restored = restore_force_aliases_in_translation(ai_translation, force_maps, glossary)
        assert restored == "Лінк сів на Епону і поїхав."


# ── Integration with GlossaryManager.get_relevant_terms ─────────────

class TestGlossaryIntegration:
    """Verify that after Force-alias substitution, glossary matching works."""

    def test_force_alias_word_found_by_glossary(self):
        """After prepare_text_for_ai, the word 'Link' should be detectable by glossary."""
        from core.glossary_manager import GlossaryManager

        gm = GlossaryManager()
        gm.load_from_text(
            plugin_name=None,
            glossary_path=None,
            raw_text='[{"original": "Link", "translation": "Лінк", "notes": "Main hero"}]',
        )

        original = "I need {escape:0:0000} to come here."
        tag_mappings = {"{F:Link}": "{escape:0:0000}"}
        prepared, force_maps = prepare_text_for_ai(original, tag_mappings)
        assert "Link" in prepared

        relevant = gm.get_relevant_terms(prepared)
        originals = [e.original for e in relevant]
        assert "Link" in originals

    def test_force_alias_word_with_surrounding_text(self):
        """Glossary should find 'Epona' in prepared text with surrounding words."""
        from core.glossary_manager import GlossaryManager

        gm = GlossaryManager()
        gm.load_from_text(
            plugin_name=None,
            glossary_path=None,
            raw_text='[{"original": "Epona", "translation": "Епона", "notes": "Horse"}]',
        )

        original = "Your horse {escape:0:0022} is fast."
        tag_mappings = {"{F:Epona}": "{escape:0:0022}"}
        prepared, _ = prepare_text_for_ai(original, tag_mappings)

        relevant = gm.get_relevant_terms(prepared)
        originals = [e.original for e in relevant]
        assert "Epona" in originals
