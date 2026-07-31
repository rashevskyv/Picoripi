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


class _RateLimited:
    """Fails the first ``n`` calls with the real 429-behind-502 message."""

    MESSAGE = (
        '502 Server Error: Bad Gateway for url: http://localhost:8081/v1/chat/'
        'completions - {"error": {"message": "upstream error: HTTP Error 429: '
        'Too Many Requests"}}'
    )

    def __init__(self, fail_first, inner=None):
        self.fail_first = fail_first
        self.inner = inner or FakeProvider()
        self.attempts = 0

    def translate(self, messages, session=None):
        self.attempts += 1
        if self.attempts <= self.fail_first:
            raise RuntimeError(self.MESSAGE)
        return self.inner.translate(messages, session=session)


def test_worker_survives_a_transient_rate_limit(qtbot):
    """A 429 part-way through must not throw the whole run away."""
    manager = _manager()
    worker = GlossaryBuildWorker(
        manager, _RateLimited(fail_first=2), DATASET, mode="draft"
    )
    worker._sleep = lambda _s: None  # no real backoff in tests
    _, finished = _capture(worker)

    worker.run()

    assert finished and finished[0][0] is True
    assert manager.get_entry("Ordon") is not None


def test_worker_skips_the_chunk_once_retries_are_spent(qtbot):
    """Persistent rate limiting costs the chunk, not the run — and says so."""
    manager = _manager()
    worker = GlossaryBuildWorker(
        manager, _RateLimited(fail_first=999), DATASET, mode="draft", retry_attempts=2
    )
    worker._sleep = lambda _s: None
    _, finished = _capture(worker)

    worker.run()

    # Every call failed, so this is a failed run -- not a success with a footnote.
    assert finished and finished[0][0] is False
    assert "gave up after retries" in finished[0][1]


def test_worker_still_aborts_on_a_configuration_error(qtbot):
    """A bad key will not fix itself on chunk 400, so it must not be retried."""
    class Unauthorized:
        def __init__(self):
            self.attempts = 0

        def translate(self, messages, session=None):
            self.attempts += 1
            raise RuntimeError("401 Client Error: Unauthorized")

    provider = Unauthorized()
    worker = GlossaryBuildWorker(_manager(), provider, DATASET, mode="draft")
    worker._sleep = lambda _s: None
    _, finished = _capture(worker)

    worker.run()

    assert finished and finished[0][0] is False
    assert provider.attempts == 1


def test_worker_reports_partial_success_when_some_chunks_land(qtbot):
    """Losing a chunk but finding terms is a success that still names the loss."""
    manager = _manager()
    # Each string exceeds the 500-char budget, so it is packed alone and the run
    # has two chunks: one to lose, one to land.
    filler = "Ordon village is calm. " * 40
    dataset = [[filler, filler + "Link visits Ordon."]]
    worker = GlossaryBuildWorker(
        manager, _RateLimited(fail_first=1), dataset, mode="draft",
        retry_attempts=1, chunk_size=500,
    )
    worker._sleep = lambda _s: None
    _, finished = _capture(worker)

    worker.run()

    ok, summary = finished[0]
    assert ok is True
    assert "gave up after retries" in summary
    assert manager.get_entry("Ordon") is not None


def test_worker_stops_once_the_backend_is_clearly_down(qtbot):
    """Consecutive give-ups mean a dead backend, not a flaky call."""
    provider = _RateLimited(fail_first=999)
    filler = "Ordon village is calm. " * 40
    dataset = [[filler, filler, filler, filler, filler]]
    worker = GlossaryBuildWorker(
        _manager(), provider, dataset, mode="draft",
        retry_attempts=1, max_consecutive_failures=2, chunk_size=500,
    )
    worker._sleep = lambda _s: None
    _, finished = _capture(worker)

    worker.run()

    ok, summary = finished[0]
    assert ok is False
    assert "not responding" in summary
    # Stopped at the threshold rather than working through all five chunks.
    assert provider.attempts == 2


def test_worker_forgives_an_isolated_failure_between_successes(qtbot):
    """One bad call in the middle must not count towards the stop threshold."""
    class Flaky:
        def __init__(self):
            self.inner = FakeProvider()
            self.n = 0

        def translate(self, messages, session=None):
            self.n += 1
            if self.n == 2:
                raise RuntimeError(_RateLimited.MESSAGE)
            return self.inner.translate(messages, session=session)

    filler = "Ordon village is calm. " * 40
    dataset = [[filler, filler, filler + " Link visits Ordon."]]
    worker = GlossaryBuildWorker(
        _manager(), Flaky(), dataset, mode="draft",
        retry_attempts=1, max_consecutive_failures=2, chunk_size=500,
    )
    worker._sleep = lambda _s: None
    _, finished = _capture(worker)

    worker.run()

    assert finished[0][0] is True


def test_worker_reports_a_cancel_as_cancelled_not_as_a_provider_error(qtbot):
    """Cancelling mid-request must not surface as a scary 502."""
    class CancelsOnCall:
        def __init__(self, worker_ref):
            self.worker_ref = worker_ref

        def translate(self, messages, session=None):
            self.worker_ref[0].cancel()
            raise RuntimeError(_RateLimited.MESSAGE)

    ref = []
    worker = GlossaryBuildWorker(
        _manager(), CancelsOnCall(ref), DATASET, mode="draft", retry_attempts=1
    )
    ref.append(worker)
    worker._sleep = lambda _s: None
    _, finished = _capture(worker)

    worker.run()

    ok, summary = finished[0]
    assert ok is False
    assert "cancelled" in summary
    assert "502" not in summary
