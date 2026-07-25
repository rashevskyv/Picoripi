"""Tests for pass-2b rolling synthesis (core/glossary_build/rolling_synthesis.py)."""
from core.glossary_build.rolling_synthesis import (
    RollingSynthesizer,
    roll_up_fragments,
)


def _join(inputs):
    """A deterministic stand-in for the AI fold: concatenate unique parts."""
    seen = []
    for part in inputs:
        for token in part.split("|"):
            if token and token not in seen:
                seen.append(token)
    return "|".join(seen)


class TestFolding:
    def test_fewer_than_five_folds_once_at_finish(self):
        result = roll_up_fragments(["a", "b", "c"], _join)
        assert result.description == "a|b|c"
        assert result.fold_calls == 1
        assert result.consumed == 3
        assert result.stopped_early is False

    def test_exactly_five_folds_once(self):
        frags = ["a", "b", "c", "d", "e"]
        result = roll_up_fragments(frags, _join)
        assert result.description == "a|b|c|d|e"
        assert result.fold_calls == 1

    def test_running_synthesis_counts_as_one_of_five(self):
        # First 5 fold to 1. Then 4 more should trigger the second fold
        # (synthesis + 4 = 5), not require a fifth new fragment.
        frags = [str(i) for i in range(9)]  # 5 then 4
        result = roll_up_fragments(frags, _join)
        assert result.fold_calls == 2
        assert result.consumed == 9
        assert result.description == "|".join(str(i) for i in range(9))

    def test_leftover_after_folds_flushed_at_finish(self):
        frags = [str(i) for i in range(7)]  # 5 -> fold, then 2 leftover
        result = roll_up_fragments(frags, _join)
        assert result.fold_calls == 2  # one rolling + one finish flush
        assert result.description == "|".join(str(i) for i in range(7))


class TestEarlyStop:
    def test_stops_when_fold_adds_nothing_new(self):
        # synthesize ignores new input after the first fold -> convergence
        calls = {"n": 0}

        def stubborn(inputs):
            calls["n"] += 1
            return "STABLE"

        # is_new default: "STABLE" == "STABLE" -> not new on 2nd fold
        result = roll_up_fragments([str(i) for i in range(20)], stubborn)
        assert result.stopped_early is True
        # first fold at 5, second fold at 5+4=9 returns STABLE again -> stop
        assert result.consumed == 9
        assert result.fold_calls == 2

    def test_no_early_stop_when_always_new(self):
        result = roll_up_fragments([str(i) for i in range(14)], _join)
        assert result.stopped_early is False
        assert result.consumed == 14

    def test_add_returns_false_after_stop(self):
        def stubborn(_inputs):
            return "SAME"

        roller = RollingSynthesizer(synthesize=stubborn)
        # feed enough to trigger two folds and converge
        results = [roller.add(str(i)) for i in range(20)]
        assert False in results  # signalled stop
        # further adds are no-ops returning False
        assert roller.add("x") is False


class TestEdgeCases:
    def test_empty_fragments(self):
        result = roll_up_fragments([], _join)
        assert result.description == ""
        assert result.fold_calls == 0
        assert result.consumed == 0

    def test_custom_fold_at(self):
        frags = ["a", "b", "c"]
        result = roll_up_fragments(frags, _join, fold_at=2)
        # folds at 2, then 1 more triggers (synth+1=2), no leftover
        assert result.description == "a|b|c"
        assert result.stopped_early is False

    def test_custom_is_new(self):
        # Treat length as the novelty signal
        def grow(inputs):
            return "x" * (len("".join(inputs)) + 1)

        result = roll_up_fragments(
            ["a"] * 12, grow, is_new=lambda new, old: len(new) > len(old)
        )
        assert result.stopped_early is False
