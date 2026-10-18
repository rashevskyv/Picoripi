"""Choose which sentences of other games of the series to reuse (D45). Nothing is applied until the user clicks Apply."""
# dialogs/series_sentence_dialog.py
from typing import Any, Dict, List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from core.i18n import tr

COLUMNS = (
    "Use", "Line", "English text", "Translation from another game", "Game",
    "Speaker here", "Speaker there", "Reason",
)
USE_COLUMN = 0


class SeriesSentenceDialog(QDialog):
    """One row per line that another game of the series translated. A row is ticked when it is safe and the setting says so."""

    def __init__(self, parent, rows: List[Dict[str, Any]]):
        """``rows``: dicts with block_idx, block_name, string_idx, source, translation, project, own_speaker_en,
        speaker_en, safe (bool), reason (str) and tick (bool, the initial check state)."""
        from PyQt6.QtWidgets import QWidget
        super().__init__(parent if isinstance(parent, QWidget) else None)
        self.setWindowTitle(tr('Sentences From Other Games of the Series'))
        self.resize(1000, 520)
        self._rows = list(rows)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        info = QLabel(tr(
            'These lines were translated in another game of the series. Each line is offered with its own check box. '
            'Safe lines start ticked; doubtful lines start unticked. Nothing is changed until you click Apply selected.'
        ), self)
        info.setWordWrap(True)
        layout.addWidget(info)

        self.table = QTableWidget(len(self._rows), len(COLUMNS), self)
        self.table.setHorizontalHeaderLabels([tr(name) for name in COLUMNS])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        for row_idx, row in enumerate(self._rows):
            self._fill_row(row_idx, row)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.select_safe_btn = QPushButton(tr('Select safe'), self)
        self.select_safe_btn.clicked.connect(lambda: self._set_checks(lambda row: bool(row.get('safe'))))
        self.select_all_btn = QPushButton(tr('Select all'), self)
        self.select_all_btn.clicked.connect(lambda: self._set_checks(lambda row: True))
        self.clear_btn = QPushButton(tr('Clear'), self)
        self.clear_btn.clicked.connect(lambda: self._set_checks(lambda row: False))
        buttons.addWidget(self.select_safe_btn)
        buttons.addWidget(self.select_all_btn)
        buttons.addWidget(self.clear_btn)
        buttons.addStretch()
        self.apply_btn = QPushButton(tr('Apply selected'), self)
        self.apply_btn.setDefault(True)
        self.apply_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton(tr('Cancel'), self)
        self.cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self.apply_btn)
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)

    def _fill_row(self, row_idx: int, row: Dict[str, Any]) -> None:
        """One table row: the check item in the first column, the texts in the others."""
        values = [
            "",
            f"[{row.get('block_name', '')}] Line {int(row.get('string_idx', 0)) + 1}",
            str(row.get("source", "")),
            str(row.get("translation", "")),
            str(row.get("project", "")),
            str(row.get("own_speaker_en", "")) or tr('(none)'),
            str(row.get("speaker_en", "")) or tr('(none)'),
            str(row.get("reason", "")) or tr('Safe'),
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setToolTip(value)
            if column == USE_COLUMN:
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if row.get("tick") else Qt.CheckState.Unchecked)
            self.table.setItem(row_idx, column, item)

    def _set_checks(self, wanted) -> None:
        """Tick every row for which ``wanted(row)`` is true, untick the rest."""
        for row_idx, row in enumerate(self._rows):
            item = self.table.item(row_idx, USE_COLUMN)
            item.setCheckState(Qt.CheckState.Checked if wanted(row) else Qt.CheckState.Unchecked)

    def accepted_rows(self) -> List[Tuple[int, int, str, str]]:
        """``(block_idx, string_idx, translation, source)`` of every ticked row, in the order of the table."""
        chosen = []
        for row_idx, row in enumerate(self._rows):
            if self.table.item(row_idx, USE_COLUMN).checkState() == Qt.CheckState.Checked:
                chosen.append((row["block_idx"], row["string_idx"], row["translation"], row["source"]))
        return chosen
