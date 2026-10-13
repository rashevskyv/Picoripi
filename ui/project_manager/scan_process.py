"""The window's side of the scan process: starts ``core.project_library.scan_child``, reads its JSON lines, stops it.

It uses ``QProcess`` signals on the window's own thread, so the window never waits for the child and no worker thread
shares the child's work. Each line of the child's output becomes one ``event`` signal. Stopping the scan kills the child;
what it already wrote to the index stays, and the next scan picks up from there.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, pyqtSignal

from utils.constants import plugins_root
from utils.logging_utils import log_error, log_warning

SCAN_MODULE = "core.project_library.scan_child"
STOP_WAIT_MS = 1500  # the close of the window waits at most this long for the child to end


class ScanProcess(QObject):
    """One scan at a time. ``command`` replaces the child command (tests and tools); the default runs the scan module."""

    event_received = pyqtSignal(dict)  # one protocol event (see core/project_library/scan.py)
    stopped = pyqtSignal(bool)  # True when the child reported its last event, False when it was cancelled or failed

    def __init__(self, parent: Optional[QObject] = None, command: Optional[Sequence[str]] = None):
        super().__init__(parent)
        self._command: List[str] = list(command) if command else [sys.executable, "-m", SCAN_MODULE]
        self._process: Optional[QProcess] = None
        self._buffer = b""
        self._done = False
        self._cancelled = False
        self._errors: List[str] = []

    def running(self) -> bool:
        return self._process is not None

    def start(self, data_dir: str, projects: Sequence[Tuple[str, str]]) -> bool:
        """Start a scan of ``projects`` (``(key, project file)``). False when one is already running."""
        if self.running():
            return False
        process = QProcess(self)
        process.setProgram(self._command[0])
        process.setArguments(self._command[1:])
        process.setWorkingDirectory(str(plugins_root().parent))  # the folder that holds the packages
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PICORIPI_SCAN_CHILD", "1")
        environment.insert("PICORIPI_HOME", str(data_dir))
        environment.insert("PYTHONIOENCODING", "utf-8")
        process.setProcessEnvironment(environment)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        process.readyReadStandardOutput.connect(self._read_output)
        process.readyReadStandardError.connect(self._read_errors)
        process.finished.connect(self._on_finished)
        process.errorOccurred.connect(self._on_error)
        self._process = process
        self._buffer = b""
        self._done = False
        self._cancelled = False
        self._errors = []
        payload = {"data_dir": str(data_dir), "projects": [[key, path] for key, path in projects]}
        process.start()
        process.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        process.closeWriteChannel()
        return True

    def cancel(self) -> None:
        """Stop the scan now. ``stopped`` is emitted with False when the child has ended."""
        if self._process is not None:
            self._cancelled = True
            self._process.kill()

    def shutdown(self, wait_ms: int = STOP_WAIT_MS) -> None:
        """Kill the child at once and wait a little for it. Called when the window closes."""
        process = self._process
        if process is None:
            return
        self._cancelled = True
        process.kill()
        process.waitForFinished(wait_ms)
        self._process = None
        process.deleteLater()

    # ----- child output -----
    def _read_output(self) -> None:
        if self._process is None:
            return
        self._buffer += bytes(self._process.readAllStandardOutput())
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            self._emit_line(line)

    def _emit_line(self, line: bytes) -> None:
        text = line.decode("utf-8", errors="replace").strip()
        if not text:
            return
        try:
            event: Dict[str, Any] = json.loads(text)
        except ValueError:
            log_warning(f"Project scan: a line of the scan process is not JSON: {text[:120]}")
            return
        if event.get("event") == "done":
            self._done = True
        self.event_received.emit(event)

    def _read_errors(self) -> None:
        if self._process is None:
            return
        text = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        self._errors.extend(line for line in text.splitlines() if line.strip())
        del self._errors[:-20]  # keep the last lines only

    def _on_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        if self._process is None:
            return
        self._read_output()
        if self._buffer.strip():
            self._emit_line(self._buffer)
            self._buffer = b""
        process = self._process
        self._process = None
        finished_ok = self._done and not self._cancelled and exit_code == 0
        if not finished_ok and not self._cancelled and self._errors:
            log_error(f"Project scan process ended with code {exit_code}: {self._errors[-1][:300]}")
        process.deleteLater()
        self.stopped.emit(finished_ok)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart and self._process is not None:
            log_error("Project scan process did not start.")
            process = self._process
            self._process = None
            process.deleteLater()
            self.stopped.emit(False)
