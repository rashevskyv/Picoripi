"""The host sets the block and string index a problem analyzer reads, on every string-analysis path."""
import threading
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from handlers.analyzer_context import analyzer_string_context
from handlers.text_operation.edit_mixin import EditMixin
from handlers.text_operation.scan_mixin import ScanMixin
from handlers.width_calculation_worker import WidthCalculationWorker
from plugins.common.problem_analyzer import GenericProblemAnalyzer

SEED = (99, 99)


class RecordingAnalyzer:
    """Plain fake: records the context it sees on each call and returns one empty set per subline."""

    def __init__(self):
        self._current_scan_block_idx, self._current_scan_string_idx = SEED
        self.seen = []

    def analyze_data_string(self, data_string, font_map, threshold, logical_hard_limit=None):
        self.seen.append((self._current_scan_block_idx, self._current_scan_string_idx, data_string))
        return [set() for _ in data_string.split("\n")]

    def get_problem_definitions(self):
        return {}


class FakeDataProcessor:
    def __init__(self, texts):
        self.texts = texts

    def get_current_string_text(self, block_idx, string_idx):
        return self.texts[string_idx], "src"

    def _get_string_from_source(self, block_idx, string_idx, data, tag):
        return self.texts[string_idx]

    def schedule_autosave(self):
        pass

    def update_edited_data(self, *args, **kwargs):
        return True


class FakeFontHelper:
    def get_font_map_for_string(self, block_idx, string_idx):
        return {"a": {"width": 10}}


class FakeGameRules:
    """Plain fake plugin: exposes the analyzer as problem_analyzer, as the host expects."""

    def __init__(self, analyzer):
        self.problem_analyzer = analyzer

    def get_problem_definitions(self):
        return {}


def test_context_sets_both_indexes_and_restores_previous_values():
    analyzer = RecordingAnalyzer()
    with analyzer_string_context(analyzer, 3, 4):
        assert (analyzer._current_scan_block_idx, analyzer._current_scan_string_idx) == (3, 4)
    assert (analyzer._current_scan_block_idx, analyzer._current_scan_string_idx) == SEED


def test_context_restores_values_when_body_raises():
    analyzer = RecordingAnalyzer()
    with pytest.raises(RuntimeError):
        with analyzer_string_context(analyzer, 1, 2):
            raise RuntimeError("boom")
    assert (analyzer._current_scan_block_idx, analyzer._current_scan_string_idx) == SEED


def test_context_accepts_object_without_attributes():
    class Bare:
        pass

    analyzer = Bare()
    with analyzer_string_context(analyzer, 0, 5):
        assert (analyzer._current_scan_block_idx, analyzer._current_scan_string_idx) == (0, 5)
    assert analyzer._current_scan_block_idx is None
    assert analyzer._current_scan_string_idx is None


def test_width_worker_analyzer_sees_each_string_being_calculated():
    analyzer = RecordingAnalyzer()
    worker = WidthCalculationWorker(
        block_idx=7,
        block_data=["first", "second"],
        block_name="B",
        font_map_helper=FakeFontHelper(),
        data_processor=FakeDataProcessor(["first", "second"]),
        game_rules_plugin=FakeGameRules(analyzer),
        mw_settings={},
        all_font_maps={},
    )
    worker.run()

    # Each string is analysed once for "Current" and once for "Original", with that string's indexes.
    assert [(b, s) for b, s, _ in analyzer.seen] == [(7, 0), (7, 0), (7, 1), (7, 1)]
    assert [text for _, _, text in analyzer.seen] == ["first", "first", "second", "second"]
    assert (analyzer._current_scan_block_idx, analyzer._current_scan_string_idx) == SEED


def test_width_worker_calls_analyzer_once_per_text_not_per_subline():
    analyzer = RecordingAnalyzer()
    worker = WidthCalculationWorker(
        block_idx=0,
        block_data=["a\nb\nc"],
        block_name="B",
        font_map_helper=FakeFontHelper(),
        data_processor=FakeDataProcessor(["a\nb\nc"]),
        game_rules_plugin=FakeGameRules(analyzer),
        mw_settings={},
        all_font_maps={},
    )
    worker.run()
    assert len(analyzer.seen) == 2  # Current and Original, three sublines each


class _Mw:
    """Plain fake of the main window fields the edit path reads."""

    def __init__(self, texts, analyzer):
        self.data_store = SimpleNamespace(physical_block_idx=1, data=[["orig0", "orig1", "orig2", "orig3"]],
                                          problems_per_subline={})
        self.string_metadata = {}
        self.font_map = {"a": {"width": 10}}
        self.line_width_warning_threshold_pixels = 280
        self.game_dialog_max_width_pixels = 300
        self.helper = FakeFontHelper()
        self.current_game_rules = FakeGameRules(analyzer)
        self.texts = texts


class _EditHost(EditMixin):
    def __init__(self, mw, data_processor):
        self.mw = mw
        self.data_processor = data_processor


class _ScanHost(ScanMixin):
    def __init__(self, mw, data_processor):
        self.mw = mw
        self.data_processor = data_processor


def test_width_action_on_edit_path_sees_the_edited_line_not_the_last_scan():
    analyzer = RecordingAnalyzer()
    analyzer._current_scan_block_idx, analyzer._current_scan_string_idx = 0, 0  # last scanned string
    mw = _Mw(["x", "y", "p\nq\nr", "w"], analyzer)
    host = _EditHost(mw, FakeDataProcessor(mw.texts))

    with patch("handlers.text_operation.edit_mixin.QMessageBox"):
        host.calculate_width_for_data_line_action(2)

    assert {(b, s) for b, s, _ in analyzer.seen} == {(1, 2)}
    # Current and Original: one analyzer call each, not one per subline (three sublines here).
    assert len(analyzer.seen) == 2
    assert (analyzer._current_scan_block_idx, analyzer._current_scan_string_idx) == (0, 0)


def test_rescan_on_edit_path_sees_the_edited_string():
    analyzer = RecordingAnalyzer()
    mw = _Mw(["x", "y", "z", "w"], analyzer)
    mw.data_store.data = [["a", "b", "c", "d"]]
    host = _ScanHost(mw, FakeDataProcessor(mw.texts))

    host._rescan_issues_for_current_string(1, 3, "edited\nline")

    assert analyzer.seen == [(1, 3, "edited\nline")]
    assert (analyzer._current_scan_block_idx, analyzer._current_scan_string_idx) == SEED


def _make_analyzer():
    return GenericProblemAnalyzer(None, None, {}, {})


def _read(analyzer):
    return analyzer._current_scan_block_idx, analyzer._current_scan_string_idx


def test_old_attribute_names_read_and_write_for_one_thread():
    analyzer = _make_analyzer()
    assert _read(analyzer) == (None, None)
    analyzer._current_scan_block_idx = 2
    analyzer._current_scan_string_idx = 5
    assert _read(analyzer) == (2, 5)
    with analyzer_string_context(analyzer, 7, 8):
        assert _read(analyzer) == (7, 8)
    assert _read(analyzer) == (2, 5)


def test_two_threads_each_keep_their_own_string_context_while_overlapping():
    analyzer = _make_analyzer()
    # Two workers and the main thread are inside their own contexts at the same time.
    barrier = threading.Barrier(3, timeout=5)
    seen = {}
    errors = []

    def worker(name, block, string):
        try:
            with analyzer_string_context(analyzer, block, string):
                barrier.wait()
                seen[name] = _read(analyzer)
                barrier.wait()
            seen[name + "_after"] = _read(analyzer)
        except Exception as exc:  # reported below; abort so the other parties do not wait
            errors.append(exc)
            barrier.abort()

    threads = [
        threading.Thread(target=worker, args=("a", 1, 10)),
        threading.Thread(target=worker, args=("b", 2, 20)),
    ]
    for thread in threads:
        thread.start()
    with analyzer_string_context(analyzer, 9, 90):
        barrier.wait()
        main_inside = _read(analyzer)
        barrier.wait()
    for thread in threads:
        thread.join(timeout=5)

    assert errors == []
    assert seen["a"] == (1, 10)
    assert seen["b"] == (2, 20)
    assert main_inside == (9, 90)
    # After each context ends, its own thread is back to None and the main thread too.
    assert seen["a_after"] == (None, None)
    assert seen["b_after"] == (None, None)
    assert _read(analyzer) == (None, None)


def test_value_set_on_one_thread_is_not_seen_by_another_thread():
    analyzer = _make_analyzer()
    analyzer._current_scan_block_idx = 4
    analyzer._current_scan_string_idx = 4
    seen = {}

    def reader():
        seen["other"] = _read(analyzer)

    thread = threading.Thread(target=reader)
    thread.start()
    thread.join(timeout=5)
    assert seen["other"] == (None, None)
    assert _read(analyzer) == (4, 4)


def test_new_analyzer_created_in_a_new_thread_sees_none():
    result = {}

    def build_and_read():
        result["values"] = _read(_make_analyzer())

    thread = threading.Thread(target=build_and_read)
    thread.start()
    thread.join(timeout=5)
    assert result["values"] == (None, None)
