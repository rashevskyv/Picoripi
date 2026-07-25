"""Tests for glossary entry lifecycle fields and backwards compatibility.

Covers the roadmap section-6 data model added to GlossaryEntry: status, icon,
description fragments, and translation variants -- plus is_valid relaxation so a
seeded (translation-less) entry still loads.
"""
import json

from core.glossary_manager import (
    STATUS_CONFIRMED,
    STATUS_SEEDED,
    STATUS_SYNTHESIZED,
    DescriptionFragment,
    GlossaryEntry,
    GlossaryManager,
    TranslationVariant,
    _entry_to_dict,
)


class TestIsValid:
    def test_legacy_entry_needs_term_and_translation(self):
        assert GlossaryEntry(original="Boss", translation="Бос").is_valid()

    def test_seeded_entry_valid_with_status_and_no_translation(self):
        e = GlossaryEntry(original="Boss", translation="", status=STATUS_SEEDED)
        assert e.is_valid()

    def test_term_only_without_status_is_invalid(self):
        assert not GlossaryEntry(original="Boss", translation="").is_valid()

    def test_empty_is_invalid(self):
        assert not GlossaryEntry(original="", translation="").is_valid()


class TestIsUnconfirmed:
    def test_seeded_is_unconfirmed(self):
        assert GlossaryEntry("t", "", status=STATUS_SEEDED).is_unconfirmed

    def test_confirmed_is_not_unconfirmed(self):
        assert not GlossaryEntry("t", "x", status=STATUS_CONFIRMED).is_unconfirmed

    def test_legacy_no_status_is_not_unconfirmed(self):
        assert not GlossaryEntry("t", "x").is_unconfirmed


class TestSerialization:
    def test_legacy_entry_omits_new_fields(self):
        d = _entry_to_dict(GlossaryEntry(original="A", translation="Б"))
        assert set(d) == {"original", "translation", "notes", "section", "profiled"}

    def test_new_fields_emitted_only_when_set(self):
        e = GlossaryEntry(
            original="A",
            translation="",
            status=STATUS_SEEDED,
            icon="icons/a.png",
            fragments=(DescriptionFragment("ctx", 1, 2),),
            translation_variants=(TranslationVariant("Б", "reason"),),
        )
        d = _entry_to_dict(e)
        assert d["status"] == STATUS_SEEDED
        assert d["icon"] == "icons/a.png"
        assert d["fragments"] == [{"text": "ctx", "block_idx": 1, "string_idx": 2}]
        assert d["translation_variants"] == [{"translation": "Б", "rationale": "reason"}]


class TestJsonRoundTrip:
    def _manager(self, tmp_path):
        path = tmp_path / "glossary.json"
        m = GlossaryManager()
        m.load_from_text(plugin_name=None, glossary_path=path, raw_text="")
        return m, path

    def _reload(self, path):
        m2 = GlossaryManager()
        m2.load_from_text(
            plugin_name=None, glossary_path=path, raw_text=path.read_text(encoding="utf-8")
        )
        return m2

    def test_seeded_entry_survives_round_trip(self, tmp_path):
        m, path = self._manager(tmp_path)
        m.seed_entry("Spring Goron", section="Characters", icon="ic.png")

        reloaded = self._reload(path)
        entry = reloaded.get_entry("Spring Goron")
        assert entry is not None
        assert entry.status == STATUS_SEEDED
        assert entry.icon == "ic.png"
        assert entry.translation == ""

    def test_legacy_json_loads_with_empty_lifecycle(self, tmp_path):
        path = tmp_path / "legacy.json"
        path.write_text(
            json.dumps([{"original": "Link", "translation": "Лінк", "notes": "hero"}]),
            encoding="utf-8",
        )
        m = self._reload(path)
        entry = m.get_entry("Link")
        assert entry.translation == "Лінк"
        assert entry.status == ""
        assert entry.fragments == ()
        assert entry.translation_variants == ()

    def test_fragments_and_variants_persist(self, tmp_path):
        m, path = self._manager(tmp_path)
        m.seed_entry("Ordon", section="Places")
        m.update_entry(
            "Ordon",
            translation="",
            notes="a village",
            status=STATUS_SYNTHESIZED,
            fragments=(DescriptionFragment("home village", 0, 3),),
            translation_variants=(TranslationVariant("Ордон", "transliteration"),),
        )
        reloaded = self._reload(path)
        entry = reloaded.get_entry("Ordon")
        assert entry.status == STATUS_SYNTHESIZED
        assert entry.fragments == (DescriptionFragment("home village", 0, 3),)
        assert entry.translation_variants == (TranslationVariant("Ордон", "transliteration"),)


class TestUpdatePreservesLifecycle:
    def _manager(self, tmp_path):
        path = tmp_path / "g.json"
        m = GlossaryManager()
        m.load_from_text(plugin_name=None, glossary_path=path, raw_text="")
        return m

    def test_plain_update_keeps_status_and_icon(self, tmp_path):
        m = self._manager(tmp_path)
        m.seed_entry("Midna", section="Characters", icon="midna.png")
        # a plain translation edit must not drop status/icon
        m.update_entry("Midna", translation="Мідна", notes="")
        entry = m.get_entry("Midna")
        assert entry.translation == "Мідна"
        assert entry.status == STATUS_SEEDED
        assert entry.icon == "midna.png"

    def test_explicit_status_override(self, tmp_path):
        m = self._manager(tmp_path)
        m.seed_entry("Midna")
        m.update_entry("Midna", translation="Мідна", notes="", status=STATUS_CONFIRMED)
        assert m.get_entry("Midna").status == STATUS_CONFIRMED


class TestSeedEntry:
    def _manager(self, tmp_path):
        path = tmp_path / "g.json"
        m = GlossaryManager()
        m.load_from_text(plugin_name=None, glossary_path=path, raw_text="")
        return m

    def test_seed_blank_term_returns_none(self, tmp_path):
        m = self._manager(tmp_path)
        assert m.seed_entry("   ") is None

    def test_seed_does_not_overwrite_existing(self, tmp_path):
        m = self._manager(tmp_path)
        m.add_entry("Zelda", "Зельда", "princess", section="Characters")
        result = m.seed_entry("Zelda", section="Places", icon="x.png")
        # returns the existing rich entry, unchanged
        assert result.translation == "Зельда"
        assert result.section == "Characters"
        assert result.icon == ""

    def test_seed_with_description_and_custom_status(self, tmp_path):
        m = self._manager(tmp_path)
        entry = m.seed_entry(
            "Boomerang", section="Items", status=STATUS_SYNTHESIZED, description="a weapon"
        )
        assert entry.status == STATUS_SYNTHESIZED
        assert entry.notes == "a weapon"
