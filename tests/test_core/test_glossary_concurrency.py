"""Tests for the AIMD concurrency window (core/glossary_build/concurrency.py)."""
from core.glossary_build.concurrency import AIMDWindow, fixed_window, local_window


class TestAIMD:
    def test_additive_increase_on_success(self):
        w = AIMDWindow(concurrency=4, maximum=16)
        assert w.on_success() == 5
        assert w.on_success() == 6

    def test_multiplicative_decrease_on_failure(self):
        w = AIMDWindow(concurrency=8, maximum=16)
        assert w.on_failure() == 4
        assert w.on_failure() == 2

    def test_probe_up_one_after_halving(self):
        w = AIMDWindow(concurrency=10, maximum=16)
        w.on_failure()  # -> 5
        assert w.concurrency == 5
        assert w.on_success() == 6  # probe +1

    def test_never_below_minimum(self):
        w = AIMDWindow(concurrency=2, minimum=1)
        w.on_failure()  # 1
        w.on_failure()  # floor
        assert w.concurrency == 1

    def test_never_above_maximum(self):
        w = AIMDWindow(concurrency=15, maximum=16)
        w.on_success()  # 16
        w.on_success()  # capped
        assert w.concurrency == 16
        assert w.at_ceiling() is True

    def test_starts_clamped(self):
        assert AIMDWindow(concurrency=100, maximum=16).concurrency == 16
        assert AIMDWindow(concurrency=0, minimum=1).concurrency == 1

    def test_maximum_never_below_minimum(self):
        w = AIMDWindow(concurrency=1, minimum=4, maximum=2)
        assert w.maximum >= w.minimum


class TestAutoMeasureOff:
    def test_fixed_window_does_not_adjust(self):
        w = fixed_window(3)
        assert w.on_success() == 3
        assert w.on_failure() == 3
        assert w.concurrency == 3

    def test_local_window_pinned_at_one(self):
        w = local_window()
        assert w.concurrency == 1
        assert w.on_success() == 1
        assert w.at_ceiling() is True
