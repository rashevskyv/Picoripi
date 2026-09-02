"""TextOperationHandler composition."""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING
from PyQt6.QtWidgets import QProgressDialog
from PyQt6.QtCore import QTimer
from handlers.base_handler import BaseHandler
from handlers.async_issue_scanner import AsyncIssueScanner
from handlers.autofix_worker import AutofixWorker
from handlers.text_operation.scan_mixin import ScanMixin
from handlers.text_operation.preview_mixin import PreviewMixin, PREVIEW_UPDATE_DELAY
from handlers.text_operation.edit_mixin import EditMixin
from handlers.text_operation.autofix_mixin import AutofixMixin

if TYPE_CHECKING:
    from core.context import ProjectContext
    from core.data_state_processor import DataStateProcessor
    from ui.ui_updater import UIUpdater

__all__ = ["TextOperationHandler", "PREVIEW_UPDATE_DELAY"]


class TextOperationHandler(
    ScanMixin,
    PreviewMixin,
    EditMixin,
    AutofixMixin,
    BaseHandler,
):
    """Handler for text operation operations."""

    def __init__(self, context: ProjectContext, data_processor: DataStateProcessor, ui_updater: UIUpdater):
        """Initialize a new instance."""
        super().__init__(context, data_processor, ui_updater)
        self._active_autofix_worker: Optional[AutofixWorker] = None
        self._active_autofix_progress: Optional[QProgressDialog] = None

        self.preview_update_timer = QTimer()
        self.preview_update_timer.setSingleShot(True)
        self.preview_update_timer.timeout.connect(self._on_preview_update_timer_timeout)
        self._debounce_block_idx = -1
        self._debounce_string_idx = -1
        # current_scanner is an AsyncIssueScanner (QRunnable) — kept around so
        # we can cooperatively cancel it when a newer scan supersedes it.
        self.current_scanner_thread: Optional[AsyncIssueScanner] = None
