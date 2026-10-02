"""safe_shutdown_thread: cancel, stop, wait; delete what stopped and park what did not (WP6 6.2)."""
from unittest.mock import MagicMock, patch

import pytest

from utils import thread_utils
from utils.thread_utils import safe_shutdown_thread, wait_for_parked_threads


@pytest.fixture(autouse=True)
def no_parked_threads():
    thread_utils._parked.clear()
    yield
    thread_utils._parked.clear()


def test_a_thread_that_stops_is_cancelled_waited_for_disconnected_and_deleted():
    worker = MagicMock()
    thread = MagicMock()
    thread.isRunning.return_value = True
    thread.wait.return_value = True
    order = MagicMock()
    order.attach_mock(worker.cancel, "cancel")
    order.attach_mock(thread.wait, "wait")
    order.attach_mock(worker.disconnect, "disconnect")

    safe_shutdown_thread(thread, worker, timeout_ms=500)

    assert [call[0] for call in order.mock_calls] == ["cancel", "wait", "disconnect"]
    thread.requestInterruption.assert_called_once()
    thread.quit.assert_called_once()
    thread.wait.assert_called_with(500)
    thread.disconnect.assert_called_once()
    worker.deleteLater.assert_called_once()
    thread.deleteLater.assert_called_once()
    thread.terminate.assert_not_called()
    assert thread_utils._parked == []


def test_a_thread_that_is_not_running_is_only_cleaned_up():
    worker = MagicMock()
    thread = MagicMock()
    thread.isRunning.return_value = False

    safe_shutdown_thread(thread, worker)

    worker.cancel.assert_called_once()
    worker.disconnect.assert_called_once()
    worker.deleteLater.assert_called_once()
    thread.disconnect.assert_called_once()
    thread.deleteLater.assert_called_once()
    thread.quit.assert_not_called()
    thread.wait.assert_not_called()


def test_a_thread_that_does_not_stop_is_parked_and_never_deleted_or_terminated():
    worker = MagicMock()
    thread = MagicMock()
    thread.isRunning.return_value = True
    thread.wait.return_value = False  # the wait timed out

    safe_shutdown_thread(thread, worker, timeout_ms=100)

    thread.quit.assert_called_once()
    thread.terminate.assert_not_called()
    thread.deleteLater.assert_not_called()      # Qt aborts the process when a running thread is destroyed
    worker.deleteLater.assert_not_called()
    worker.disconnect.assert_called_once()      # but its late result must not reach a closed window
    assert thread_utils._parked == [(thread, worker)]

    # ... and it is released when it ends at last
    release = thread.finished.connect.call_args.args[0]
    release()
    assert thread_utils._parked == []
    thread.deleteLater.assert_called_once()
    worker.deleteLater.assert_called_once()


def test_parked_threads_get_a_last_wait_when_the_application_quits():
    thread = MagicMock()
    thread.isRunning.return_value = True
    thread.wait.return_value = False
    safe_shutdown_thread(thread, None, timeout_ms=100)
    thread.wait.reset_mock()

    wait_for_parked_threads(timeout_ms=1000)

    thread.wait.assert_called_once()
    assert 0 < thread.wait.call_args.args[0] <= 1000


def test_a_worker_without_cancel_is_fine():
    class DummyWorker:
        def disconnect(self):
            pass

        def deleteLater(self):
            pass

    worker = MagicMock(spec=DummyWorker)
    thread = MagicMock()
    thread.isRunning.return_value = False

    safe_shutdown_thread(thread, worker)

    worker.disconnect.assert_called_once()
    worker.deleteLater.assert_called_once()


@patch('utils.thread_utils.QThread.currentThread')
def test_a_thread_never_waits_for_itself(mock_current_thread):
    worker = MagicMock()
    thread = MagicMock()
    thread.isRunning.return_value = True
    mock_current_thread.return_value = thread

    safe_shutdown_thread(thread, worker)

    thread.quit.assert_called_once()
    thread.wait.assert_not_called()
    thread.terminate.assert_not_called()
    thread.deleteLater.assert_not_called()      # it is still running: this very call is inside it


def test_failures_of_the_worker_or_the_thread_do_not_escape():
    worker = MagicMock()
    worker.cancel.side_effect = Exception("Cancel failure")
    worker.disconnect.side_effect = Exception("Disconnect failure")
    worker.deleteLater.side_effect = Exception("DeleteLater failure")

    thread = MagicMock()
    thread.isRunning.return_value = True
    thread.disconnect.side_effect = Exception("Disconnect thread failure")
    thread.requestInterruption.side_effect = Exception("Interruption thread failure")
    thread.deleteLater.side_effect = Exception("DeleteLater thread failure")

    safe_shutdown_thread(thread, worker)
