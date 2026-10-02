"""Canonical key, aliases and the single lookup every glossary mutator uses (WP3 3.1)."""
import json

import pytest

from core.glossary_manager import STATUS_CONFIRMED, GlossaryManager, TranslationVariant


def _loaded(tmp_path, entries=()):
    path = tmp_path / "glossary.json"
    path.write_text(json.dumps(list(entries), ensure_ascii=False), encoding="utf-8")
    manager = GlossaryManager()
    manager.load_from_text(plugin_name=None, glossary_path=path, raw_text=path.read_text(encoding="utf-8"))
    return manager, path


class TestCanonicalKey:
    @pytest.mark.parametrize("term, key", [
        ("Hylian Shields", "hylian shield"),
        ("The Postman", "postman"),
        ("POSTMAN", "postman"),
        ("Fairy's Tears", "fairy tear"),
        ("Pieces of Heart", "piece of heart"),
        ("Items screen", "item screen"),
        ("Zoras", "zora"),
        ("boxes", "box"),
        ("glass", "glass"),          # -ss is not a plural
        ("Malus", "malus"),          # nor is -us
        ("lens", "lens"),
        ("Ooccoo Jr.", "ooccoo jr"),
        ("Свічки", "свічки"),        # only English plurals are folded
        ("", ""),
    ])
    def test_key(self, term, key):
        assert GlossaryManager.canonical_key(term) == key

    def test_groups_list_entries_that_share_a_key(self, tmp_path):
        manager, _ = _loaded(tmp_path, [
            {"original": "Rupee", "translation": "рупія"},
            {"original": "Rupees", "translation": "рупії"},
            {"original": "Lake Hylia", "translation": "озеро Гайлія"},
        ])
        assert [[e.original for e in group] for group in manager.canonical_groups()] == [["Rupee", "Rupees"]]


class TestOneLookupForEveryMutator:
    def test_add_entry_on_a_case_variant_updates_instead_of_appending(self, tmp_path):
        manager, _ = _loaded(tmp_path, [{"original": "Hylian Shield", "translation": "гайлійський щит",
                                         "status": "confirmed"}])
        manager.add_entry("Hylian shield", "щит Гайлії", "note")
        entries = manager.get_entries()
        assert len(entries) == 1
        assert (entries[0].original, entries[0].translation, entries[0].status) == (
            "Hylian Shield", "щит Гайлії", STATUS_CONFIRMED)

    def test_a_plural_from_an_automatic_source_is_folded_without_overwriting(self, tmp_path):
        manager, _ = _loaded(tmp_path, [{"original": "Rupee", "translation": "рупія", "notes": "Гроші"}])
        entry = manager.add_entry("Rupees", "рупії", "інший опис")
        assert len(manager.get_entries()) == 1
        assert (entry.original, entry.translation, entry.notes) == ("Rupee", "рупія", "Гроші")

    def test_a_plural_fills_gaps_of_the_existing_entry(self, tmp_path):
        manager, _ = _loaded(tmp_path, [{"original": "Rupee", "translation": "", "status": "seeded"}])
        entry = manager.add_entry("Rupees", "рупії", "Гроші")
        assert (entry.original, entry.translation, entry.notes) == ("Rupee", "рупії", "Гроші")

    def test_a_manual_addition_may_keep_a_variant_separate(self, tmp_path):
        manager, _ = _loaded(tmp_path, [{"original": "Clawshot", "translation": "Кігтемет"}])
        manager.add_entry("Clawshots", "Подвійні гаки", "", fold_variants=False)
        assert [e.original for e in manager.get_entries()] == ["Clawshot", "Clawshots"]
        # ... and each stays reachable by its own spelling.
        manager.update_entry("clawshots", "Подвійний кігтемет", "")
        assert manager.get_entry("Clawshot").translation == "Кігтемет"
        assert manager.get_entry("Clawshots").translation == "Подвійний кігтемет"

    def test_update_through_a_case_or_plural_variant_reaches_the_entry(self, tmp_path):
        manager, _ = _loaded(tmp_path, [{"original": "Lake Hylia", "translation": "озеро Гайлія"}])
        assert manager.update_entry("lake hylia", "Озеро Гайлія", "n").original == "Lake Hylia"
        assert manager.update_entry("Lake Hylias", "озеро Гайлія", "n").original == "Lake Hylia"
        assert manager.update_entry("Death Mountain", "x", "") is None

    def test_seed_does_not_duplicate_a_variant(self, tmp_path):
        manager, _ = _loaded(tmp_path, [{"original": "Goron", "translation": "ґорон"}])
        assert manager.seed_entry("Gorons").original == "Goron"
        assert manager.seed_entry("THE GORON").original == "Goron"
        assert len(manager.get_entries()) == 1

    def test_delete_never_folds(self, tmp_path):
        manager, _ = _loaded(tmp_path, [{"original": "Rupee", "translation": "рупія"}])
        assert manager.delete_entry("Rupees") is False
        assert manager.delete_entry("rupee") is True

    def test_find_entry_folds_and_get_entry_does_not(self, tmp_path):
        manager, _ = _loaded(tmp_path, [{"original": "Rupee", "translation": "рупія"}])
        assert manager.find_entry("The Rupees").original == "Rupee"
        assert manager.get_entry("Rupees") is None


class TestLifecycleSurvivesBulkOperations:
    def test_global_replace_keeps_status_variants_and_aliases(self, tmp_path):
        manager, path = _loaded(tmp_path, [{
            "original": "Hyrule Castle", "translation": "Замок Хайрул", "notes": "Столиця Хайрулу",
            "status": "confirmed", "user_notes": "мій запис", "aliases": ["Castle of Hyrule"],
            "translation_variants": [{"translation": "Замок Хайрул", "rationale": "r"}],
        }])
        manager.global_replace("Хайрул", "Гайрул")
        entry = manager.get_entries()[0]
        assert entry.translation == "Замок Гайрул" and entry.notes == "Столиця Гайрулу"
        assert (entry.status, entry.user_notes, entry.aliases) == (STATUS_CONFIRMED, "мій запис", ("Castle of Hyrule",))
        assert entry.translation_variants == (TranslationVariant("Замок Хайрул", "r"),)
        reloaded, _ = _loaded(tmp_path, json.loads(path.read_text(encoding="utf-8")))
        assert reloaded.get_entries()[0].aliases == ("Castle of Hyrule",)

    def test_an_alias_finds_its_entry(self, tmp_path):
        manager, _ = _loaded(tmp_path, [{"original": "Mirror of Twilight", "translation": "Дзеркало Сутінків",
                                         "aliases": ["Twilight Mirror"]}])
        assert manager.get_entry("twilight mirror").original == "Mirror of Twilight"
        assert manager.update_entry("Twilight Mirror", "Дзеркало Сутінок", "").original == "Mirror of Twilight"


class TestMergeCanonicalDuplicates:
    ENTRIES = [
        {"original": "Clawshot", "translation": "Кігтемет", "status": "confirmed", "notes": "Предмет"},
        {"original": "Clawshots", "translation": "Подвійні гаки", "notes": "Два кігтемети"},
        {"original": "The Postman", "translation": "Листоноша", "notes": "Персонаж, що розносить листи"},
        {"original": "POSTMAN", "translation": "Поштар"},
        {"original": "Lake Hylia", "translation": "озеро Гайлія"},
    ]

    def test_dry_run_reports_and_changes_nothing(self, tmp_path):
        manager, path = _loaded(tmp_path, self.ENTRIES)
        before = path.read_text(encoding="utf-8")
        report = manager.merge_canonical_duplicates()
        assert report == [
            {"canonical": "clawshot", "survivor": "Clawshot", "merged": ["Clawshots"],
             "diverging": {"Clawshots": "Подвійні гаки"}},
            {"canonical": "postman", "survivor": "The Postman", "merged": ["POSTMAN"],
             "diverging": {"POSTMAN": "Поштар"}},
        ]
        assert len(manager.get_entries()) == 5 and path.read_text(encoding="utf-8") == before

    def test_merge_keeps_the_confirmed_entry_and_the_losing_translation_as_a_variant(self, tmp_path):
        manager, _ = _loaded(tmp_path, self.ENTRIES)
        manager.merge_canonical_duplicates(dry_run=False)

        assert [e.original for e in manager.get_entries()] == ["Clawshot", "The Postman", "Lake Hylia"]
        clawshot = manager.get_entry("Clawshot")
        assert (clawshot.translation, clawshot.status, clawshot.aliases) == ("Кігтемет", STATUS_CONFIRMED, ("Clawshots",))
        assert [v.translation for v in clawshot.translation_variants] == ["Подвійні гаки"]
        assert "Два кігтемети" in clawshot.notes
        assert manager.canonical_groups() == []
        assert manager.merge_canonical_duplicates(dry_run=False) == []      # idempotent
