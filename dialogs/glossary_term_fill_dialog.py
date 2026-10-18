"""Preview and fill the strings that a series glossary term translates (D45, item 1)."""
# dialogs/glossary_term_fill_dialog.py
import os
from pathlib import Path
from typing import Any, Dict, Optional

from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QProgressBar, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from core.glossary.series import series_chain, series_managers_of
from core.glossary.term_fill import CONFLICT, FILL, GLOSSARY_CONFLICT, SAME
from core.i18n import tr
from core.translation.series_fill import registered_memories
from core.translation.series_memory import MEMORY_NAME
from handlers import glossary_term_fill as fill_logic
from handlers.series_term_fill_worker import SeriesTermFillWorker
from utils.thread_utils import safe_shutdown_thread

STATUS_TEXT = {
    FILL: 'Will be filled',
    SAME: 'Already the same',
    CONFLICT: 'Conflict: a different translation is kept',
    GLOSSARY_CONFLICT: 'Conflict: the glossaries differ, nothing is filled',
}
REFUSED_TEXT = {
    'tags': 'Not filled: the tags do not match',
    'window': 'Not filled: the text does not fit the window',
}
PROJECT_STATUS_TEXT = {
    'done': 'Done',
    'no project file': 'No project file',
    'no terms': 'No series term in this project',
    'failed': 'Failed',
}


def _same_file(first: Path, second: Path) -> bool:
    return os.path.normcase(os.path.abspath(first)) == os.path.normcase(os.path.abspath(second))


class GlossaryTermFillDialog(QDialog):
    """Lists the planned fills of the open project. **Fill untranslated lines** writes the ones that pass the checks.
    **Fill the other projects of the series** writes their untranslated lines into their backups, on a worker."""

    def __init__(self, mw: Any, parent=None):
        from PyQt6.QtWidgets import QWidget
        super().__init__(parent if isinstance(parent, QWidget) else None)
        self.mw = mw
        self.setWindowTitle(tr('Fill Terms from the Glossary'))
        self.resize(1000, 560)
        self._worker: Optional[SeriesTermFillWorker] = None
        _, self.fills = fill_logic.plan_open_project(mw)
        self._row_of: Dict[tuple, int] = {}

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        summary = QLabel(self._summary_text(), self)
        summary.setWordWrap(True)
        layout.addWidget(summary)

        self.table = QTableWidget(len(self.fills), 6, self)
        self.table.setHorizontalHeaderLabels([
            tr('Line'), tr('English text'), tr('Term'), tr('Translation'), tr('Current translation'), tr('Status'),
        ])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        for row_idx, fill in enumerate(self.fills):
            self._fill_row(row_idx, fill, tr(STATUS_TEXT[fill.status]))
        layout.addWidget(self.table, 1)

        self.result_label = QLabel('', self)
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)
        self.progress = QProgressBar(self)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        buttons = QHBoxLayout()
        self.fill_btn = QPushButton(tr('Fill untranslated lines'), self)
        self.fill_btn.setEnabled(any(fill.status == FILL for fill in self.fills))
        self.fill_btn.clicked.connect(self._apply)
        self.series_btn = QPushButton(tr('Fill the other projects of the series'), self)
        self.series_btn.setToolTip(tr(
            'Writes the untranslated lines of the other projects into their backups (saved translations). '
            'A project restores them with its Restore action. A translation already in a project is kept.'
        ))
        self.series_btn.clicked.connect(self._start_series)
        self.cancel_btn = QPushButton(tr('Cancel'), self)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_series)
        buttons.addWidget(self.fill_btn)
        buttons.addWidget(self.series_btn)
        buttons.addWidget(self.cancel_btn)
        buttons.addStretch()
        self.close_btn = QPushButton(tr('Close'), self)
        self.close_btn.clicked.connect(self.reject)
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

    def _summary_text(self) -> str:
        counts = {status: sum(1 for fill in self.fills if fill.status == status) for status in STATUS_TEXT}
        return tr(
            '{fill} lines will be filled, {same} already have the term, {conflict} keep a different translation, '
            '{glossary} need a decision in the glossary. A line is written only when its tags and window fit.',
            fill=counts[FILL], same=counts[SAME], conflict=counts[CONFLICT], glossary=counts[GLOSSARY_CONFLICT],
        )

    def _block_label(self, block_idx: int) -> str:
        names = getattr(getattr(self.mw, 'data_store', None), 'block_names', None) or {}
        return names.get(str(block_idx)) or f"Block {block_idx + 1}"

    def _fill_row(self, row_idx: int, fill, status: str) -> None:
        values = [
            f"[{self._block_label(fill.block_idx)}] Line {fill.string_idx + 1}",
            fill.source, fill.term, fill.translation, fill.current, status,
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setToolTip(str(value))
            self.table.setItem(row_idx, column, item)
        self._row_of[(fill.block_idx, fill.string_idx)] = row_idx

    def _apply(self) -> None:
        """Write the untranslated lines that pass the checks; refused lines show why and stay untouched."""
        written, refused = fill_logic.apply_fills(self.mw, self.fills)
        for fill, reason in refused:
            self.table.item(self._row_of[(fill.block_idx, fill.string_idx)], 5).setText(tr(REFUSED_TEXT.get(reason, reason)))
        for fill in written:
            self.table.item(self._row_of[(fill.block_idx, fill.string_idx)], 5).setText(tr('Filled'))
        self.fill_btn.setEnabled(False)
        status_bar = getattr(self.mw, 'statusBar', None)
        if status_bar:
            status_bar.showMessage(
                tr('Filled {count} lines from the glossary; {refused} refused by the checks.',
                   count=len(written), refused=len(refused)),
                6000,
            )

    # ----- the other projects of the series (worker)

    def _other_projects(self) -> Dict[str, Path]:
        """Every project registered beside the open project's series glossaries, except the open one."""
        manager = getattr(self.mw, 'project_manager', None)
        project = getattr(manager, 'project', None)
        project_dir = getattr(manager, 'project_dir', None)
        if project is None or not project_dir:
            return {}
        own_memory = Path(project_dir) / MEMORY_NAME
        found = registered_memories(series_chain(project, Path(project_dir)))
        return {name: memory for name, memory in found.items() if not _same_file(memory, own_memory)}

    def _start_series(self) -> None:
        projects = self._other_projects()
        if not projects:
            self.result_label.setText(tr('No other project of this series is registered beside the glossary.'))
            return
        entries = fill_logic.series_entries(series_managers_of(self.mw))
        self._worker = SeriesTermFillWorker(entries, projects, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_series_done)
        self.progress.setRange(0, len(projects))
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.series_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.result_label.setText(tr('Filling {count} other projects of the series...', count=len(projects)))
        self._worker.start()

    def _cancel_series(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.cancel_btn.setEnabled(False)

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(done)

    def _on_series_done(self, results) -> None:
        self.progress.setVisible(False)
        self.cancel_btn.setEnabled(False)
        self.series_btn.setEnabled(True)
        if results is None:
            self.result_label.setText(tr('Cancelled. The projects before the cancel keep their backups.'))
            return
        lines = []
        for name in sorted(results):
            result = results[name]
            status = tr(PROJECT_STATUS_TEXT.get(result.get('status', ''), result.get('status', '')))
            if result.get('status') == 'done':
                lines.append(tr('{name}: {status}; written {written}, kept {kept}, refused by tags {refused}.',
                                name=name, status=status, written=result['written'], kept=result['kept'],
                                refused=result['refused_tags']))
            else:
                lines.append(f"{name}: {status}")
        self.result_label.setText("\n".join(lines))

    def closeEvent(self, event) -> None:
        """A running fill is cancelled and given a bounded time to stop before the dialog goes."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            safe_shutdown_thread(self._worker, None, 3000)
        super().closeEvent(event)
