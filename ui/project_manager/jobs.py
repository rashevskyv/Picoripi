"""Background jobs of the project manager: disk reads, registry writes, string counts and the card scan."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt6.QtCore import pyqtSignal

from core.project_library import index
from core.project_library.cards import read_card
from utils.logging_utils import log_debug, log_error
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


CardTarget = Tuple[str, str, Optional[Dict[str, Any]]]  # (project key, project file, cached card or None)


class CardScanJob(WorkerThread):
    """Reads the card of each project, skipping projects whose file has not changed since the cached card.

    Emits ``card_ready`` per project as soon as it has its card, so the window fills in while the scan runs.
    The new cards are written to the index at the end. Cancelling keeps what was already read.
    """

    card_ready = pyqtSignal(str, dict)
    done = pyqtSignal(int)
    failed = pyqtSignal(str)

    def __init__(self, directory: str, targets: List[CardTarget]):
        super().__init__()
        self._directory = directory
        self._targets = targets

    def run(self) -> None:
        updates: Dict[str, Dict[str, Any]] = {}
        scanned = 0
        for key, project_file, cached in self._targets:
            if self.isInterruptionRequested():
                break
            card = self._card(project_file, cached)
            if card is not cached:
                updates[key] = {"card": card}
            self.card_ready.emit(key, card)
            scanned += 1
        try:
            index.merge(self._directory, updates)
        except OSError as exc:
            log_error(f"Could not save the project index: {exc}")
            self.failed.emit(str(exc))
        log_debug(f"Project manager scanned {scanned} of {len(self._targets)} projects.")
        self.done.emit(scanned)

    @staticmethod
    def _card(project_file: str, cached: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            stat = os.stat(project_file)
        except OSError:
            return {"missing": True, "issues": ["project_file_missing"], "name": Path(project_file).parent.name}
        if cached and cached.get("mtime_ns") == stat.st_mtime_ns and cached.get("size") == stat.st_size:
            return cached
        try:
            return read_card(project_file)
        except (OSError, ValueError) as exc:
            return {"issues": ["unreadable"], "error": str(exc), "name": Path(project_file).parent.name}
