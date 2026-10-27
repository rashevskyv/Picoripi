"""Launch custom scripts away from the UI thread."""
import os
import subprocess
from itertools import count
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from utils.thread_utils import WorkerThread, safe_shutdown_thread
from core.i18n import tr

_worker_ids = count(1)


class ScriptLaunchWorker(WorkerThread):
    """Validate and start one configured script on a worker thread."""

    result = pyqtSignal(int, str, str, bool)

    def __init__(self, name: str, script_path: str):
        super().__init__()
        self.name = name
        self.script_path = script_path
        self.worker_id = next(_worker_ids)

    def run(self):
        path = Path(self.script_path)
        missing_script = False
        try:
            if not path.is_file():
                missing_script = True
                raise FileNotFoundError(tr("Configured script path does not exist or is not a file: {}" ).format(self.script_path))
            resolved_path = path.resolve()
            if self.isInterruptionRequested():
                return
            if os.name == "nt":
                # Doubled outer quotes survive cmd's /k quote stripping, so "&" and spaces stay in the path.
                subprocess.Popen(
                    f'cmd.exe /k ""{resolved_path}""',
                    cwd=str(path.parent.resolve()),
                    creationflags=0x00000010,
                )
            else:
                subprocess.Popen([str(resolved_path)], cwd=str(path.parent.resolve()))
            self.result.emit(self.worker_id, self.name, "", True)
        except Exception as exc:
            detail = tr("Configured script path does not exist or is not a file: {}" ).format(self.script_path) \
                if missing_script else str(exc)
            self.result.emit(
                self.worker_id, tr("Run External Script Error"),
                tr("Failed to start tool '{}':\n{}").format(self.name, detail), False,
            )


class ScriptLaunchController(QObject):
    """Own script launch workers and deliver their results to the main window."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self._workers = {}
        self._closing = False

    def launch(self, name: str, script_path: str) -> None:
        if self._closing:
            return
        worker = ScriptLaunchWorker(name, script_path)
        worker.result.connect(self._on_result)
        worker.finished.connect(worker.deleteLater)
        self._workers[worker.worker_id] = worker
        worker.start()

    @pyqtSlot(int, str, str, bool)
    def _on_result(self, worker_id, title, message, succeeded):
        self._workers.pop(worker_id, None)
        if self._closing:
            return
        if succeeded:
            self.main_window.statusBar.showMessage(tr("Started tool: {}" ).format(title), 3000)
        else:
            self.main_window.show_message(title, message, "error")

    def shutdown(self) -> None:
        self._closing = True
        for worker in tuple(self._workers.values()):
            safe_shutdown_thread(worker, worker, timeout_ms=1000)
        self._workers.clear()
