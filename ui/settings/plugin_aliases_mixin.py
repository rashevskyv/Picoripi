from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QPushButton, QMenu
)
from PyQt6.QtCore import Qt
from core.i18n import tr


class PluginAliasesMixin:
    """Tag aliases subtab for plugin settings."""

    def _setup_aliases_subtab(self, tab):
        """Internal helper to setup aliases subtab."""
        layout = QVBoxLayout(tab)
        
        # Search Filter
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel(tr('Filter Aliases:')))
        self.aliases_search_edit = QLineEdit(tab)
        self.aliases_search_edit.setPlaceholderText(tr('Search by alias or original tag...'))
        self.aliases_search_edit.setClearButtonEnabled(True)
        self.aliases_search_edit.textChanged.connect(self._filter_aliases_table)
        search_layout.addWidget(self.aliases_search_edit)
        layout.addLayout(search_layout)
        
        # Table
        self.aliases_table = QTableWidget(0, 2, tab)
        self.aliases_table.setHorizontalHeaderLabels(["Alias (e.g. {F:Link})", "Original Tag (e.g. {escape:0:0000})"])
        self.aliases_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.aliases_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.aliases_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        
        # Context Menu & double click
        self.aliases_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.aliases_table.customContextMenuRequested.connect(self._show_aliases_context_menu)
        self.aliases_table.mouseDoubleClickEvent = lambda e: self._handle_aliases_double_click(e)
        layout.addWidget(self.aliases_table)
        
        btn_row = QHBoxLayout()
        add_btn = QPushButton(tr('Add Alias'), tab)
        add_btn.setToolTip(
            tr('<b>Add alias</b><br>Click — append an empty alias row mapping a raw game tag to a readable name.<br>Use the search field above to find an existing alias before adding a duplicate.')
        )
        add_btn.clicked.connect(lambda: self._add_alias_row())
        remove_btn = QPushButton(tr('Remove Alias'), tab)
        remove_btn.setToolTip(
            tr('<b>Remove alias</b><br>Click — delete the selected alias row; with nothing selected it removes the last row. One row per click.')
        )
        remove_btn.clicked.connect(self._remove_alias_row)
        btn_row.addWidget(add_btn); btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        
        # Populate
        self._populate_aliases_table()

    def _populate_aliases_table(self):
        """Internal helper to populate aliases table."""
        self.aliases_table.setRowCount(0)
        default_tag_mappings = getattr(self.mw, "default_tag_mappings", {})
        for idx, (alias, orig_tag) in enumerate(default_tag_mappings.items()):
            self.aliases_table.insertRow(idx)
            self.aliases_table.setItem(idx, 0, QTableWidgetItem(alias))
            self.aliases_table.setItem(idx, 1, QTableWidgetItem(orig_tag))
        self.aliases_table.resizeColumnsToContents()

    def _add_alias_row(self, alias="", orig_tag="", insert_at_row=None):
        """Internal helper to add alias row."""
        if insert_at_row is not None:
            row = insert_at_row
        else:
            row = self.aliases_table.rowCount()
        self.aliases_table.insertRow(row)
        self.aliases_table.setItem(row, 0, QTableWidgetItem(alias))
        self.aliases_table.setItem(row, 1, QTableWidgetItem(orig_tag))

    def _remove_alias_row(self):
        """Internal helper to remove alias row."""
        curr = self.aliases_table.currentRow()
        if curr != -1:
            self.aliases_table.removeRow(curr)
        elif self.aliases_table.rowCount() > 0:
            self.aliases_table.removeRow(self.aliases_table.rowCount() - 1)

    def _filter_aliases_table(self, text):
        """Internal helper to filter aliases table."""
        search_text = text.lower()
        for r in range(self.aliases_table.rowCount()):
            row_matches = False
            for c in range(self.aliases_table.columnCount()):
                item = self.aliases_table.item(r, c)
                cell_text = item.text().lower() if item else ""
                if search_text in cell_text:
                    row_matches = True
                    break
            self.aliases_table.setRowHidden(r, not row_matches)

    def _handle_aliases_double_click(self, event):
        """Internal helper to handle aliases double click."""
        item = self.aliases_table.itemAt(event.pos())
        if item is None:
            row = self.aliases_table.rowAt(event.pos().y())
            if row == -1:
                self._add_alias_row()
            else:
                self._add_alias_row(insert_at_row=row + 1)
        else:
            QTableWidget.mouseDoubleClickEvent(self.aliases_table, event)

    def _show_aliases_context_menu(self, pos):
        """Internal helper to show aliases context menu."""
        menu = QMenu(self)
        item = self.aliases_table.itemAt(pos)
        clicked_row = item.row() if item else -1
        if clicked_row == -1:
            clicked_row = self.aliases_table.rowAt(pos.y())
            
        selected_rows = sorted(list(set([i.row() for i in self.aliases_table.selectedItems()])))
        if clicked_row != -1 and clicked_row not in selected_rows:
            selected_rows = [clicked_row]
            
        add_action = menu.addAction(tr('Add Alias'))
        clone_action = menu.addAction(f"Clone Alias{'es' if len(selected_rows) > 1 else ''}")
        delete_action = menu.addAction(f"Delete Alias{'es' if len(selected_rows) > 1 else ''}")
        
        if not selected_rows:
            clone_action.setEnabled(False)
            delete_action.setEnabled(False)
            
        action = menu.exec(self.aliases_table.viewport().mapToGlobal(pos))
        
        if action == add_action:
            if clicked_row != -1:
                self._add_alias_row(insert_at_row=clicked_row + 1)
            else:
                self._add_alias_row()
        elif action == clone_action:
            for row in reversed(selected_rows):
                item0 = self.aliases_table.item(row, 0)
                item1 = self.aliases_table.item(row, 1)
                alias = item0.text() if item0 else ""
                orig = item1.text() if item1 else ""
                self._add_alias_row(alias=alias, orig_tag=orig, insert_at_row=row + 1)
        elif action == delete_action:
            for row in reversed(selected_rows):
                self.aliases_table.removeRow(row)
