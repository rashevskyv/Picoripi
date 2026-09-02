from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMenu, QPushButton, QLineEdit
)
from PyQt6.QtCore import Qt
from .settings_widgets import TagDisplayWidget
from core.i18n import tr


class PluginTablesMixin:
    """Context tags tables for plugin settings."""

    def _setup_context_tags_subtab(self, tab):
        """Internal helper to setup context tags subtab."""
        layout = QVBoxLayout(tab)
        
        # Search Filter
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel(tr('Filter Tags:')))
        self.tags_search_edit = QLineEdit(self)
        self.tags_search_edit.setPlaceholderText(tr('Search by hex, emoji, or tag name...'))
        self.tags_search_edit.setClearButtonEnabled(True)
        self.tags_search_edit.textChanged.connect(self._filter_tags_tables)
        search_layout.addWidget(self.tags_search_edit)
        layout.addLayout(search_layout)
        
        # Single Tags
        single_group = QGroupBox(tr('Single Tags (RMB without selection)'), self)
        single_layout = QVBoxLayout(single_group)
        self.single_tags_table = QTableWidget(0, 2, self)
        self.single_tags_table.setHorizontalHeaderLabels(["Display (Emoji/Hex)", "Tag"])
        
        header = self.single_tags_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            
        self.single_tags_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.single_tags_table.customContextMenuRequested.connect(lambda pos: self._show_table_context_menu(pos, self.single_tags_table))
        self.single_tags_table.mouseDoubleClickEvent = lambda e: self._handle_table_double_click(e, self.single_tags_table)
        single_layout.addWidget(self.single_tags_table)
        
        single_btn_row = QHBoxLayout()
        add_single_btn = QPushButton(tr('Add Row'), self)
        add_single_btn.setToolTip(
            tr('<b>Add row</b><br>Click — append an empty single-tag row, then type the tag and its display text.<br>Changes take effect after you press OK in Settings.')
        )
        add_single_btn.clicked.connect(lambda: self._add_table_row(self.single_tags_table))
        remove_single_btn = QPushButton(tr('Remove Row'), self)
        remove_single_btn.setToolTip(
            tr('<b>Remove row</b><br>Click — delete the row selected in the table; with nothing selected it removes the last row. One row per click.')
        )
        remove_single_btn.clicked.connect(lambda: self._remove_table_row(self.single_tags_table))
        single_btn_row.addWidget(add_single_btn); single_btn_row.addWidget(remove_single_btn)
        single_layout.addLayout(single_btn_row)
        layout.addWidget(single_group)
        
        # Wrap Tags
        wrap_group = QGroupBox(tr('Wrap Tags (RMB with selection)'), self)
        wrap_layout = QVBoxLayout(wrap_group)
        self.wrap_tags_table = QTableWidget(0, 3, self)
        self.wrap_tags_table.setHorizontalHeaderLabels(["Display (Emoji/Hex)", "Opening Tag", "Closing Tag"])
        
        header_wrap = self.wrap_tags_table.horizontalHeader()
        header_wrap.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            
        self.wrap_tags_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.wrap_tags_table.customContextMenuRequested.connect(lambda pos: self._show_table_context_menu(pos, self.wrap_tags_table))
        self.wrap_tags_table.mouseDoubleClickEvent = lambda e: self._handle_table_double_click(e, self.wrap_tags_table)
        wrap_layout.addWidget(self.wrap_tags_table)
        
        wrap_btn_row = QHBoxLayout()
        add_wrap_btn = QPushButton(tr('Add Row'), self)
        add_wrap_btn.setToolTip(
            tr('<b>Add row</b><br>Click — append an empty wrapping-tag row (a tag with an opening and a closing part).<br>Changes take effect after you press OK in Settings.')
        )
        add_wrap_btn.clicked.connect(lambda: self._add_table_row(self.wrap_tags_table))
        remove_wrap_btn = QPushButton(tr('Remove Row'), self)
        remove_wrap_btn.setToolTip(
            tr('<b>Remove row</b><br>Click — delete the row selected in the table; with nothing selected it removes the last row. One row per click.')
        )
        remove_wrap_btn.clicked.connect(lambda: self._remove_table_row(self.wrap_tags_table))
        wrap_btn_row.addWidget(add_wrap_btn); wrap_btn_row.addWidget(remove_wrap_btn)
        wrap_layout.addLayout(wrap_btn_row)
        layout.addWidget(wrap_group)

    def _handle_table_double_click(self, event, table):
        """Internal helper to handle table double click."""
        item = table.itemAt(event.pos())
        if item is None:
            row = table.rowAt(event.pos().y())
            if row == -1:
                self._add_table_row(table)
            else:
                self._add_table_row(table, insert_at_row=row + 1)
        else:
            QTableWidget.mouseDoubleClickEvent(table, event)

    def _show_table_context_menu(self, pos, table):
        """Internal helper to show table context menu."""
        menu = QMenu(self)
        
        item = table.itemAt(pos)
        clicked_row = item.row() if item else -1
        
        if clicked_row == -1:
            clicked_row = table.rowAt(pos.y())
            
        selected_rows = sorted(list(set([i.row() for i in table.selectedItems()])))
        if clicked_row != -1 and clicked_row not in selected_rows:
            selected_rows = [clicked_row]
            
        add_action = menu.addAction(tr('Add Row'))
        clone_action = menu.addAction(f"Clone Row{'s' if len(selected_rows) > 1 else ''}")
        delete_action = menu.addAction(f"Delete Row{'s' if len(selected_rows) > 1 else ''}")
        
        if not selected_rows:
            clone_action.setEnabled(False)
            delete_action.setEnabled(False)
            
        action = menu.exec(table.viewport().mapToGlobal(pos))
        
        if action == add_action:
            if clicked_row != -1:
                self._add_table_row(table, insert_at_row=clicked_row + 1)
            else:
                self._add_table_row(table)
        elif action == clone_action:
            for row in reversed(selected_rows):
                widget = table.cellWidget(row, 0)
                disp = widget.text() if widget else ""
                
                item1 = table.item(row, 1)
                col1 = item1.text() if item1 else ""
                
                col2 = ""
                if table.columnCount() > 2:
                    item2 = table.item(row, 2)
                    col2 = item2.text() if item2 else ""
                    
                self._add_table_row(table, display_text=disp, col1=col1, col2=col2, insert_at_row=row + 1)
        elif action == delete_action:
            for row in reversed(selected_rows):
                table.removeRow(row)

    def _add_table_row(self, table, display_text="", col1="", col2="", insert_at_row=None):
        """Internal helper to add table row."""
        sorting_was_enabled = table.isSortingEnabled()
        if sorting_was_enabled:
            table.setSortingEnabled(False)
            
        if insert_at_row is not None:
            row = insert_at_row
        else:
            row = table.rowCount()
        table.insertRow(row)
        
        disp_item = QTableWidgetItem()
        disp_item.setData(Qt.ItemDataRole.DisplayRole, display_text)
        table.setItem(row, 0, disp_item)
        
        widget = TagDisplayWidget(display_text, table)
        widget.textChanged.connect(lambda txt, i=disp_item: i.setData(Qt.ItemDataRole.DisplayRole, txt))
        table.setCellWidget(row, 0, widget)
        
        table.setItem(row, 1, QTableWidgetItem(col1))
        
        if table.columnCount() > 2:
            table.setItem(row, 2, QTableWidgetItem(col2))
            
        if sorting_was_enabled:
            table.setSortingEnabled(True)

    def _filter_tags_tables(self, text):
        """Internal helper to filter tags tables."""
        search_text = text.lower()
        for table in (self.single_tags_table, self.wrap_tags_table):
            for r in range(table.rowCount()):
                row_matches = False
                for c in range(table.columnCount()):
                    widget = table.cellWidget(r, c)
                    if widget and isinstance(widget, TagDisplayWidget):
                        cell_text = widget.text().lower()
                    else:
                        item = table.item(r, c)
                        cell_text = item.text().lower() if item else ""
                    if search_text in cell_text:
                        row_matches = True
                        break
                table.setRowHidden(r, not row_matches)

    def _remove_table_row(self, table):
        """Internal helper to remove table row."""
        curr = table.currentRow()
        if curr != -1: table.removeRow(curr)
        elif table.rowCount() > 0: table.removeRow(table.rowCount() - 1)
