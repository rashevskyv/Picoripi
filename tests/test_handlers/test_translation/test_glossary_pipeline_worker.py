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
        self.overrides = []

    def translate(self, messages, session=None, settings_override=None):
        user = messages[1]["content"]
        self.calls.append(user)
        self.overrides.append(settings_override or {})
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


def test_auto_mode_always_proposes_translations(qtbot):
    manager = _manager()
    worker = GlossaryBuildWorker(
        manager, FakeProvider(), DATASET, mode="auto", translate=False
    )
    _capture(worker)

    worker.run()

    assert manager.get_entry("Ordon").translation == "Ордон"


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
        def translate(self, messages, session=None, settings_override=None):
            raise RuntimeError("provider exploded")

    manager = _manager()
    worker = GlossaryBuildWorker(
        manager, BoomProvider(), DATASET, mode="thorough", max_consecutive_failures=1
    )
    worker._sleep = lambda _s: None
    _, finished = _capture(worker)

    worker.run()

    assert finished and finished[0][0] is False
    assert "exploded" in finished[0][1]


def test_worker_gives_the_request_room_to_answer(qtbot):
    """A reply can take 25s while the endpoint works through its accounts."""
    provider = FakeProvider()
    worker = GlossaryBuildWorker(_manager(), provider, DATASET, mode="draft")
    _capture(worker)

    worker.run()

    assert provider.overrides and all(o["timeout"] >= 90 for o in provider.overrides)


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

    def translate(self, messages, session=None, settings_override=None):
        self.attempts += 1
        if self.attempts <= self.fail_first:
            raise RuntimeError(self.MESSAGE)
        return self.inner.translate(messages, session=session)


def test_worker_survives_a_transient_rate_limit(qtbot):
    """A 429 part-way through must not throw the whole run away."""
    manager = _manager()
    worker = GlossaryBuildWorker(
        manager, _RateLimited(fail_first=1), DATASET, mode="draft"
    )
    worker._sleep = lambda _s: None  # the retry pass waits for real otherwise
    _, finished = _capture(worker)

    worker.run()

    # The chunk failed on the first pass and landed on the retry pass.
    assert finished and finished[0][0] is True
    assert manager.get_entry("Ordon") is not None


def test_worker_makes_exactly_one_extra_attempt_per_failure(qtbot):
    """The endpoint retries across its own accounts; piling more on got us banned."""
    provider = _RateLimited(fail_first=999)
    worker = GlossaryBuildWorker(_manager(), provider, DATASET, mode="draft")
    worker._sleep = lambda _s: None
    _, finished = _capture(worker)

    worker.run()

    # One chunk: the first pass and the retry pass, and nothing beyond that.
    assert provider.attempts == 2
    # Every call failed, so this is a failed run -- not a success with a footnote.
    assert finished and finished[0][0] is False
    assert "still failed after the retry pass" in finished[0][1]


def test_worker_waits_the_time_the_server_asked_for(qtbot):
    """A 429 means every account is spent: retrying at once just extends it."""
    class Throttled:
        def translate(self, messages, session=None, settings_override=None):
            error = RuntimeError("429 Client Error: Too Many Requests")
            error.retry_after = 42.0
            raise error

    slept = []
    worker = GlossaryBuildWorker(_manager(), Throttled(), DATASET, mode="draft")
    worker._sleep = slept.append
    _capture(worker)

    worker.run()

    assert slept == [42.0]


def test_worker_reports_partial_success_when_some_chunks_land(qtbot):
    """Losing a chunk but finding terms is a success that still names the loss."""
    manager = _manager()
    # Each string exceeds the 500-char budget, so it is packed alone and the run
    # has two chunks. The failing one keeps failing, so it survives the retry.
    filler = "Ordon village is calm. " * 40
    dataset = [[filler, filler + "Link visits Ordon."]]

    class OneBadChunk:
        def __init__(self):
            self.inner = FakeProvider()

        def translate(self, messages, session=None, settings_override=None):
            if "Link visits" not in messages[1]["content"]:
                raise RuntimeError(_RateLimited.MESSAGE)
            return self.inner.translate(messages, session=session)

    worker = GlossaryBuildWorker(manager, OneBadChunk(), dataset, mode="draft", chunk_size=500)
    worker._sleep = lambda _s: None
    _, finished = _capture(worker)

    worker.run()

    ok, summary = finished[0]
    assert ok is True
    assert "still failed after the retry pass" in summary
    assert manager.get_entry("Ordon") is not None


def test_worker_stops_once_the_backend_is_clearly_down(qtbot):
    """Consecutive failures mean a dead backend, not a flaky call."""
    provider = _RateLimited(fail_first=999)
    filler = "Ordon village is calm. " * 40
    dataset = [[filler, filler, filler, filler, filler]]
    worker = GlossaryBuildWorker(
        _manager(), provider, dataset, mode="draft",
        workers=1, max_consecutive_failures=2, chunk_size=500,
    )
    worker._sleep = lambda _s: None
    _, finished = _capture(worker)

    worker.run()

    ok, summary = finished[0]
    assert ok is False
    assert "not responding" in summary
    # Stopped at the threshold rather than working through all five chunks, and
    # a dead backend gets no retry pass either.
    assert provider.attempts == 2


def test_the_stop_threshold_counts_the_whole_pool_not_one_thread(qtbot):
    """Three threads failing once each is the same dead backend as one failing thrice."""
    provider = _RateLimited(fail_first=999)
    filler = "Ordon village is calm. " * 40
    dataset = [[filler] * 40]
    worker = GlossaryBuildWorker(
        _manager(), provider, dataset, mode="draft",
        workers=4, max_consecutive_failures=3, chunk_size=500,
    )
    worker._sleep = lambda _s: None
    _, finished = _capture(worker)

    worker.run()

    assert finished[0][0] is False
    assert "not responding" in finished[0][1]
    # The batch in flight cannot be unsent, but the run stopped there rather
    # than working through all forty chunks.
    assert provider.attempts <= 8


def test_worker_forgives_an_isolated_failure_between_successes(qtbot):
    """One bad call in the middle must not count towards the stop threshold."""
    class Flaky:
        def __init__(self):
            self.inner = FakeProvider()
            self.n = 0

        def translate(self, messages, session=None, settings_override=None):
            self.n += 1
            if self.n == 2:
                raise RuntimeError(_RateLimited.MESSAGE)
            return self.inner.translate(messages, session=session)

    filler = "Ordon village is calm. " * 40
    dataset = [[filler, filler, filler + " Link visits Ordon."]]
    worker = GlossaryBuildWorker(
        _manager(), Flaky(), dataset, mode="draft",
        workers=1, max_consecutive_failures=2, chunk_size=500,
    )
    worker._sleep = lambda _s: None
    _, finished = _capture(worker)

    worker.run()

    assert finished[0][0] is True


def test_worker_runs_the_pass_in_parallel(qtbot):
    """Six chunks, six threads: they must overlap, not queue."""
    import threading

    class Concurrent:
        def __init__(self, expected):
            self.inner = FakeProvider()
            self.barrier = threading.Barrier(expected, timeout=10)
            self.overlapped = False

        def translate(self, messages, session=None, settings_override=None):
            try:
                self.barrier.wait()
                self.overlapped = True
            except threading.BrokenBarrierError:
                pass
            return self.inner.translate(messages, session=session)

    filler = "Ordon village is calm. " * 40
    dataset = [[filler] * 6]
    provider = Concurrent(expected=6)
    worker = GlossaryBuildWorker(
        _manager(), provider, dataset, mode="draft", workers=6, chunk_size=500
    )
    _capture(worker)

    worker.run()

    # The barrier only releases when all six requests are in flight at once.
    assert provider.overlapped is True


def test_worker_reports_a_cancel_as_cancelled_not_as_a_provider_error(qtbot):
    """Cancelling mid-request must not surface as a scary 502."""
    class CancelsOnCall:
        def __init__(self, worker_ref):
            self.worker_ref = worker_ref

        def translate(self, messages, session=None, settings_override=None):
            self.worker_ref[0].cancel()
            raise RuntimeError(_RateLimited.MESSAGE)

    ref = []
    worker = GlossaryBuildWorker(_manager(), CancelsOnCall(ref), DATASET, mode="draft")
    ref.append(worker)
    worker._sleep = lambda _s: None
    _, finished = _capture(worker)

    worker.run()

    ok, summary = finished[0]
    assert ok is False
    assert "cancelled" in summary
    assert "502" not in summary
