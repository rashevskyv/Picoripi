"""Rebuilding an older translation memory with the context of its rows (core/translation/memory_context.py and the
worker in handlers/memory_context_worker.py). Synthetic texts only."""
import json

import pytest

from core.translation import memory_context as mc
from core.translation.series_memory import source_hash
from handlers.memory_context_worker import MemoryContextWorker


def _memory(rows_by_source):
    return {source_hash(source): rows for source, rows in rows_by_source.items()}


def _legacy(source, translation):
    return {"source": source, "translation": translation}


def _ctx(speaker, fold):
    return {"speaker": speaker, "addressee": "", "fold": fold}


def no_tags(source):
    return {}


class TestPlan:
    def test_a_legacy_row_takes_the_context_of_its_saved_place(self):
        memory = _memory({"Yes": [_legacy("Yes", "Так")]})
        places = [mc.SavedPlace(0, 1, "Yes", "Так")]
        result = mc.plan_rebuild(memory, places, lambda s: True, lambda p: _ctx("A", "f1"), no_tags)
        assert result.memory[source_hash("Yes")] == [{"source": "Yes", "translation": "Так", **_ctx("A", "f1")}]
        assert (result.updated, result.split, result.missing) == (1, 0, 0)

    def test_a_further_context_of_the_same_text_gets_its_own_row(self):
        memory = _memory({"Yes": [_legacy("Yes", "Так")]})
        places = [mc.SavedPlace(0, 1, "Yes", "Так"), mc.SavedPlace(0, 2, "Yes", "Так")]
        contexts = {1: _ctx("A", "f1"), 2: _ctx("B", "f2")}
        result = mc.plan_rebuild(memory, places, lambda s: True, lambda p: contexts[p.string], no_tags)
        rows = result.memory[source_hash("Yes")]
        assert sorted(row["fold"] for row in rows) == ["f1", "f2"]
        assert (result.updated, result.split) == (1, 1)

    def test_a_place_without_a_matching_row_is_counted_and_nothing_is_invented(self):
        memory = _memory({"Yes": [_legacy("Yes", "Так")]})
        places = [mc.SavedPlace(0, 1, "Yes", "Інше")]
        result = mc.plan_rebuild(memory, places, lambda s: True, lambda p: _ctx("A", "f1"), no_tags)
        assert result.memory == memory
        assert result.missing == 1

    def test_a_text_that_does_not_repeat_gets_no_context_but_its_tag_kinds(self):
        memory = _memory({"Hi": [_legacy("Hi", "Привіт")]})
        places = [mc.SavedPlace(0, 0, "Hi", "Привіт")]
        def tags(source):
            return {"syntax": "gen5msg", "tags": [], "neutral": "hi"}

        result = mc.plan_rebuild(memory, places, lambda s: False, lambda p: _ctx("A", "f1"), tags)
        assert result.memory[source_hash("Hi")] == [
            {"source": "Hi", "translation": "Привіт", "syntax": "gen5msg", "tags": [], "neutral": "hi"}]
        assert (result.tagged, result.updated) == (1, 0)

    def test_the_input_memory_is_not_changed(self):
        memory = _memory({"Yes": [_legacy("Yes", "Так")]})
        before = json.dumps(memory, sort_keys=True)
        mc.plan_rebuild(memory, [mc.SavedPlace(0, 1, "Yes", "Так")], lambda s: True, lambda p: _ctx("A", "f1"), no_tags)
        assert json.dumps(memory, sort_keys=True) == before

    def test_a_cancel_stops_the_plan_and_says_so(self):
        memory = _memory({"Yes": [_legacy("Yes", "Так")], "No": [_legacy("No", "Ні")]})
        places = [mc.SavedPlace(0, 1, "Yes", "Так"), mc.SavedPlace(0, 2, "No", "Ні")]
        calls = iter([False, True])
        result = mc.plan_rebuild(memory, places, lambda s: True, lambda p: _ctx("A", "f1"), no_tags,
                                 should_cancel=lambda: next(calls))
        assert result.cancelled is True

    def test_a_saved_place_needs_a_translation_and_a_block_prefix(self):
        data = [["", "Yes", "No"]]
        saved = {"file::key::1": "Так", "file::key::2": "  ", "other::k::0": "x"}
        places = mc.places_of(data, ["file::key::"], saved)
        assert places == [mc.SavedPlace(0, 1, "Yes", "Так")]


class TestFiles:
    def test_the_first_write_keeps_the_previous_file_and_a_restore_brings_it_back(self, tmp_path):
        path = tmp_path / "translation_memory.json"
        original = _memory({"Yes": [_legacy("Yes", "Так")]})
        path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
        backup = mc.write_rebuilt(path, _memory({"Yes": [{**_legacy("Yes", "Так"), **_ctx("A", "f1")}]}))
        assert backup.name == mc.BACKUP_NAME
        assert json.loads(backup.read_text(encoding="utf-8")) == original
        assert "fold" in json.loads(path.read_text(encoding="utf-8"))[source_hash("Yes")][0]

        mc.write_rebuilt(path, _memory({"Yes": []}))  # a second rebuild keeps the first backup
        assert json.loads(backup.read_text(encoding="utf-8")) == original

        assert mc.restore_backup(path) is True
        assert json.loads(path.read_text(encoding="utf-8")) == original

    def test_a_restore_without_a_backup_changes_nothing(self, tmp_path):
        path = tmp_path / "translation_memory.json"
        path.write_text("{}", encoding="utf-8")
        assert mc.restore_backup(path) is False
        assert path.read_text(encoding="utf-8") == "{}"


class TestWorker:
    def _project(self, tmp_path, saved_text="Так"):
        path = tmp_path / "translation_memory.json"
        path.write_text(json.dumps(_memory({"Yes": [_legacy("Yes", "Так")]}), ensure_ascii=False), encoding="utf-8")
        data = [["", "Yes", "Yes"]]
        saved = {"file::key::1": saved_text, "file::key::2": "Так"}
        contexts = {1: _ctx("A", "f1"), 2: _ctx("B", "f2")}
        return path, data, saved, contexts

    def test_the_worker_writes_the_rebuilt_memory_and_reports_the_result(self, tmp_path):
        path, data, saved, contexts = self._project(tmp_path)
        memory = mc.load_memory(path)
        worker = MemoryContextWorker(path, memory, data, ["file::key::"], saved,
                                     lambda p: contexts[p.string], no_tags)
        results, progress = [], []
        worker.done.connect(results.append)
        worker.progress.connect(lambda done, total: progress.append((done, total)))
        worker.run()
        assert results and results[0].updated == 1 and results[0].split == 1
        assert progress[-1] == (2, 2)
        folds = sorted(row["fold"] for row in json.loads(path.read_text(encoding="utf-8"))[source_hash("Yes")])
        assert folds == ["f1", "f2"]

    def test_a_cancelled_worker_writes_nothing(self, tmp_path):
        path, data, saved, contexts = self._project(tmp_path)
        before = path.read_text(encoding="utf-8")
        worker = MemoryContextWorker(path, mc.load_memory(path), data, ["file::key::"], saved,
                                     lambda p: contexts[p.string], no_tags)
        results = []
        worker.done.connect(results.append)
        worker.cancel()
        worker.run()
        assert results == [None]
        assert path.read_text(encoding="utf-8") == before
        assert not (tmp_path / mc.BACKUP_NAME).exists()

    def test_a_failure_is_reported_and_the_file_is_intact(self, tmp_path):
        path, data, saved, _contexts = self._project(tmp_path)
        before = path.read_text(encoding="utf-8")

        def broken(place):
            raise RuntimeError("no context")

        worker = MemoryContextWorker(path, mc.load_memory(path), data, ["file::key::"], saved, broken, no_tags)
        failures = []
        worker.failed.connect(failures.append)
        worker.run()
        assert failures == ["no context"]
        assert path.read_text(encoding="utf-8") == before


@pytest.mark.parametrize("counts, source, expected", [({"Yes": 2}, "Yes", True), ({"Yes": 1}, "Yes", False),
                                                       ({}, "Yes", False)])
def test_a_text_repeats_when_more_than_one_place_holds_it(counts, source, expected):
    assert mc.repeats_of(counts)(source) is expected


class TestHandlerActions:
    """The menu actions say what they cannot do before a worker starts."""

    def _handler(self, manager):
        from types import SimpleNamespace

        from handlers import saved_translations_handler as module

        return module, module.SavedTranslationsHandler(SimpleNamespace(saved_translations_manager=manager), None, None)

    def test_without_a_memory_file_the_update_says_so_and_starts_no_worker(self, monkeypatch):
        from types import SimpleNamespace

        module, handler = self._handler(SimpleNamespace(memory_file=lambda: None, context_for=None))
        shown = []
        monkeypatch.setattr(module.QMessageBox, "information", lambda parent, title, text: shown.append(text))
        handler.update_memory_with_context_action()
        assert len(shown) == 1 and "no translation memory" in shown[0]
        assert getattr(handler, "_memory_worker", None) is None

    def test_a_restore_without_a_copy_says_so(self, monkeypatch, tmp_path):
        from types import SimpleNamespace

        module, handler = self._handler(SimpleNamespace(memory_file=lambda: tmp_path / "translation_memory.json",
                                                        clear_cache=lambda: None))
        shown = []
        monkeypatch.setattr(module.QMessageBox, "information", lambda parent, title, text: shown.append(text))
        handler.restore_memory_before_context_action()
        assert len(shown) == 1 and "No copy" in shown[0]
