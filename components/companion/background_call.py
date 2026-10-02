"""Run one blocking Companion request off the GUI thread, behind a progress window the user can cancel."""
from __future__ import annotations

from typing import Any, Callable, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QProgressDialog, QWidget

from core.i18n import tr
from utils.logging_utils import log_error
from utils.thread_utils import safe_shutdown_thread

# Workers that are running: a QThread must stay referenced until Qt says it has finished.
_running: set = set()


class CompanionCallWorker(QThread):
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
        _running.discard(worker)        # safe_shutdown_thread keeps it alive from here on
        safe_shutdown_thread(worker, worker, timeout_ms=300)

    def release():
        _running.discard(worker)
        worker.deleteLater()

    _running.add(worker)
    worker.finished_with_result.connect(finish)
    worker.finished.connect(release)
    progress.canceled.connect(cancel)
    worker.start()
    progress.show()
    return worker
