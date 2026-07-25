"""Tests for pass-2 centered windows (core/glossary_build/context_window.py)."""
from core.glossary_build.context_window import (
    Occurrence,
    build_context_stack,
    build_window,
    plan_window_size,
)


class TestPlanWindowSize:
    def test_single_occurrence_gets_max_window(self):
        assert plan_window_size(1, stack_budget=8000, max_window=4000) == 4000

    def test_many_occurrences_share_budget(self):
        assert plan_window_size(10, stack_budget=8000, max_window=4000) == 800

    def test_floor_is_min_window(self):
        assert plan_window_size(1000, stack_budget=8000, min_window=240) == 240

    def test_zero_or_negative_returns_max(self):
        assert plan_window_size(0, max_window=4000) == 4000
        assert plan_window_size(-3, max_window=4000) == 4000

    def test_matches_roadmap_shape(self):
        # 1 -> deep, 40 -> thin; monotonically non-increasing
        sizes = [plan_window_size(n) for n in (1, 10, 40)]
        assert sizes[0] > sizes[1] > sizes[2]


class TestBuildWindow:
    def _dataset(self):
        # one block of 11 single-char strings s0..s10
        return [[f"s{i}" for i in range(11)]]

    def test_center_always_included(self):
        dataset = self._dataset()
        occ = Occurrence(0, 5)
        win = build_window(dataset, occ, window_size=1)  # tiny budget
        assert "s5" in win.text
        assert win.start_string_idx == 5
        assert win.end_string_idx == 5

    def test_expands_symmetrically_around_center(self):
        dataset = self._dataset()
        occ = Occurrence(0, 5)
        # each "s#" is 2 chars, separator 1 char; window big enough for a few
        win = build_window(dataset, occ, window_size=20)
        assert win.start_string_idx < 5 < win.end_string_idx
        # symmetric-ish: center stays inside the span
        assert win.start_string_idx <= 5 <= win.end_string_idx

    def test_stops_at_block_boundaries(self):
        dataset = self._dataset()
        occ = Occurrence(0, 0)  # at the very start
        win = build_window(dataset, occ, window_size=10000)
        assert win.start_string_idx == 0
        assert win.end_string_idx == 10  # grew only forward

    def test_window_text_joins_included_strings(self):
        dataset = [["alpha", "beta", "gamma"]]
        occ = Occurrence(0, 1)
        win = build_window(dataset, occ, window_size=10000)
        assert win.text == "alpha\nbeta\ngamma"


class TestBuildContextStack:
    def test_one_window_per_occurrence(self):
        dataset = [[f"line {i}" for i in range(20)]]
        occs = [Occurrence(0, 2), Occurrence(0, 10), Occurrence(0, 15)]
        windows, overflowed = build_context_stack(dataset, occs)
        assert len(windows) == 3
        assert overflowed is False

    def test_overflow_samples_and_flags(self):
        dataset = [[f"line {i}" for i in range(200)]]
        occs = [Occurrence(0, i) for i in range(100)]
        windows, overflowed = build_context_stack(dataset, occs, max_occurrences=40)
        assert overflowed is True
        assert len(windows) == 40

    def test_sampling_is_spread_not_truncated(self):
        dataset = [[f"line {i}" for i in range(200)]]
        occs = [Occurrence(0, i) for i in range(100)]
        windows, _ = build_context_stack(dataset, occs, max_occurrences=10)
        centers = [w.occurrence.string_idx for w in windows]
        # spread across the range, not the first 10
        assert centers[0] == 0
        assert centers[-1] >= 80

    def test_invalid_occurrences_dropped(self):
        dataset = [["a", "b", "c"]]
        occs = [
            Occurrence(0, 1),   # valid
            Occurrence(5, 0),   # bad block
            Occurrence(0, 99),  # bad string
        ]
        windows, _ = build_context_stack(dataset, occs)
        assert len(windows) == 1
        assert windows[0].occurrence == Occurrence(0, 1)

    def test_no_valid_occurrences_returns_empty(self):
        dataset = [["a"]]
        windows, overflowed = build_context_stack(dataset, [Occurrence(9, 9)])
        assert windows == []
        assert overflowed is False

    def test_more_occurrences_yield_thinner_windows(self):
        dataset = [[f"a long game string number {i} with words" for i in range(60)]]
        few, _ = build_context_stack(dataset, [Occurrence(0, 30)])
        many, _ = build_context_stack(dataset, [Occurrence(0, i) for i in range(0, 40)])
        # a lone occurrence should span at least as many strings as a crowded one
        few_span = few[0].end_string_idx - few[0].start_string_idx
        many_span = many[0].end_string_idx - many[0].start_string_idx
        assert few_span >= many_span
