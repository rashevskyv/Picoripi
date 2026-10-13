"""The window's side of the scan process: starts ``core.project_library.scan_child``, reads its JSON lines, stops it.

It uses ``QProcess`` signals on the window's own thread, so the window never waits for the child and no worker thread
shares the child's work. Each line of the child's output becomes one ``event`` signal; each line of its stderr (plugin
prints, the child's warnings) goes to the app log as a warning. Cancel asks the child to stop between projects; the
child that has not ended after ``CANCEL_GRACE_MS`` is killed. Closing the window kills it at once. What the child already
wrote to the index stays, and the next scan picks up from there.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, pyqtSignal

from utils.constants import plugins_root
from utils.logging_utils import log_error, log_warning

SCAN_MODULE = "core.project_library.scan_child"
STOP_WAIT_MS = 1500  # the close of the window waits at most this long for the child to end
CANCEL_GRACE_MS = 2000  # after a cancel the child has this long to stop between projects, then it is killed
ERROR_LINE_MAX = 500  # a stderr line is logged up to this many characters


class ScanProcess(QObject):
    """One scan at a time. ``command`` replaces the child command (tests and tools); the default runs the scan module."""

    event_received = pyqtSignal(dict)  # one protocol event (see core/project_library/scan.py)
    stopped = pyqtSignal(bool)  # True when the child reported its last event, False when it was cancelled or failed

    def __init__(self, parent: Optional[QObject] = None, command: Optional[Sequence[str]] = None):
        super().__init__(parent)
        self._command: List[str] = list(command) if command else [sys.executable, "-m", SCAN_MODULE]
        self._process: Optional[QProcess] = None
        self._buffer = b""
        self._error_buffer = b""
        self._done = False
        self._cancelled = False
        self._errors: List[str] = []
        self._grace = QTimer(self)
        self._grace.setSingleShot(True)
        self._grace.timeout.connect(self._kill_after_grace)

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
        self._error_buffer = b""
        self._done = False
        self._cancelled = False
        self._errors = []
        payload = {"data_dir": str(data_dir), "projects": [[key, path] for key, path in projects]}
        process.start()
        # The write channel stays open: a line "cancel" on it is how the window stops the child.
        process.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        return True

    def cancel(self) -> None:
        """Ask the child to stop between projects. It is killed if it has not ended after ``CANCEL_GRACE_MS``.
        ``stopped`` is emitted with False when the child has ended."""
        process = self._process
        if process is None or self._cancelled:
            return
        self._cancelled = True
        process.write(b"cancel\n")
        self._grace.start(CANCEL_GRACE_MS)

    def shutdown(self, wait_ms: int = STOP_WAIT_MS) -> None:
        """Kill the child at once and wait a little for it. Called when the window closes."""
        process = self._process
        if process is None:
            return
        self._grace.stop()
        self._cancelled = True
        process.kill()
        process.waitForFinished(wait_ms)
        self._process = None
        process.deleteLater()

    def _kill_after_grace(self) -> None:
        """The fallback of ``cancel``: the child did not stop between projects in time."""
        if self._process is not None:
            log_warning("Project scan did not stop in time; the scan process is killed.")
            self._process.kill()

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
        self._error_buffer += bytes(self._process.readAllStandardError())
        while b"\n" in self._error_buffer:
            line, self._error_buffer = self._error_buffer.split(b"\n", 1)
            self._log_error_line(line)

    def _log_error_line(self, line: bytes) -> None:
        text = line.decode("utf-8", errors="replace").strip()
        if not text:
            return
        self._errors.append(text)
        del self._errors[:-20]  # keep the last lines for the message of a failed scan
        log_warning(f"Project scan: {text[:ERROR_LINE_MAX]}")

    def _on_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        if self._process is None:
            return
        self._grace.stop()
        self._read_output()
        if self._buffer.strip():
            self._emit_line(self._buffer)
            self._buffer = b""
        self._read_errors()
        if self._error_buffer.strip():
            self._log_error_line(self._error_buffer)
            self._error_buffer = b""
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
