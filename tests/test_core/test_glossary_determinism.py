"""The same input must build the same glossary, whatever order the requests answer in (WP3 3.2)."""
import json
import threading
import time
from pathlib import Path

from core.glossary_build.parallel import LOOKAHEAD_FACTOR, run_pool
from core.glossary_build.pipeline_coordinator import MODE_DRAFT, GlossaryBuildCoordinator
from core.glossary_build.sweep_driver import RawTerm, merge_raw_terms
from core.glossary_manager import GlossaryManager

PROMPTS = json.loads(Path("translation_prompts/glossary_pipeline_prompts.json").read_text(encoding="utf-8"))


class TestRunPoolOrder:
    def test_results_are_released_in_item_order_whatever_finishes_first(self):
        def work(item):
            time.sleep((5 - item) * 0.02)   # the last item answers first
            return item * 10

        seen, progress = [], []
        run_pool(range(6), work, workers=6,
                 on_result=lambda item, result: seen.append((item, result)),
                 on_progress=lambda done, total: progress.append(done))

        assert seen == [(i, i * 10) for i in range(6)]
        assert progress == [1, 2, 3, 4, 5, 6]

    def test_a_failed_unit_does_not_hold_back_the_ones_after_it(self):
        def work(item):
            if item == 1:
                raise RuntimeError("boom")
            return item

        seen = []
        outcome = run_pool(range(5), work, workers=2, on_result=lambda item, result: seen.append(item))

        assert seen == [0, 2, 3, 4] and outcome.failed == [1]

    def test_the_pool_never_runs_far_ahead_of_a_slow_first_unit(self):
        release = threading.Event()
        started = []
        lock = threading.Lock()

        def work(item):
            with lock:
                started.append(item)
            if item == 0:
                release.wait(timeout=5)
            return item

        seen = []
        thread = threading.Thread(target=lambda: run_pool(
            range(40), work, workers=2, on_result=lambda item, result: seen.append(item)))
        thread.start()
        deadline = time.monotonic() + 3
        while len(started) < 2 * LOOKAHEAD_FACTOR and time.monotonic() < deadline:
            time.sleep(0.01)
        time.sleep(0.1)
        ahead = len(started)
        release.set()
        thread.join(timeout=10)

        assert ahead == 2 * LOOKAHEAD_FACTOR       # bounded while item 0 is stuck
        assert seen == list(range(40))             # and nothing is lost or reordered

    def test_finished_units_behind_a_stuck_one_are_kept_when_the_run_is_cancelled(self):
        cancelled = threading.Event()

        def work(item):
            if item == 0:
                cancelled.wait(timeout=5)
                raise RuntimeError("never came back")
            if item == 3:
                cancelled.set()
            return item

        seen = []
        outcome = run_pool(range(8), work, workers=4, is_cancelled=cancelled.is_set,
                           on_result=lambda item, result: seen.append(item))

        assert outcome.cancelled is True
        assert seen == sorted(seen) and {1, 2, 3} <= set(seen)
        assert outcome.stop_error is None


class TestMajoritySpelling:
    def test_display_form_is_the_most_common_spelling(self):
        aggregated = {}
        merge_raw_terms(aggregated, [RawTerm("Hylian shield"), RawTerm("Hylian Shield"), RawTerm("Hylian Shield")],
                        normalize=GlossaryManager.canonical_key)
        assert [agg.term for agg in aggregated.values()] == ["Hylian Shield"]

    def test_a_tie_goes_to_the_first_spelling_seen(self):
        aggregated = {}
        merge_raw_terms(aggregated, [RawTerm("Rupees"), RawTerm("Rupee")], normalize=GlossaryManager.canonical_key)
        assert [agg.term for agg in aggregated.values()] == ["Rupees"]


def _build(delays):
    """A draft build over three chunks whose replies arrive in the given order."""
    manager = GlossaryManager()
    manager.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
    replies = {
        "alpha": [{"term": "Hylian shield", "section": "Items", "fragment": "a shield"},
                  {"term": "Zora", "section": "Races", "fragment": "river folk"}],
        "beta": [{"term": "Hylian Shield", "section": "Items", "fragment": "sturdy"},
                 {"term": "Ordon", "section": "Places", "fragment": "a village"}],
        "gamma": [{"term": "Hylian Shield", "section": "Items", "fragment": "sold in Kakariko"},
                  {"term": "Zoras", "section": "Races", "fragment": "they swim"}],
    }

    def call(messages):
        user = messages[1]["content"]
        for marker, reply in replies.items():
            if marker in user:
                time.sleep(delays[marker])
                return json.dumps(reply)
        return "[]"

    dataset = [["alpha " + "x" * 3000, "beta " + "y" * 3000, "gamma " + "z" * 3000]]
    coordinator = GlossaryBuildCoordinator(manager, call, PROMPTS, workers=3, chunk_size="local")
    coordinator.build(dataset, MODE_DRAFT)
    return [(entry.original, entry.section, tuple(f.text for f in entry.fragments)) for entry in manager.get_entries()]


def test_a_build_is_the_same_whatever_order_the_chunks_answer_in():
    forward = _build({"alpha": 0.0, "beta": 0.03, "gamma": 0.06})
    backward = _build({"alpha": 0.06, "beta": 0.03, "gamma": 0.0})

    assert forward == backward
    originals = [original for original, _, _ in forward]
    assert originals == ["Hylian Shield", "Ordon", "Zora"]      # by section, then canonical key
    shield = next(row for row in forward if row[0] == "Hylian Shield")
    assert shield[2] == ("a shield", "sturdy", "sold in Kakariko")   # one entry, all three fragments


def test_translate_targets_are_ordered_by_length_then_family_head_first():
    manager = GlossaryManager()
    manager.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
    for term in ("Zora Armor", "Hylian Shield", "Zora", "Hylian", "The Zora Queen"):
        manager.add_entry(term, "", "description", fold_variants=False)
    order = []

    def call(messages):
        order.append(messages[1]["content"].split("Term:", 1)[1].split("\n", 1)[0].strip())
        return json.dumps([{"translation": "x", "rationale": ""}])

    GlossaryBuildCoordinator(manager, call, PROMPTS, workers=1).run_translate()

    assert order == ["Hylian", "Zora", "Hylian Shield", "Zora Armor", "The Zora Queen"]
