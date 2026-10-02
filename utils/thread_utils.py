"""Qt thread helpers: owner-bound single-shot timers and a shutdown that never destroys a running thread."""
import time
from typing import Optional, Any
from PyQt6.QtCore import QObject, QThread, QTimer
from utils.logging_utils import log_debug, log_warning

# Threads that did not stop in time, with their workers. Qt aborts the process
# when a running QThread is destroyed, so these stay referenced until they end.
_parked: list = []


def single_shot(msec: int, context: Any, fn) -> None:
    """``QTimer.singleShot`` that never fires after *context* is destroyed.

    PyQt6 has no ``singleShot(msec, context, slot)`` overload; a lambda passed
    to the 2-arg form outlives the widgets it captures. A child timer dies with
    its parent instead.
    """
    if not isinstance(context, QObject):
        QTimer.singleShot(msec, fn)
        return
    timer = QTimer(context)
    timer.setSingleShot(True)
    timer.timeout.connect(fn)
    timer.timeout.connect(timer.deleteLater)
    timer.start(msec)


def _attempt(action, what: str) -> None:
    try:
        action()
    except Exception as exc:
        log_debug(f"safe_shutdown_thread: {what} failed: {exc}")


def safe_shutdown_thread(thread: Optional[QThread], worker: Optional[Any] = None, timeout_ms: int = 1000) -> None:
    """Stop a QThread and its worker without ever destroying a thread that still runs.

    Order: ask the worker to cancel, ask the thread to stop, wait up to
    ``timeout_ms``, cut the signals so that no late result reaches a closed
    window. Only a stopped thread is deleted; one that did not stop is parked
    until it ends by itself (see ``wait_for_parked_threads``). A thread is
    never terminated: that leaves locks held and files half-written.
    """
    cancel = getattr(worker, 'cancel', None)
    if callable(cancel):
        _attempt(cancel, "cancel")

    stopped = True
    if thread and thread.isRunning():
        _attempt(thread.requestInterruption, "requestInterruption")
        thread.quit()
        if QThread.currentThread() == thread:
            # Waiting for oneself is a deadlock; the thread ends when this call returns.
            stopped = False
        else:
            stopped = bool(thread.wait(timeout_ms))

    for target in (worker, thread):
        if target is not None:
            _attempt(target.disconnect, "disconnect")

    if stopped:
        for target in (worker, thread):
            if target is not None:
                _attempt(target.deleteLater, "deleteLater")
        return

    log_warning(f"safe_shutdown_thread: {thread} did not stop within {timeout_ms} ms; parked until it does.")
    _park(thread, worker)


def _park(thread: QThread, worker: Optional[Any]) -> None:
    entry = (thread, worker)
    _parked.append(entry)

    def release():
        if entry in _parked:
            _parked.remove(entry)
        for target in (worker, thread):
            if target is not None:
                _attempt(target.deleteLater, "deleteLater")

    _attempt(lambda: thread.finished.connect(release), "watching a parked thread")


def wait_for_parked_threads(timeout_ms: int = 8000) -> None:
    """Give the threads that ignored a shutdown a last chance to end. Call once, when the application quits."""
    deadline = time.monotonic() + timeout_ms / 1000
    for thread, _worker in list(_parked):
        remaining = max(0, int((deadline - time.monotonic()) * 1000))
        if not thread.wait(remaining):
            log_warning(f"wait_for_parked_threads: {thread} is still running at exit.")
