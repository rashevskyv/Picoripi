"""pytest-qt lifecycle test for GlossaryBuildWorker."""
import json

from handlers.translation.glossary_pipeline_worker import GlossaryBuildWorker
from core.glossary_manager import STATUS_SYNTHESIZED, STATUS_TRANSLATED, GlossaryManager


class _Resp:
    def __init__(self, text):
        self.text = text


class FakeProvider:
    """Routes provider.translate to a canned reply by pass-specific prompt."""

    def translate(self, messages, session=None):
        user = messages[1]["content"]
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


DATASET = [["Ordon village is calm", "Link visits Ordon"]]


def test_worker_builds_and_describes(qtbot):
    manager = _manager()
    worker = GlossaryBuildWorker(manager, FakeProvider(), DATASET, mode="thorough")
    stages = []
    worker.progress.connect(lambda stage, d, t: stages.append(stage))

    with qtbot.waitSignal(worker.build_finished, timeout=5000) as blocker:
        worker.start()

    success, summary = blocker.args
    assert success is True
    assert "seeded" in summary
    assert manager.get_entry("Ordon").status == STATUS_SYNTHESIZED
    assert "sweep" in stages and "describe" in stages
    worker.wait()


def test_worker_translate_flag_runs_pass_3(qtbot):
    manager = _manager()
    worker = GlossaryBuildWorker(
        manager, FakeProvider(), DATASET, mode="thorough", translate=True
    )
    with qtbot.waitSignal(worker.build_finished, timeout=5000):
        worker.start()

    entry = manager.get_entry("Ordon")
    assert entry.status == STATUS_TRANSLATED
    assert entry.translation == "Ордон"
    worker.wait()


def test_worker_cancel_before_start(qtbot):
    manager = _manager()
    worker = GlossaryBuildWorker(manager, FakeProvider(), DATASET, mode="thorough")
    worker.cancel()

    with qtbot.waitSignal(worker.build_finished, timeout=5000) as blocker:
        worker.start()

    success, summary = blocker.args
    assert success is False
    assert "cancelled" in summary
    assert manager.get_entries() == []
    worker.wait()


def test_worker_provider_error_reported(qtbot):
    class BoomProvider:
        def translate(self, messages, session=None):
            raise RuntimeError("provider exploded")

    manager = _manager()
    worker = GlossaryBuildWorker(manager, BoomProvider(), DATASET, mode="thorough")

    with qtbot.waitSignal(worker.build_finished, timeout=5000) as blocker:
        worker.start()

    success, summary = blocker.args
    assert success is False
    assert "exploded" in summary
    worker.wait()
