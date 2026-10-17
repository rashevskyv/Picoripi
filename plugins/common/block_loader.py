"""Plugin files read off the UI thread, answered from memory on it.

A hook the UI calls while it paints, selects a string or validates one must not open a file. ``ReadThrough.get``
answers such a call from its memory. On a miss, on the UI thread, it starts one worker for the key and returns the
caller's default; the worker stores its result on the UI thread when it ends, and ``on_ready(key)`` runs there, so the
owner can rescan the block. Off the UI thread, and headless (tests, scripts), the read runs inline.

A read that raises stores ``None`` and is logged: a broken file is not read again and again.
``clear`` drops the values and stops the running reads when the project state is reset.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable, Dict, Hashable, Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from utils import app_mode
from utils.logging_utils import log_debug
from utils.thread_utils import WorkerThread, safe_shutdown_thread

STOP_MS = 1000     # how long a clear waits for a running read before it parks the thread


def _guarded(label: str, key: Hashable, read: Callable[[], Any]) -> Any:
    try:
        return read()
    except Exception as error:  # noqa: BLE001 - a file that cannot be read keeps the owner's fallback
        log_debug(f"{label}: read of {key} failed: {error!r}")
        return None


class _Reader(WorkerThread):
    """One read off the UI thread. ``done`` carries (key, generation, value) back to the UI thread."""

    done = pyqtSignal(object, int, object)

    def __init__(self, label: str, key: Hashable, generation: int, read: Callable[[], Any]):
        super().__init__()
        self._label = label
        self._key = key
        self._generation = generation
        self._read = read

    def run(self) -> None:
        value = _guarded(self._label, self._key, self._read)
        if not self.isInterruptionRequested():
            self.done.emit(self._key, self._generation, value)


class ReadThrough(QObject):
    """The values of one plugin's file reads, by key. ``label`` names the reads in the log."""

    def __init__(self, label: str, on_ready: Optional[Callable[[Any], None]] = None):
        super().__init__()
        self._label = label
        self._on_ready = on_ready
        self._values: Dict[Hashable, Any] = {}
        self._readers: Dict[Hashable, _Reader] = {}
        self._generation = 0

    def get(self, key: Hashable, read: Callable[[], Any], default: Any = None) -> Any:
        """The value of ``key`` from memory. A miss on the UI thread starts its read and returns ``default``."""
        if key in self._values:
            return self._values[key]
        if app_mode.headless or threading.current_thread() is not threading.main_thread():
            value = _guarded(self._label, key, read)
            self._values[key] = value
            return value
        if key not in self._readers:
            reader = _Reader(self._label, key, self._generation, read)
            reader.done.connect(self._arrived)
            self._readers[key] = reader
            reader.start()
        return default

    @pyqtSlot(object, int, object)
    def _arrived(self, key: Hashable, generation: int, value: Any) -> None:
        if generation != self._generation:     # the project this read was for is gone
            return
        self._readers.pop(key, None)
        self._values[key] = value
        if self._on_ready is not None:
            self._on_ready(key)

    def clear(self) -> None:
        """Drop the values and stop the running reads (UI thread, when the project state is reset)."""
        self._generation += 1
        readers = list(self._readers.values())
        self._readers.clear()
        self._values.clear()
        for reader in readers:
            safe_shutdown_thread(reader, None, STOP_MS)


def source_of(mw: Any, block_idx: int) -> Optional[Tuple[str, Path]]:
    """``(relative path, absolute path)`` of a block's source file, from the open project (no disk access)."""
    try:
        pm = getattr(mw, "project_manager", None)
        block_map = getattr(mw, "block_to_project_file_map", None) or {}
        index = block_map.get(block_idx, block_idx)
        blocks = pm.project.blocks
        if not isinstance(index, int) or not 0 <= index < len(blocks):
            return None
        block = blocks[index]
        return str(block.source_file).replace("\\", "/"), Path(pm.get_absolute_path(block.source_file))
    except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
        log_debug(f"block_loader: no file behind block {block_idx}: {error}")
        return None


def rescan_block(mw: Any, block_idx: int) -> None:
    """UI thread: a read of this block ended; the host runs the block's problem scan again (no-op without a host)."""
    scanner = getattr(mw, "issue_scan_handler", None)
    if scanner is not None:
        scanner.rescan_issues_for_single_block(block_idx, show_message_on_completion=False)


__all__ = ["ReadThrough", "rescan_block", "source_of"]
