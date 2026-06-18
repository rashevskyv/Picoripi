from typing import Optional, Any
from PyQt6.QtCore import QThread
from utils.logging_utils import log_debug, log_warning, log_error

def safe_shutdown_thread(thread: Optional[QThread], worker: Optional[Any] = None, timeout_ms: int = 1000) -> None:
    """
    Safely shuts down a QThread and its associated worker.
    Failsafe disconnects all signals, cancels the worker if it supports cancel,
    requests interruption, quits the thread, and waits for completion.
    """
    if worker:
        # 1. Call cancel if worker has it
        if hasattr(worker, 'cancel') and callable(worker.cancel):
            try:
                log_debug(f"safe_shutdown_thread: Requesting cancellation on worker {worker}")
                worker.cancel()
            except Exception as e:
                log_debug(f"safe_shutdown_thread: Failed to cancel worker: {e}")
        
        # 2. Failsafe disconnect signals to prevent crashes during GUI shutdown
        try:
            worker.disconnect()
            log_debug(f"safe_shutdown_thread: Disconnected signals for worker {worker}")
        except Exception:
            pass

        # 3. Schedule worker deletion
        try:
            worker.deleteLater()
            log_debug(f"safe_shutdown_thread: Called deleteLater on worker {worker}")
        except Exception:
            pass

    if thread:
        # Failsafe disconnect thread signals
        try:
            thread.disconnect()
            log_debug(f"safe_shutdown_thread: Disconnected signals for thread {thread}")
        except Exception:
            pass

        if thread.isRunning():
            try:
                thread.requestInterruption()
                log_debug(f"safe_shutdown_thread: Requested interruption on thread {thread}")
            except Exception as e:
                log_debug(f"safe_shutdown_thread: Failed to request interruption: {e}")

            thread.quit()
            log_debug(f"safe_shutdown_thread: Sent quit signal to thread {thread}")

            # Prevent self-waiting (deadlock) if called from within the thread itself
            from PyQt6.QtCore import QThread
            if QThread.currentThread() == thread:
                log_warning("safe_shutdown_thread: safe_shutdown_thread called from within the target thread itself. Skipping wait.")
            else:
                if not thread.wait(timeout_ms):
                    log_warning(f"safe_shutdown_thread: Thread {thread} did not stop within {timeout_ms}ms, terminating.")
                    try:
                        thread.terminate()
                        thread.wait()
                    except Exception as e:
                        log_error(f"safe_shutdown_thread: Error terminating thread: {e}")
                else:
                    log_debug(f"safe_shutdown_thread: Thread {thread} joined successfully.")

        # 4. Schedule thread deletion
        try:
            thread.deleteLater()
            log_debug(f"safe_shutdown_thread: Called deleteLater on thread {thread}")
        except Exception:
            pass
