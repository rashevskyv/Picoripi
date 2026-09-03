"""Glossary term table tabs, selection, filter, and reload."""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)
from core.glossary_manager import (
    STATUS_CONFIRMED,
    GlossaryEntry,
    GlossaryOccurrence,
    possible_duplicate_pairs,
    render_notes,
)
from core.i18n import tr

from components.glossary.widgets import (
    _GlossaryTermTable,
    _MULTI_VARIANT_BRUSH,
    _PROVISIONAL_FOREGROUND,
    _UNREVIEWED_BRUSH,
)


class TableMixin:
    """Glossary term table tabs, selection, filter, and reload."""

    def _active_table(self) -> QTableWidget:
        """Internal helper to active table."""
        if not hasattr(self, '_tab_widget') or self._tab_widget.count() == 0:
            # Fallback legacy table if it somehow exists
            return self._entry_table if self._entry_table else QTableWidget(self)
        widget = self._tab_widget.currentWidget()
        if isinstance(widget, QTableWidget):
            return widget
        return self._entry_table if self._entry_table else QTableWidget(self)

    def _on_tab_changed(self, index: int) -> None:
        """Internal helper to handle the tab changed event."""
        if self._is_populating:
            return
        active_table = self._active_table()
        row = active_table.currentRow()
        self._show_entry_for_row(row)

    def _glossary_tab_names(self, entries: Sequence[GlossaryEntry]) -> list[str]:
        sections = sorted({entry.section for entry in self._all_entries if entry.section})
        tabs = ["All"] + sections
        if any(not entry.section for entry in entries):
            tabs.append("Unassigned")
        return tabs

    @staticmethod
    def _glossary_tab_label(tab_name: str) -> str:
        """Display label for a tab. Internal keys stay English."""
        return tr(tab_name)

    def _glossary_tab_key(self, index: int) -> str:
        """English tab identity, independent of the translated caption."""
        tip = self._tab_widget.tabToolTip(index)
        if tip:
            return tip
        return self._tab_widget.tabText(index)

    def _entries_for_glossary_tab(self, tab_name: str, entries: Sequence[GlossaryEntry]) -> list[GlossaryEntry]:
        if tab_name == "All":
            return list(entries)
        if tab_name == "Unassigned":
            return [entry for entry in entries if not entry.section]
        return [entry for entry in entries if entry.section == tab_name]

    def _fill_glossary_table(self, table: QTableWidget, tab_entries: Sequence[GlossaryEntry], *, resize: bool) -> None:
        table.setSortingEnabled(False)
        table.blockSignals(True)
        table.setUpdatesEnabled(False)
        table.setRowCount(len(tab_entries))
        try:
            for row, entry in enumerate(tab_entries):
                occurrences = self._occurrences.get(entry.original, [])
                values = [
                    entry.original,
                    entry.translation,
                    render_notes(
                        entry.notes,
                        translation=entry.translation,
                        original=entry.original,
                    ),
                    str(len(occurrences)),
                ]
                review_brush = self._review_brush(entry)
                provisional = self._is_provisional_character(entry)
                for col, value in enumerate(values):
                    item = table.item(row, col)
                    if item is None:
                        item = QTableWidgetItem()
                        table.setItem(row, col, item)
                    item.setText(value)
                    item.setBackground(QBrush())
                    item.setForeground(QBrush())
                    item.setToolTip("")
                    if col == 3:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if col == 0:
                        item.setData(Qt.ItemDataRole.UserRole, entry)
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if review_brush is not None:
                        item.setBackground(review_brush)
                        item.setToolTip(self._review_reason(entry))
                    if provisional:
                        item.setForeground(_PROVISIONAL_FOREGROUND)
                        item.setToolTip(
                            tr(
                                'Provisional speaker identity.\n\n'
                                '"{original}" was extracted from game data as a temporary speaker identifier. '
                                'Select this term in the Glossary to assign its permanent character name, '
                                'or use Merge Speakers to match it against a script.',
                                original=entry.original,
                            )
                        )
            if resize:
                table.resizeColumnToContents(0)
                table.resizeColumnToContents(1)
                table.resizeColumnToContents(3)
        finally:
            table.setUpdatesEnabled(True)
            table.setSortingEnabled(True)
            table.blockSignals(False)

    def _make_glossary_table(self) -> QTableWidget:
        table = _GlossaryTermTable(self)
        table.setAutoScroll(False)
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels([
            tr('Term'),
            tr('Translation'),
            tr('Notes'),
            tr('Count'),
        ])
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.cellClicked.connect(self._on_entry_selected)
        table.currentCellChanged.connect(self._on_entry_current_changed)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(self._on_entry_context_menu)
        if self._update_callback:
            table.setEditTriggers(
                QAbstractItemView.EditTrigger.DoubleClicked
                | QAbstractItemView.EditTrigger.EditKeyPressed
                | QAbstractItemView.EditTrigger.AnyKeyPressed
            )
            table.itemChanged.connect(self._on_entry_edited)
        else:
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        return table

    def _populate_entries(self, entries: Sequence[GlossaryEntry]) -> None:
        """Internal helper to populate entries."""
        self._is_populating = True
        
        # Save current selected term and tab to restore after population
        selected_term = self._current_entry.original if self._current_entry else None
        current_tab_key = (
            self._glossary_tab_key(self._tab_widget.currentIndex())
            if hasattr(self, '_tab_widget') and self._tab_widget.count() > 0
            else "All"
        )
        tabs_to_create = self._glossary_tab_names(entries)
        existing_tabs = [
            self._glossary_tab_key(idx) for idx in range(self._tab_widget.count())
        ] if hasattr(self, "_tab_widget") else []
        reuse = existing_tabs == tabs_to_create and all(name in self._tables for name in tabs_to_create)

        if reuse:
            self._tab_widget.blockSignals(True)
            for tab_name in tabs_to_create:
                self._fill_glossary_table(
                    self._tables[tab_name],
                    self._entries_for_glossary_tab(tab_name, entries),
                    resize=False,
                )
        else:
            self._tab_widget.blockSignals(True)
            self._tab_widget.clear()
            self._tables.clear()
            for tab_name in tabs_to_create:
                table = self._make_glossary_table()
                self._fill_glossary_table(
                    table,
                    self._entries_for_glossary_tab(tab_name, entries),
                    resize=True,
                )
                self._tables[tab_name] = table
                tab_idx = self._tab_widget.addTab(table, self._glossary_tab_label(tab_name))
                self._tab_widget.setTabToolTip(tab_idx, tab_name)
            
        restore_idx = 0
        for idx in range(self._tab_widget.count()):
            if self._glossary_tab_key(idx) == current_tab_key:
                restore_idx = idx
                break
        self._tab_widget.setCurrentIndex(restore_idx)
        self._tab_widget.blockSignals(False)
        self._is_populating = False
        
        if selected_term:
            self._select_initial_term(selected_term, switch_tab=False)
        elif self._active_table().rowCount() > 0:
            self._active_table().selectRow(0)
            self._show_entry_for_row(0)
        else:
            self._clear_entry_details()

    def _select_initial_term(self, term: str, switch_tab: bool = True) -> None:
        """Internal helper to select initial term."""
        if not term:
            return
        
        term_to_find = term.strip()
        
        # 1. Find which section this term belongs to
        target_section = "All"
        for entry in self._all_entries:
            if entry.original.strip() == term_to_find:
                target_section = entry.section if entry.section else "Unassigned"
                break
                
        # 2. Switch to the corresponding tab if requested
        if switch_tab and hasattr(self, '_tab_widget'):
            self._tab_widget.blockSignals(True)
            found_tab = False
            for idx in range(self._tab_widget.count()):
                if self._glossary_tab_key(idx) == target_section:
                    self._tab_widget.setCurrentIndex(idx)
                    found_tab = True
                    break
            if not found_tab:
                for idx in range(self._tab_widget.count()):
                    if self._glossary_tab_key(idx) == "All":
                        self._tab_widget.setCurrentIndex(idx)
                        break
            self._tab_widget.blockSignals(False)
            
        # 3. Select inside active table
        active_table = self._active_table()
        for row in range(active_table.rowCount()):
            item = active_table.item(row, 0)
            if not item: continue
            
            entry = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(entry, GlossaryEntry) and entry.original.strip() == term_to_find:
                active_table.setCurrentCell(row, 0)
                active_table.scrollToItem(item, QTableWidget.ScrollHint.PositionAtCenter)
                self._show_entry_for_row(row)
                return

    def focus_term(self, term: str) -> None:
        """Filter the list to ``term`` and select its entry (public entry point).

        Robust for both a freshly created dialog and one that is already open:
        it narrows the search box to the term (matching original or translation,
        so the entry is always visible) and selects the exact original if present.
        """
        term = (term or "").strip()
        if not term:
            return
        if self._search_field.text().strip() != term:
            timer = getattr(self, "_filter_timer", None)
            if timer is not None:
                timer.stop()
            self._search_field.blockSignals(True)
            self._search_field.setText(term)
            self._search_field.blockSignals(False)
        self._apply_filter(term)
        self._select_initial_term(term, switch_tab=True)

    def _show_entry_for_row(self, row: int) -> None:
        """Internal helper to show entry for row."""
        if row < 0:
            self._clear_entry_details()
            return
        entry = self._entry_for_row(row)
        if entry:
            self._populate_entry_details(entry)
            self._update_occurrences(entry)
        else:
            self._clear_entry_details()

    def _on_entry_current_changed(self, row: int, _column: int, _prev_row: int, _prev_column: int) -> None:
        """Internal helper to handle the entry current changed event."""
        if self._is_populating:
            return
        self._show_entry_for_row(row)

    def _on_entry_selected(self, row: int, _column: int) -> None:
        """Internal helper to handle the entry selected event."""
        self._show_entry_for_row(row)

    def _on_entry_edited(self, item: QTableWidgetItem) -> None:
        """Internal helper to handle the entry edited event."""
        if self._is_populating or not self._update_callback:
            return
        row = item.row()
        column = item.column()
        if column not in (1, 2):
            return
        entry = self._entry_for_row(row)
        if not entry:
            return
        translation_item = self._active_table().item(row, 1)
        notes_item = self._active_table().item(row, 2)
        new_translation = translation_item.text().strip() if translation_item else ''
        new_notes = notes_item.text().strip() if notes_item else ''
        if new_translation == entry.translation and new_notes == entry.notes:
            if self._current_entry and self._current_entry.original == entry.original:
                self._mark_editor_dirty(False)
            return
        if self._attempt_entry_update(entry, new_translation, new_notes):
            if self._current_entry and self._current_entry.original == entry.original:
                self._mark_editor_dirty(False)
            return
        self._is_populating = True
        self._active_table().blockSignals(True)
        if translation_item:
            translation_item.setText(entry.translation)
        if notes_item:
            notes_item.setText(entry.notes)
        self._active_table().blockSignals(False)
        self._is_populating = False
        if self._current_entry and self._current_entry.original == entry.original:
            self._populate_entry_details(entry)

    def _entry_for_row(self, row: int) -> Optional[GlossaryEntry]:
        """Internal helper to entry for row."""
        if row < 0:
            return None
        active_table = self._active_table()
        if row >= active_table.rowCount():
            return None
        item = active_table.item(row, 0)
        if not item:
            return None
        entry = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(entry, GlossaryEntry):
            return entry
        if 0 <= row < len(self._filtered_entries):
            return self._filtered_entries[row]
        return None

    @staticmethod
    def _review_reason(entry: GlossaryEntry) -> str:
        """Why this entry is flagged — shown as the row tooltip."""
        variants = getattr(entry, "translation_variants", ()) or ()
        if len(variants) > 1:
            listed = "\n".join(
                f"  • {v.translation}" + (f" — {v.rationale}" if v.rationale else "")
                for v in variants
            )
            return tr(
                '{count} translation variants proposed:\n{listed}',
                count=len(variants),
                listed=listed,
            )
        status = getattr(entry, "status", "") or "unconfirmed"
        return tr('Awaiting review (status: {status}).', status=status)

    @staticmethod
    def _review_brush(entry: GlossaryEntry) -> Optional[QBrush]:
        """Background for a row that still needs a person to look at it."""
        if not TableMixin._needs_review(entry):
            return None
        if len(getattr(entry, "translation_variants", ()) or ()) > 1:
            return _MULTI_VARIANT_BRUSH
        return _UNREVIEWED_BRUSH

    @staticmethod
    def _needs_review(entry: GlossaryEntry) -> bool:
        """Whether the entry still awaits a human decision.

        A confirmed entry is settled and never flagged -- the proposed variants
        stay on record so the choice can be revisited, but their presence is not
        an open question any more. Otherwise: several defensible translations, or
        a status that has not been confirmed yet. Legacy entries carry no status
        and are not flagged, so the marker stays meaningful instead of colouring
        everything.
        """
        if getattr(entry, "status", "") == STATUS_CONFIRMED:
            return False
        if len(getattr(entry, "translation_variants", ()) or ()) > 1:
            return True
        return bool(getattr(entry, "is_unconfirmed", False))

    def _apply_filter(self, text: str) -> None:
        """Internal helper to apply filter."""
        pattern = text.strip().lower()
        if not pattern:
            self._filtered_entries = list(self._all_entries)
        else:
            def matches(entry: GlossaryEntry) -> bool:
                haystack = " ".join(
                     filter(None, [entry.original, entry.translation, entry.notes])
                ).lower()
                return pattern in haystack
            self._filtered_entries = [entry for entry in self._all_entries if matches(entry)]
        if self._unconfirmed_only_checkbox.isChecked():
            self._filtered_entries = [
                entry for entry in self._filtered_entries if self._needs_review(entry)
            ]
        self._populate_entries(self._filtered_entries)
        if self._pending_select_term:
            self._select_initial_term(self._pending_select_term, switch_tab=False)
            self._pending_select_term = None
            return
        if self._filtered_entries:
            self._active_table().selectRow(0)
            self._show_entry_for_row(0)
        else:
            self._clear_entry_details()
            self._occurrence_list.clear()
            self._occurrence_label.setText(tr('Mentions: 0   Spoken: 0'))

    def reload_data(
        self,
        entries: Sequence[GlossaryEntry],
        occurrence_map: Dict[str, List[GlossaryOccurrence]]
    ) -> None:
        """Hot-reload entries and occurrences from external source and refresh UI."""
        self._all_entries = list(entries)
        self._duplicate_pairs = possible_duplicate_pairs(self._all_entries)
        self._occurrences = occurrence_map
        
        # Save currently selected term name to restore selection after reload
        selected_term = None
        if self._current_entry:
            selected_term = self._current_entry.original
            
        # Apply filters to re-populate the table
        self._apply_filter(self._search_field.text())
        
        # Restore selection if possible, otherwise select first row
        if selected_term:
            self._select_initial_term(selected_term, switch_tab=False)
        elif self._filtered_entries:
            self._active_table().selectRow(0)
            self._show_entry_for_row(0)
