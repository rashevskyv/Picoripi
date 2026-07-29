from unittest.mock import MagicMock
from PyQt6.QtCore import QThreadPool
from handlers.async_issue_scanner import AsyncIssueScanner, get_scanner_thread_pool

def test_async_issue_scanner_init():
    analyzer = MagicMock()
    scanner = AsyncIssueScanner(
        block_idx=1,
        string_idx=2,
        text="Hello World",
        font_map={},
        width_threshold=100,
        analyzer=analyzer
    )
    assert scanner.block_idx == 1
    assert scanner.string_idx == 2
    assert scanner.text == "Hello World"
    assert scanner.isRunning() is True
    assert scanner.is_cancelled() is False

def test_async_issue_scanner_cancel():
    analyzer = MagicMock()
    scanner = AsyncIssueScanner(
        block_idx=1,
        string_idx=2,
        text="Hello World",
        font_map={},
        width_threshold=100,
        analyzer=analyzer
    )
    scanner.cancel()
    assert scanner.is_cancelled() is True
    assert scanner.isRunning() is False

def test_async_issue_scanner_run_basic(qtbot):
    analyzer = MagicMock()
    analyzer.analyze_data_string.return_value = ["warning1"]

    scanner = AsyncIssueScanner(
        block_idx=0,
        string_idx=0,
        text="Hello",
        font_map={},
        width_threshold=100,
        analyzer=analyzer
    )

    signals_emitted = []
    def on_finished(block_idx, string_idx, text, problems, glossary, translation, spellcheck):
        signals_emitted.append((block_idx, string_idx, text, problems, glossary, translation, spellcheck))

    scanner.finished_scan.connect(on_finished)
    scanner.run()

    assert len(signals_emitted) == 1
    assert signals_emitted[0][0] == 0
    assert signals_emitted[0][1] == 0
    assert signals_emitted[0][2] == "Hello"
    assert signals_emitted[0][3] == ["warning1"]

def test_async_issue_scanner_run_sublines(qtbot):
    analyzer = MagicMock()
    del analyzer.analyze_data_string # Force analyze_subline usage
    analyzer.analyze_subline.return_value = ["sub_warning"]

    scanner = AsyncIssueScanner(
        block_idx=0,
        string_idx=0,
        text="Hello\nWorld",
        font_map={},
        width_threshold=100,
        analyzer=analyzer
    )

    signals_emitted = []
    def on_finished(*args):
        signals_emitted.append(args)

    scanner.finished_scan.connect(on_finished)
    scanner.run()

    assert len(signals_emitted) == 1
    assert signals_emitted[0][3] == [["sub_warning"], ["sub_warning"]]

def test_async_issue_scanner_run_tag_mismatch():
    analyzer = MagicMock()
    analyzer.analyze_data_string.return_value = []
    analyzer.check_tags_mismatch.return_value = True
    analyzer.problem_ids = MagicMock()
    analyzer.problem_ids.PROBLEM_TAG_WARNING = "TAG_WARNING"

    scanner = AsyncIssueScanner(
        block_idx=0,
        string_idx=0,
        text="Edited {Tag}",
        font_map={},
        width_threshold=100,
        analyzer=analyzer,
        source_text="Source {Tag2}"
    )

    signals_emitted = []
    scanner.finished_scan.connect(lambda *args: signals_emitted.append(args))
    scanner.run()

    assert len(signals_emitted) == 1
    assert "TAG_WARNING" in signals_emitted[0][3][0]

def test_async_issue_scanner_run_glossary():
    analyzer = MagicMock()
    analyzer.analyze_data_string.return_value = []
    
    mock_entry = MagicMock()
    mock_entry.original = "Key"
    mock_entry.translation = "Value"
    mock_entry.notes = "Note"
    
    mock_match = MagicMock()
    mock_match.start = 0
    mock_match.end = 3
    mock_match.entry = mock_entry

    glossary_manager = MagicMock()
    glossary_manager.get_entries.return_value = [mock_entry]
    glossary_manager.find_matches.return_value = [mock_match]

    scanner = AsyncIssueScanner(
        block_idx=0,
        string_idx=0,
        text="Key word",
        font_map={},
        width_threshold=100,
        analyzer=analyzer,
        glossary_manager=glossary_manager,
        glossary_enabled=True
    )

    signals_emitted = []
    scanner.finished_scan.connect(lambda *args: signals_emitted.append(args))
    scanner.run()

    assert len(signals_emitted) == 1
    assert len(signals_emitted[0][4]) == 1
    assert signals_emitted[0][4][0]["original"] == "Key"
    assert signals_emitted[0][4][0]["translation"] == "Value"

def test_async_issue_scanner_run_translation_matches():
    analyzer = MagicMock()
    analyzer.analyze_data_string.return_value = []
    
    mock_entry = MagicMock()
    mock_entry.original = "Word"
    mock_entry.translation = "TranslatedWord"
    mock_entry.notes = "Note"

    glossary_manager = MagicMock()
    glossary_manager.get_entries.return_value = [mock_entry]
    glossary_manager.get_relevant_terms.return_value = [mock_entry]
    
    import re
    glossary_manager.build_translation_regex.return_value = re.compile("TranslatedWord", re.IGNORECASE)

    scanner = AsyncIssueScanner(
        block_idx=0,
        string_idx=0,
        text="TranslatedWord",
        font_map={},
        width_threshold=100,
        analyzer=analyzer,
        glossary_manager=glossary_manager,
        glossary_enabled=True,
        source_text="Word"
    )

    signals_emitted = []
    scanner.finished_scan.connect(lambda *args: signals_emitted.append(args))
    scanner.run()

    assert len(signals_emitted) == 1
    assert len(signals_emitted[0][5]) == 1
    assert signals_emitted[0][5][0]["translation"] == "TranslatedWord"

def test_async_issue_scanner_run_spellcheck():
    analyzer = MagicMock()
    analyzer.analyze_data_string.return_value = []

    spellcheck_manager = MagicMock()
    spellcheck_manager.enabled = True
    spellcheck_manager.hunspell = MagicMock()
    spellcheck_manager.hunspell.lookup.return_value = False # Misspelled
    spellcheck_manager.hunspell.suggest.return_value = ["Word1", "Word2"]
    spellcheck_manager.custom_words = set()
    spellcheck_manager._spell_cache = {}
    spellcheck_manager._suggestions_cache = {}

    scanner = AsyncIssueScanner(
        block_idx=0,
        string_idx=0,
        text="misspelled",
        font_map={},
        width_threshold=100,
        analyzer=analyzer,
        spellchecker_manager=spellcheck_manager
    )

    signals_emitted = []
    scanner.finished_scan.connect(lambda *args: signals_emitted.append(args))
    scanner.run()

    assert len(signals_emitted) == 1
    assert len(signals_emitted[0][6]) == 1 # Spellcheck matches list of tuples
    assert spellcheck_manager._suggestions_cache["misspelled"] == ["Word1", "Word2"]

def test_async_issue_scanner_cancelled_early():
    analyzer = MagicMock()
    scanner = AsyncIssueScanner(
        block_idx=0,
        string_idx=0,
        text="Hello",
        font_map={},
        width_threshold=100,
        analyzer=analyzer
    )
    scanner.cancel()
    signals_emitted = []
    scanner.finished_scan.connect(lambda *args: signals_emitted.append(args))
    scanner.run()
    assert len(signals_emitted) == 0

def test_get_scanner_thread_pool():
    pool = get_scanner_thread_pool()
    assert isinstance(pool, QThreadPool)
    assert pool.maxThreadCount() == 1
