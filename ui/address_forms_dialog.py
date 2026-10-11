"""Forms of Address dialog: character traits, trait rules and speaker -> addressee pairs of the open project."""
from __future__ import annotations

from typing import Any, Dict, List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.address_forms import ANY, FORMS, known_names, load_table, save_table
from core.i18n import tr


def _cell(text: str) -> QTableWidgetItem:
    return QTableWidgetItem(str(text or ""))


class _Table(QWidget):
    """A table with Add and Remove buttons; the last column may be a form combo."""

    def __init__(self, headers: List[str], form_column: int = -1, parent=None):
        super().__init__(parent)
        self.form_column = form_column
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, len(headers), self)
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        add = QPushButton(tr('Add'), self)
        add.clicked.connect(lambda: self.add_row())
        remove = QPushButton(tr('Remove'), self)
        remove.clicked.connect(self.remove_selected)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        layout.addLayout(buttons)

    def add_row(self, values: List[str] = ()) -> int:
        row = self.table.rowCount()
        self.table.insertRow(row)
        values = list(values) + [""] * (self.table.columnCount() - len(values))
        for column, value in enumerate(values):
            if column == self.form_column:
                combo = QComboBox(self.table)
                combo.addItems(list(FORMS))
                combo.setCurrentText(value if value in FORMS else FORMS[0])
                self.table.setCellWidget(row, column, combo)
            else:
                self.table.setItem(row, column, _cell(value))
        return row

    def remove_selected(self) -> None:
        for index in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(index)

    def value(self, row: int, column: int) -> str:
        if column == self.form_column:
            widget = self.table.cellWidget(row, column)
            return widget.currentText() if isinstance(widget, QComboBox) else ""
        item = self.table.item(row, column)
        return item.text().strip() if item else ""

    def rows(self) -> List[List[str]]:
        return [[self.value(r, c) for c in range(self.table.columnCount())] for r in range(self.table.rowCount())]


class AddressFormsDialog(QDialog):
    """Edit who addresses whom formally or informally; saved in the project metadata."""

    def __init__(self, main_window: Any, parent=None):
        owner = parent if isinstance(parent, QWidget) else main_window
        super().__init__(owner if isinstance(owner, QWidget) else None)
        self.mw = main_window
        self.setWindowTitle(tr('Forms of Address'))
        self.resize(720, 520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        project = getattr(getattr(main_window, "project_manager", None), "project", None)
        self.table_data = load_table(project)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr(
            'Who speaks to whom formally (ви) or informally (ти). A pair beats a rule; rules apply in order, '
            'the first one whose traits both characters have wins; "*" is anyone. Traits are free words: '
            'child, adult, elder, royalty, deity, male, female...'
        ), wordWrap=True))
        tabs = QTabWidget(self)
        layout.addWidget(tabs, 1)

        self.characters = _Table([tr('Name'), tr('Traits (comma-separated)')], parent=self)
        for name in known_names(self.table_data, self._speaker_names()):
            self.characters.add_row([name, ", ".join(self.table_data["traits"].get(name, []))])
        tabs.addTab(self.characters, tr('Characters'))

        self.rule_table = _Table([tr('Speaker trait'), tr('Addressee trait'), tr('Form')], form_column=2, parent=self)
        for rule in self.table_data["rules"]:
            self.rule_table.add_row([rule.get("from", ANY), rule.get("to", ANY), rule.get("form", "")])
        tabs.addTab(self.rule_table, tr('Rules'))

        self.pairs = _Table([tr('Speaker'), tr('Addressee'), tr('Form')], form_column=2, parent=self)
        for pair in self.table_data["pairs"]:
            self.pairs.add_row([pair.get("speaker", ""), pair.get("addressee", ""), pair.get("form", "")])
        tabs.addTab(self.pairs, tr('Pairs'))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _speaker_names(self) -> List[str]:
        """The names the editor's Speaker field shows (the prompts use the same)."""
        try:
            from core.speaker_resolution import build_speaker_pool
            return sorted(set(build_speaker_pool(self.mw).values()), key=str.casefold)
        except Exception:
            return []

    def collected(self) -> Dict[str, Any]:
        traits = {}
        for name, words in self.characters.rows():
            if name:
                traits[name] = [w.strip() for w in words.split(",") if w.strip()]
        return {
            "traits": traits,
            "rules": [{"from": a or ANY, "to": b or ANY, "form": form} for a, b, form in self.rule_table.rows()],
            "pairs": [{"speaker": s, "addressee": a, "form": form} for s, a, form in self.pairs.rows() if s and a],
        }

    def accept(self) -> None:
        manager = getattr(self.mw, "project_manager", None)
        project = getattr(manager, "project", None)
        if project is not None:
            save_table(project, self.collected())
            manager.save()
        super().accept()
