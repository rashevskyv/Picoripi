"""Visual synchronization progress and status dialog for Picoripi Companion."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from components.companion.conflict_dialog import CompanionConflictDialog
from core.companion_sync import (
    CompanionSyncClient,
    CompanionSyncWorker,
    ConflictRecord,
    MergeResult,
    apply_conflict_resolutions,
)
from core.glossary.models import GlossaryEntry, GlossaryOccurrence
from core.i18n import tr
from utils.logging_utils import log_debug, log_info
from utils.thread_utils import safe_shutdown_thread


class CompanionSyncDialog(QDialog):
    """Synchronization window showing progress, diff status, and collision resolution."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        client: Optional[CompanionSyncClient] = None,
        project_name: str = "DefaultProject",
        glossary_path: Optional[Path] = None,
        entries: Optional[Sequence[GlossaryEntry]] = None,
        occurrence_map: Optional[Dict[str, List[GlossaryOccurrence]]] = None,
        reference_data: Optional[Dict[Tuple[int, int], str]] = None,
        auto_close_ms: int = 1200,
        auto_start: bool = True,
        is_closing: bool = False,
    ):
        super().__init__(parent)
        self.client = client
        self.project_name = project_name
        self.glossary_path = glossary_path
        self.entries = entries
        self.occurrence_map = occurrence_map
        self.reference_data = reference_data
        self.is_closing = is_closing
        self.auto_close_ms = 800 if (is_closing and auto_close_ms == 1200) else auto_close_ms
        self.auto_start = auto_start

        self.was_successful: bool = False
        self.terms_pulled: int = 0
        self.terms_pushed: int = 0
        self.message: str = ""

        self._worker: Optional[CompanionSyncWorker] = None
        self._close_timer: Optional[QTimer] = None

        if self.is_closing:
            self.setWindowTitle(tr("Closing Picoripi — Synchronizing Glossary…"))
        else:
            self.setWindowTitle(tr("Companion Synchronization"))
        self.setFixedSize(480, 200)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        self._setup_ui()


    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        # Header with cloud icon
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        icon_label = QLabel("☁", self)
        icon_label.setStyleSheet("font-size: 32px; color: #6366f1;")
        header_layout.addWidget(icon_label)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_label = QLabel(tr("Companion Synchronization"), self)
        title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #1e293b;")
        title_col.addWidget(title_label)

        if self.is_closing:
            self._subtitle_label = QLabel(
                tr("Synchronizing local glossary changes with Companion server before exit…"), self
            )
        else:
            self._subtitle_label = QLabel(
                tr("Project: {name}").format(name=self.project_name), self
            )
        self._subtitle_label.setStyleSheet("font-size: 12px; color: #64748b;")
        title_col.addWidget(self._subtitle_label)

        header_layout.addLayout(title_col)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Progress bar
        self._progress_bar = QProgressBar(self)
        self._progress_bar.setFixedHeight(10)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setRange(0, 0)  # Indeterminate pulse by default
        self._progress_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #e2e8f0; border-radius: 5px; background-color: #f1f5f9; }"
            "QProgressBar::chunk { background-color: #6366f1; border-radius: 4px; }"
        )
        layout.addWidget(self._progress_bar)

        # Status text
        self._status_label = QLabel(tr("Connecting to Companion server…"), self)
        self._status_label.setStyleSheet("font-size: 12px; color: #334155;")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        layout.addStretch()

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        skip_label = tr("Skip & Close") if self.is_closing else tr("Skip & Work Offline")
        self._skip_button = QPushButton(skip_label, self)
        self._skip_button.clicked.connect(self._on_skip_clicked)
        btn_layout.addWidget(self._skip_button)


        self._retry_button = QPushButton(tr("Retry"), self)
        self._retry_button.clicked.connect(self.start_sync)
        self._retry_button.setVisible(False)
        btn_layout.addWidget(self._retry_button)

        self._close_button = QPushButton(tr("Close"), self)
        self._close_button.clicked.connect(self.accept)
        self._close_button.setVisible(False)
        btn_layout.addWidget(self._close_button)

        layout.addLayout(btn_layout)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.auto_start and self._worker is None and not self.was_successful:
            QTimer.singleShot(50, self.start_sync)

    def start_sync(self) -> None:
        """Launch the background synchronization worker."""
        if not self.client or not self.client.is_configured:
            self._on_sync_finished(
                False, tr("Companion server URL or API token is not configured."), 0, 0
            )
            return

        self._status_label.setText(tr("Connecting to Companion server…"))
        self._status_label.setStyleSheet("font-size: 12px; color: #334155;")
        self._progress_bar.setRange(0, 0)
        self._retry_button.setVisible(False)
        self._close_button.setVisible(False)
        self._skip_button.setVisible(True)
        self._skip_button.setText(tr("Skip & Work Offline"))

        worker = CompanionSyncWorker(
            client=self.client,
            project_name=self.project_name,
            glossary_path=self.glossary_path,
            entries=self.entries,
            occurrence_map=self.occurrence_map,
            reference_data=self.reference_data,
        )
        self._worker = worker
        worker.progress_status.connect(self._on_progress_status)
        worker.conflicts_detected.connect(self._on_conflicts_detected)
        worker.finished_with_result.connect(self._on_sync_finished)
        worker.start()

    def _on_progress_status(self, text: str) -> None:
        self._status_label.setText(text)

    def _on_conflicts_detected(self, conflicts: List[ConflictRecord], merge_result: MergeResult) -> None:
        log_info(f"CompanionSyncDialog: {len(conflicts)} conflict(s) detected. Opening resolver.")
        self._status_label.setText(
            tr("Resolving {count} collision(s) with Companion…").format(count=len(conflicts))
        )
        conflict_dialog = CompanionConflictDialog(conflicts, self)
        res_code = conflict_dialog.exec()
        if res_code == QDialog.DialogCode.Accepted:
            resolutions = conflict_dialog.get_resolutions()
            updated_merge = apply_conflict_resolutions(merge_result, resolutions)
            ok, msg, pulled, pushed, _, _ = self.client.commit_merge(
                project_name=self.project_name,
                glossary_path=self.glossary_path,
                merge_result=updated_merge,
                occurrence_map=self.occurrence_map,
                reference_data=self.reference_data,
                on_status=self._status_label.setText,
            )
            self._on_sync_finished(ok, msg, pulled, pushed)
        else:
            self._on_sync_finished(
                False, tr("Synchronization cancelled due to unresolved conflicts."), 0, 0
            )

    def _on_sync_finished(self, ok: bool, msg: str, pulled: int, pushed: int) -> None:
        self.was_successful = ok
        self.terms_pulled = pulled
        self.terms_pushed = pushed
        self.message = msg

        if ok:
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(100)
            self._status_label.setText(f"✓ {msg}")
            self._status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #16a34a;")
            self._skip_button.setVisible(False)
            self._close_button.setVisible(True)

            if self.auto_close_ms > 0:
                self._close_timer = QTimer(self)
                self._close_timer.setSingleShot(True)
                self._close_timer.timeout.connect(self.accept)
                self._close_timer.start(self.auto_close_ms)
        else:
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(0)
            self._status_label.setText(f"✗ {msg}")
            self._status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #dc2626;")
            fail_label = tr("Close Anyway") if self.is_closing else tr("Continue Offline")
            self._skip_button.setText(fail_label)
            self._skip_button.setVisible(True)
            self._retry_button.setVisible(True)
            self._close_button.setVisible(False)


    def _on_skip_clicked(self) -> None:
        log_debug("CompanionSyncDialog: User skipped sync to work offline.")
        self._stop_worker()
        self.reject()

    def _stop_worker(self) -> None:
        """Ask the worker to stop and let go of it.

        It cannot be interrupted inside a network request; it ends when the
        request does (the client's timeout) and writes nothing after that.
        """
        worker, self._worker = self._worker, None
        if worker is not None:
            safe_shutdown_thread(worker, worker, timeout_ms=300)

    def closeEvent(self, event) -> None:
        if self._close_timer and self._close_timer.isActive():
            self._close_timer.stop()
        self._stop_worker()
        super().closeEvent(event)
