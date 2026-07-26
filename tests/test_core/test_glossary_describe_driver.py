"""Tests for passes 2/2b describe driver (core/glossary_build/describe_driver.py)."""
from core.glossary_build.context_window import Occurrence
from core.glossary_build.describe_driver import describe_term


def _dataset(n=200):
    return [[f"line {i} mentions the term here" for i in range(n)]]


class TestSingleStack:
    def test_one_synthesize_call_when_fits(self):
        dataset = _dataset()
        occs = [Occurrence(0, 5), Occurrence(0, 40)]
        calls = {"stack": 0, "fold": 0}

        def synth(windows):
            calls["stack"] += 1
            return f"desc from {len(windows)} windows"

        def fold(_texts):
            calls["fold"] += 1
            return "FOLDED"

        result = describe_term(dataset, occs, synth, fold=fold)
        assert result.folded is False
        assert result.stacks_processed == 1
        assert calls["stack"] == 1
        assert calls["fold"] == 0
        assert "windows" in result.description

    def test_no_occurrences_returns_empty(self):
        result = describe_term(_dataset(), [], lambda w: "x")
        assert result.description == ""

    def test_all_invalid_occurrences_empty(self):
        result = describe_term(_dataset(3), [Occurrence(9, 9)], lambda w: "x")
        assert result.description == ""


class TestOverflowFolding:
    def test_many_occurrences_fold(self):
        dataset = _dataset()
        # 90 occurrences, batch_size 40 -> 3 batches -> folding
        occs = [Occurrence(0, i) for i in range(90)]
        stack_calls = {"n": 0}

        def synth(windows):
            stack_calls["n"] += 1
            return f"fragment {stack_calls['n']}"

        def fold(texts):
            return " | ".join(texts)

        result = describe_term(dataset, occs, synth, fold=fold, batch_size=40)
        assert result.folded is True
        assert result.stacks_processed == 3
        assert "fragment" in result.description

    def test_overflow_without_fold_falls_back_to_first_stack(self):
        dataset = _dataset()
        occs = [Occurrence(0, i) for i in range(90)]

        def synth(windows):
            return "single stack only"

        result = describe_term(dataset, occs, synth, fold=None, batch_size=40)
        assert result.folded is False
        assert result.stacks_processed == 1
        assert result.description == "single stack only"

    def test_early_stop_halts_batches(self):
        dataset = _dataset()
        occs = [Occurrence(0, i) for i in range(200)]  # 5 batches of 40
        stack_calls = {"n": 0}

        def synth(windows):
            stack_calls["n"] += 1
            return "frag"

        def fold(_texts):
            return "STABLE"  # never changes -> convergence triggers early stop

        result = describe_term(dataset, occs, synth, fold=fold, batch_size=40, fold_at=2)
        assert result.stopped_early is True
        # stopped before processing all 5 batches
        assert result.stacks_processed < 5
