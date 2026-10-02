"""Which glossary rows reach a translation prompt, and how they are matched (WP3 3.4)."""
from core.glossary.models import GlossaryEntry
from core.glossary.occurrence_mixin import RELEVANT_TERMS_LIMIT
from core.glossary_manager import STATUS_CONFIRMED, STATUS_SEEDED, STATUS_TRANSLATED, GlossaryManager
from core.translation.glossary_formatter import NOTES_LIMIT, GlossaryPromptFormatter


def _manager(*rows):
    """rows: (original, translation) or (original, translation, status)."""
    manager = GlossaryManager()
    manager.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
    for original, translation, *rest in rows:
        manager.add_entry(original, translation, "", fold_variants=False)
        if rest:
            manager.update_entry(original, translation, "", status=rest[0])
    return manager


def _found(manager, text):
    return [(m.entry.original, text[m.start:m.end]) for m in manager.find_matches(text)]


def _relevant(manager, text, **kwargs):
    return [entry.original for entry in manager.get_relevant_terms(text, **kwargs)]


class TestPluralTolerantMatching:
    def test_a_plural_in_the_text_finds_the_singular_entry(self):
        manager = _manager(("Rupee", "Рупія"), ("Fox", "Лис"), ("Fairy", "Фея"))

        assert _found(manager, "You got 20 Rupees!") == [("Rupee", "Rupees")]
        assert _found(manager, "Two foxes and three fairies.") == [("Fox", "foxes"), ("Fairy", "fairies")]

    def test_a_term_is_still_matched_only_as_a_whole_word(self):
        manager = _manager(("oat", "овес"), ("Rupee", "Рупія"))

        assert _found(manager, "The boats float; no Rupeesque oath.") == []

    def test_the_entry_spelled_exactly_like_the_text_wins(self):
        manager = _manager(("Clawshot", "Кігтемет"), ("Clawshots", "Кігтемети"))

        assert _found(manager, "Clawshots!") == [("Clawshots", "Clawshots")]
        assert _found(manager, "A Clawshot.") == [("Clawshot", "Clawshot")]

    def test_a_plural_of_a_term_split_by_a_tag_is_found(self):
        manager = _manager(("Hylian Shield", "Хайлійський щит"))

        assert _found(manager, "Two Hylian{Color:Red} Shields here") == [("Hylian Shield", "Hylian{Color:Red} Shields")]
        assert _found(manager, "Two Hylian Shields here") == [("Hylian Shield", "Hylian Shields")]

    def test_a_non_latin_or_very_short_term_gets_no_plural(self):
        manager = _manager(("Меч", "Sword"), ("It", "Воно"))

        assert _found(manager, "Мечs and Its") == []

    def test_an_alias_in_the_text_finds_its_entry(self):
        manager = _manager(("Postman", "Листоноша"))
        manager._entries[0] = GlossaryEntry("Postman", "Листоноша", aliases=("Mailman",))
        manager._build_pattern_cache()

        assert _found(manager, "The mailman runs. Mailmans?") == [("Postman", "mailman"), ("Postman", "Mailmans")]


class TestRelevantTerms:
    def test_a_term_inside_a_longer_term_is_not_listed_on_its_own(self):
        manager = _manager(("Hylia", "Хайлія"), ("Lake", "Озеро"), ("Lake Hylia", "Озеро Хайлія"))

        assert _relevant(manager, "Go to Lake Hylia") == ["Lake Hylia"]

    def test_it_is_listed_when_it_also_stands_alone(self):
        manager = _manager(("Hylia", "Хайлія"), ("Lake Hylia", "Озеро Хайлія"))

        assert _relevant(manager, "Go to Lake Hylia, blessed by Hylia.") == ["Lake Hylia", "Hylia"]

    def test_an_entry_without_a_translation_is_left_out_of_the_prompt(self):
        manager = _manager(("Zora", "", STATUS_SEEDED), ("Rupee", "Рупія"))

        assert _relevant(manager, "A Zora took my Rupee.") == ["Rupee"]
        assert _relevant(manager, "A Zora took my Rupee.", translated_only=False) == ["Zora", "Rupee"]

    def test_an_untranslated_longer_term_does_not_hide_the_translated_one_inside_it(self):
        manager = _manager(("Hylia", "Хайлія"), ("Lake Hylia", "", STATUS_SEEDED))

        assert _relevant(manager, "Go to Lake Hylia") == ["Hylia"]

    def test_the_list_is_capped_by_rank_and_stays_in_text_order(self):
        rows = [(f"Term{index:02d}x", "переклад", STATUS_TRANSLATED) for index in range(RELEVANT_TERMS_LIMIT)]
        manager = _manager(("Draftword", "чернетка", STATUS_SEEDED), *rows, ("Kingname", "Король", STATUS_CONFIRMED))
        text = "Draftword " + " ".join(original for original, *_ in rows) + " Kingname"

        relevant = _relevant(manager, text)

        assert len(relevant) == RELEVANT_TERMS_LIMIT
        assert "Kingname" in relevant and "Draftword" not in relevant      # a person's decision in, a draft out
        assert relevant == sorted(relevant, key=text.index)
        assert len(_relevant(manager, text, limit=None)) == RELEVANT_TERMS_LIMIT + 2

    def test_among_equals_the_term_mentioned_more_often_is_kept(self):
        manager = _manager(("Alpha", "А"), ("Bravo", "Б"), ("Charlie", "В"))

        assert _relevant(manager, "Alpha Bravo Charlie Charlie Bravo", limit=2) == ["Bravo", "Charlie"]


class TestPromptTable:
    def test_a_long_note_is_cut_at_a_word_and_marked(self):
        entry = GlossaryEntry("Zora", "Зора", notes="{{TERM}} — річковий народ. " + "дуже довга примітка " * 40)

        table = GlossaryPromptFormatter().glossary_entries_to_text([entry])
        notes = table.splitlines()[2].split(" | ")[2].rstrip(" |")

        assert len(notes) <= NOTES_LIMIT + 1 and notes.endswith("…") and not notes.endswith(" …")
        assert notes.startswith("Зора — річковий народ.")

    def test_a_short_note_is_left_alone(self):
        entry = GlossaryEntry("Zora", "Зора", notes="{{TERM}} — річковий народ.")

        assert GlossaryPromptFormatter().glossary_entries_to_text([entry]).endswith("| Зора — річковий народ. |")
