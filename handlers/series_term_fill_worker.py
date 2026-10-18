"""Background fill of the series terms into the other projects of a series (D45, item 1; plan in core/translation/series_fill.py).

One project after another; progress between projects; cancel stops before the next project. The projects already
written keep their backup (each write is atomic and keeps the first copy). The open project is not in the list.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Dict, List, Tuple

from PyQt6.QtCore import pyqtSignal

from core.translation import series_fill
from utils.logging_utils import log_error
from utils.thread_utils import WorkerThread


class SeriesTermFillWorker(WorkerThread):
    """Signals: ``progress(done, total)``; ``done(results)`` where results maps each project name to its
    ``fill_project`` result, or None when cancelled."""

    progress = pyqtSignal(int, int)
    done = pyqtSignal(object)

    def __init__(self, entries: List[Tuple[str, str]], projects: Dict[str, Path], parent=None):
        super().__init__(parent)
        # copies: the window may change its glossary while this runs
        self._entries = list(entries)
        self._projects = dict(projects)
        self._cancel = threading.Event()

    def cancel(self) -> None:
        """Stop before the next project. A project being written finishes its atomic write."""
        self._cancel.set()

    def run(self) -> None:
        results: Dict[str, dict] = {}
        names = sorted(self._projects)
        for index, name in enumerate(names):
            if self._cancel.is_set():
                self.done.emit(None)
                return
            self.progress.emit(index, len(names))
            try:
                results[name] = series_fill.fill_project(self._projects[name].parent, self._entries, self._cancel.is_set)
            except Exception as error:  # one broken project does not stop the others
                log_error(f"Series term fill failed for {name}: {error}", exc_info=True)
                results[name] = {"status": "failed", "error": str(error)}
            if results[name].get("status") == "cancelled":
                self.done.emit(None)
                return
        self.progress.emit(len(names), len(names))
        self.done.emit(results)
