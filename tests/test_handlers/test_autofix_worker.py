import pytest
from unittest.mock import MagicMock
from handlers.autofix_worker import AutofixWorker

def test_autofix_worker_init():
    game_rules = MagicMock()
    data = [["line1", "line2"]]
    edited_data = {}
    edited_file_data = []
    string_metadata = {}
    all_font_maps = {}
    font_map = {}
    allowed_problems = {"prob1"}
    
    worker = AutofixWorker(
        game_rules=game_rules,
        target_strings=[(0, 0)],
        data=data,
        edited_data=edited_data,
        edited_file_data=edited_file_data,
        string_metadata=string_metadata,
        all_font_maps=all_font_maps,
        font_map=font_map,
        warning_threshold=200,
        logical_hard_limit=300,
        allowed_problems=allowed_problems,
        page_local=False
    )
    
    assert worker.game_rules == game_rules
    assert worker.target_strings == [(0, 0)]
    assert worker.data == data
    assert worker.allowed_problems == allowed_problems
    assert worker.page_local is False

def test_autofix_worker_run_success():
    game_rules = MagicMock()
    # Mock autofix_data_string to change text on first iteration, and then break
    game_rules.autofix_data_string.side_effect = [
        ("fixed_line1", True),  # First iteration: changed
        ("fixed_line1", False)  # Second iteration: no change
    ]
    
    data = [["line1"]]
    edited_data = {}
    edited_file_data = []
    string_metadata = {}
    all_font_maps = {}
    font_map = {}
    allowed_problems = {"prob1"}
    
    worker = AutofixWorker(
        game_rules=game_rules,
        target_strings=[(0, 0)],
        data=data,
        edited_data=edited_data,
        edited_file_data=edited_file_data,
        string_metadata=string_metadata,
        all_font_maps=all_font_maps,
        font_map=font_map,
        warning_threshold=200,
        logical_hard_limit=300,
        allowed_problems=allowed_problems,
        page_local=False
    )
    
    finished_results = []
    def on_finished(res):
        finished_results.extend(res)
        
    worker.completed.connect(on_finished)
    worker.run()
    
    assert len(finished_results) == 1
    assert finished_results[0] == (0, 0, "line1", "fixed_line1")
    game_rules.autofix_data_string.assert_called()

def test_autofix_worker_run_no_changes():
    game_rules = MagicMock()
    game_rules.autofix_data_string.return_value = ("line1", False)
    
    data = [["line1"]]
    edited_data = {}
    edited_file_data = []
    string_metadata = {}
    all_font_maps = {}
    font_map = {}
    allowed_problems = {"prob1"}
    
    worker = AutofixWorker(
        game_rules=game_rules,
        target_strings=[(0, 0)],
        data=data,
        edited_data=edited_data,
        edited_file_data=edited_file_data,
        string_metadata=string_metadata,
        all_font_maps=all_font_maps,
        font_map=font_map,
        warning_threshold=200,
        logical_hard_limit=300,
        allowed_problems=allowed_problems,
        page_local=False
    )
    
    finished_results = []
    def on_finished(res):
        finished_results.extend(res)
        
    worker.completed.connect(on_finished)
    worker.run()
    
    assert len(finished_results) == 0

def test_autofix_worker_run_cancelled():
    game_rules = MagicMock()
    # Let it return changed once, but we will cancel during execution
    game_rules.autofix_data_string.return_value = ("fixed", True)
    
    data = [["line1", "line2"]]
    edited_data = {}
    edited_file_data = []
    string_metadata = {}
    all_font_maps = {}
    font_map = {}
    allowed_problems = {"prob1"}
    
    worker = AutofixWorker(
        game_rules=game_rules,
        target_strings=[(0, 0), (0, 1)],
        data=data,
        edited_data=edited_data,
        edited_file_data=edited_file_data,
        string_metadata=string_metadata,
        all_font_maps=all_font_maps,
        font_map=font_map,
        warning_threshold=200,
        logical_hard_limit=300,
        allowed_problems=allowed_problems,
        page_local=False
    )
    
    # Mock run to cancel worker before processing
    worker.cancel()
    
    cancelled_called = [False]
    def on_cancelled():
        cancelled_called[0] = True
        
    worker.cancelled.connect(on_cancelled)
    worker.run()
    
    assert cancelled_called[0] is True

def test_autofix_worker_error():
    game_rules = MagicMock()
    game_rules.autofix_data_string.side_effect = Exception("Autofix failed")
    
    data = [["line1"]]
    edited_data = {}
    edited_file_data = []
    string_metadata = {}
    all_font_maps = {}
    font_map = {}
    allowed_problems = {"prob1"}
    
    worker = AutofixWorker(
        game_rules=game_rules,
        target_strings=[(0, 0)],
        data=data,
        edited_data=edited_data,
        edited_file_data=edited_file_data,
        string_metadata=string_metadata,
        all_font_maps=all_font_maps,
        font_map=font_map,
        warning_threshold=200,
        logical_hard_limit=300,
        allowed_problems=allowed_problems,
        page_local=False
    )
    
    error_msg = []
    def on_error(msg):
        error_msg.append(msg)
        
    worker.error.connect(on_error)
    worker.run()
    
    assert len(error_msg) == 1
    assert "Autofix failed" in error_msg[0]


def test_autofix_worker_cancel_safe_shutdown():
    game_rules = MagicMock()
    game_rules.autofix_data_string.return_value = ("fixed", True)
    
    data = [["line1"]]
    worker = AutofixWorker(
        game_rules=game_rules,
        target_strings=[(0, 0)],
        data=data,
        edited_data={},
        edited_file_data=[],
        string_metadata={},
        all_font_maps={},
        font_map={},
        warning_threshold=200,
        logical_hard_limit=300,
        allowed_problems=set(),
        page_local=False
    )
    
    assert worker.isRunning() is False
    worker.cancel()
    assert worker._is_cancelled is True


class FakeGameRules:
    def __init__(self, slow=False):
        self.slow = slow

    def autofix_data_string(self, *args, **kwargs):
        if self.slow:
            import time
            time.sleep(0.02)
        return ("fixed", True)


def test_autofix_worker_real_thread_lifecycle(qtbot):
    game_rules = FakeGameRules(slow=False)
    
    data = [["line1"]]
    worker = AutofixWorker(
        game_rules=game_rules,
        target_strings=[(0, 0)],
        data=data,
        edited_data={},
        edited_file_data=[],
        string_metadata={},
        all_font_maps={},
        font_map={},
        warning_threshold=200,
        logical_hard_limit=300,
        allowed_problems=set(),
        page_local=False
    )
    
    completed_called = False
    def on_completed(results):
        nonlocal completed_called
        completed_called = True
    worker.completed.connect(on_completed)
    
    error_msg = None
    def on_error(msg):
        nonlocal error_msg
        error_msg = msg
    worker.error.connect(on_error)
    
    finished_called = False
    def on_finished():
        nonlocal finished_called
        finished_called = True
    worker.finished.connect(on_finished)
    
    try:
        worker.start()
        # Wait for the thread to finish execution on OS level
        finished_ok = worker.wait(15000)
        assert finished_ok is True, "Worker thread timed out on wait()"
    finally:
        worker.cancel()
        worker.wait(15000)
        
    # Process queued signals
    from PyQt6.QtCore import QCoreApplication
    QCoreApplication.processEvents()
        
    assert error_msg is None, f"Worker failed with error: {error_msg}"
    assert finished_called is True, "Worker thread did not even finish"
    assert completed_called is True, "Worker finished but completed was not called"


def test_autofix_worker_real_thread_cancellation(qtbot):
    game_rules = FakeGameRules(slow=True)
    
    # Use enough strings to give it time to receive cancel request
    data = [["line1", "line2", "line3", "line4", "line5", "line6", "line7", "line8", "line9", "line10"]]
    target = [(0, i) for i in range(10)]
    worker = AutofixWorker(
        game_rules=game_rules,
        target_strings=target,
        data=data,
        edited_data={},
        edited_file_data=[],
        string_metadata={},
        all_font_maps={},
        font_map={},
        warning_threshold=200,
        logical_hard_limit=300,
        allowed_problems=set(),
        page_local=False
    )
    
    cancelled_called = False
    def on_cancelled():
        nonlocal cancelled_called
        cancelled_called = True
    worker.cancelled.connect(on_cancelled)
    
    error_msg = None
    def on_error(msg):
        nonlocal error_msg
        error_msg = msg
    worker.error.connect(on_error)
    
    finished_called = False
    def on_finished():
        nonlocal finished_called
        finished_called = True
    worker.finished.connect(on_finished)
    
    try:
        worker.start()
        # Give the thread a little time to start executing loop
        qtbot.wait(100)
        worker.cancel()
        
        # Wait for the thread to finish execution on OS level
        finished_ok = worker.wait(15000)
        assert finished_ok is True, "Worker thread timed out on wait()"
    finally:
        worker.cancel()
        worker.wait(15000)
        
    # Process queued signals
    from PyQt6.QtCore import QCoreApplication
    QCoreApplication.processEvents()
        
    assert error_msg is None, f"Worker failed with error: {error_msg}"
    assert finished_called is True, "Worker thread did not even finish"
    assert cancelled_called is True, "Worker finished but cancelled was not called"

