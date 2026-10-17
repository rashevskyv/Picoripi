"""Background rebuild of a translation memory with the context its rows were made under (core/translation/memory_context.py).

The plan runs on this thread and writes nothing until it is complete and not cancelled: a cancelled run leaves the
memory file as it was. The context of a repeated text comes from ``context_for`` (the prompt composer's saved_context),
which the save and restore paths call too; the plugin hooks behind it are not audited for thread safety (see D44).
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from PyQt6.QtCore import QThread, pyqtSignal

from core.translation import memory_context as mc
from utils.logging_utils import log_error


class MemoryContextWorker(QThread):
    """Plans and writes the rebuild. Signals: ``progress(done, total)``; ``done(result)`` (None when cancelled);
    ``failed(text)``."""

    progress = pyqtSignal(int, int)
    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(
        self,
        path: Path,
        memory: Dict[str, List[Dict[str, Any]]],
        data: Sequence[Any],
        block_prefixes: Sequence[str],
        saved: Dict[str, str],
        context_for: Callable[[mc.SavedPlace], Optional[Dict[str, str]]],
        tag_fields_for: Callable[[str], Dict[str, Any]],
        parent: Any = None,
    ):
        super().__init__(parent)
        # the inputs are copies: the interface may change its own memory while this runs
        self._path = Path(path)
        self._memory = memory
        self._data = data
        self._block_prefixes = list(block_prefixes)
        self._saved = saved
        self._context_for = context_for
        self._tag_fields_for = tag_fields_for
        self._cancel = threading.Event()

    def cancel(self) -> None:
        """Stop at the next place. Nothing is written after a cancel."""
        self._cancel.set()

    def run(self) -> None:
        try:
            places = mc.places_of(self._data, self._block_prefixes, self._saved)
            repeats = mc.repeats_of(mc.counts_of(self._data))
            result = mc.plan_rebuild(
                self._memory, places, repeats, self._context_for, self._tag_fields_for,
                should_cancel=self._cancel.is_set,
                report=lambda done, total: self.progress.emit(done, total),
            )
            if result.cancelled:
                self.done.emit(None)
                return
            mc.write_rebuilt(self._path, result.memory)
            self.done.emit(result)
        except Exception as error:  # the memory file is only replaced by the last step, so it is intact here
            log_error(f"Translation memory rebuild failed: {error}", exc_info=True)
            self.failed.emit(str(error))
