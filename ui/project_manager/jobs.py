"""Background jobs of the project manager: registry reads and writes, file searches and icon files.

The scan of the projects (cards, icons, string counts) is not here: it runs in a child process, see ``scan_process.py``.
"""
from __future__ import annotations

from typing import Any, Callable

from PyQt6.QtCore import pyqtSignal

from utils.logging_utils import log_error
from utils.thread_utils import WorkerThread


class BackgroundJob(WorkerThread):
    """Runs one function on a worker thread and reports its result, or its error message."""

    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, function: Callable[..., Any], *args: Any):
        super().__init__()
        self._function = function
        self._args = args

    def run(self) -> None:
        try:
            result = self._function(*self._args)
        except Exception as exc:  # reported to the window; a worker must not raise
            log_error(f"Project manager job failed: {exc}", exc_info=True)
            self.failed.emit(str(exc))
            return
        self.done.emit(result)
