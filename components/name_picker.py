"""Searchable dialog for choosing a speaker name."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)


class SpeakerSelectionDialog(QDialog):
    """Choose one speaker without expanding every name into a menu."""

    def __init__(self, names, selected_name=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose speaker")
        self.setMinimumSize(480, 520)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose the speaker for the selected strings:"))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search names…")
        self.search_edit.setClearButtonEnabled(True)
        layout.addWidget(self.search_edit)

        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setUniformItemSizes(True)
        layout.addWidget(self.list_widget)

        ordered_names = ["None"] + sorted(
            {
                str(name).strip()
                for name in names
                if str(name).strip() and str(name).strip() != "None"
            },
            key=str.casefold,
        )
        selected_item = None
        for name in ordered_names:
            item = QListWidgetItem(name)
            self.list_widget.addItem(item)
            if name == (selected_name or "None"):
                selected_item = item
        self.list_widget.setCurrentItem(selected_item or self.list_widget.item(0))

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Select")
        layout.addWidget(self.buttons)

        self.search_edit.textChanged.connect(self._filter_names)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self.accept())
        self.list_widget.currentItemChanged.connect(self._update_accept_state)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self._update_accept_state(self.list_widget.currentItem())

    def _update_accept_state(self, item, _previous=None):
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(item is not None)

    def _filter_names(self, text):
        query = text.strip().casefold()
        first_match = None
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            visible = not query or query in item.text().casefold()
            item.setHidden(not visible)
            if visible and first_match is None:
                first_match = item
        current = self.list_widget.currentItem()
        if query and (current is None or current.isHidden()):
            self.list_widget.setCurrentItem(first_match)

    def selection(self):
        item = self.list_widget.currentItem()
        return item.text() if item is not None else "None"
