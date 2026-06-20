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

def test_glossary_occurrence_worker_cancel(qtbot):
    from handlers.translation.glossary_handler import GlossaryOccurrenceWorker
    from core.glossary_manager import GlossaryManager

    glossary_manager = GlossaryManager()
    glossary_manager.add_entry("Zelda", "Зельда", "")
    
    dataset = [["Zelda is a princess of Hyrule"] * 100] * 50
    worker = GlossaryOccurrenceWorker(glossary_manager, dataset)
    
    # We will record signals
    emitted = []
    worker.finished_with_result.connect(lambda val: emitted.append(val))
    
    worker.start()
    worker.requestInterruption()
    worker.wait(2000)
    
    assert worker.isFinished() or not worker.isRunning()
    # It should not emit finished_with_result since it was cancelled
    assert len(emitted) == 0

def test_spellcheck_dialog_close_during_analysis(qtbot):
    from dialogs.spellcheck_dialog import SpellcheckDialog
    
    spellchecker_manager = MagicMock()
    spellchecker_manager.custom_words = set()
    spellchecker_manager._spell_cache = {}
    spellchecker_manager.hunspell = MagicMock()
    
    import time
    spellchecker_manager.hunspell.lookup.side_effect = lambda word: time.sleep(0.0005) or True
    
    # Use parent None
    parent = None
    
    # Create large text of unique alphabetic words to bypass new_cache_entries hit
    words = []
    for i in range(2000):
        suffix = ""
        temp = i
        for _ in range(4):
            suffix += chr(97 + (temp % 26))
            temp //= 26
        words.append("word" + suffix)
    text = "\n".join(words)
    
    dialog = SpellcheckDialog(parent, text, spellchecker_manager, starting_line_number=0, line_numbers=[0]*2000, block_idx=0, force_async=True)
    
    # Let analysis start (50ms timer + startup delay)
    qtbot.waitUntil(lambda: hasattr(dialog, 'analysis_worker') and dialog.analysis_worker is not None, timeout=3000)
    
    assert dialog.analysis_worker is not None
    assert dialog.analysis_worker.isRunning()
    
    # Close dialog while worker is running
    dialog.reject()
    
    # Verify closing flag is set
    assert dialog._is_closing is True
    
    # Wait for thread to shutdown safely and dialog to reject
    qtbot.waitUntil(lambda: dialog.analysis_worker is None, timeout=3000)

def test_search_review_dialog_close_during_analysis(qtbot):
    from dialogs.search_review_dialog import SearchReviewDialog
    import dialogs.search_review_dialog
    import time
    
    parent = None
    text = "\n".join(["query text line"] * 1000)
    
    # Monkeypatch find_smart_matches in search_review_dialog to slow it down
    original_find = dialogs.search_review_dialog.find_smart_matches
    dialogs.search_review_dialog.find_smart_matches = lambda text_in, query_in, case_in: time.sleep(0.001) or original_find(text_in, query_in, case_in)
    
    try:
        dialog = SearchReviewDialog(parent, text, "query", starting_line_number=0, line_numbers=list(range(1000)), block_idx=0, force_async=True)
        
        # Let search start (50ms timer + startup delay)
        qtbot.waitUntil(lambda: hasattr(dialog, 'search_worker') and dialog.search_worker is not None, timeout=3000)
        
        assert dialog.search_worker is not None
        assert dialog.search_worker.isRunning()
        
        # Close dialog while worker is running
        dialog.reject()
        
        # Verify closing flag is set
        assert dialog._is_closing is True
        
        # Wait for thread to shutdown safely and dialog to reject
        qtbot.waitUntil(lambda: dialog.search_worker is None, timeout=3000)
    finally:
        # Restore original function
        dialogs.search_review_dialog.find_smart_matches = original_find

