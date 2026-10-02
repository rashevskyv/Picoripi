"""Run one blocking Companion request off the GUI thread, behind a progress window the user can cancel."""
from __future__ import annotations

from typing import Any, Callable, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QProgressDialog, QWidget

from core.i18n import tr
from utils.logging_utils import log_error
from utils.thread_utils import WorkerThread, safe_shutdown_thread


class CompanionCallWorker(WorkerThread):
    """Calls ``call(cancelled)`` in a thread and reports what it returned (``None`` if it raised)."""

    finished_with_result = pyqtSignal(object)

    def __init__(self, call: Callable[[Callable[[], bool]], Any]):
        super().__init__()
        self._call = call

    def run(self):
        try:
            result = self._call(self.isInterruptionRequested)
        except Exception as exc:
            log_error(f"CompanionCallWorker: the request failed: {exc}", exc_info=True)
            result = None
        self.finished_with_result.emit(result)


def run_companion_call(
    parent: Optional[QWidget],
    call: Callable[[Callable[[], bool]], Any],
    on_result: Callable[[Any], None],
    label: Optional[str] = None,
) -> CompanionCallWorker:
    """Start ``call`` in the background; ``on_result(result)`` runs on the GUI thread unless the user cancelled.

    ``call`` receives a ``cancelled()`` callable to pass on to the Companion client.
    Nobody has to hold the returned worker: it keeps itself alive until it ends.
    """
    worker = CompanionCallWorker(call)
    progress = QProgressDialog(label or tr("Contacting Companion server…"), tr("Cancel"), 0, 0, parent)
    progress.setWindowTitle(tr("Companion Sync"))
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    settled = []

    def finish(result):
        if settled:
            return
        settled.append(True)
        progress.close()
        on_result(result)

    def cancel():
        if settled:
            return
        settled.append(True)
        safe_shutdown_thread(worker, worker, timeout_ms=300)

    worker.finished_with_result.connect(finish)
    worker.finished.connect(worker.deleteLater)
    progress.canceled.connect(cancel)
    worker.start()
    progress.show()
    return worker
