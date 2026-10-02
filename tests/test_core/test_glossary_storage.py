"""Glossary storage: ids, deletions that stay deleted, one write for many changes (WP3 3.6)."""
import json
import os
from pathlib import Path

from companion.server.models import GlossaryEntryUpdate
from companion.server.storage import StorageManager
from core.companion_sync import entries_differ, keep_local_deletions, merge_glossaries
from core.glossary.models import GlossaryEntry, legacy_entry_id
from core.glossary_build.pipeline_coordinator import MODE_DRAFT, STORE_BATCH, GlossaryBuildCoordinator
from core.glossary_manager import STATUS_TRANSLATED, GlossaryManager

PROMPTS = json.loads(Path("translation_prompts/glossary_pipeline_prompts.json").read_text(encoding="utf-8"))


def _manager(path, raw="[]"):
    path.write_text(raw, encoding="utf-8")
    manager = GlossaryManager()
    manager.load_from_text(plugin_name=None, glossary_path=path, raw_text=raw)
    return manager


def _stored(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _count_writes(manager, monkeypatch):
    writes = []
    real = manager._write_file
    monkeypatch.setattr(manager, "_write_file", lambda raw: (writes.append(1), real(raw))[1])
    return writes


class TestEntryId:
    def test_a_new_entry_gets_an_id_that_is_stored_and_survives_reload_and_rename(self, tmp_path):
        path = tmp_path / "glossary.json"
        manager = _manager(path)

        created = manager.add_entry("Zora", "Зора", "")
        manager.rename_original("Zora", "Zora Folk")
        reloaded = _manager(path, path.read_text(encoding="utf-8"))

        assert len(created.id) == 32
        assert _stored(path)[0]["id"] == created.id
        assert reloaded.get_entry("Zora Folk").id == created.id

    def test_entries_stored_before_ids_get_the_id_their_term_implies(self, tmp_path):
        raw = json.dumps([{"original": "Zora", "translation": "Зора", "notes": ""}])
        first = _manager(tmp_path / "a.json", raw)
        second = _manager(tmp_path / "b.json", raw)

        assert first.get_entry("Zora").id == second.get_entry("Zora").id == legacy_entry_id("Zora")

    def test_the_id_is_not_part_of_equality(self):
        assert GlossaryEntry("Zora", "Зора", id="a") == GlossaryEntry("Zora", "Зора", id="b")


class TestTombstones:
    def test_a_deletion_is_recorded_in_the_file_and_is_not_an_entry_after_reload(self, tmp_path):
        path = tmp_path / "glossary.json"
        manager = _manager(path)
        zora = manager.add_entry("Zora", "Зора", "")
        manager.add_entry("Rupee", "Рупія", "")

        manager.delete_entry("Zora")
        reloaded = _manager(path, path.read_text(encoding="utf-8"))

        stones = [item for item in _stored(path) if item.get("deleted_at")]
        assert [(s["original"], s["id"]) for s in stones] == [("Zora", zora.id)]
        assert [e.original for e in reloaded.get_entries()] == ["Rupee"]
        reloaded.add_entry("Goron", "Ґорон", "")                       # the record survives later writes
        assert [s["original"] for s in _stored(path) if s.get("deleted_at")] == ["Zora"]

    def test_adding_the_term_again_withdraws_the_deletion(self, tmp_path):
        path = tmp_path / "glossary.json"
        manager = _manager(path)
        manager.add_entry("Zora", "Зора", "")
        manager.delete_entry("Zora")

        manager.add_entry("zora", "Зора", "")

        assert not [item for item in _stored(path) if item.get("deleted_at")]

    def test_an_entry_merged_into_another_is_recorded_as_deleted(self, tmp_path):
        path = tmp_path / "glossary.json"
        manager = _manager(path)
        manager.add_entry("Postman", "Листоноша", "")
        other = manager.add_entry("The Postman", "Поштар", "", fold_variants=False)

        manager.merge_into("Postman", "The Postman")

        assert [(s["original"], s["id"]) for s in _stored(path) if s.get("deleted_at")] == [("The Postman", other.id)]


class TestWrites:
    def test_a_transaction_writes_once(self, tmp_path, monkeypatch):
        manager = _manager(tmp_path / "glossary.json")
        writes = _count_writes(manager, monkeypatch)

        with manager.transaction():
            for index in range(50):
                manager.add_entry(f"Term {index:02d}x", "переклад", "")
            with manager.transaction():                      # nesting does not write early
                manager.delete_entry("Term 00x")
            assert writes == [] and manager.get_entry("Term 07x") is not None

        assert writes == [1]
        assert len([item for item in _stored(tmp_path / "glossary.json") if not item.get("deleted_at")]) == 49
        assert [m.entry.original for m in manager.find_matches("Term 07x here")] == ["Term 07x"]

    def test_flush_writes_what_is_owed_and_an_idle_transaction_writes_nothing(self, tmp_path, monkeypatch):
        manager = _manager(tmp_path / "glossary.json")
        writes = _count_writes(manager, monkeypatch)

        with manager.transaction() as flush:
            flush()
            manager.add_entry("Zora", "Зора", "")
            flush()
            flush()
        with manager.transaction():
            pass

        assert writes == [1]

    def test_a_failed_write_leaves_the_old_file_whole(self, tmp_path, monkeypatch):
        path = tmp_path / "glossary.json"
        manager = _manager(path)
        manager.add_entry("Zora", "Зора", "")
        before = path.read_text(encoding="utf-8")

        def refuse(source, target):
            raise OSError("disk full")

        monkeypatch.setattr(os, "replace", refuse)
        manager.add_entry("Rupee", "Рупія", "")

        assert path.read_text(encoding="utf-8") == before

    def test_a_build_writes_the_file_a_few_times_not_once_per_term(self, tmp_path, monkeypatch):
        path = tmp_path / "glossary.json"
        manager = _manager(path)
        writes = _count_writes(manager, monkeypatch)
        names = [f"Qx{chr(97 + i // 26)}{chr(97 + i % 26)}zar" for i in range(60)]     # 60 unrelated terms

        def call(messages):
            user = messages[1]["content"]
            if "Term:" in user:
                return json.dumps([{"translation": "переклад", "rationale": ""}])
            return json.dumps([{"term": name, "section": "Items", "fragment": "a thing"} for name in names])

        coordinator = GlossaryBuildCoordinator(manager, call, PROMPTS, workers=1)
        coordinator.build([["some game text"]], MODE_DRAFT)
        result = coordinator.run_translate()

        assert result.translated == 60
        assert len(writes) <= 60 // STORE_BATCH + 3
        stored = _stored(path)
        assert len(stored) == 60 and all(item["translation"] == "переклад" for item in stored)


def test_a_re_sweep_adds_evidence_to_a_translated_entry_without_resetting_it(tmp_path):
    manager = _manager(tmp_path / "glossary.json")
    manager.add_entry("Zora", "Зора", "river folk")
    manager.update_entry("Zora", "Зора", "river folk", status=STATUS_TRANSLATED)

    def call(messages):
        return json.dumps([{"term": "Zoras", "section": "Races", "fragment": "they guard the river"}])

    result = GlossaryBuildCoordinator(manager, call, PROMPTS, workers=1).build([["The Zoras guard the river."]], MODE_DRAFT)

    entry = manager.get_entry("Zora")
    assert (entry.translation, entry.status, entry.notes) == ("Зора", STATUS_TRANSLATED, "river folk")
    assert [fragment.text for fragment in entry.fragments] == ["they guard the river"]
    assert result.seeded == 0 and len(manager.get_entries()) == 1


def _row(original, translation="x", updated_at="2026-10-01T10:00:00+00:00", **extra):
    return {"original": original, "translation": translation, "updated_at": updated_at, **extra}


def _stone(original, deleted_at="2026-10-02T10:00:00+00:00", **extra):
    return {"original": original, "id": extra.pop("id", legacy_entry_id(original)), "deleted_at": deleted_at}


def _live(entries):
    return [e["original"] for e in entries if not e.get("deleted_at")]


class TestSync:
    def test_a_local_deletion_is_not_undone_by_the_server_copy(self):
        local = [_row("Rupee"), _stone("Zora")]
        remote = [_row("Rupee"), _row("Zora")]

        result = merge_glossaries(local, remote)

        assert _live(result.merged_entries) == ["Rupee"]
        assert [e["original"] for e in result.merged_entries if e.get("deleted_at")] == ["Zora"]
        assert (result.pulled_count, result.pushed_count, result.conflicts) == (0, 1, [])

    def test_a_deletion_made_elsewhere_removes_the_local_entry(self):
        result = merge_glossaries([_row("Rupee"), _row("Zora")], [_row("Rupee"), _stone("Zora")])

        assert _live(result.merged_entries) == ["Rupee"]
        assert (result.pulled_count, result.pushed_count) == (1, 0)

    def test_an_entry_changed_after_the_deletion_comes_back_and_the_deletion_is_dropped(self):
        remote = [_row("Zora", "Зора нова", updated_at="2026-10-03T10:00:00+00:00")]

        result = merge_glossaries([_stone("Zora")], remote)

        assert result.merged_entries == remote and result.pulled_count == 1

    def test_a_plain_pull_keeps_local_deletions(self):
        local = [_row("Rupee"), _stone("Zora")]
        remote = [_row("Rupee"), _row("Zora"), _row("Goron")]

        kept = keep_local_deletions(local, remote)

        assert _live(kept) == ["Rupee", "Goron"]
        assert [e["original"] for e in kept if e.get("deleted_at")] == ["Zora"]
        assert keep_local_deletions(kept, kept) == kept           # and nothing piles up

    def test_a_rename_is_one_entry_not_two(self):
        local = [_row("Zora Folk", "Зора", updated_at="2026-10-02T10:00:00+00:00", id="abc")]
        remote = [_row("Zora", "Зора", id="abc")]

        result = merge_glossaries(local, remote)

        assert _live(result.merged_entries) == ["Zora Folk"] and result.pushed_count == 1

    def test_a_rename_of_an_entry_stored_before_ids_is_matched_through_its_implied_id(self):
        local = [_row("Zora Folk", "Зора", updated_at="2026-10-02T10:00:00+00:00", id=legacy_entry_id("Zora"))]

        result = merge_glossaries(local, [_row("Zora", "Зора")])

        assert _live(result.merged_entries) == ["Zora Folk"]

    def test_entries_without_ids_merge_as_before(self):
        result = merge_glossaries([_row("Rupee"), _row("Zora")], [_row("Zora"), _row("Goron")])

        assert _live(result.merged_entries) == ["Rupee", "Zora", "Goron"]
        assert (result.pulled_count, result.pushed_count) == (1, 1)

    def test_a_changed_alias_list_is_a_difference(self):
        assert entries_differ(_row("Postman"), _row("Postman", aliases=["The Postman"])) == (True, ["aliases"])


class TestCompanionServer:
    def test_deletion_records_are_stored_for_sync_and_hidden_from_everything_else(self, tmp_path):
        storage = StorageManager(tmp_path)
        summary = storage.save_project("demo", [_row("Rupee", status="translated"), _stone("Zora")])

        assert summary.total_terms == 1
        assert [e["original"] for e in storage.get_glossary("demo")] == ["Rupee"]
        assert [e["original"] for e in storage.get_glossary("demo", include_deleted=True)] == ["Rupee", "Zora"]
        assert storage.list_projects()[0].total_terms == 1

    def test_editing_an_entry_on_the_server_keeps_the_deletion_records(self, tmp_path):
        storage = StorageManager(tmp_path)
        storage.save_project("demo", [_row("Rupee"), _stone("Zora")])

        storage.update_entry("demo", GlossaryEntryUpdate(original="Rupee", translation="Рупія"))
        assert storage.update_entry("demo", GlossaryEntryUpdate(original="Zora", translation="Зора")) is None

        stored = storage.get_glossary("demo", include_deleted=True)
        assert stored[0]["translation"] == "Рупія" and stored[1].get("deleted_at")
