import pytest
from unittest.mock import MagicMock
from dialogs.spellcheck_dialog import SpellcheckAnalysisWorker
from dialogs.search_review_dialog import SearchWorker

def test_spellcheck_worker_success(qtbot):
    spellchecker_manager = MagicMock()
    spellchecker_manager.custom_words = {"hello"}
    spellchecker_manager._spell_cache = {"world": False}
    spellchecker_manager.hunspell = MagicMock()
    spellchecker_manager.hunspell.lookup.side_effect = lambda word: word != "test"

    text = "Hello world.\nThis is a test."
    worker = SpellcheckAnalysisWorker(text, spellchecker_manager)

    with qtbot.waitSignal(worker.finished, timeout=1000) as blocker:
        worker.start()

    items_to_review, new_cache_entries = blocker.args

    assert len(items_to_review) == 1
    start, end, word, line_idx = items_to_review[0]
    assert word == "test"
    assert line_idx == 1
    assert new_cache_entries["test"] is True

def test_spellcheck_worker_cancel(qtbot):
    spellchecker_manager = MagicMock()
    spellchecker_manager.custom_words = set()
    spellchecker_manager._spell_cache = {}
    spellchecker_manager.hunspell = MagicMock()
    spellchecker_manager.hunspell.lookup.return_value = True

    text = "\n".join(["word"] * 5000)
    worker = SpellcheckAnalysisWorker(text, spellchecker_manager)

    with qtbot.waitSignal(worker.cancelled, timeout=1000):
        worker.start()
        worker.cancel()

    worker.wait(2000)
    assert worker.isFinished() or not worker.isRunning()

def test_search_worker_local_success(qtbot):
    params = {
        'text': "This is a search query test.\nSecond line with query.",
        'query': "query",
        'ignore_tags': True,
        'is_fuzzy': False,
        'case_sensitive': False,
        'line_numbers': [0, 1],
        'block_idx': 0,
        'block_indices': [0, 0]
    }

    worker = SearchWorker('local', params)

    with qtbot.waitSignal(worker.finished, timeout=1000) as blocker:
        worker.start()

    items_to_review, text, line_numbers, block_indices, unique_string_indices = blocker.args

    assert len(items_to_review) == 2
    start, end, word, line_idx = items_to_review[0]
    assert word == "query"

def test_search_worker_cancel(qtbot):
    params = {
        'text': "\n".join(["query text line"] * 5000),
        'query': "query",
        'ignore_tags': True,
        'is_fuzzy': False,
        'case_sensitive': False,
        'line_numbers': list(range(5000)),
        'block_idx': 0,
        'block_indices': [0] * 5000
    }

    worker = SearchWorker('local', params)

    with qtbot.waitSignal(worker.cancelled, timeout=1000):
        worker.start()
        worker.cancel()

    worker.wait(2000)
    assert worker.isFinished() or not worker.isRunning()

def test_search_worker_global_success(qtbot):
    data_processor = MagicMock()
    data_processor.get_current_string_text.side_effect = lambda b, s: (f"Text in block {b} string {s} with query word", "")

    data = [
        ["str0", "str1"],
        ["str0"]
    ]

    params = {
        'data': data,
        'data_processor': data_processor,
        'query': "query",
        'case_sensitive': False,
        'search_in_original': False,
        'ignore_tags': True,
        'is_fuzzy': False
    }

    worker = SearchWorker('global', params)

    with qtbot.waitSignal(worker.finished, timeout=1000) as blocker:
        worker.start()

    items_to_review, current_text, line_numbers, block_indices, unique_string_indices = blocker.args

    assert len(unique_string_indices) == 3
    assert "Text in block 0 string 0" in current_text
