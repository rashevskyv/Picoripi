import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import QThread
from utils.thread_utils import safe_shutdown_thread

def test_safe_shutdown_thread_all_branches():
    # Setup mock worker and thread
    worker = MagicMock()
    thread = MagicMock()
    thread.isRunning.return_value = True
    thread.wait.return_value = True

    # Call helper
    safe_shutdown_thread(thread, worker, timeout_ms=500)

    # Verify worker cancel & disconnect
    worker.cancel.assert_called_once()
    worker.disconnect.assert_called_once()
    worker.deleteLater.assert_called_once()

    # Verify thread disconnect & shutdown flow
    thread.disconnect.assert_called_once()
    thread.requestInterruption.assert_called_once()
    thread.quit.assert_called_once()
    thread.wait.assert_called_with(500)
    thread.deleteLater.assert_called_once()
    thread.terminate.assert_not_called()

def test_safe_shutdown_thread_not_running():
    worker = MagicMock()
    thread = MagicMock()
    thread.isRunning.return_value = False

    safe_shutdown_thread(thread, worker)

    # Verify worker still cancelled, disconnected, deleteLater called
    worker.cancel.assert_called_once()
    worker.disconnect.assert_called_once()
    worker.deleteLater.assert_called_once()

    # Verify thread disconnected and deleteLater called, but not quit/wait
    thread.disconnect.assert_called_once()
    thread.deleteLater.assert_called_once()
    thread.quit.assert_not_called()
    thread.wait.assert_not_called()

def test_safe_shutdown_thread_timeout_terminates():
    worker = MagicMock()
    thread = MagicMock()
    thread.isRunning.return_value = True
    thread.wait.return_value = False  # Simulate timeout

    safe_shutdown_thread(thread, worker, timeout_ms=100)

    # Thread quit was called, wait timed out, so terminate was called
    thread.quit.assert_called_once()
    thread.terminate.assert_called_once()
    # It waits twice: once for timeout, second after terminate
    assert thread.wait.call_count == 2

def test_safe_shutdown_thread_no_cancel_method():
    # Worker has no cancel attribute
    class DummyWorker:
        def disconnect(self):
            pass
        def deleteLater(self):
            pass

    worker = MagicMock(spec=DummyWorker)
    thread = MagicMock()
    thread.isRunning.return_value = False

    # Should run fine without AttributeError
    safe_shutdown_thread(thread, worker)
    worker.disconnect.assert_called_once()
    worker.deleteLater.assert_called_once()

@patch('PyQt6.QtCore.QThread.currentThread')
def test_safe_shutdown_thread_self_wait_guard(mock_current_thread):
    worker = MagicMock()
    thread = MagicMock()
    thread.isRunning.return_value = True
    
    # Simulate currentThread returning the same thread object
    mock_current_thread.return_value = thread

    safe_shutdown_thread(thread, worker)

    # Should not call thread.wait to avoid self-deadlock
    thread.quit.assert_called_once()
    thread.wait.assert_not_called()
    thread.terminate.assert_not_called()

def test_safe_shutdown_thread_exception_resilience():
    # Ensure that even if worker or thread throws exceptions on cancel/disconnect/deleteLater, 
    # the function completes without raising exceptions.
    worker = MagicMock()
    worker.cancel.side_effect = Exception("Cancel failure")
    worker.disconnect.side_effect = Exception("Disconnect failure")
    worker.deleteLater.side_effect = Exception("DeleteLater failure")

    thread = MagicMock()
    thread.isRunning.return_value = True
    thread.disconnect.side_effect = Exception("Disconnect thread failure")
    thread.requestInterruption.side_effect = Exception("Interruption thread failure")
    thread.deleteLater.side_effect = Exception("DeleteLater thread failure")

    # Should not raise any exceptions
    safe_shutdown_thread(thread, worker)
