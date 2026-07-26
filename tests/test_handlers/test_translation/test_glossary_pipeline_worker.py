"""Lifecycle tests for GlossaryBuildWorker.

``run()`` is invoked directly rather than via ``start()`` so signal delivery is
synchronous and order-independent: cross-thread queued delivery is unreliable in
the shared suite (a conftest helper can quit the main event loop), and this
exercises the same worker code path either way. One test still starts a real
thread to cover actual threaded execution.
"""
import json

from handlers.translation.glossary_pipeline_worker import GlossaryBuildWorker
from core.glossary_manager import STATUS_SYNTHESIZED, STATUS_TRANSLATED, GlossaryManager


class _Resp:
    def __init__(self, text):
        self.text = text


class FakeProvider:
    """Routes provider.translate to a canned reply by pass-specific prompt."""

    def __init__(self):
        self.calls = []

    def translate(self, messages, session=None):
        user = messages[1]["content"]
        self.calls.append(user)
        if "Game text chunk" in user:
            return _Resp(json.dumps([{"term": "Ordon", "section": "Places", "fragment": "a village"}]))
        if "Excerpts where it appears" in user:
            return _Resp(json.dumps({"description": "a described place"}))
        if "Partial descriptions" in user:
            return _Resp(json.dumps({"description": "folded"}))
        if "Description:" in user:
            return _Resp(json.dumps([{"translation": "Ордон", "rationale": "translit"}]))
        return _Resp("[]")


def _manager():
    m = GlossaryManager()
    m.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
    return m


def _capture(worker):
    """Collect emitted signals into plain lists."""
    stages, finished = [], []
    worker.progress.connect(lambda stage, d, t: stages.append(stage))
    worker.build_finished.connect(lambda ok, summary: finished.append((ok, summary)))
    return stages, finished


DATASET = [["Ordon village is calm", "Link visits Ordon"]]


def test_worker_builds_and_describes(qtbot):
    manager = _manager()
    worker = GlossaryBuildWorker(manager, FakeProvider(), DATASET, mode="thorough")
    stages, finished = _capture(worker)

    worker.run()

    assert finished and finished[0][0] is True
    assert "seeded" in finished[0][1]
    assert manager.get_entry("Ordon").status == STATUS_SYNTHESIZED
    assert "sweep" in stages and "describe" in stages


def test_worker_translate_flag_runs_pass_3(qtbot):
    manager = _manager()
    worker = GlossaryBuildWorker(
        manager, FakeProvider(), DATASET, mode="thorough", translate=True
    )
    _capture(worker)

    worker.run()

    entry = manager.get_entry("Ordon")
    assert entry.status == STATUS_TRANSLATED
    assert entry.translation == "Ордон"


def test_worker_draft_mode_skips_describe(qtbot):
    manager = _manager()
    provider = FakeProvider()
    worker = GlossaryBuildWorker(manager, provider, DATASET, mode="draft")
    _capture(worker)

    worker.run()

    assert manager.get_entry("Ordon") is not None
    assert not any("Excerpts where it appears" in c for c in provider.calls)


def test_worker_cancel_stops_work(qtbot):
    manager = _manager()
    worker = GlossaryBuildWorker(manager, FakeProvider(), DATASET, mode="thorough")
    _, finished = _capture(worker)
    worker.cancel()

    worker.run()

    assert finished and finished[0][0] is False
    assert "cancelled" in finished[0][1]
    assert manager.get_entries() == []


def test_worker_provider_error_reported(qtbot):
    class BoomProvider:
        def translate(self, messages, session=None):
            raise RuntimeError("provider exploded")

    manager = _manager()
    worker = GlossaryBuildWorker(manager, BoomProvider(), DATASET, mode="thorough")
    _, finished = _capture(worker)

    worker.run()

    assert finished and finished[0][0] is False
    assert "exploded" in finished[0][1]


def test_worker_runs_on_a_real_thread(qtbot):
    """Smoke test that the worker actually executes when started as a thread."""
    manager = _manager()
    worker = GlossaryBuildWorker(manager, FakeProvider(), DATASET, mode="draft")

    worker.start()
    assert worker.wait(10000) is True
    assert worker.isFinished()
    assert manager.get_entry("Ordon") is not None
