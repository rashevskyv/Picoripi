"""REVIEW_QUEUE WP6 6.5 and WP1: every AIWorker path behaves as before the run() split; legacy glossary strictness.

The golden files were recorded by ``tests/fixtures/review_queue/wp1_6/ai/make_golden.py`` on the old code; the
same scenario functions run here on the current code.
"""
import importlib.util
import json
from pathlib import Path

import pytest

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "review_queue" / "wp1_6" / "ai"


def _scenarios():
    spec = importlib.util.spec_from_file_location("rq_wp1_6_ai_golden", GOLDEN_DIR / "make_golden.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCENARIOS = _scenarios()
WORKER_GOLDEN = json.loads((GOLDEN_DIR / "worker_paths.json").read_text(encoding="utf-8"))
BASELINE_GOLDEN = json.loads((GOLDEN_DIR / "baseline.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def current(qapp):
    return json.loads(json.dumps(SCENARIOS.worker_scenarios(), ensure_ascii=False))


def _intended(path, events):
    """The golden with the changes made on purpose since it was recorded."""
    if path == "block_sequential_error_on_chunk_2":   # the sequential error names its chunk, as the parallel one does
        prefix = "1 of 3 chunks failed (chunk 2); the finished chunks are kept. "
        return [[e[0], prefix + e[1], *e[2:]] if e[0] == "error" else e for e in events]
    return events


@pytest.mark.parametrize("path", sorted(WORKER_GOLDEN))
def test_worker_path_emits_and_sends_exactly_what_it_did_before_the_split(current, path):
    """Progress text, detail line, per-chunk apply, errors, cancel and the requests themselves, signal by signal."""
    assert current[path]["calls"] == WORKER_GOLDEN[path]["calls"]
    assert current[path]["events"] == _intended(path, WORKER_GOLDEN[path]["events"])


def test_the_golden_covers_what_the_review_item_lists():
    """The 6.5 item asks for: progress text, detail line, per-chunk apply, Cancel mid-run, one failed chunk."""
    seq = WORKER_GOLDEN["block_sequential"]["events"]
    assert ["step", 1, "Translating chunk 2/3 (Attempt 1)", 1] in seq
    assert ["detail", "Chapter 2: Ordon | File: blk0.bmg | Line: 12 (Script Line: 112)"] in seq
    assert [e[1] for e in seq if e[0] == "chunk"] == [0, 1, 2]
    par = WORKER_GOLDEN["block_parallel_error_on_chunk_2"]["events"]
    assert [e[1] for e in par if e[0] == "chunk"] == [0, 2]  # the others are kept
    assert any(e[0] == "error" and e[2] == [1] and "chunk 2" in e[1] for e in par)
    cancel = WORKER_GOLDEN["block_sequential_cancel_during_chunk_2"]["events"]
    assert [e[0] for e in cancel][-1] == "finished" and not any(e[0] == "error" for e in cancel)


# ------------------------------------------------- WP1: legacy AI Build Glossary


@pytest.mark.parametrize("kind", ["prose", "object", "empty"])
def test_legacy_build_glossary_stops_on_a_chunk_that_is_not_a_term_list(qapp, kind):
    """Before: an object or an empty reply was dropped silently (and the build 'succeeded'). Now: an error."""
    before = BASELINE_GOLDEN[f"legacy_glossary_{kind}"]["events"]
    run = SCENARIOS.legacy_glossary_with_unreadable_chunk(kind)
    now = run["events"]

    errors = [e for e in now if e[0] == "error"]
    assert len(errors) == 1 and errors[0][1].startswith("Failed to parse AI response")
    assert len(run["calls"]) == 2  # the third chunk is never sent
    assert not any(e[0] == "success" for e in now)
    if kind != "prose":
        assert any(e[0] == "success" for e in before) and not any(e[0] == "error" for e in before)


def test_legacy_build_glossary_reads_a_term_list_wrapped_in_prose(qapp):
    """Not stricter where it need not be: prose around a list is fine (the old code lost every such chunk)."""
    now = SCENARIOS.legacy_glossary_with_unreadable_chunk("array_after_prose")["events"]
    success = [e for e in now if e[0] == "success"]
    assert len(success) == 1
    assert [term["original"] for term in json.loads(success[0][1])] == ["Term0", "Ordon", "Term2"]
    assert BASELINE_GOLDEN["legacy_glossary_array_after_prose"]["events"][-2] == ["success", "[]"]
