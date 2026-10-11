"""Progress page: count the project in a worker, keep the daily history, open the page; feed the room's page."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices

from core import progress_stats
from core.i18n import tr
from utils.atomic_io import atomic_write_text
from utils.logging_utils import log_debug
from utils.thread_utils import WorkerThread

PAGE_NAME = "progress.html"


class ProgressWorker(WorkerThread):
    """Counts a snapshot of the project and records today in its history; emits ``(summary, history)``."""

    done = pyqtSignal(dict, dict)

    def __init__(self, data, edited_file_data, edited_data, block_names, project: str, project_dir: Optional[Path],
                 page: Optional[Path] = None):
        super().__init__()
        self.args = (data, edited_file_data, edited_data, block_names, project)
        self.project_dir = project_dir
        self.page = page

    def run(self) -> None:
        try:
            summary = progress_stats.summarize(*self.args)
            if self.isInterruptionRequested():
                return
            history = progress_stats.record_day(self.project_dir, summary)
            if self.page is not None:
                atomic_write_text(self.page, progress_stats.render_html(summary, history))
            self.done.emit(summary, history)
        except Exception as exc:
            log_debug(f"ProgressWorker: {exc}")


def project_dir_of(mw: Any) -> Optional[Path]:
    value = getattr(getattr(mw, "project_manager", None), "project_dir", None)
    return Path(value) if value else None


def start_progress_worker(mw: Any, on_done: Callable[[dict, dict], None], page: Optional[Path] = None) -> Optional[ProgressWorker]:
    """Snapshot the open project on the UI thread (shallow copies only) and count it in a worker."""
    store = getattr(mw, "data_store", None)
    if store is None or not getattr(store, "data", None):
        return None
    project = getattr(getattr(getattr(mw, "project_manager", None), "project", None), "name", "") or ""
    worker = ProgressWorker(list(store.data), list(getattr(store, "edited_file_data", None) or []),
                            dict(getattr(store, "edited_data", None) or {}),
                            dict(getattr(store, "block_names", None) or {}), project, project_dir_of(mw), page)
    worker.done.connect(on_done)
    worker.start()
    return worker


def open_progress_page(mw: Any) -> None:
    """Tools → Progress: count, write ``progress.html`` in the project folder (with the room's board) and open it."""
    if getattr(getattr(mw, "data_store", None), "data", None) in (None, []):
        bar = getattr(mw, "statusBar", None)
        if bar is not None:
            bar.showMessage(tr('Open a project first: the progress page counts the open project.'), 5000)
        return
    collab = getattr(mw, "collab_handler", None)
    if collab is not None and collab.client is not None:
        # In a room the room serves the page, with the team board; send a fresh summary, then open it.
        url = f"{collab.client.base_url}/stats"

        def show_room(summary: dict, history: dict) -> None:
            if collab.client is not None:
                collab.client.set_summary({**summary, "history": history})
            QDesktopServices.openUrl(QUrl(url))
        mw._progress_worker = start_progress_worker(mw, show_room)
        return
    folder = project_dir_of(mw)
    if folder is None:
        return
    page = folder / PAGE_NAME
    mw._progress_worker = start_progress_worker(
        mw, lambda _summary, _history: QDesktopServices.openUrl(QUrl.fromLocalFile(str(page))), page)
