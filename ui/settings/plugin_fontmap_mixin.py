from pathlib import Path
import json
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QPushButton, QMenu
)
from PyQt6.QtCore import Qt
from utils.logging_utils import log_debug
from core.i18n import tr


class PluginFontmapMixin:
    """Font map table subtab for plugin settings."""

    def _setup_font_map_subtab(self, tab):
        """Internal helper to setup font map subtab."""
        layout = QVBoxLayout(tab)
        
        # Search Filter
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel(tr('Filter Characters:')))
        self.font_map_search_edit = QLineEdit(tab)
        self.font_map_search_edit.setPlaceholderText(tr('Search by character or sequence...'))
        self.font_map_search_edit.setClearButtonEnabled(True)
        self.font_map_search_edit.textChanged.connect(self._filter_font_map_table)
        search_layout.addWidget(self.font_map_search_edit)
        layout.addLayout(search_layout)
        
        # Table
        self.font_map_table = QTableWidget(0, 2, tab)
        self.font_map_table.setHorizontalHeaderLabels(["Character / Sequence", "Width (pixels)"])
        self.font_map_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.font_map_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.font_map_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        
        # Context Menu & double click
        self.font_map_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.font_map_table.customContextMenuRequested.connect(self._show_font_map_context_menu)
        self.font_map_table.mouseDoubleClickEvent = lambda e: self._handle_font_map_double_click(e)
        layout.addWidget(self.font_map_table)
        
        btn_row = QHBoxLayout()
        add_btn = QPushButton(tr('Add Character'), tab)
        add_btn.setToolTip(
            tr('<b>Add character</b><br>Click — append an empty row for a character and its pixel width.<br>Widths feed the line-width warnings, so recalculate widths after changing them.')
        )
        add_btn.clicked.connect(lambda: self._add_font_map_row())
        remove_btn = QPushButton(tr('Remove Character'), tab)
        remove_btn.setToolTip(
            tr('<b>Remove character</b><br>Click — delete the selected character row; with nothing selected it removes the last row. One row per click.')
        )
        remove_btn.clicked.connect(self._remove_font_map_row)
        btn_row.addWidget(add_btn); btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        
        # Populate
        self._populate_font_map_table()

    def _populate_font_map_table(self):
        """Internal helper to populate font map table."""
        self.font_map_table.setRowCount(0)
        
        plugin_dir_name = self.plugin_combo.currentData() or getattr(self.mw, 'active_game_plugin', 'zelda_bmg')
        if not plugin_dir_name:
            return
            
        font_map_path = Path("plugins") / plugin_dir_name / "font_map.json"
        if not font_map_path.exists():
            font_map_path = Path("plugins") / "common" / "defaults" / "font_map.json"
            
        font_map = {}
        if font_map_path.exists():
            try:
                with open(font_map_path, 'r', encoding='utf-8') as f:
                    font_map = json.load(f)
            except Exception as e:
                log_debug(f"Failed to read font_map.json inside settings setup: {e}")
                
        if not font_map and hasattr(self.mw, 'current_font_map'):
            font_map = self.mw.current_font_map or {}
            
        for idx, (char, info) in enumerate(font_map.items()):
            self.font_map_table.insertRow(idx)
            self.font_map_table.setItem(idx, 0, QTableWidgetItem(char))
            
            width_val = ""
            if isinstance(info, dict):
                width_val = str(info.get("width", ""))
            elif isinstance(info, (int, float)):
                width_val = str(int(info))
                
            self.font_map_table.setItem(idx, 1, QTableWidgetItem(width_val))
            
        self.font_map_table.resizeColumnsToContents()

    def _add_font_map_row(self, char="", width_val="", insert_at_row=None):
        """Internal helper to add font map row."""
        if insert_at_row is not None:
            row = insert_at_row
        else:
            row = self.font_map_table.rowCount()
        self.font_map_table.insertRow(row)
        self.font_map_table.setItem(row, 0, QTableWidgetItem(char))
        self.font_map_table.setItem(row, 1, QTableWidgetItem(width_val))

    def _remove_font_map_row(self):
        """Internal helper to remove font map row."""
        curr = self.font_map_table.currentRow()
        if curr != -1:
            self.font_map_table.removeRow(curr)
        elif self.font_map_table.rowCount() > 0:
            self.font_map_table.removeRow(self.font_map_table.rowCount() - 1)

    def _filter_font_map_table(self, text):
        """Internal helper to filter font map table."""
        search_text = text.lower()
        for r in range(self.font_map_table.rowCount()):
            row_matches = False
            for c in range(self.font_map_table.columnCount()):
                item = self.font_map_table.item(r, c)
                cell_text = item.text().lower() if item else ""
                if search_text in cell_text:
                    row_matches = True
                    break
            self.font_map_table.setRowHidden(r, not row_matches)

    def _handle_font_map_double_click(self, event):
        """Internal helper to handle font map double click."""
        item = self.font_map_table.itemAt(event.pos())
        if item is None:
            row = self.font_map_table.rowAt(event.pos().y())
            if row == -1:
                self._add_font_map_row()
            else:
                self._add_font_map_row(insert_at_row=row + 1)
        else:
            QTableWidget.mouseDoubleClickEvent(self.font_map_table, event)

    def _show_font_map_context_menu(self, pos):
        """Internal helper to show font map context menu."""
        menu = QMenu(self)
        item = self.font_map_table.itemAt(pos)
        clicked_row = item.row() if item else -1
        if clicked_row == -1:
            clicked_row = self.font_map_table.rowAt(pos.y())
            
        selected_rows = sorted(list(set([i.row() for i in self.font_map_table.selectedItems()])))
        if clicked_row != -1 and clicked_row not in selected_rows:
            selected_rows = [clicked_row]
            
        add_action = menu.addAction(tr('Add Character'))
        clone_action = menu.addAction(f"Clone Character{'s' if len(selected_rows) > 1 else ''}")
        delete_action = menu.addAction(f"Delete Character{'s' if len(selected_rows) > 1 else ''}")
        
        if not selected_rows:
            clone_action.setEnabled(False)
            delete_action.setEnabled(False)
            
        action = menu.exec(self.font_map_table.viewport().mapToGlobal(pos))
        
        if action == add_action:
            if clicked_row != -1:
                self._add_font_map_row(insert_at_row=clicked_row + 1)
            else:
                self._add_font_map_row()
        elif action == clone_action:
            for row in reversed(selected_rows):
                item0 = self.font_map_table.item(row, 0)
                item1 = self.font_map_table.item(row, 1)
                char = item0.text() if item0 else ""
                width_val = item1.text() if item1 else ""
                self._add_font_map_row(char=char, width_val=width_val, insert_at_row=row + 1)
        elif action == delete_action:
            for row in reversed(selected_rows):
                self.font_map_table.removeRow(row)
