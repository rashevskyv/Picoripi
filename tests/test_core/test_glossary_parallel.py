"""Tests for the build's thread pool (core/glossary_build/parallel.py).

The rules that matter are the ones that cost half an hour of work when they are
wrong: a failing unit must not take the finished ones with it, results must land
against their own item, and a 429's Retry-After must actually be waited out.
"""
import threading

from core.glossary_build.parallel import (
    PoolResult,
    retry_after_seconds,
    run_pool,
    run_with_retry_pass,
)


class TestFailuresAreData:
    def test_one_failing_unit_does_not_lose_the_others(self):
        def work(item):
            if item == 3:
                raise RuntimeError("boom")
            return item * 10

        done = {}
        outcome = run_pool(
            range(6), work, workers=4, on_result=lambda item, r: done.__setitem__(item, r)
        )

        assert outcome.failed == [3]
        assert done == {0: 0, 1: 10, 2: 20, 4: 40, 5: 50}

    def test_every_unit_failing_is_reported_not_raised(self):
        def work(item):
            raise ValueError(item)

        outcome = run_pool(range(4), work, workers=2)
        assert outcome.failed == [0, 1, 2, 3]


class TestResultsCarryTheirItem:
    def test_results_pair_with_their_own_item_not_a_position(self):
        # Uneven work, so completion order is not submission order.
        barrier = threading.Barrier(3)

        def work(item):
            if item in (0, 1, 2):
                barrier.wait(timeout=5)
            return f"result-{item}"

        pairs = []
        run_pool(range(5), work, workers=3, on_result=lambda i, r: pairs.append((i, r)))

        assert all(result == f"result-{item}" for item, result in pairs)


class TestProgressAndIncrementalWriting:
    def test_results_arrive_one_at_a_time_during_the_run(self):
        writes = []
        progress = []
        run_pool(
            range(4),
            lambda item: item,
            workers=4,
            on_result=lambda i, r: writes.append(i),
            on_progress=lambda done, total: progress.append((done, total)),
        )
        assert sorted(writes) == [0, 1, 2, 3]
        assert progress == [(1, 4), (2, 4), (3, 4), (4, 4)]


class TestStoppingOnADeadBackend:
    def test_consecutive_failures_are_counted_across_the_whole_pool(self):
        attempted = []

        def work(item):
            attempted.append(item)
            raise RuntimeError("dead")

        outcome = run_pool(range(50), work, workers=3, max_consecutive_failures=3)

        assert outcome.stop_error is not None
        # It stopped early instead of grinding through all fifty.
        assert len(attempted) < 50

    def test_a_success_resets_the_streak(self):
        def work(item):
            if item % 2:
                raise RuntimeError("odd")
            return item

        outcome = run_pool(range(10), work, workers=1, max_consecutive_failures=3)
        assert outcome.stop_error is None
        assert outcome.failed == [1, 3, 5, 7, 9]


class TestCancellation:
    def test_a_cancelled_run_attempts_nothing(self):
        attempted = []
        outcome = run_pool(
            range(10),
            lambda i: attempted.append(i),
            workers=4,
            is_cancelled=lambda: True,
        )
        assert attempted == []
        assert outcome.failed == []
        assert outcome.cancelled is True


class TestRetryAfter:
    def test_the_header_the_server_sent_is_the_wait(self):
        error = RuntimeError("429")
        error.retry_after = 30.0
        assert retry_after_seconds(error) == 30.0

    def test_no_header_means_no_demand(self):
        assert retry_after_seconds(RuntimeError("plain")) == 0.0

    def test_the_retry_pass_waits_the_time_the_server_asked_for(self):
        slept = []

        def work(item):
            if item in seen:
                return item
            seen.add(item)
            error = RuntimeError("429 Too Many Requests")
            error.retry_after = 45.0
            raise error

        seen = set()
        outcome = run_with_retry_pass(
            [1, 2], work, workers=2, retry_delay=60.0, sleep=slept.append
        )

        assert slept == [45.0]      # the server's number, not the configured one
        assert outcome.failed == []  # both succeeded on the second pass

    def test_the_configured_delay_covers_a_silent_server(self):
        slept = []
        run_with_retry_pass(
            [1], lambda i: (_ for _ in ()).throw(RuntimeError("502 Server Error")),
            workers=2, retry_delay=15.0, sleep=slept.append,
        )
        assert slept == [15.0]


class TestTheRetryPass:
    def test_failures_are_tried_again_more_quietly(self):
        widths = []

        def work(item):
            widths.append(threading.current_thread().name)
            raise RuntimeError("no")

        outcome = run_with_retry_pass(
            list(range(8)), work, workers=6, retry_workers=2,
            retry_delay=0, sleep=lambda s: None,
        )
        # Every unit was attempted twice: once per pass.
        assert len(widths) == 16
        assert outcome.failed == list(range(8))

    def test_a_stopped_run_is_not_retried(self):
        attempts = []

        def work(item):
            attempts.append(item)
            raise RuntimeError("dead")

        slept = []
        run_with_retry_pass(
            list(range(20)), work, workers=2, max_consecutive_failures=2,
            retry_delay=5, sleep=slept.append,
        )
        assert slept == []   # no second pass into a dead backend

    def test_nothing_failed_means_no_wait_at_all(self):
        slept = []
        outcome = run_with_retry_pass(
            [1, 2, 3], lambda i: i, workers=3, retry_delay=60, sleep=slept.append
        )
        assert slept == []
        assert isinstance(outcome, PoolResult) and outcome.failed == []
